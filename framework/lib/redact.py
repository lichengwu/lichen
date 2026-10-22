"""framework/lib/redact.py — 硬红线扫描（Python 侧）。

与 scripts/redact.sh 的 HARD_PATTERNS 同源：自动收编 / 导出前的安全门。
命中即拒绝自动动作（改为挂人工），没有"确认后放过"。
"""

from __future__ import annotations

import re
from pathlib import Path

from .util import EXCLUDE_NAMES, EXCLUDE_SUFFIX

# 与 scripts/redact.sh 保持一致；顺序无关（都是独立正则）
HARD_PATTERNS = [
    (r"ghp_[A-Za-z0-9]{36,}", "GitHub PAT (ghp_)"),
    (r"gho_[A-Za-z0-9]{36,}", "GitHub OAuth token (gho_)"),
    (r"github_pat_[A-Za-z0-9_]{36,}", "GitHub fine-grained PAT"),
    (r"sk-[A-Za-z0-9]{20,}", "API secret key (sk-)"),
    (r"AKIA[0-9A-Z]{16}", "AWS access key id"),
    (r"BEGIN (RSA|OPENSSH|EC|DSA) PRIVATE KEY", "private key block"),
    (r"xox[baprs]-[A-Za-z0-9-]{10,}", "Slack token"),
    (r"AIza[0-9A-Za-z_-]{35}", "Google API key"),
    (r"(?<![0-9])1[3-9][0-9]{9}(?![0-9])", "手机号段（11 位）"),
    (r"[a-zA-Z0-9._%+-]+@(gmail|qq|163|outlook|foxmail|icloud|msn|hotmail|yahoo|sina|sohu|139|189)\.(com|cn)", "个人邮箱"),
]

_COMPILED = [(re.compile(p), label) for p, label in HARD_PATTERNS]


def _iter_text_files(root: Path):
    for p in sorted(Path(root).rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(root)
        if any(part in EXCLUDE_NAMES for part in rel.parts):
            continue
        if p.suffix in EXCLUDE_SUFFIX:
            continue
        yield p


def scan_tree(root: Path, max_hits: int = 20) -> list:
    """扫描目录树，返回命中描述列表（空 = 干净）。二进制/非 UTF-8 文件跳过。"""
    root = Path(root)
    hits = []
    if not root.is_dir():
        return hits
    for p in _iter_text_files(root):
        try:
            text = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for rx, label in _COMPILED:
            for m in rx.finditer(text):
                line_no = text[: m.start()].count("\n") + 1
                hits.append(f"{p.name}:{line_no}: {label}")
                if len(hits) >= max_hits:
                    return hits
    return hits


def scan_text(text: str, name: str = "<text>") -> list:
    hits = []
    for rx, label in _COMPILED:
        for m in rx.finditer(text):
            line_no = text[: m.start()].count("\n") + 1
            hits.append(f"{name}:{line_no}: {label}")
    return hits
