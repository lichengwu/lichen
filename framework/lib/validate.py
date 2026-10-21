"""framework/lib/validate.py — propose→validate→land 三段式的 validate 段（AutoHarness promoter）。

任何 T0 落盘（scaffold / adopt / promote / import 安装）之前必须过检。
过了才原子落盘；不过 → 转 T1 挂人工，**不许猜**。

检查分级：
  BLOCK   硬性问题——缺失 frontmatter 关键字段、硬红线命中、正文为空。
          不过检 = 不落盘（scaffold/adopt 一律转候选区暂存）。
  WARN    海拔纪律（正文 ≤ max_body_lines 非空行）、name 与目录名不一致。
          strict=True（scaffold/promote 的自产产物）时升级为 BLOCK；
          adopt 既有本地技能时不阻塞，只提示人工拆分 references。
"""

from __future__ import annotations

from pathlib import Path

from . import scan
from .redact import scan_tree
from .util import read_frontmatter_file

DEFAULT_MAX_BODY_LINES = 25  # 海拔纪律：SKILL.md 正文 ≤25 非空行，细节进 references/


def _body_lines(text: str) -> int:
    """frontmatter 之后的非空行数。"""
    body = text
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) == 3:
            body = parts[2]
    return sum(1 for ln in body.splitlines() if ln.strip())


def validate_skill_dir(skill_dir: Path, strict: bool = False,
                       max_body_lines: int = DEFAULT_MAX_BODY_LINES) -> list:
    """校验一个技能目录。返回问题列表（空 = 过检）。

    strict=True 用于框架自产产物（scaffold/promote）：海拔与命名不一致也阻塞。
    """
    d = Path(skill_dir)
    problems = []
    skill_md = d / "SKILL.md"
    if not skill_md.is_file():
        return [f"缺少 SKILL.md: {d}"]
    try:
        text = skill_md.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        return [f"SKILL.md 不可读: {e}"]
    if not text.strip():
        return ["SKILL.md 为空"]

    fm = read_frontmatter_file(skill_md)
    if not fm.get("name"):
        problems.append("frontmatter 缺少 name")
    if not fm.get("description"):
        problems.append("frontmatter 缺少 description")
    if fm.get("name") and fm.get("name") != d.name:
        msg = f"frontmatter name={fm.get('name')} 与目录名 {d.name} 不一致"
        problems.append(msg if strict else f"[提示] {msg}")

    hits = scan_tree(d, max_hits=5)
    if hits:
        problems.append("硬红线命中: " + "; ".join(hits[:3]))

    n = _body_lines(text)
    if n > max_body_lines:
        msg = (f"正文 {n} 个非空行 > {max_body_lines}（海拔纪律：细节移入 references/）")
        problems.append(msg if strict else f"[提示] {msg}")

    # 自产限定：脚手架必须带触发措辞（双读者规则，见 _do_scaffold 前置教训）
    if strict:
        desc = str(fm.get("description") or "")
        if desc and not scan.has_trigger_markers(desc):
            problems.append("description 缺触发措辞（双读者规则）")

    return problems


def blocking(problems: list) -> list:
    """只取 BLOCK 级问题（[提示] 前缀的是 WARN）。"""
    return [p for p in problems if not p.startswith("[提示]")]
