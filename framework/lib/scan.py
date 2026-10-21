"""framework/lib/scan.py — 本地技能发现与启发式判断。

包含：
  find_local_skills   扫描 scan_dirs，发现仓库之外的本地技能（收编候选）
  owning_skill_dir    从文件路径向上找所属技能目录（PostToolUse 用）
  intent_tokens       prompt → coarse 词元（隐私：不存原文）
  cluster_intents     按词元重合度聚类重复意图（scaffold 候选的依据）
  has_trigger_markers description 是否含触发措辞（双读者规则）
  covered_by          某组词元是否已被现有技能覆盖
所有启发式都是"够用且可解释"的粗规则：假阳性代价是一个待人工看的候选，假阴性只是没有自动建议。
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import paths
from .util import read_frontmatter_file

# description 触发措辞标记（面向模型的触发语，见 .agents/invocation.md 双读者规则）
TRIGGER_MARKERS = ("当", "提到", "触发", "使用", "用于", "use when", "when the user", "trigger")

EN_STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "from", "have", "has", "are",
    "you", "your", "not", "but", "all", "can", "will", "just", "please", "help",
    "want", "need", "how", "what", "when", "where", "which", "about", "into",
    "using", "make", "made", "some", "then", "than", "them", "they", "there",
    "here", "also", "very", "more", "most", "such", "only", "over", "under",
}


def find_local_skills(scan_roots: list) -> list:
    """扫描目录下的技能（一级子目录含 SKILL.md）。返回 [{id,path,fm,skill_md}]。"""
    out = []
    seen = set()
    for root in scan_roots:
        root = Path(root)
        if not root.is_dir():
            continue
        for child in sorted(root.iterdir()):
            if child.is_symlink():
                continue  # 物化视图（hub 的技能级链接等）不是收编源——评审 F1-3
            skill_md = child / "SKILL.md"
            if not child.is_dir() or not skill_md.is_file():
                continue
            if child.name in seen:
                continue
            seen.add(child.name)
            out.append({
                "id": child.name,
                "path": child,
                "fm": read_frontmatter_file(skill_md),
                "skill_md": skill_md,
            })
    return out


def owning_skill_dir(file_path: Path, roots: list, max_up: int = 6):
    """从文件路径向上找包含 SKILL.md 的目录。返回 (skill_dir, root) 或 (None, None)。"""
    p = Path(file_path).resolve()
    roots = [Path(r).resolve() for r in roots]
    cur = p.parent if p.is_file() or not p.exists() else p
    for _ in range(max_up):
        if (cur / "SKILL.md").is_file():
            for r in roots:
                try:
                    cur.relative_to(r)
                    return cur, r
                except ValueError:
                    continue
            return cur, None  # 在技能目录里但不在任何扫描根下（仍是技能写入）
        if cur.parent == cur:
            break
        cur = cur.parent
    return None, None


def _ascii_words(tokens: list) -> set:
    return {t for t in tokens if re.fullmatch(r"[a-z0-9][a-z0-9_.-]{2,}", t)}


def _cjk_bigrams(tokens: list) -> set:
    return {t for t in tokens if re.fullmatch(r"[\u4e00-\u9fff]{2}", t)}


def intent_tokens(text: str) -> list:
    """prompt → coarse 词元：ASCII 词（≥4 字符、去停用词）+ CJK 二元组。

    只取特征，不取内容——聚类只需要可比较的形状。
    """
    text = (text or "").lower()
    words = [w for w in re.findall(r"[a-z][a-z0-9_.-]{3,}", text) if w not in EN_STOPWORDS]
    grams = []
    for run in re.findall(r"[\u4e00-\u9fff]{2,}", text):
        run = run[:40]
        grams.extend(run[i:i + 2] for i in range(len(run) - 1))
    out = []
    for t in words + grams:
        if t not in out:
            out.append(t)
    return out[:24]


def _intents_match(a: list, b: list) -> bool:
    """两条意图算"同一类"的粗规则：≥2 个相同 ASCII 词，或 ≥4 个相同中文二元组。"""
    wa, wb = _ascii_words(a), _ascii_words(b)
    if len(wa & wb) >= 2:
        return True
    ca, cb = _cjk_bigrams(a), _cjk_bigrams(b)
    return len(ca & cb) >= 4


def _parse_ts(ts: str):
    try:
        return datetime.fromisoformat(ts)
    except (ValueError, TypeError):
        return None


def cluster_intents(signals: list, min_count: int, days: int) -> list:
    """把窗口内的 intent 信号聚类，返回 count >= min_count 的簇。"""
    cutoff = datetime.now(timezone.utc).astimezone() - timedelta(days=days)
    recent = []
    for s in signals:
        if s.get("kind") != "intent":
            continue
        ts = _parse_ts(s.get("ts", ""))
        if ts is None or ts < cutoff:
            continue
        recent.append(s)
    clusters = []
    for s in recent:
        toks = s.get("tokens") or []
        for c in clusters:
            if _intents_match(toks, c["rep"]):
                c["count"] += 1
                c["hashes"].add(s.get("hash"))
                c["last"] = max(c["last"], s.get("ts", ""))
                c["rep"] = toks  # 以最新一条为代表
                break
        else:
            clusters.append({
                "rep": toks,
                "count": 1,
                "hashes": {s.get("hash")},
                "first": s.get("ts", ""),
                "last": s.get("ts", ""),
                "sessions": {s.get("session")},
            })
    return [c for c in clusters if c["count"] >= min_count]


def has_trigger_markers(description: str) -> bool:
    d = (description or "").lower()
    return any(m.lower() in d for m in TRIGGER_MARKERS)


def skill_search_tokens(skill: dict) -> list:
    """技能的可检索词元：name + description + SKILL.md 前 2000 字符。"""
    fm = skill.get("fm") or {}
    text = f"{skill.get('id', '')} {fm.get('name', '')} {fm.get('description', '')}"
    try:
        body = (skill["dir"] / "SKILL.md").read_text(encoding="utf-8")[:2000]
        text += " " + body.lower()
    except (OSError, UnicodeDecodeError, KeyError):
        pass
    return intent_tokens(text)


def covered_by(tokens: list, skills: list) -> str | None:
    """返回覆盖这组意图的技能 id（启发式），没有则 None。"""
    for s in skills:
        if _intents_match(tokens, skill_search_tokens(s)):
            return s["id"]
    return None


def repo_roots() -> list:
    return [paths.SKILLS_ROOT]
