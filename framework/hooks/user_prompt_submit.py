#!/usr/bin/env python3
"""framework/hooks/user_prompt_submit.py — UserPromptSubmit 钩子。

只记录意图信号（重复意图是 scaffold 候选的原料），**永不输出、永不注入**。

隐私铁律：只存 sha256(prompt) 与 coarse 词元（ASCII 词 + CJK 二元组），
prompt 原文永不落盘。同一会话内连续重复的哈希去重，避免信号文件膨胀。
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # framework/

from lib import paths, scan, signals  # noqa: E402


def main() -> int:
    try:
        try:
            payload = json.load(sys.stdin)
        except (json.JSONDecodeError, OSError):
            return 0
        prompt = payload.get("prompt") or payload.get("user_prompt") or ""
        if not prompt or not prompt.strip():
            return 0
        toks = scan.intent_tokens(prompt)
        if not toks:
            return 0
        recent = signals.read_all(limit=20)
        h = None
        import hashlib
        h = hashlib.sha256(prompt.strip().encode("utf-8")).hexdigest()
        for s in recent:
            if s.get("kind") == "intent" and s.get("hash") == h:
                return 0  # 近期已记录过同一意图
        signals.record("intent", hash=h, tokens=toks,
                       session=payload.get("session_id", ""))
    except Exception:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
