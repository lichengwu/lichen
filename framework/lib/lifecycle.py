"""framework/lib/lifecycle.py — 技能生命周期：试用期、信任门、归档复活。

借鉴 AutoHarness（probation + 容量竞争归档）与 SkillMaxxing（trusted 门）。
所有状态都记在 sidecar（.skill-meta.json）里，git 可追踪：
  probation_until   ISO 日期；到期时 loads < probation_min_uses → 挂人工
  mature            试用期达标转正（默认 false；人工锻造的技能直接 true）
  trust             false = 自动产物，不被 export/import 之外自动依赖；
                    loads >= trust_min_loads 或人工 confirm 后转正
归档 = 移入 skills/.archive/<bucket>/<id>（可复活，永不删除）。
"""

from __future__ import annotations

import shutil
from datetime import datetime, timedelta
from pathlib import Path

from . import meta, paths
from .util import copy_tree, dir_hash, now_iso, today, write_json_atomic

ARCHIVE_BUCKET = ".archive"


def _today() -> datetime:
    return datetime.now()


def _parse_date(s: str):
    try:
        return datetime.fromisoformat(str(s)[:10])
    except (ValueError, TypeError):
        return None


# ---------- 试用期 ----------

def start_probation(meta_dict: dict, days: int) -> dict:
    """自动产物的 sidecar 字段初始化（不落盘，返回新 dict）。"""
    m = dict(meta_dict)
    m["probation_until"] = (_today() + timedelta(days=days)).date().isoformat()
    m["mature"] = False
    m["trust"] = False
    return m


def in_probation(meta_dict: dict) -> bool:
    until = _parse_date(meta_dict.get("probation_until") or "")
    if until is None:
        return False
    return _today() <= until


def probation_expired(meta_dict: dict) -> bool:
    """有 probation_until 且已过期（未转正）。"""
    until = _parse_date(meta_dict.get("probation_until") or "")
    if until is None or meta_dict.get("mature"):
        return False
    return _today() > until


def mature_skill(skill: dict, note: str = "") -> str:
    """试用期达标 → mature + trust 转正。返回 changelog 文本。"""
    d = skill["dir"]
    m = dict(skill.get("meta") or {})
    m.pop("probation_until", None)
    m["mature"] = True
    m["trust"] = True
    change = note or "试用期达标：mature + trust 转正"
    m = meta.append_changelog(m, change, bump=False)
    m["base_sha256"] = dir_hash(d)
    meta.write_sidecar(d, m)
    skill["meta"] = m
    return change


# ---------- 信任门 ----------

def should_trust(meta_dict: dict, loads: int, min_loads: int) -> bool:
    """trust=false 且 loads 达标 → 可自动转正。"""
    if meta_dict.get("trust", True):
        return False
    return loads >= max(1, int(min_loads))


def confirm_trust(skill: dict, on: bool = True, auto: bool = False) -> str:
    """人工 confirm/revoke trust（或 loads 达标自动转正）。返回说明文本。"""
    d = skill["dir"]
    m = dict(skill.get("meta") or {})
    m["trust"] = bool(on)
    who = "自动" if auto else "人工"
    m = meta.append_changelog(
        m, f"{who}{'确认' if on else '撤销'}信任（trust={on}）", bump=False)
    m["base_sha256"] = dir_hash(d)
    meta.write_sidecar(d, m)
    skill["meta"] = m
    return f"{skill['id']} trust={on}"


# ---------- 归档 / 复活（容量竞争） ----------

def archive_dir(skill: dict) -> Path:
    return paths.SKILLS_ROOT / ARCHIVE_BUCKET / skill["bucket"] / skill["id"]


def archive_skill(skill: dict, reason: str = "") -> str:
    """移入 skills/.archive/<bucket>/<id>。永不删除，可 unarchive 复活。"""
    d = skill["dir"]
    dest = archive_dir(skill)
    if dest.exists():
        raise SystemExit(f"ERROR: 归档目标已存在: {dest}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    meta.snapshot(d)  # 归档前留快照（撤销依据）
    shutil.move(str(d), str(dest))
    m = meta.read_sidecar(dest)
    m = meta.append_changelog(m, f"归档：{reason or '容量竞争/人工归档'}", bump=False)
    m["archived_at"] = now_iso()
    meta.write_sidecar(dest, m)
    return str(dest)


def unarchive_skill(skill_id: str) -> str:
    """从 .archive/ 复活回原桶。"""
    aroot = paths.SKILLS_ROOT / ARCHIVE_BUCKET
    if not aroot.is_dir():
        raise SystemExit("ERROR: 没有归档区（skills/.archive/ 不存在）")
    for bucket_dir in sorted(aroot.iterdir()):
        src = bucket_dir / skill_id
        if src.is_dir() and (src / "SKILL.md").is_file():
            dest = paths.SKILLS_ROOT / bucket_dir.name / skill_id
            if dest.exists():
                raise SystemExit(f"ERROR: 目标已存在: {dest}")
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dest))
            m = meta.read_sidecar(dest)
            m = meta.append_changelog(m, "从归档区复活", bump=False)
            m.pop("archived_at", None)
            m["base_sha256"] = dir_hash(dest)
            meta.write_sidecar(dest, m)
            # 归档桶空了就清理（不留空目录，check.sh 会查空目录）；失败不影响复活
            try:
                try:
                    next(bucket_dir.iterdir())
                except StopIteration:
                    bucket_dir.rmdir()
                    try:
                        next(aroot.iterdir())
                    except StopIteration:
                        aroot.rmdir()
            except OSError:
                pass
            return str(dest)
    raise SystemExit(f"ERROR: 归档区找不到 {skill_id}（lichen status 查看列表）")


def list_archived() -> list:
    aroot = paths.SKILLS_ROOT / ARCHIVE_BUCKET
    if not aroot.is_dir():
        return []
    out = []
    for bucket_dir in sorted(aroot.iterdir()):
        for skill_dir in sorted(bucket_dir.iterdir()):
            if (skill_dir / "SKILL.md").is_file():
                out.append({"id": skill_dir.name, "bucket": bucket_dir.name,
                            "dir": skill_dir, "meta": meta.read_sidecar(skill_dir)})
    return out


def archived_count() -> int:
    return len(list_archived())
