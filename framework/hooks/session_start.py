#!/usr/bin/env python3
"""framework/hooks/session_start.py — SessionStart / PreCompact 钩子。

职责（ADR 0002 §2.5 静默纪律）：
  1. 确保运行目录存在（幂等）
  2. 扫描本地技能目录，记录 local_seen 信号（发现=收编的原料）
  3. 有摘要才注入（≤3 行，自包含指令）；没有就零输出——默认状态是沉默
  4. 注入后消费摘要（基线对齐），下次 evolve 只报增量

任何异常都静默 exit 0——hooks 永远不许弄坏用户的会话。
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # framework/ → lib 包可导入

from lib import evolve, paths, scan, signals  # noqa: E402


def main() -> int:
    try:
        try:
            payload = json.load(sys.stdin)
        except (json.JSONDecodeError, OSError):
            payload = {}
        cwd = payload.get("cwd") or "."
        paths.ensure_state()

        cfg = paths.load_config()
        for ls in scan.find_local_skills(paths.resolve_scan_dirs(cfg, cwd)):
            signals.record("local_seen", skill_id=ls["id"], path=str(ls["path"]))

        digest = evolve.consume_digest()
        if digest:
            print(json.dumps({
                "continue": True,
                "hookSpecificOutput": {
                    "hookEventName": payload.get("hook_event_name", "SessionStart"),
                    "additionalContext": digest,
                },
            }, ensure_ascii=False))
    except Exception:
        return 0  # 静默失败是纪律，不是疏漏
    return 0


if __name__ == "__main__":
    sys.exit(main())
