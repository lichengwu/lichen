"""framework/lib/exchange.py — skillpack/1：导出 / 导入 / 校验。

协议（ADR 0002 §2.6）：
  dist/<pack>/MANIFEST.json + skills/<id>/... + config/...
  - 每个技能带目录级 sha256 与逐文件 sha256（防篡改）
  - sidecar 随包携带（来源登记是迁移质量的一部分）
  - 导入三方合并：base 来自 state/versions 快照；本地已进化（generation>0）永不静默覆盖
  - 冲突 → 两侧落 state/incoming/，挂 T1 pending，不许猜
"""

from __future__ import annotations

import re
import shutil
import zipfile
from pathlib import Path

from . import meta, paths
from .redact import scan_tree
from .util import (copy_tree, dir_hash, now_iso, read_json, sha256_file,
                   today, write_json_atomic)

FORMAT = "skillpack/1"
FRAMEWORK_VERSION = "0.1.0"
CONFIG_PAYLOAD_DIRS = [".agents"]  # --include-config 携带的配置树
_SAFE_NAME = re.compile(r"^[a-z0-9][a-z0-9-]*$")
# 资产类型轴（PRD v2 DDR-2）：交换协议 kind-generic，本版本只实装 skill。
# 新增 kind = 加一个 adapter（validate/land/scaffold/render 四件套），不动协议。
SUPPORTED_KINDS = {"skill"}


# ---------- 导出 ----------

def export_pack(name: str | None = None, out_dir: str | None = None,
                include_config: bool = False, mine_only: bool = False,
                skills: list | None = None, buckets: list | None = None,
                categories: list | None = None,
                dry: bool = False) -> dict:
    all_skills = meta.list_repo_skills()
    # 私有桶默认不导出（治理与发布分离）。只有显式 --skill <id> 或
    # --bucket .private 才把私有技能打进包——私有包是自用迁移场景。
    priv = paths.PRIVATE_BUCKET
    want_ids = set(skills) if skills else set()
    want_buckets = set(buckets) if buckets else set()
    selected = [s for s in all_skills
                if s["bucket"] != priv
                or s["id"] in want_ids
                or priv in want_buckets]
    if skills:
        wanted = set(skills)
        selected = [s for s in selected if s["id"] in wanted]
    if buckets:
        wanted_b = set(buckets)
        selected = [s for s in selected if s["bucket"] in wanted_b]
    if categories:
        # 场景轴过滤（DDR-5）：多标签命中其一即导——"导出我的办公场景包"
        wanted_c = set(categories)
        selected = [s for s in selected if wanted_c & set(meta.categories_of(s))]
    if mine_only:
        selected = [s for s in selected if (s["meta"] or {}).get("origin") in ("local-forged", "adopted")]
    if not selected:
        raise SystemExit("ERROR: 没有匹配任何技能（检查 --skill/--bucket/--mine 过滤条件）")

    # 安全门：硬红线命中即拒绝导出
    for s in selected:
        hits = scan_tree(s["dir"])
        if hits:
            raise SystemExit("ERROR: 硬红线命中，拒绝导出（先修复再打包）:\n  " + "\n  ".join(hits[:10]))

    pack_name = name or f"skillpack-{today()}"
    out = Path(out_dir) if out_dir else paths.DIST_DIR
    if not out.is_absolute():
        out = paths.REPO_ROOT / out
    pack_dir = out / pack_name

    if dry:
        return {"dry": True, "name": pack_name, "dir": str(pack_dir),
                "skills": [s["id"] for s in selected]}

    if pack_dir.exists():
        raise SystemExit(f"ERROR: 输出目录已存在: {pack_dir}（换一个 --name 或先清理）")

    entries = []
    for s in selected:
        dst = pack_dir / "skills" / s["id"]
        copy_tree(s["dir"], dst)
        m = s["meta"] or {}
        entries.append({
            "id": s["id"],
            "kind": (m.get("kind") or "skill"),          # 资产类型轴（v2.0 仅 skill）
            "visibility": m.get("visibility") or ("private" if s["bucket"] == paths.PRIVATE_BUCKET else "public"),
            "execution": m.get("execution") or "hybrid",  # 执行模式轴（auto|manual|hybrid）
            "categories": meta.categories_of(s),          # 场景轴（DDR-5，多标签）
            "bucket": s["bucket"],
            "origin": m.get("origin", "unregistered"),
            "source": m.get("source"),
            "license": m.get("license"),
            "upstream_ref": m.get("upstream_ref"),
            "generation": m.get("generation"),
            "sha256": dir_hash(dst),
            # base_hint：本方这个版本所基于的上一版哈希（导入方从未导入过祖先包时，
            # 靠它定位三方合并的共同基线——originating 机器的 last_seen 为空）
            "base_hint": m.get("last_seen_sha256"),
            "files": _file_hashes(dst),
        })
        meta.snapshot(s["dir"])  # 导出即登记一个已见版本（导入合并的 base 线索）

    configs = []
    if include_config:
        for cd in CONFIG_PAYLOAD_DIRS:
            src = paths.REPO_ROOT / cd
            if src.is_dir():
                dst = pack_dir / "config" / cd
                copy_tree(src, dst)
                configs.append({"path": cd, "sha256": dir_hash(src),
                                "files": _file_hashes(dst)})

    manifest = {
        "format": FORMAT,
        "name": pack_name,
        "created_by": "framework export",
        "framework_version": FRAMEWORK_VERSION,
        "exported_at": now_iso(),
        "source_repo": paths.REPO_ROOT.name,
        "counts": {"skills": len(entries), "configs": len(configs)},
        "skills": entries,
        "configs": configs,
    }
    write_json_atomic(pack_dir / "MANIFEST.json", manifest)

    zip_path = out / f"{pack_name}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(pack_dir.rglob("*")):
            if p.is_file():
                zf.write(p, arcname=p.relative_to(pack_dir.parent).as_posix())

    _bump_counter("exports")
    return {"dry": False, "name": pack_name, "dir": str(pack_dir),
            "zip": str(zip_path), "skills": [e["id"] for e in entries],
            "configs": len(configs),
            "bytes": zip_path.stat().st_size}


# ---------- 导入 ----------

def import_pack(src: str, dry: bool = False) -> dict:
    pack_dir, unpacked = _resolve_pack(src)
    try:
        return _import_from_dir(pack_dir, dry=dry)
    finally:
        pass  # 解包目录留在 state/incoming/ 供检查，不自动清理


def _import_from_dir(pack_dir: Path, dry: bool = False) -> dict:
    manifest = read_json(pack_dir / "MANIFEST.json", None)
    if not isinstance(manifest, dict):
        raise SystemExit(f"ERROR: {pack_dir} 里没有 MANIFEST.json")
    if manifest.get("format") != FORMAT:
        raise SystemExit(f"ERROR: 不支持的包格式: {manifest.get('format')!r}（需要 {FORMAT}）")

    problems = verify_pack(pack_dir, manifest)
    if problems:
        raise SystemExit("ERROR: 包校验失败（可能被篡改）:\n  " + "\n  ".join(problems[:10]))

    pack_name = manifest.get("name", pack_dir.name)
    report = {"pack": pack_name, "installed": [], "updated": [], "skipped": [],
              "conflicts": [], "pending": [], "dry": dry}
    evo = _load_evo()

    for entry in manifest.get("skills") or []:
        sid = entry.get("id", "")
        if not _SAFE_NAME.match(sid or ""):
            report["pending"].append({"skill_id": sid, "kind": "import_reject",
                                      "detail": f"技能 id 不合法: {sid!r}"})
            continue
        kind = entry.get("kind") or "skill"
        if kind not in SUPPORTED_KINDS:
            # 资产类型轴（DDR-2）：协议是 kind-generic 的，v2.0 只实装 skill。
            # 未知 kind 不猜、不硬装——挂 pending 让人知道这个包需要更新的 lichen。
            report["pending"].append({"skill_id": sid, "kind": "import_reject",
                                      "detail": f"不支持的资产类型 {kind!r}（本版本支持: {', '.join(sorted(SUPPORTED_KINDS))}）"})
            continue
        theirs = pack_dir / "skills" / sid
        if not theirs.is_dir():
            report["pending"].append({"skill_id": sid, "kind": "import_reject",
                                      "detail": "包内缺少技能目录"})
            continue
        target = _find_existing(sid) or (paths.SKILLS_ROOT / (entry.get("bucket") if _SAFE_NAME.match(entry.get("bucket") or "") else "local") / sid)
        if not target.exists():
            if dry:
                report["installed"].append(sid)
                continue
            copy_tree(theirs, target)
            _write_imported_sidecar(target, entry, pack_name)
            meta.snapshot(target)
            report["installed"].append(sid)
            continue

        ours_hash = dir_hash(target)
        if ours_hash == entry.get("sha256"):
            # 版本相同也要登记 last_seen：保持版本图连通。否则日后对方再变时
            # 找不到共同基线，本可自动的三方合并会退化成挂人工。
            if not dry:
                skip_meta = meta.read_sidecar(target)
                if skip_meta.get("last_seen_sha256") != entry.get("sha256"):
                    skip_meta["last_seen_sha256"] = entry.get("sha256")
                # 场景轴并集（DDR-5）：同版本不改内容哈希，但对方的标签词汇
                # 值得学——词表外标签原样保留，doctor 警告提示收编进词表
                merged_cats = sorted(set(skip_meta.get("categories") or [])
                                     | set(entry.get("categories") or []))
                if merged_cats:
                    skip_meta["categories"] = merged_cats
                meta.write_sidecar(target, skip_meta)
                meta.snapshot(target)  # 内容寻址，已存在则跳过
            report["skipped"].append(f"{sid}（版本相同）")
            continue
        ours_meta = meta.read_sidecar(target)
        last_seen = ours_meta.get("last_seen_sha256")
        # 包版本进快照库：它可能成为未来某次合并的共同基线
        # （快照按内容哈希寻址，已存在则跳过）
        meta.snapshot(theirs)

        # 同源识别（fork 模型高频路径）：本技能是自动收编来的，且收编时的
        # 源正文哈希 == 包版本 → 这个包就是收编来源的同源导出。
        # 本地正文没变上面已 skip；走到这说明本地又改了——「本地已更新」。
        if ours_meta.get("source_body_hash") and ours_meta["source_body_hash"] == entry.get("sha256"):
            report["skipped"].append(f"{sid}（收编同源，保留本地版）")
            continue

        if last_seen == ours_hash:
            # 只有对方变了 → 快进
            if dry:
                report["updated"].append(f"{sid}（快进，dry-run）")
                continue
            meta.snapshot(target)
            _replace_dir(target, theirs)
            _sidecar_after_update(ours_meta, entry, pack_name)
            meta.write_sidecar(target, ours_meta)
            meta.snapshot(target)
            report["updated"].append(f"{sid}（快进）")
        elif last_seen == entry.get("sha256"):
            report["skipped"].append(f"{sid}（本地已更新，保留本地版）")
        else:
            # 双方都动过 → 三方合并或挂人工
            if (ours_meta.get("origin") == "upstream") or (entry.get("origin") == "upstream"):
                _stage_incoming(sid, theirs, "upstream 技能：走 skill-forge update 工作流（三路合并+人工确认）")
                report["pending"].append({"skill_id": sid, "kind": "import_conflict",
                                          "detail": f"upstream 技能 {sid} 两侧版本不一致，已暂存 state/incoming/{sid}/",
                                          "hint": "skill-forge update 工作流"})
                continue
            # base 解析：先找本地 last_seen；若本机从未导入过祖先包
            # （originating 机器，last_seen 为空），退回包内 base_hint
            base_dir = meta.find_version(sid, (last_seen or "")[:8])
            if base_dir is None and entry.get("base_hint"):
                base_dir = meta.find_version(sid, str(entry["base_hint"])[:8])
            if base_dir is None:
                _stage_incoming(sid, theirs, "找不到共同基线快照，人工裁决")
                report["pending"].append({"skill_id": sid, "kind": "import_conflict",
                                          "detail": f"{sid} 双方都进化过且无共同基线，已暂存 state/incoming/{sid}/",
                                          "hint": "人工比对两份差异"})
                continue
            # 合并前先快照本地版（AutoHarness curator 纪律）：合并是少数无法用
            # 一次原子改名撤销的操作，事前留底才能回退
            meta.snapshot(target)
            status, merged = _merge_dirs(base_dir, target, theirs)
            if status == "conflict":
                _stage_incoming(sid, theirs, f"逐行合并有 {len(merged['conflicts'])} 处冲突，人工裁决")
                report["conflicts"].append(sid)
                report["pending"].append({"skill_id": sid, "kind": "import_conflict",
                                          "detail": f"{sid} 合并冲突 {len(merged['conflicts'])} 处，已暂存 state/incoming/{sid}/",
                                          "hint": "人工比对两份差异"})
            else:
                if dry:
                    report["updated"].append(f"{sid}（可三方合并，dry-run）")
                    continue
                _apply_merged(target, merged)
                _sidecar_after_update(ours_meta, entry, pack_name)
                meta.write_sidecar(target, ours_meta)
                meta.snapshot(target)
                report["updated"].append(f"{sid}（三方合并）")

    # 配置合并
    for centry in manifest.get("configs") or []:
        rel = centry.get("path", "")
        if ".." in Path(rel).parts:
            continue
        theirs = pack_dir / "config" / rel
        if not theirs.exists():
            continue
        ours = paths.REPO_ROOT / rel
        if not ours.exists():
            if not dry:
                copy_tree(theirs, ours)
                evo.setdefault("config_seen", {})[rel] = sha256_file(ours) if ours.is_file() else dir_hash(ours)
            report["installed"].append(f"config:{rel}")
            continue
        ours_hash = sha256_file(ours) if ours.is_file() else dir_hash(ours)
        seen = (evo.get("config_seen") or {}).get(rel)
        if ours_hash == centry.get("sha256"):
            report["skipped"].append(f"config:{rel}（相同）")
        elif seen == ours_hash:
            if not dry:
                shutil.copy2(theirs, ours) if ours.is_file() else copy_tree(theirs, ours)
                evo.setdefault("config_seen", {})[rel] = sha256_file(ours) if ours.is_file() else dir_hash(ours)
            report["updated"].append(f"config:{rel}（快进）")
        elif seen == centry.get("sha256"):
            report["skipped"].append(f"config:{rel}（本地已更新）")
        else:
            _stage_incoming(f"config-{Path(rel).name}", theirs, "配置双方都改过，人工裁决")
            report["pending"].append({"skill_id": f"config:{rel}", "kind": "import_conflict",
                                      "detail": f"配置 {rel} 双方都改过，对方版本已暂存",
                                      "hint": "人工比对两份差异"})

    if not dry:
        _merge_pending(evo, report["pending"])
        evo["counters"]["imports"] = evo["counters"].get("imports", 0) + 1
        _save_evo(evo)
    return report


def verify_pack(pack_dir: Path, manifest: dict) -> list:
    """校验包完整性：列出的文件必须存在且哈希一致，也不许多出文件。"""
    problems = []
    for entry in manifest.get("skills") or []:
        sid = entry.get("id", "")
        sdir = pack_dir / "skills" / sid
        if not sdir.is_dir():
            problems.append(f"缺少技能目录: skills/{sid}")
            continue
        actual = _file_hashes(sdir)
        for rel, sha in (entry.get("files") or {}).items():
            if actual.get(rel) != sha:
                problems.append(f"{sid}/{rel} 哈希不符（被篡改？）")
        for rel in actual:
            if rel not in (entry.get("files") or {}):
                problems.append(f"{sid}/{rel} 未登记（多余文件）")
        if dir_hash(sdir) != entry.get("sha256"):
            problems.append(f"{sid} 目录哈希不符")
    for centry in manifest.get("configs") or []:
        rel = centry.get("path", "")
        cdir = pack_dir / "config" / rel
        if not cdir.exists():
            problems.append(f"缺少配置: {rel}")
            continue
        actual = _file_hashes(cdir)
        for frel, sha in (centry.get("files") or {}).items():
            if actual.get(frel) != sha:
                problems.append(f"{rel}/{frel} 哈希不符")
    return problems


# ---------- 内部工具 ----------

def _file_hashes(root: Path) -> dict:
    out = {}
    for p in sorted(Path(root).rglob("*")):
        if p.is_file():
            out[p.relative_to(root).as_posix()] = sha256_file(p)
    return out


def _find_existing(sid: str) -> Path | None:
    for bucket_dir in sorted(paths.SKILLS_ROOT.iterdir()):
        if bucket_dir.is_dir() and (bucket_dir / sid / "SKILL.md").is_file():
            return bucket_dir / sid
    return None


def _replace_dir(target: Path, src: Path) -> None:
    backup = target.with_name(target.name + ".import-bak")
    if backup.exists():
        shutil.rmtree(backup, ignore_errors=True)
    target.rename(backup)
    copy_tree(src, target)
    shutil.rmtree(backup, ignore_errors=True)


def _write_imported_sidecar(target: Path, entry: dict, pack_name: str) -> None:
    fm_meta = meta.read_sidecar(target)  # 包内自带的 sidecar
    merged = {
        "origin": entry.get("origin") or fm_meta.get("origin") or "local-forged",
        "source": entry.get("source"),
        "license": entry.get("license"),
        "upstream_ref": entry.get("upstream_ref"),
        "invocation": fm_meta.get("invocation") or "model",
        "generation": int(fm_meta.get("generation") or entry.get("generation") or 1),
        "changelog": fm_meta.get("changelog") or [{
            "gen": 1, "date": today(), "change": f"随包 {pack_name} 导入"}],
        "base_sha256": entry.get("sha256"),
        "last_seen_sha256": entry.get("sha256"),
        "imported_from": pack_name,
        "imported_at": now_iso(),
        # 场景轴（DDR-5）：包内 sidecar 与 MANIFEST 声明取并集去重。
        # 词表外标签原样保留（对方词表不同），doctor 会警告提示人工收编。
        "categories": sorted(set(fm_meta.get("categories") or [])
                             | set(entry.get("categories") or [])),
    }
    meta.write_sidecar(target, merged)


def _sidecar_after_update(meta_dict: dict, entry: dict, pack_name: str) -> None:
    """快进/合并后更新本地 sidecar（就地修改传入 dict）。"""
    for k in ("source", "license", "upstream_ref"):
        if not meta_dict.get(k) and entry.get(k):
            meta_dict[k] = entry[k]
    if not meta_dict.get("origin"):
        meta_dict["origin"] = entry.get("origin") or "local-forged"
    # 场景轴合并（DDR-5）：本地标签 ∪ 对方标签，去重保序
    merged_cats = sorted(set(meta_dict.get("categories") or [])
                         | set(entry.get("categories") or []))
    if merged_cats:
        meta_dict["categories"] = merged_cats
    meta_dict["generation"] = int(meta_dict.get("generation") or 0) + 1
    log = list(meta_dict.get("changelog") or [])
    log.append({"gen": meta_dict["generation"], "date": today(),
                "change": f"导入更新自 {pack_name}（版本 {str(entry.get('sha256'))[:8]}）"})
    meta_dict["changelog"] = log
    meta_dict["last_seen_sha256"] = entry.get("sha256")
    meta_dict["imported_from"] = pack_name
    meta_dict["imported_at"] = now_iso()


def _merge_dirs(base_dir: Path, ours_dir: Path, theirs_dir: Path) -> tuple:
    """逐文件三方合并。返回 ("clean"|"conflict", {rel: (status, content)})。"""
    from . import merge3
    rels = set()
    for d in (base_dir, ours_dir, theirs_dir):
        if d and d.is_dir():
            # 必须是相对路径：merge_files 用 d / rel 寻址，绝对路径会穿透到同一文件
            rels.update(p.relative_to(d).as_posix() for p in d.rglob("*") if p.is_file())
    result = {}
    conflict_files = []
    for rel in sorted(rels):
        status, content = merge3.merge_files(base_dir, ours_dir, theirs_dir, rel)
        if status in ("conflict", "binary_conflict"):
            conflict_files.append(rel)
        result[rel] = (status, content)
    if conflict_files:
        return "conflict", {"conflicts": conflict_files, "files": result}
    return "clean", {"conflicts": [], "files": result}


def _apply_merged(target: Path, merged: dict) -> None:
    for rel, (status, content) in merged["files"].items():
        p = target / rel
        if status == "theirs" and content is not None:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(content)
        elif status == "merged" and content is not None:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
        # same / ours → 保持本地不动


def _stage_incoming(sid: str, src_dir: Path, note: str) -> None:
    dst = paths.INCOMING_DIR / sid
    if dst.exists():
        shutil.rmtree(dst, ignore_errors=True)
    copy_tree(src_dir, dst)
    (dst / "NOTE.md").write_text(
        f"# 导入暂存\n\n{note}\n\n来源：framework import\n时间：{now_iso()}\n"
        f"本地版本未被覆盖。人工裁决后手动合并或删除本目录。\n", encoding="utf-8")


def _resolve_pack(src: str) -> tuple:
    p = Path(src).expanduser()
    if not p.is_absolute():
        p = Path.cwd() / p
    if p.is_file() and zipfile.is_zipfile(p):
        dest = paths.INCOMING_DIR / f"_unpack-{today()}-{p.stem}"
        if dest.exists():
            shutil.rmtree(dest, ignore_errors=True)
        with zipfile.ZipFile(p) as zf:
            zf.extractall(dest)
        # MANIFEST 可能在解压根或下一级
        if (dest / "MANIFEST.json").exists():
            return dest, dest
        for child in sorted(dest.iterdir()):
            if child.is_dir() and (child / "MANIFEST.json").exists():
                return child, dest
        raise SystemExit(f"ERROR: zip 里找不到 MANIFEST.json: {p}")
    if p.is_dir() and (p / "MANIFEST.json").exists():
        return p, None
    raise SystemExit(f"ERROR: 找不到技能包: {p}（需要含 MANIFEST.json 的目录或 zip）")


# ---------- evolution.json 辅助（exchange 自带最小读写，避免循环导入） ----------

def _load_evo() -> dict:
    evo = read_json(paths.EVOLUTION_FILE, None)
    if not isinstance(evo, dict):
        evo = paths.empty_evolution()
        evo["created"] = now_iso()
    return evo


def _save_evo(evo: dict) -> None:
    write_json_atomic(paths.EVOLUTION_FILE, evo)


def _bump_counter(key: str) -> None:
    try:
        evo = _load_evo()
        evo["counters"][key] = evo["counters"].get(key, 0) + 1
        _save_evo(evo)
    except OSError:
        pass


def _merge_pending(evo: dict, pending: list) -> None:
    pend = {(p.get("kind"), p.get("skill_id")): p for p in (evo.get("pending") or [])}
    for p in pending:
        pend[(p.get("kind"), p.get("skill_id"))] = dict(p, since=now_iso())
    evo["pending"] = sorted(pend.values(), key=lambda p: (p.get("kind") or "", p.get("skill_id") or ""))
