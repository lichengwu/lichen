"""framework/lib/evaluate.py — 相邻两代对比评估与回滚（unisone 的 evaluate/rollback）。

没有 benchmark 时的"够用且可解释"指标（全部本地可算）：
  files     文件数（结构丰满度）
  refs      references/ 引用文件数（海拔纪律执行度）
  lines     正文非空行数（过高 = 该拆）
  desc_len  description 长度（过短 = 触发信息不足）
  hygiene   硬红线命中数（0 为干净）
判定（相邻两代快照对比，逐项看方向）：
  任一改善且无恶化 → IMPROVED
  全部相同         → NO CHANGE
  任一恶化         → DEGRADED
rollback 先从快照恢复，再给恢复后的版本留 changelog——撤销本身也是一次进化。
"""

from __future__ import annotations

import shutil
from pathlib import Path

from . import meta, paths, scan
from .redact import scan_tree
from .util import copy_tree, dir_hash, read_frontmatter_file, today

# 指标方向：True = 越大越好
BETTER_IF_HIGHER = {"files": True, "refs": True, "desc_len": True}
# lines：适中最好，用区间判断（超过上限视为恶化）
LINES_GOOD_MAX = 25


def metrics(skill_dir: Path) -> dict:
    d = Path(skill_dir)
    if not (d / "SKILL.md").is_file():
        return {}
    files = sum(1 for p in d.rglob("*") if p.is_file() and p.name != ".skill-meta.json")
    refs_dir = d / "references"
    refs = sum(1 for p in refs_dir.rglob("*") if p.is_file()) if refs_dir.is_dir() else 0
    try:
        text = (d / "SKILL.md").read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        text = ""
    body = text.split("---", 2)[2] if text.startswith("---") else text
    lines = sum(1 for ln in body.splitlines() if ln.strip())
    fm = read_frontmatter_file(d / "SKILL.md")
    desc = str(fm.get("description") or "")
    return {
        "files": files,
        "refs": refs,
        "lines": lines,
        "desc_len": len(desc),
        "hygiene": len(scan_tree(d, max_hits=10)),
    }


def _direction(key: str, prev, cur) -> str:
    """'better' | 'worse' | 'same'"""
    if prev == cur:
        return "same"
    if key == "hygiene":
        return "better" if cur < prev else "worse"
    if key == "lines":
        if cur <= LINES_GOOD_MAX and prev > LINES_GOOD_MAX:
            return "better"
        if cur > LINES_GOOD_MAX and prev <= LINES_GOOD_MAX:
            return "worse"
        return "same"
    higher_better = BETTER_IF_HIGHER.get(key, True)
    if higher_better:
        return "better" if cur > prev else "worse"
    return "better" if cur < prev else "worse"


def compare(prev: dict, cur: dict) -> tuple:
    """返回 (verdict, reasons)。verdict ∈ IMPROVED / NO CHANGE / DEGRADED。"""
    reasons = []
    has_better = has_worse = False
    for k in sorted(set(prev) | set(cur)):
        a, b = prev.get(k), cur.get(k)
        if a is None or b is None:
            continue
        d = _direction(k, a, b)
        if d == "better":
            has_better = True
            reasons.append(f"{k} {a}→{b} ↑")
        elif d == "worse":
            has_worse = True
            reasons.append(f"{k} {a}→{b} ↓")
    if has_worse:
        return "DEGRADED", reasons
    if has_better:
        return "IMPROVED", reasons
    return "NO CHANGE", []


def evaluate_skill(skill_id: str, index: dict | None = None) -> dict:
    """对比该技能相邻两代（versions/ 里最后两个快照）。

    只有一个快照时退化为「当前 vs 该快照」（当代可能尚未入快照库的场景）。
    """
    index = index if index is not None else meta.index_by_id(meta.list_repo_skills())
    skill = index.get(skill_id)
    if not skill:
        raise SystemExit(f"ERROR: 技能不存在: {skill_id}")
    versions = meta.list_versions(skill_id)  # 时间正序
    cur = metrics(skill["dir"])
    if len(versions) >= 2:
        prev_dir = paths.VERSIONS_DIR / skill_id / versions[-2]
        cur_dir = paths.VERSIONS_DIR / skill_id / versions[-1]
        prev, cur_m = metrics(prev_dir), metrics(cur_dir)
        basis = f"{versions[-2]} → {versions[-1]}"
    elif len(versions) == 1:
        prev_dir = paths.VERSIONS_DIR / skill_id / versions[-1]
        prev, cur_m = metrics(prev_dir), cur
        basis = f"当前 vs 最近快照 {versions[-1]}"
    else:
        prev, cur_m, basis = {}, cur, "无历史快照（先跑一次 framework evolve）"
    if not prev:
        return {"skill": skill_id, "verdict": "NO CHANGE", "basis": basis,
                "reasons": [], "prev": {}, "cur": cur_m}
    verdict, reasons = compare(prev, cur_m)
    return {"skill": skill_id, "verdict": verdict, "basis": basis,
            "reasons": reasons, "prev": prev, "cur": cur_m}


def rollback_skill(skill_id: str, to_sha8: str = "", index: dict | None = None) -> str:
    """从版本快照恢复。先快照当前（留撤销依据），再原子恢复，最后留痕。"""
    index = index if index is not None else meta.index_by_id(meta.list_repo_skills())
    skill = index.get(skill_id)
    if not skill:
        raise SystemExit(f"ERROR: 技能不存在: {skill_id}")
    if to_sha8:
        src = meta.find_version(skill_id, to_sha8)
        if src is None:
            raise SystemExit(f"ERROR: 找不到快照 {to_sha8}（framework status 查看版本列表）")
    else:
        versions = meta.list_versions(skill_id)
        if not versions:
            raise SystemExit(f"ERROR: {skill_id} 没有历史快照可回滚")
        src = paths.VERSIONS_DIR / skill_id / versions[-1]
    d = skill["dir"]
    meta.snapshot(d, tag="pre-rollback")  # 当前版本先入快照库（可再回滚）
    tmp = d.with_name(d.name + ".rollback-tmp")
    if tmp.exists():
        shutil.rmtree(tmp, ignore_errors=True)
    copy_tree(src, tmp)
    # 恢复后保留 changelog：读回退版 sidecar，追加回滚记录
    m = meta.read_sidecar(tmp)
    m = meta.append_changelog(m, f"回滚到快照 {src.name}", bump=False)
    m["base_sha256"] = dir_hash(tmp)
    meta.write_sidecar(tmp, m)
    # 原子替换：先挪旧的到 .prev，再 rename，失败可还原
    prev_dir = d.with_name(d.name + ".prev")
    if prev_dir.exists():
        shutil.rmtree(prev_dir, ignore_errors=True)
    d.rename(prev_dir)
    try:
        tmp.rename(d)
    except OSError:
        prev_dir.rename(d)  # 还原
        shutil.rmtree(tmp, ignore_errors=True)
        raise SystemExit(f"ERROR: 回滚失败，已还原: {skill_id}")
    shutil.rmtree(prev_dir, ignore_errors=True)
    return f"{skill_id} 已回滚到 {src.name}"
