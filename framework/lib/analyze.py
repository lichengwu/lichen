"""framework/lib/analyze.py — 信号 → 进化决策（纯函数，不写文件）。

决策分级：
  T0  自动执行（本地、可 git 回滚、留 changelog）
  T1  人工门（进入 evolution.json 的 pending，digest 点名）
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import lifecycle, meta, paths, scan, taxonomy
from .redact import scan_tree
from .util import dir_hash
from .validate import validate_skill_dir


def _within(ts: str, days: int) -> bool:
    try:
        t = datetime.fromisoformat(ts)
    except (ValueError, TypeError):
        return False
    return t >= datetime.now(timezone.utc).astimezone() - timedelta(days=days)


def _adoption_problems(local_skill: dict) -> list:
    """收编前的检查（validate 段）：frontmatter 基本完整 + 硬红线干净 + 海拔提示。"""
    problems = []
    fm = local_skill.get("fm") or {}
    if not fm.get("name"):
        problems.append("frontmatter 缺少 name")
    if not fm.get("description"):
        problems.append("frontmatter 缺少 description")
    hits = scan_tree(local_skill["path"], max_hits=5)
    if hits:
        problems.append("硬红线命中: " + "; ".join(hits[:3]))
    return problems


def _loads_of(sid: str, signals: list) -> int:
    return sum(1 for s in signals
               if s.get("kind") == "skill_use" and s.get("skill_id") == sid
               and s.get("subtype") == "load")


def analyze(cfg: dict, index: dict, local_skills: list, signals: list, evo: dict) -> list:
    decisions = []
    auto = cfg.get("auto", {})
    th = cfg.get("thresholds", {})
    repo_skills = list(index.values())

    # ---------- 1. 本地新技能 → 自动收编 ----------
    if auto.get("adopt_local_skills", True):
        excluded = set(cfg.get("exclude_skills") or [])
        ignored = set(cfg.get("ignore_skills") or [])
        for ls in local_skills:
            if ls["id"] in index:
                continue  # 已在管理
            if ls["id"] in ignored:
                continue  # 噪声名单（内置副本等）：连私有桶也不进
            try:
                ls["path"].resolve().relative_to(paths.SKILLS_ROOT.resolve())
                continue  # 扫描目录指进了仓库自己，跳过
            except ValueError:
                pass
            problems = _adoption_problems(ls)
            if ls["id"] in excluded:
                # 治理与发布分离（PRD v2 P-8）：排除名单 = 不公开，不等于不管理。
                # 个人向/手动执行技能收编进 .private 桶——纳入治理，永不公开。
                if not auto.get("private_adoption", True):
                    continue
                decisions.append({
                    "tier": "T0",
                    "kind": "adopt_local",
                    "skill_id": ls["id"],
                    "detail": f"本地技能 {ls['id']} → 私有桶（排除清单同源：纳入治理，永不公开）"
                              + ("" if not problems else "：未过检 → 转候选"),
                    "data": {"path": str(ls["path"]), "ok": not problems,
                             "problems": problems, "private": True},
                })
                continue
            decisions.append({
                "tier": "T0",
                "kind": "adopt_local",
                "skill_id": ls["id"],
                "detail": f"本地新技能 {ls['id']}（{ls['path']}）"
                          + ("" if not problems else "：未过检 → 转候选"),
                "data": {"path": str(ls["path"]), "ok": not problems, "problems": problems},
            })

    # ---------- 2. 编辑爆发 → generation++ 留痕 ----------
    if auto.get("generation_bump", True):
        burst_days = int(th.get("edit_burst_days", 7))
        burst_n = int(th.get("edit_burst", 3))
        counts = {}
        for s in signals:
            if s.get("kind") != "skill_write":
                continue
            if not _within(s.get("ts", ""), burst_days):
                continue
            sid = s.get("skill_id")
            if sid in index:
                counts[sid] = counts.get(sid, 0) + 1
        for sid, n in sorted(counts.items()):
            if n < burst_n:
                continue
            last_bump = ((evo.get("skills") or {}).get(sid) or {}).get("last_bump_ts", "")
            if last_bump and _within(last_bump, burst_days):
                continue  # 本窗口已留过痕
            decisions.append({
                "tier": "T0",
                "kind": "bump_generation",
                "skill_id": sid,
                "detail": f"{sid} 在 {burst_days} 天内被编辑 {n} 次（编辑爆发）",
                "data": {"count": n},
            })

    # ---------- 3. 重复意图 → scaffold 候选 ----------
    if auto.get("scaffold_candidates", True):
        clusters = scan.cluster_intents(
            signals,
            min_count=int(th.get("intent_repeat", 3)),
            days=int(th.get("intent_repeat_days", 30)),
        )
        existing_candidates = _candidate_slugs()
        for c in clusters:
            toks = c.get("rep") or []
            if scan.covered_by(toks, repo_skills):
                continue
            slug = _slug_from_tokens(toks)
            if slug in existing_candidates:
                continue  # 候选已存在，不重复 scaffold
            decisions.append({
                "tier": "T0",
                "kind": "scaffold_candidate",
                "skill_id": slug,
                "detail": f"重复意图 ×{c['count']}（{c.get('first', '')[:10]} 起）：{' '.join(toks[:6])}",
                "data": {"slug": slug, "tokens": toks, "count": c["count"],
                         "first": c.get("first"), "last": c.get("last")},
            })

    # ---------- 4. 卫生检查（确定性修补） ----------
    if auto.get("hygiene_fix", True):
        for s in repo_skills:
            sid = s["id"]
            if not s["meta"]:
                decisions.append({"tier": "T0", "kind": "ensure_sidecar", "skill_id": sid,
                                  "detail": f"{sid} 缺少 sidecar 登记", "data": {}})
                continue
            actual = meta.invocation_of(s)
            if s["meta"].get("invocation") != actual:
                decisions.append({"tier": "T0", "kind": "fix_invocation", "skill_id": sid,
                                  "detail": f"{sid} sidecar.invocation 与 frontmatter 不一致", "data": {}})
            fm = s["fm"] or {}
            desc = fm.get("description", "")
            if actual == "model" and desc and not scan.has_trigger_markers(desc):
                decisions.append({"tier": "T0", "kind": "fix_triggers", "skill_id": sid,
                                  "detail": f"{sid} description 缺触发措辞（双读者规则）", "data": {}})
            # 场景轴卫生（DDR-5）：无标签且关键词/桶默认都猜不出来 → 挂人工。
            # 卫生预跑（evolve._auto_categorize）已处理能猜的；这里是"宁缺勿滥"的兜底。
            if auto.get("auto_categorize", True) and not s["meta"].get("categories"):
                tax = taxonomy.load(cfg)
                if not taxonomy.classify(s, tax) and not taxonomy.bucket_default(s["bucket"], cfg):
                    decisions.append({
                        "tier": "T1", "kind": "uncategorized", "skill_id": sid,
                        "detail": f"{sid} 无场景标签，且关键词无法自动归类",
                        "data": {},
                        "hint": f"framework categorize {sid} <场景>（词表见 config.default.json taxonomy，可扩展）",
                    })
            if fm.get("name") and fm.get("name") != sid:
                decisions.append({"tier": "T1", "kind": "rename_skill", "skill_id": sid,
                                  "detail": f"{sid} frontmatter name={fm.get('name')} 与目录名不一致（改名影响引用，人工决断）",
                                  "data": {}, "hint": "framework doctor 查看详情"})

    # ---------- 6. 试用期 / 信任门（probation + trust，AutoHarness / SkillMaxxing） ----------
    probation_days = int(th.get("probation_days", 30))
    probation_min = int(th.get("probation_min_uses", 3))
    trust_min = int(th.get("trust_min_loads", 5))
    for s in repo_skills:
        sid = s["id"]
        m = s.get("meta") or {}
        loads = _loads_of(sid, signals)
        # 6a. 试用期达标 → mature + trust 转正（T0）
        if not m.get("mature") and m.get("probation_until") and not lifecycle.probation_expired(m):
            if loads >= probation_min:
                decisions.append({
                    "tier": "T0", "kind": "mature_skill", "skill_id": sid,
                    "detail": f"{sid} 试用期内 loads={loads} ≥ {probation_min}，转正 mature",
                    "data": {"loads": loads},
                })
        # 6b. 试用期到期未达标 → 挂人工（充实 or 归档，不自动删）
        elif lifecycle.probation_expired(m):
            decisions.append({
                "tier": "T1", "kind": "probation_expired", "skill_id": sid,
                "detail": f"{sid} 试用期（{m.get('probation_until')}）已过但 loads={loads} < {probation_min}",
                "data": {"loads": loads},
                "hint": f"人工充实后 framework evolve 重评，或 framework archive {sid} 归档",
            })
        # 6c. trust=false 但已被反复加载 → 自动转正（T0）
        if lifecycle.should_trust(m, loads, trust_min):
            decisions.append({
                "tier": "T0", "kind": "trust_skill", "skill_id": sid,
                "detail": f"{sid} loads={loads} ≥ {trust_min}，自动解除 trust=false",
                "data": {"loads": loads},
            })

    # ---------- 7. 容量竞争（local 桶超限 → 挂人工，给归档命令） ----------
    capacity = int(th.get("capacity", 40))
    local_now = [s for s in repo_skills if s["bucket"] == "local"]
    if len(local_now) > capacity:
        coldest = min(local_now,
                      key=lambda s: (_loads_of(s["id"], signals),
                                     (s.get("meta") or {}).get("probation_until") or "9999"))
        decisions.append({
            "tier": "T1", "kind": "archive_candidate", "skill_id": coldest["id"],
            "detail": f"local 桶 {len(local_now)}/{capacity} 超容，最冷门：{coldest['id']}",
            "data": {"loads": _loads_of(coldest["id"], signals)},
            "hint": f"framework archive {coldest['id']}（可复活：framework unarchive）",
        })

    # ---------- 8. 收编源漂移（T1：含脱敏考量，不自动回灌） ----------
    for s in repo_skills:
        m = s.get("meta") or {}
        if m.get("origin") != "adopted" or not m.get("source"):
            continue
        src = Path(str(m["source"])).expanduser()
        if not src.is_dir():
            continue
        try:
            cur = meta.sha256_skill_md(src)
        except OSError:
            continue
        recorded = m.get("source_sha256")
        if recorded and cur != recorded:
            decisions.append({
                "tier": "T1", "kind": "adopted_source_drift", "skill_id": s["id"],
                "detail": f"收编源已变化：{src}（仓库副本可能已落后）",
                "data": {"source": str(src)},
                "hint": "人工比对后同步（注意脱敏规则）",
            })

    # T0 在前，T1 在后
    return sorted(decisions, key=lambda d: 0 if d["tier"] == "T0" else 1)


def _candidate_slugs() -> set:
    if not paths.CANDIDATES_DIR.is_dir():
        return set()
    return {d.name for d in paths.CANDIDATES_DIR.iterdir() if d.is_dir()}


def _slug_from_tokens(tokens: list) -> str:
    from .util import slugify
    ascii_words = [t for t in tokens if t.isascii() and len(t) >= 4]
    if ascii_words:
        return slugify("-".join(ascii_words[:3]))
    cjk = "".join(t for t in tokens if not t.isascii())[:12]
    return slugify(cjk) or "candidate"
