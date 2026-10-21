"""framework/lib/evolve.py — 执行 T0 决策，更新进化账本（evolution.json）。

铁律：
  - 只执行可从 git 历史完整恢复的本地写操作（T0）
  - 每个动作都留 changelog（auto: 前缀），没有留痕的修改视为没发生
  - 单个动作失败不影响其他动作；全部异常不穿透（hooks 纪律）
"""

from __future__ import annotations

from pathlib import Path

from . import analyze as analyze_mod
from . import digest as digest_mod
from . import hubloc
from . import lifecycle, lock as lock_mod, meta, paths, scan, signals as signals_mod
from . import taxonomy as taxonomy_mod
from .util import copy_tree, dir_hash, now_iso, read_json, today, write_json_atomic
from .validate import blocking as blocking_problems
from .validate import validate_skill_dir

LOCAL_BUCKET = "local"  # 自动收编 / 候选晋升的统一落点


def load_evolution() -> dict:
    evo = read_json(paths.EVOLUTION_FILE, None)
    if not isinstance(evo, dict):
        evo = paths.empty_evolution()
        evo["created"] = now_iso()
    return evo


def save_evolution(evo: dict) -> None:
    write_json_atomic(paths.EVOLUTION_FILE, evo)


def run_evolve(apply: bool = False, cfg: dict | None = None, cwd: Path | None = None,
               quiet: bool = False, source: str = "cli") -> dict:
    """分析并（可选）执行。返回报告 dict。永不抛异常。

    并发纪律（PRD v2 NFR-9）：分析是只读的，放锁外；所有 read-modify-write
    （账本、sidecar、快照）在 evolve.lock 排他锁内完成。多会话 Stop hook
    并发时，后来者等待或超时跳过——绝不交叉写。
    """
    cfg = cfg or paths.load_config()
    paths.ensure_state()

    # ---- 锁外：只读分析（扫描可能几百 ms，不堵其他会话）----
    index = meta.index_by_id(meta.list_repo_skills())
    _merge_hub_into_index(index)
    local_skills = scan.find_local_skills(paths.resolve_scan_dirs(cfg, cwd))
    sigs = signals_mod.read_all(limit=paths.SIGNALS_ANALYZE_LIMIT)

    with lock_mod.file_lock(paths.EVOLUTION_LOCK, timeout=paths.LOCK_TIMEOUT) as locked:
        if not locked:
            report = _skipped_report("另一会话正在进化（锁超时）——本次跳过，下轮补上")
            if not quiet:
                _print_report(report)
            return report
        return _evolve_locked(apply, cfg, source, quiet, index, local_skills, sigs)


def _merge_hub_into_index(index: dict) -> None:
    """把 hub 技能并入内存索引（只读视图）——防 analyze 对已有 hub 技能重复收编。

    hub 是独立仓库（ADR 0004），不在 meta.list_repo_skills 扫描面里；不并进去的话，
    WorkBuddy 原件会被当成「仓库没有的新技能」再次收编。hub 技能自带 sidecar，
    卫生预跑（场景回填）照常工作；仓库写路径的信号（skill_write）不会指向 hub
    （owning_skill_dir 的 roots 限定在仓库内）。hub 未初始化/异常时静默跳过
    （hooks 纪律：进化永不因 hub 挂掉）。
    """
    try:
        from . import hub as hub_mod
        for hs in hub_mod.list_hub_skills():
            if hs["id"] not in index:
                hs["bucket"] = f"hub:{hs['zone']}"
                index[hs["id"]] = hs
    except Exception:  # noqa: BLE001 — hooks 纪律
        pass


def _ensure_hub() -> Path:
    """收编目标 hub 必须存在；缺则轻量初始化（mkdir + 登记，不碰 git）。

    hook 上下文里不能弹交互、不能抛 SystemExit（BaseException 不被 _execute
    的兜底捕获）——所以这里是确定性的自动补建，不是报错。
    """
    from . import hubloc
    root = hubloc.hub_root()
    root.mkdir(parents=True, exist_ok=True)
    if not hubloc.registered_path():
        hubloc.register(str(root))
    return root


def _evolve_locked(apply: bool, cfg: dict, source: str, quiet: bool,
                   index: dict, local_skills: list, sigs: list) -> dict:
    """调用方持有 evolve.lock。"""
    orig_apply = apply
    rate_limited = False
    evo = load_evolution()

    # 卫生预跑：场景标签回填（DDR-5）。确定性关键词分类，元数据卫生动作——
    # 不消耗自动进化预算（max_auto_per_day 管的是内容进化，不是贴标签），
    # 预演模式只计数不落盘；失败静默跳过（分类永远不该阻断进化主流程）。
    n_cats = _auto_categorize(index, cfg, quiet=quiet, write=apply)

    decisions = analyze_mod.analyze(cfg, index, local_skills, sigs, evo)
    t0 = [d for d in decisions if d["tier"] == "T0"]
    t1 = [d for d in decisions if d["tier"] == "T1"]

    # 每日自动执行上限（借鉴 Hermes max_auto_skills_per_day：控制爆炸半径，
    # 也防"信号抖动 → 一夜之间改半个仓库"）。0 = 不限。
    max_auto = int((cfg.get("thresholds") or {}).get("max_auto_per_day", 10))
    if orig_apply and max_auto > 0:
        if evo.get("auto_today_date") != today():
            evo["auto_today_date"] = today()
            evo["auto_today"] = 0
        if int(evo.get("auto_today", 0)) >= max_auto:
            apply = False
            rate_limited = True

    applied, errors = [], []
    if apply:
        for d in t0:
            try:
                msg = _execute(d, index, evo)
                if msg:
                    applied.append(msg)
            except Exception as e:  # noqa: BLE001 — hooks 纪律：单个动作失败不扩散
                errors.append(f"{d.get('kind')}/{d.get('skill_id')}: {e}")

    # T1 挂账（按 kind+skill_id 去重，保留最新）
    pend = {(p.get("kind"), p.get("skill_id")): p for p in (evo.get("pending") or [])}
    for d in t1:
        pend[(d["kind"], d["skill_id"])] = {
            "kind": d["kind"], "skill_id": d["skill_id"],
            "detail": d["detail"], "hint": d.get("hint", ""),
            "since": now_iso(),
        }
    # 销账：已打上场景标签的技能，其 uncategorized 提醒自动移除
    # （其他 T1 种类的解决状态框架无从判断，保持挂账让人工确认）
    for s in index.values():
        if (s["meta"] or {}).get("categories"):
            pend.pop(("uncategorized", s["id"]), None)
    evo["pending"] = sorted(pend.values(), key=lambda p: (p.get("kind"), p.get("skill_id") or ""))

    # 计数器与技能统计（AutoHarness MNG 三态：loads / views / writes + 速率）
    evo["counters"]["signals"] = len(signals_mod.read_all())
    requests = sum(1 for s in sigs if s.get("kind") == "intent")
    evo["counters"]["requests"] = requests
    evo["counters"]["categorizations"] = int(evo["counters"].get("categorizations", 0)) + n_cats
    skills_stat = evo.get("skills") or {}
    for sid in index:
        st = skills_stat.get(sid) or {}
        st["generation"] = (index[sid]["meta"] or {}).get("generation")
        st["loads"] = sum(1 for s in sigs if s.get("kind") == "skill_use"
                          and s.get("skill_id") == sid and s.get("subtype") == "load")
        st["views"] = sum(1 for s in sigs if s.get("kind") == "skill_use"
                          and s.get("skill_id") == sid and s.get("subtype") == "view")
        st["writes"] = sum(1 for s in sigs if s.get("kind") == "skill_write" and s.get("skill_id") == sid)
        st["rate"] = round(st["loads"] / requests, 4) if requests else 0.0
        writes_ts = [s.get("ts", "") for s in sigs
                     if s.get("kind") == "skill_write" and s.get("skill_id") == sid]
        if writes_ts:
            st["last_write"] = max(writes_ts)
        skills_stat[sid] = st
    evo["skills"] = skills_stat

    if signals_mod.prune_if_big() and not quiet:
        print("（signals.jsonl 已截断）")

    if orig_apply and not rate_limited:
        evo["auto_today"] = int(evo.get("auto_today", 0)) + len(applied)

    evo["last_evolve"] = now_iso()
    evo["last_evolve_source"] = source
    evo["digest"] = digest_mod.render(evo, cfg)
    save_evolution(evo)

    report = {
        "planned": len(t0) + len(t1),
        "t0": len(t0), "t1": len(t1),
        "applied": applied, "errors": errors,
        "pending": evo["pending"],
        "digest": evo["digest"],
        "apply": orig_apply,
        "rate_limited": rate_limited,
        "skipped": "",
        "plan": t0,
        "categorized": n_cats,
    }
    if not quiet:
        _print_report(report)
    return report


def _skipped_report(reason: str) -> dict:
    return {"planned": 0, "t0": 0, "t1": 0, "applied": [], "errors": [],
            "pending": [], "digest": "", "apply": False, "rate_limited": False,
            "skipped": reason, "plan": []}


def _print_report(r: dict) -> None:
    if r.get("skipped"):
        print(f"[evolve:跳过] {r['skipped']}")
        return
    mode = "执行" if r["apply"] else "预演（--apply 才落盘）"
    print(f"[evolve:{mode}] 计划 {r['planned']} 项（T0 自动 {r['t0']} / T1 人工 {r['t1']}）")
    if r.get("categorized"):
        verb = "已自动分类" if r["apply"] else "将自动分类"
        print(f"  · 场景轴回填：{verb} {r['categorized']} 个技能（framework categorize 可修正）")
    if not r["apply"]:
        for d in r.get("plan") or []:
            print(f"  · [{d['kind']}] {d.get('skill_id', '')}: {d['detail']}")
    for m in r["applied"]:
        print(f"  ✓ {m}")
    for e in r["errors"]:
        print(f"  ✗ {e}")
    if r.get("rate_limited"):
        print("  （已达当日自动执行上限——本次改为预演；调 thresholds.max_auto_per_day 或明早再来）")
    if not r["apply"] and r["t0"] and not r.get("rate_limited"):
        print("  （以上为计划，未落盘）")
    if r["pending"]:
        print(f"  ⏳ 待人工裁决 {len(r['pending'])} 项（详见 framework status）")


# ---------- T0 执行器 ----------

def _execute(d: dict, index: dict, evo: dict) -> str | None:
    kind = d["kind"]
    sid = d.get("skill_id") or ""
    if kind == "adopt_local":
        return _do_adopt(d, evo)
    if kind == "bump_generation":
        return _do_bump(d, index, evo)
    if kind == "scaffold_candidate":
        return _do_scaffold(d, evo)
    if kind == "ensure_sidecar":
        skill = index.get(sid)
        if skill and meta.ensure_sidecar(skill):
            return f"登记 {sid}（补 sidecar）"
        return None
    if kind == "fix_invocation":
        skill = index.get(sid)
        if skill and meta.fix_invocation_field(skill):
            return f"修正 {sid} 的 invocation 登记"
        return None
    if kind == "fix_triggers":
        return _do_fix_triggers(index.get(sid))
    if kind == "mature_skill":
        skill = index.get(sid)
        if skill:
            lifecycle.mature_skill(skill, f"试用期达标（loads={d['data'].get('loads')}）")
            return f"转正 {sid}（mature + trust）"
        return None
    if kind == "trust_skill":
        skill = index.get(sid)
        if skill:
            lifecycle.confirm_trust(skill, on=True, auto=True)
            return f"解除 {sid} 的 trust=false（loads={d['data'].get('loads')}）"
        return None
    return None


# ---------- 场景轴：category 自动分类（DDR-5，确定性卫生动作） ----------

def _classify_new(skill_dir: Path, sid: str, fm: dict, cfg: dict, bucket: str) -> list:
    """新资产落地时打场景标签：关键词优先，桶默认兜底（DDR-5）。"""
    tax = taxonomy_mod.load(cfg)
    cats = taxonomy_mod.classify({"id": sid, "dir": skill_dir, "fm": fm}, tax)
    return cats or taxonomy_mod.bucket_default(bucket, cfg)


def apply_categories(skill: dict, cats: list, note: str = "") -> list:
    """写 sidecar.categories（不 bump generation——元数据卫生，不是内容进化）。

    调用方负责持有 evolve.lock（evolve 卫生预跑 / CLI categorize 都走锁）。
    """
    d = skill["dir"]
    m = dict(skill.get("meta") or {})
    m["categories"] = [str(c) for c in cats]
    m = meta.append_changelog(
        m, note or f"场景标签更新：{', '.join(m['categories'])}", bump=False)
    meta.write_sidecar(d, m)
    skill["meta"] = m
    return m["categories"]


def _auto_categorize(index: dict, cfg: dict, quiet: bool = False,
                     write: bool = True) -> int:
    """给缺场景标签的技能自动打标（classify → 桶默认值）。返回（将）新打标数。

    只处理"categories 缺失或为空"的技能；已有标签不动（人工修正优先）。
    不消耗自动进化预算（max_auto_per_day）：这是元数据卫生，不是内容进化。
    猜不出来（无命中、无桶默认）就留着——analyze 会挂 T1 请人工分类。
    write=False 时只计数不落盘（evolve 预演模式：预演不写任何文件）。
    调用方持有 evolve.lock。
    """
    tax = taxonomy_mod.load(cfg)
    if not tax:
        return 0
    n = 0
    for skill in index.values():
        m = skill.get("meta") or {}
        if m.get("categories"):
            continue  # 已有标签（人工或上轮自动）不动
        if not m.get("origin"):
            continue  # 没有 sidecar 的技能走 ensure_sidecar 决策，不在这贴
        cats = taxonomy_mod.classify(skill, tax)
        src = "关键词"
        if not cats:
            cats = taxonomy_mod.bucket_default(skill["bucket"], cfg)
            src = f"桶默认（{skill['bucket']}）"
        if not cats:
            continue
        if write:
            apply_categories(skill, cats, note=f"自动分类（{src}）：{', '.join(cats)}")
        n += 1
    return n


def _display_path(p: Path) -> str:
    """登记用路径：$HOME 下的一律转 ~ 形式——公开仓库的 sidecar 不携带用户名。"""
    p = Path(p)
    try:
        return "~/" + p.resolve().relative_to(Path.home()).as_posix()
    except (ValueError, OSError):
        return str(p)


def _do_adopt(d: dict, evo: dict) -> str:
    src = Path(d["data"]["path"])
    sid = d["skill_id"]
    private = bool(d["data"].get("private"))
    # 收编目标 = hub（ADR 0004：hub 承接一切积累，框架仓库永纯）。
    # private 标记 → hub/private/ 私有桶。
    dst_root = (_ensure_hub() / hubloc.PRIVATE_DIR) if private else _ensure_hub()
    dst = dst_root / sid
    if dst.exists():
        return None
    if not d["data"].get("ok", False):
        return _stage_rejected(sid, src, d["data"].get("problems") or [])
    copy_tree(src, dst)
    # validate 段（propose→validate→land）：land 之前必须过检（只拦 BLOCK，WARN 放行）
    problems = blocking_problems(validate_skill_dir(dst, strict=False))
    if problems:
        import shutil
        shutil.rmtree(dst, ignore_errors=True)
        return _stage_rejected(sid, src, problems)
    fm = _fm_of(dst)
    src_display = _display_path(src)
    cfg = paths.load_config()
    bucket = "private" if private else "hub"
    cats = _classify_new(dst, sid, fm, cfg, bucket)
    sidecar = {
        "kind": "skill",                       # 资产类型轴（PRD v2 DDR-2）：v2.0 仅 skill
        "visibility": "private",               # F2 fail-safe：一律私有，公开走白名单显式提升
        "execution": "hybrid",                 # 执行模式轴（DDR-1）：auto|manual|hybrid
        "categories": cats,                    # 场景轴（DDR-5）：多标签，受控词表
        "origin": "adopted",
        "source": src_display,
        "license": fm.get("license"),
        "invocation": "user" if str(fm.get("disable-model-invocation", "")).lower() == "true" else "model",
        "generation": 1,
        "changelog": [{"gen": 1, "date": today(),
                       "change": f"自动收编自 {src_display}（framework evolve → hub"
                                 f"{'/private' if private else ''}）"
                                 + ("（私有桶：纳入治理，永不公开）" if private else "")
                                 + (f"；场景：{', '.join(cats)}" if cats else "")}],
        "base_sha256": dir_hash(dst),
        "source_sha256": meta.sha256_skill_md(src),
        # 收编时源目录的正文哈希：import 同源包时的谱系连线。
        # 场景：clone 框架 → 本机技能被自动收编 → 又从同源机器 import 包——
        # 没有这条线，同源技能会因「无共同基线」误挂人工。
        "source_body_hash": dir_hash(src),
        "imported_from": None,
    }
    sidecar = lifecycle.start_probation(
        sidecar, int(cfg.get("thresholds", {}).get("probation_days", 30)))
    meta.write_sidecar(dst, sidecar)
    meta.snapshot(dst)
    evo["counters"]["adoptions"] = evo["counters"].get("adoptions", 0) + 1
    dest = f"hub/{hubloc.PRIVATE_DIR}/（私有，永不公开）" if private else "hub/（visibility=private，公开走白名单）"
    return f"收编 {sid} → {dest}（源：{src_display}，试用期 {sidecar['probation_until']}）"


def _stage_rejected(sid: str, src: Path, problems: list) -> str:
    """未过检的本地技能 → 候选区暂存（不复制内容，只留问题清单）。"""
    cdir = paths.CANDIDATES_DIR / sid
    cdir.mkdir(parents=True, exist_ok=True)
    lines = ["# 收编未过检", "", f"源：`{src}`", "", "## 问题", ""]
    lines += [f"- {p}" for p in problems]
    lines += ["", "人工处理：修复上述问题后重跑 `framework evolve`，或 `framework promote " + sid + "` 强制晋升。"]
    (cdir / "PROBLEMS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return f"暂存候选 {sid}（未过检：{problems[0] if problems else '?'}）"


def _do_bump(d: dict, index: dict, evo: dict) -> str | None:
    sid = d["skill_id"]
    skill = index.get(sid)
    if not skill:
        return None
    gen = meta.bump_generation(skill, f"自动进化：{d['detail']}")
    st = (evo.get("skills") or {}).get(sid) or {}
    st["last_bump_ts"] = now_iso()
    evo.setdefault("skills", {})[sid] = st
    evo["counters"]["evolutions"] = evo["counters"].get("evolutions", 0) + 1
    return f"进化 {sid} → generation {gen}"


def _do_scaffold(d: dict, evo: dict) -> str | None:
    slug = d["data"]["slug"]
    cdir = paths.CANDIDATES_DIR / slug
    if cdir.exists():
        return None
    cdir.mkdir(parents=True, exist_ok=True)
    toks = d["data"].get("tokens") or []
    title = " ".join(t for t in toks if t.isascii())[:60] or "".join(toks)[:40] or slug
    # 触发措辞前置（见 _do_fix_triggers 的截断教训）
    zh = any("\u4e00" <= ch <= "\u9fff" for t in toks for ch in t)
    joiner = "、" if zh else ", "
    head = "当用户需要相关能力时使用：" if zh else "Use when the user needs related capabilities: "
    skill_md = _render_template("SKILL.md.tmpl", {
        "name": slug,
        "title": title,
        "trigger": head + joiner.join(toks[:8]),
    })
    (cdir / "SKILL.md").write_text(skill_md, encoding="utf-8")
    evidence = [
        "# 候选证据", "",
        f"- 重复意图出现 **{d['data'].get('count')} 次**",
        f"- 首次：{d['data'].get('first')}",
        f"- 最近：{d['data'].get('last')}",
        f"- 意图词元：{' '.join(toks[:16])}",
        "",
        "本骨架由 framework 自动生成。充实内容后 `framework promote " + slug + "` 晋升为正式技能。",
        "撰写方法论见 skills/agent/skill-forge/references/authoring.md。",
    ]
    (cdir / "EVIDENCE.md").write_text("\n".join(evidence) + "\n", encoding="utf-8")
    # validate 段（strict）：自产产物必须过检才留在候选区
    problems = validate_skill_dir(cdir, strict=True)
    if problems:
        (cdir / "PROBLEMS.md").write_text(
            "# 自动产物未过检\n\n" + "\n".join(f"- {p}" for p in problems) + "\n",
            encoding="utf-8")
        return f"候选 {slug} 未过 strict 自检（见 state/candidates/{slug}/PROBLEMS.md）"
    evo["counters"]["candidates"] = evo["counters"].get("candidates", 0) + 1
    return f"新候选 {slug}（重复意图 ×{d['data'].get('count')}）"


def _do_fix_triggers(skill: dict | None) -> str | None:
    if not skill:
        return None
    d = skill["dir"]
    skill_md = d / "SKILL.md"
    try:
        text = skill_md.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    fm = skill.get("fm") or {}
    desc = fm.get("description", "")
    if not desc or scan.has_trigger_markers(desc):
        return None
    # 触发语前置（AutoHarness 教训）：索引/扫描表面常按行截断 description，
    # 追加在尾部的触发 cue 会整段丢失——前置才保证任何截断水平下都可见。
    cjk = sum(1 for ch in desc if "\u4e00" <= ch <= "\u9fff")
    if cjk > len(desc) // 4:
        head = f"当用户需要 {skill['id']} 相关能力时使用。"
    else:
        head = f"Use when the user needs {skill['id']} related capabilities. "
    new_desc = head + desc.lstrip()
    # 只替换 description 行（标量单行）
    lines = text.split("\n")
    for i, ln in enumerate(lines):
        if ln.startswith("description:"):
            lines[i] = f"description: {new_desc}"
            break
    else:
        return None
    meta.snapshot(d)
    skill_md.write_text("\n".join(lines), encoding="utf-8")
    skill["meta"] = meta.append_changelog(dict(skill.get("meta") or {}),
                                          "自动修补：description 补触发措辞（双读者规则）")
    meta.write_sidecar(d, skill["meta"])
    return f"修补 {skill['id']} 的 description 触发语"


def _fm_of(skill_dir: Path) -> dict:
    from .util import read_frontmatter_file
    return read_frontmatter_file(skill_dir / "SKILL.md")


def _render_template(name: str, vars_: dict) -> str:
    tpl = (paths.TEMPLATES_DIR / name).read_text(encoding="utf-8")
    for k, v in vars_.items():
        tpl = tpl.replace("{{" + k + "}}", str(v))
    return tpl


# ---------- 候选晋升（T0 本地写，但只允许显式调用，不在 Stop 自动执行） ----------

def promote_candidate(slug: str) -> str:
    cdir = paths.CANDIDATES_DIR / slug
    if not cdir.is_dir():
        raise SystemExit(f"ERROR: 候选不存在: {slug}（framework status 查看候选列表）")
    dst = _ensure_hub() / slug
    if dst.exists():
        raise SystemExit(f"ERROR: 目标已存在: {dst}")
    # validate 段（strict）：人工点了晋升也要过自产限定，不过就是不过
    problems = validate_skill_dir(cdir, strict=True)
    if problems:
        raise SystemExit("ERROR: 候选未过检，拒绝晋升：\n  - " + "\n  - ".join(problems))
    copy_tree(cdir, dst)
    for junk in ("PROBLEMS.md", "EVIDENCE.md"):
        p = dst / junk
        if p.exists():
            p.unlink()
    fm = _fm_of(dst)
    cfg = paths.load_config()
    cats = _classify_new(dst, slug, fm, cfg, "hub")
    sidecar = {
        "kind": "skill",                       # 资产类型轴（PRD v2 DDR-2）：v2.0 仅 skill
        "visibility": "private",               # F2 fail-safe：公开走白名单显式提升
        "execution": "hybrid",                 # 执行模式轴（DDR-1）：auto|manual|hybrid
        "categories": cats,                    # 场景轴（DDR-5）
        "origin": "local-forged",
        "source": None,
        "license": fm.get("license"),
        "invocation": "user" if str(fm.get("disable-model-invocation", "")).lower() == "true" else "model",
        "generation": 1,
        "changelog": [{"gen": 1, "date": today(),
                       "change": f"从自动候选晋升 → hub（证据见原 EVIDENCE.md）"
                                 + (f"；场景：{', '.join(cats)}" if cats else "")}],
        "base_sha256": dir_hash(dst),
    }
    sidecar = lifecycle.start_probation(
        sidecar, int(cfg.get("thresholds", {}).get("probation_days", 30)))
    meta.write_sidecar(dst, sidecar)
    meta.snapshot(dst)
    return f"晋升候选 {slug} → hub/{slug}（visibility=private，试用期至 {sidecar['probation_until']}）"


# ---------- digest 消费（SessionStart 注入后调用） ----------

def consume_digest() -> str:
    """SessionStart 打印摘要后调用：把基线对齐到当前计数，摘要清零。"""
    with lock_mod.file_lock(paths.EVOLUTION_LOCK, timeout=paths.LOCK_TIMEOUT) as locked:
        if not locked:
            return ""
        evo = load_evolution()
        printed = evo.get("digest", "")
        evo["baseline"] = dict(evo.get("counters", {}))
        evo["digest"] = ""
        save_evolution(evo)
        return printed
