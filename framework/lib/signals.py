"""framework/lib/signals.py — 信号层：追加写入 state/signals.jsonl。

隐私铁律：intent 信号只存 sha256(prompt) 与 coarse 词元，prompt 原文永不落盘。
"""

from __future__ import annotations

from pathlib import Path

from . import paths
from .util import append_jsonl, now_iso, read_jsonl


def record(kind: str, **fields) -> None:
    """记录一条信号。任何异常都不允许穿透（hooks 纪律：永远 exit 0）。"""
    try:
        paths.ensure_state()
        append_jsonl(paths.SIGNALS_FILE, {"ts": now_iso(), "kind": kind, **fields})
    except OSError:
        pass


def read_all(limit: int = 0) -> list:
    return read_jsonl(paths.SIGNALS_FILE, limit=limit or None)


def prune_if_big() -> bool:
    """signals.jsonl 超限时截断。返回是否截断过。"""
    p = paths.SIGNALS_FILE
    if not p.exists():
        return False
    try:
        lines = p.read_text(encoding="utf-8").splitlines()
    except OSError:
        return False
    if len(lines) <= paths.SIGNALS_MAX_LINES:
        return False
    keep = lines[-paths.SIGNALS_KEEP_LINES:]
    with open(p, "w", encoding="utf-8") as f:
        f.write("\n".join(keep) + "\n")
    return True


def count_by_kind(signals: list) -> dict:
    out = {}
    for s in signals:
        out[s.get("kind", "?")] = out.get(s.get("kind", "?"), 0) + 1
    return out
