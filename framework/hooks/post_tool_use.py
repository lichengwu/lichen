#!/usr/bin/env python3
"""framework/hooks/post_tool_use.py — PostToolUse 钩子（匹配 Skill|Read|Write|Edit|MultiEdit|NotebookEdit）。

只记录三类信号，**永不输出**（AutoHarness MNG 三态计数）：
  skill_use/subtype=load   Skill 工具调用 → 真实加载（速率分子的核心）
  skill_use/subtype=view   Read 落在技能目录 → 查看（人/模型在翻这个技能）
  skill_write/subtype=patch 写入/编辑技能目录 → 编辑爆发的原料

速率 = loads / 期间请求数（UserPromptSubmit 计一条 intent），进 status 速率表。

性能纪律：非目标工具第一行就退出；整个脚本预算 <0.5s。
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # framework/

from lib import paths, scan, signals  # noqa: E402

WATCHED = {"Skill", "Read", "Write", "Edit", "MultiEdit", "NotebookEdit"}


def main() -> int:
    try:
        try:
            payload = json.load(sys.stdin)
        except (json.JSONDecodeError, OSError):
            return 0
        tool = payload.get("tool_name", "")
        if tool not in WATCHED:
            return 0
        tool_input = payload.get("tool_input") or {}

        if tool == "Skill":
            sid = (tool_input.get("skill") or tool_input.get("skill_id")
                   or tool_input.get("command") or tool_input.get("name") or "")
            if sid:
                signals.record("skill_use", skill_id=str(sid), subtype="load")
            return 0

        path_str = (tool_input.get("file_path") or tool_input.get("notebook_path")
                    or tool_input.get("path") or "")
        if not path_str:
            return 0
        roots = paths.resolve_scan_dirs(paths.load_config(), payload.get("cwd") or ".")
        roots.append(paths.SKILLS_ROOT)
        skill_dir, _root = scan.owning_skill_dir(Path(path_str), roots)
        if skill_dir is None:
            return 0
        if tool == "Read":
            signals.record("skill_use", skill_id=skill_dir.name, subtype="view")
        else:
            signals.record("skill_write", skill_id=skill_dir.name,
                           subtype="patch", tool=tool)
    except Exception:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
