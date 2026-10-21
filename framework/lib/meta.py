"""framework/lib/meta.py — 技能索引、sidecar（.skill-meta.json）与版本快照。

sidecar 是进化账本：origin 三态 + generation + changelog（schema 见
skills/agent/skill-forge/references/provenance.md）。框架新增两个可选字段：
  base_sha256     收编/导入/导出时登记的本版本目录哈希（导入三方合并的 base 线索）
  source_sha256   收编时源 SKILL.md 的哈希（检测收编源漂移）
资产三轴（PRD v2 DDR-1/2/3）+ 场景轴（DDR-5）：
  kind / visibility / execution / categories（多标签，受控词表见 taxonomy.py）
旧 sidecar 不含这些字段，所有操作保持向后兼容（缺省即默认值）。
"""

from __future__ import annotations

import shutil
from pathlib import Path

from . import paths
from .util import copy_tree, dir_hash, now_iso, read_json, sha256_file, today, write_json_atomic

SIDECAR = ".skill-meta.json"
VALID_ORIGINS = {"local-forged", "upstream", "adopted"}

# 每个技能保留的版本快照数（导入三方合并的 base 来源，按时间倒序保留）
SNAPSHOT_KEEP = 5


# ---------- sidecar 读写 ----------

def read_sidecar(skill_dir: Path) -> dict:
    return read_json(Path(skill_dir) / SIDECAR, {}) or {}


def write_sidecar(skill_dir: Path, meta: dict) -> None:
    write_json_atomic(Path(skill_dir) / SIDECAR, meta)


def append_changelog(meta: dict, change: str, bump: bool = True) -> dict:
    """追加一条 changelog；bump=True 时 generation++。返回新 meta（不落盘）。"""
    meta = dict(meta)
    if bump:
        meta["generation"] = int(meta.get("generation") or 0) + 1
    log = list(meta.get("changelog") or [])
    log.append({"gen": meta.get("generation", 1), "date": today(), "change": change})
    meta["changelog"] = log
    return meta


# ---------- 仓库技能索引 ----------

def list_repo_skills() -> list:
    """扫描 skills/<bucket>/<id>/，返回 [{bucket,id,dir,meta,fm}]。

    .archive/（墓地）不计入现役；.private/ 相反——它是治理中的私有桶
    （个人向/手动执行技能：纳入管理，永不公开），计入现役。
    """
    out = []
    root = paths.SKILLS_ROOT
    if not root.is_dir():
        return out
    for bucket_dir in sorted(root.iterdir()):
        if not bucket_dir.is_dir() or bucket_dir.name.startswith("."):
            continue
        for skill_dir in sorted(bucket_dir.iterdir()):
            skill_md = skill_dir / "SKILL.md"
            if not skill_md.is_file():
                continue
            out.append({
                "bucket": bucket_dir.name,
                "id": skill_dir.name,
                "dir": skill_dir,
                "meta": read_sidecar(skill_dir),
                "fm": _read_fm(skill_md),
            })
    priv = root / paths.PRIVATE_BUCKET
    if priv.is_dir():
        for skill_dir in sorted(priv.iterdir()):
            skill_md = skill_dir / "SKILL.md"
            if not skill_md.is_file():
                continue
            out.append({
                "bucket": paths.PRIVATE_BUCKET,
                "id": skill_dir.name,
                "dir": skill_dir,
                "meta": read_sidecar(skill_dir),
                "fm": _read_fm(skill_md),
            })
    return out


def _read_fm(skill_md: Path) -> dict:
    from .util import read_frontmatter_file
    return read_frontmatter_file(skill_md)


def index_by_id(skills: list) -> dict:
    return {s["id"]: s for s in skills}


def invocation_of(skill: dict) -> str:
    """从 frontmatter 推断调用模式：disable-model-invocation: true → user，否则 model。"""
    fm = skill.get("fm") or {}
    if str(fm.get("disable-model-invocation", "")).lower() == "true":
        return "user"
    return "model"


def categories_of(skill: dict) -> list:
    """场景轴标签（sidecar.categories，多标签；缺省 []）。

    场景轴与 bucket 治理轴正交（PRD v2.1 DDR-5）：bucket 回答"从哪来、
    走哪条治理路径"，category 回答"用户想干什么时该想到它"。
    """
    m = skill.get("meta") or {}
    return [str(c) for c in (m.get("categories") or [])]


# ---------- 版本快照（导入合并的 base 来源） ----------

def _version_dir(skill_id: str, sha8: str) -> Path:
    return paths.VERSIONS_DIR / skill_id / sha8


def snapshot(skill_dir: Path, tag: str = "") -> str:
    """把技能当前版本快照进 state/versions/<id>/<时间>-<sha8>/，返回 sha8。

    目录名带时间前缀，可按名排序做保留策略。已是同一内容（sha8 相同）则不重复快照。
    """
    skill_dir = Path(skill_dir)
    h = dir_hash(skill_dir)
    sha8 = h[:8]
    vroot = paths.VERSIONS_DIR / skill_dir.name
    vroot.mkdir(parents=True, exist_ok=True)
    for existing in vroot.iterdir():
        if existing.name.endswith("-" + sha8):
            return sha8  # 同一版本已快照过
    stamp = now_iso().replace(":", "").replace("-", "").replace("+", "")[:15]
    dest = vroot / f"{stamp}-{sha8}"
    tmp = dest.with_name(dest.name + ".partial")
    if tmp.exists():
        shutil.rmtree(tmp, ignore_errors=True)
    copy_tree(skill_dir, tmp)
    tmp.rename(dest)
    _prune_versions(vroot)
    return sha8


def _prune_versions(vroot: Path, keep: int = SNAPSHOT_KEEP) -> None:
    versions = sorted(d for d in vroot.iterdir() if d.is_dir() and not d.name.endswith(".partial"))
    for old in versions[:-keep]:
        shutil.rmtree(old, ignore_errors=True)


def find_version(skill_id: str, sha8: str) -> Path | None:
    """按 sha8 找快照目录；找不到返回 None。"""
    if not sha8:
        return None
    vroot = paths.VERSIONS_DIR / skill_id
    if not vroot.is_dir():
        return None
    for d in sorted(vroot.iterdir()):
        if d.name.endswith("-" + sha8):
            return d
    return None


def list_versions(skill_id: str) -> list:
    vroot = paths.VERSIONS_DIR / skill_id
    if not vroot.is_dir():
        return []
    return sorted(d.name for d in vroot.iterdir() if d.is_dir())


# ---------- 登记（T0 自动写） ----------

def ensure_sidecar(skill: dict, note: str = "") -> bool:
    """缺 sidecar 的技能补一张最小登记卡。返回是否新建。"""
    d = skill["dir"]
    if (d / SIDECAR).exists():
        return False
    meta = {
        "origin": "local-forged",
        "source": None,
        "license": None,
        "invocation": invocation_of(skill),
        "generation": 1,
        "changelog": [{
            "gen": 1,
            "date": today(),
            "change": note or "自动登记：此前缺失 sidecar。如技能来自外部仓库，请人工改为 upstream 并补 source/upstream_ref",
        }],
        "base_sha256": dir_hash(d),
        # 场景轴占位：evolve 的卫生预跑随后自动打标（taxonomy.classify）
        "categories": [],
    }
    write_sidecar(d, meta)
    skill["meta"] = meta
    return True


def fix_invocation_field(skill: dict) -> bool:
    """sidecar.invocation 与 frontmatter 实际不一致时修正（确定性修复）。"""
    d = skill["dir"]
    meta = skill.get("meta") or {}
    if not meta:
        return False
    actual = invocation_of(skill)
    if meta.get("invocation") == actual:
        return False
    meta = dict(meta)
    meta["invocation"] = actual
    meta = append_changelog(meta, f"自动修补：invocation {meta.get('invocation')} → {actual}（对齐 frontmatter）", bump=False)
    write_sidecar(d, meta)
    skill["meta"] = meta
    return True


def bump_generation(skill: dict, change: str) -> int:
    """generation++ 并留痕。返回新代数。"""
    d = skill["dir"]
    meta = dict(skill.get("meta") or {})
    snapshot(d)  # 留旧版本快照（导入合并的 base）
    meta = append_changelog(meta, change, bump=True)
    meta["base_sha256"] = dir_hash(d)
    write_sidecar(d, meta)
    skill["meta"] = meta
    return int(meta.get("generation") or 1)


def sha256_skill_md(skill_dir: Path) -> str:
    return sha256_file(Path(skill_dir) / "SKILL.md")
