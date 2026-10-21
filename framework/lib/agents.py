"""framework/lib/agents.py — 多 agent 注册表与物化（hub 的视图层）。

hub 是 SSOT；各 agent 的技能目录是 hub 的视图。v1 物化只做 link——
技能级 symlink（链接名 = 技能 id，与 frontmatter name 一致）。评审 F1 修订：
生态是单层发现模型（skills/<name>/SKILL.md），桶级链接扫不到第二层；
vercel-labs/skills 的成熟模式即「canonical 副本 + 每技能一条链」。

注册表为代码内置（v1 无配置，佐井拍板）；新 agent = REGISTRY 加一条。
WorkBuddy 是创作面：只收编（adopt → hub）不物化。隔离区（quarantine/）永不物化。
"""

from __future__ import annotations

import os
from pathlib import Path

from . import hub, hubloc
from .hubloc import RESERVED_DIRS

# 内置注册表（v1 无配置）。detect 任一路径存在即视为已安装；
# targets 为空 = 无物化落点（创作面或共用他人落点或预留）。
REGISTRY = [
    {
        "id": "codex", "label": "Codex CLI",
        "detect": ["~/.codex", "~/.agents/skills"],
        "targets": [{"path": "~/.agents/skills", "mode": "link"}],
        "adopt_from": ["~/.agents/skills", ".agents/skills"],
        "note": "落点 ~/.agents/skills 是厂商中立目录（Cursor/Cline/OpenCode 原生共用，零成本覆盖）",
    },
    {
        "id": "pi", "label": "pi coding agent",
        "detect": ["~/.pi"],
        "targets": [],
        "adopt_from": ["~/.pi/agent/skills"],
        "note": "原生读 ~/.agents/skills（与 Codex 共用落点）与 ~/.pi/agent/skills",
    },
    {
        "id": "claude-code", "label": "Claude Code",
        "detect": ["~/.claude"],
        "targets": [{"path": "~/.claude/skills", "mode": "link"}],
        "adopt_from": ["~/.claude/skills"],
        "note": "官方支持技能级 symlink；单层发现（skills/<name>/SKILL.md）",
    },
    {
        "id": "qwen", "label": "Qwen Code（千问）",
        "detect": ["~/.qwen"],
        "targets": [{"path": "~/.qwen/skills", "mode": "link"}],
        "adopt_from": ["~/.qwen/skills"],
        "note": "官方个人技能目录 ~/.qwen/skills（Agent Skills 标准）；未安装时自动跳过",
    },
    {
        "id": "workbuddy", "label": "WorkBuddy（创作面）",
        "detect": ["~/.workbuddy"],
        "targets": [],
        "adopt_from": ["~/.workbuddy/skills"],
        "note": "创作面：只收编进 hub，不物化——技能原位就是创作源，evolve 自动收集增量",
    },
    {
        "id": "junie", "label": "Junie / PyCharm（预留）",
        "detect": ["~/.junie", "~/.aiassistant"],
        "targets": [],
        "adopt_from": [],
        "note": "v2：index 模式（AGENTS.md 托管块注入）；本版不物化",
    },
]


def _expand(p: str) -> Path:
    return Path(os.path.expanduser(p))


def get(agent_id: str) -> dict | None:
    for ag in REGISTRY:
        if ag["id"] == agent_id:
            return ag
    return None


def detected(ag: dict) -> bool:
    return any(_expand(p).exists() for p in ag.get("detect", []))


# ---------- 物化（link 模式） ----------

def _link_target_of(link: Path) -> Path:
    """symlink 指向的绝对路径（不要求存在）。"""
    raw = os.readlink(str(link))
    p = Path(raw)
    return p if p.is_absolute() else (link.parent / p)


def sync(dry: bool = False, agent_filter: str = "") -> dict:
    """把 hub 技能物化为各 detected agent 的技能级 symlink。幂等。

    规则：
      - 隔离区（quarantine/）永不物化（评审 F3）；private/ 区照常物化
        （private = 不发布，不是不给本机 agent 用）
      - 链接名 = 技能 id（与 frontmatter name 一致，评审 F1）
      - 目标已有同名实体目录 → 记冲突跳过，绝不静默覆盖
      - 失效/漂移的己方链接（指向 hub 内已不存在技能）→ 清理重建
      - 非己方的 symlink（其他工具的链）不碰
    返回 {created, fresh, conflict, removed, skipped_agents} 消息列表。
    """
    root = hubloc.hub_root()
    if not root.is_dir():
        raise SystemExit("ERROR: hub 尚未初始化（framework hub init）")
    root = root.resolve()
    skills = {s["id"]: s for s in hub.list_hub_skills(root)
              if s["zone"] in ("public", "private")}
    report = {"created": [], "fresh": [], "conflict": [], "removed": [], "skipped_agents": []}

    for ag in REGISTRY:
        if agent_filter and ag["id"] != agent_filter:
            continue
        if not detected(ag):
            report["skipped_agents"].append(ag["id"])
            continue
        for t in ag.get("targets", []):
            if t.get("mode") != "link":
                continue  # v1 仅 link；copy 是 symlink 验证失败时的兜底（暂不实装）
            tdir = _expand(t["path"])
            if not tdir.exists():
                if dry:
                    report["created"].append(f"[dry-run] 将创建目录 {tdir}")
                    continue
                tdir.mkdir(parents=True, exist_ok=True)
            # 第一遍：清理己方失效链接
            for child in sorted(tdir.iterdir()):
                if not child.is_symlink():
                    continue
                resolved = _link_target_of(child)
                try:
                    resolved.relative_to(root)
                except ValueError:
                    continue  # 非己方链接（vercel-labs 等），不碰
                in_hub = resolved.is_dir() and (resolved / "SKILL.md").is_file() \
                    and resolved.name in skills
                if in_hub:
                    continue
                if not dry:
                    child.unlink()
                report["removed"].append(f"{ag['id']}:{child.name}（指向已不存在的 hub 技能）")
            # 第二遍：补链
            for sid in sorted(skills):
                target = skills[sid]["dir"].resolve()
                link = tdir / sid
                if link.is_symlink():
                    if _link_target_of(link) == target:
                        report["fresh"].append(f"{ag['id']}/{sid}")
                    else:
                        if not dry:
                            link.unlink()
                            os.symlink(str(target), str(link))
                        report["removed"].append(f"{ag['id']}/{sid}（重链：原指向 {_link_target_of(link)}）")
                        report["created"].append(f"{ag['id']}/{sid}")
                elif link.exists():
                    report["conflict"].append(
                        f"{ag['id']}/{sid}（目标已有同名实体目录，未覆盖——人工裁决）")
                else:
                    if not dry:
                        os.symlink(str(target), str(link))
                    report["created"].append(f"{ag['id']}/{sid}")
    return report


# ---------- doctor ----------

def doctor() -> tuple:
    """只读体检。返回 (problems, warns, infos)——与 framework doctor 同风格。"""
    problems, warns, infos = [], [], []
    root = hubloc.hub_root()
    if os.environ.get("LICHEN_HUB"):
        infos.append(f"LICHEN_HUB 覆盖生效：{root}")
    if not root.is_dir():
        problems.append(f"hub 不存在: {root}（framework hub init）")
        return problems, warns, infos
    skills = hub.list_hub_skills(root)
    ids = {s["id"] for s in skills}
    dup = len(skills) != len(ids)
    if dup:
        problems.append("hub 内技能 id 重名（public/private 区同名）——人工裁决")
    # hub 结构（评审 m11）：根下未知目录警告
    known = ids | RESERVED_DIRS
    for child in sorted(root.iterdir()):
        if child.name.startswith(".") or child.is_file() or child.name in known:
            continue
        if child.is_dir():
            warns.append(f"hub 根下未知目录: {child.name}/（既非技能也非保留区——确认或移走）")
    q = [s for s in skills if s["zone"] == "quarantine"]
    if q:
        infos.append(f"隔离区 {len(q)} 个待审查：{', '.join(s['id'] for s in q)}"
                     "（framework hub promote <名> 晋升）")
    infos.append(f"发布集 {len(hub.publishable(root))} 个"
                 f"（public 区 且 visibility=public；迁移默认 private，白名单制）")

    for ag in REGISTRY:
        on = detected(ag)
        label = f"{ag['label']}({ag['id']})"
        if not on:
            infos.append(f"{label}: 未安装（detect 未命中），注册表保留")
            continue
        targets = ag.get("targets", [])
        if not targets:
            infos.append(f"{label}: 无独立落点——{ag.get('note', '')}")
            continue
        for t in targets:
            tdir = _expand(t["path"])
            if not tdir.is_dir():
                warns.append(f"{label}: 落点不存在 {tdir}（agents sync 会创建）")
                continue
            ok = bad = conflicts = 0
            for s in skills:
                if s["zone"] == "quarantine":
                    continue
                link = tdir / s["id"]
                if link.is_symlink():
                    try:
                        _link_target_of(link).relative_to(root.resolve())
                        ok += 1
                    except (ValueError, OSError):
                        bad += 1
                elif link.exists():
                    conflicts += 1
            if bad:
                problems.append(f"{label}: {bad} 条失效链接（agents sync 重建）")
            if conflicts:
                warns.append(f"{label}: {conflicts} 个同名冲突（实体目录存在，未物化——人工裁决）")
            infos.append(f"{label}: {ok} 条有效链接 · 落点 {tdir}")
    return problems, warns, infos
