"""framework/lib/digest.py — 一行式摘要渲染（无感知原则的出口）。

纪律（ADR 0002 §2.5）：
  - 最多 digest_max_lines 行；没有待办就返回空串——默认状态是沉默
  - 摘要必须自包含（带下一步命令），模型不需要知道基础技能的存在
"""

from __future__ import annotations

from . import paths


def ready_candidates() -> list:
    if not paths.CANDIDATES_DIR.is_dir():
        return []
    return sorted(d.name for d in paths.CANDIDATES_DIR.iterdir()
                  if d.is_dir() and (d / "SKILL.md").exists())


def render(evo: dict, cfg: dict) -> str:
    max_lines = int(cfg.get("digest_max_lines", 3))
    c = evo.get("counters") or {}
    b = evo.get("baseline") or {}
    lines = []

    d_adopt = c.get("adoptions", 0) - b.get("adoptions", 0)
    d_evo = c.get("evolutions", 0) - b.get("evolutions", 0)
    d_cand = c.get("candidates", 0) - b.get("candidates", 0)
    if d_adopt or d_evo or d_cand:
        parts = []
        if d_adopt:
            parts.append(f"收编 {d_adopt}")
        if d_evo:
            parts.append(f"进化 {d_evo}")
        if d_cand:
            parts.append(f"新候选 {d_cand}")
        lines.append("🧬 技能系统自进化：本次 " + " · ".join(parts) + "。查看：framework status")

    pending = evo.get("pending") or []
    if pending:
        p = pending[0]
        hint = p.get("hint") or ""
        suffix = f"（{hint}）" if hint else ""
        more = f" 等 {len(pending)} 项" if len(pending) > 1 else ""
        lines.append(f"⏳ 待人工裁决：{p.get('detail', '')}{more}{suffix}")

    cands = ready_candidates()
    if cands and len(lines) < max_lines:
        shown = ", ".join(cands[:3]) + ("…" if len(cands) > 3 else "")
        lines.append(f"▶ 候选技能待锻造：{shown}（framework promote <名> 晋升）")

    return "\n".join(lines[:max_lines])
