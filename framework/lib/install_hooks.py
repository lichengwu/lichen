"""framework/lib/install_hooks.py — 把框架 hooks 注册进各 harness 的 settings.json。

支持的 harness（settings.json 的 hooks 字段，格式同构）：
  claude     ~/.claude/settings.json（user）/ <cwd>/.claude/settings.json（project）
  codebuddy  ~/.codebuddy/settings.json / <cwd>/.codebuddy/settings.json
  workbuddy  ~/.workbuddy/settings.json / <cwd>/.workbuddy/settings.json
                （WorkBuddy IDE 的确切路径以其文档为准；不确定时用 --file 显式指定）

安全设计：
  - 写入前备份（settings.json.bak-<时间戳>）
  - 幂等：已注册（命令串含 marker）不重复添加
  - 卸载只删自己的条目，不动用户其他配置
  - 默认命令形如 python3 "${LICHEN_HOME:-<绝对路径>}/framework/hooks/x.py"
    （shell 会展开变量；--plain 则直接写绝对路径，适配不经过 shell 的 runner）

marker 双兼容（m-3 修复）：R0 品牌统一（framework → lichen）后，旧注册
（framework/hooks/）必须仍能被新版本 lichen uninstall-hooks 卸掉，
否则用户机器上留下永远清不掉的僵尸 hook。
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

from . import paths

HARNESSES = {
    "claude": {"user": "~/.claude/settings.json", "project": ".claude/settings.json"},
    "codebuddy": {"user": "~/.codebuddy/settings.json", "project": ".codebuddy/settings.json"},
    "workbuddy": {"user": "~/.workbuddy/settings.json", "project": ".workbuddy/settings.json"},
}

MARKERS = ("framework/hooks/", "lichen/hooks/")


def _is_ours(command: str) -> bool:
    return any(m in str(command) for m in MARKERS)

# 事件 → (matcher, timeout秒, 脚本名)
# timeout 是 harness 硬上限；NFR-1 的预算（0.5/0.5/2/2/20s）是目标值，
# 硬上限宽于预算 2~4 倍，防慢机器误杀；违约由 tests 发现，不靠 harness 兜底。
HOOK_SPECS = [
    ("SessionStart", "startup", 3, "session_start.py"),
    ("PreCompact", "*", 3, "session_start.py"),
    ("UserPromptSubmit", "*", 2, "user_prompt_submit.py"),
    ("PostToolUse", "Skill|Read|Write|Edit|MultiEdit|NotebookEdit", 2, "post_tool_use.py"),
    ("Stop", "*", 30, "stop.py"),
]


def _command(home: Path, script: str, plain: bool) -> str:
    if plain:
        return f'python3 "{home}/framework/hooks/{script}"'
    return f'python3 "${{LICHEN_HOME:-{home}}}/framework/hooks/{script}"'


def build_hooks(home: Path, plain: bool = False) -> dict:
    hooks = {}
    for event, matcher, timeout, script in HOOK_SPECS:
        entry = {
            "matcher": matcher,
            "hooks": [{
                "type": "command",
                "command": _command(home, script, plain),
                "timeout": timeout,
            }],
        }
        hooks.setdefault(event, []).append(entry)
    return {"hooks": hooks}


def _target_files(target: str, scope: str, cwd: Path) -> list:
    if target == "auto":
        out = []
        for h in HARNESSES.values():
            p = Path(h[scope]).expanduser()
            if not p.is_absolute():
                p = Path(cwd) / p
            if p.parent.is_dir():
                out.append(p)
        return out
    spec = HARNESSES.get(target)
    if not spec:
        raise SystemExit(f"ERROR: 未知 harness: {target}（可选 {', '.join(HARNESSES)} / auto）")
    p = Path(spec[scope]).expanduser()
    if not p.is_absolute():
        p = Path(cwd) / p
    return [p]


def _read_settings(p: Path) -> dict:
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError) as e:
        raise SystemExit(f"ERROR: {p} 不是合法 JSON（{e}）。请先手工修复再安装。")


def _already_registered(settings: dict) -> bool:
    for entries in (settings.get("hooks") or {}).values():
        for e in entries or []:
            for h in (e.get("hooks") or []):
                if _is_ours(h.get("command", "")):
                    return True
    return False


def install(target: str = "auto", scope: str = "user", cwd: Path | None = None,
            plain: bool = False, dry: bool = False) -> list:
    home = paths.REPO_ROOT
    cwd = Path(cwd) if cwd else Path.cwd()
    fragment = build_hooks(home, plain=plain)
    reports = []
    for p in _target_files(target, scope, cwd):
        settings = _read_settings(p)
        if _already_registered(settings):
            reports.append((p, "已注册，跳过"))
            continue
        merged = json.loads(json.dumps(settings))  # deep copy
        hooks = merged.setdefault("hooks", {})
        for event, entries in fragment["hooks"].items():
            existing = hooks.get(event) or []
            existing.extend(entries)
            hooks[event] = existing
        if dry:
            reports.append((p, f"[dry-run] 将注册 {len(fragment['hooks'])} 个事件"))
            continue
        p.parent.mkdir(parents=True, exist_ok=True)
        if p.exists():
            bak = p.with_name(p.name + ".bak-" + datetime.now().strftime("%Y%m%d%H%M%S"))
            shutil.copy2(p, bak)
        else:
            bak = None
        p.write_text(json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        reports.append((p, f"已注册（备份: {bak.name if bak else '无原文件'}）"))
    return reports


def uninstall(target: str = "auto", scope: str = "user", cwd: Path | None = None,
              dry: bool = False) -> list:
    cwd = Path(cwd) if cwd else Path.cwd()
    reports = []
    for p in _target_files(target, scope, cwd):
        if not p.exists():
            reports.append((p, "文件不存在，跳过"))
            continue
        settings = _read_settings(p)
        hooks = settings.get("hooks") or {}
        removed = 0
        for event in list(hooks.keys()):
            kept = []
            for e in hooks[event] or []:
                sub = [h for h in (e.get("hooks") or []) if not _is_ours(h.get("command", ""))]
                if len(sub) != len(e.get("hooks") or []):
                    removed += len(e.get("hooks") or []) - len(sub)
                if sub:
                    e = dict(e, hooks=sub)
                    kept.append(e)
            if kept:
                hooks[event] = kept
            else:
                del hooks[event]
        if not hooks:
            settings.pop("hooks", None)
        if dry:
            reports.append((p, f"[dry-run] 将移除 {removed} 条"))
            continue
        if removed:
            bak = p.with_name(p.name + ".bak-" + datetime.now().strftime("%Y%m%d%H%M%S"))
            shutil.copy2(p, bak)
            p.write_text(json.dumps(settings, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            reports.append((p, f"已移除 {removed} 条（备份: {bak.name}）"))
        else:
            reports.append((p, "没有框架条目，跳过"))
    return reports


def registered_in(cwd: Path | None = None) -> list:
    """供 doctor 使用：返回已注册框架 hooks 的设置文件列表。"""
    cwd = Path(cwd) if cwd else Path.cwd()
    out = []
    for scope in ("user", "project"):
        for p in _target_files("auto", scope, cwd):
            if p.exists() and _already_registered(_read_settings(p)):
                out.append(p)
    return out
