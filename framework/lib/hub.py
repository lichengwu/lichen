"""framework/lib/hub.py — hub 仓库：使用积累的唯一权威副本（SSOT，ADR 0004）。

三分模型：框架仓库只装框架和种子；hub 承接全部积累；agent 目录是 hub 的视图
（lib/agents.py 物化）。hub 内容是标准 Agent Skills 格式——不装 lichen 也能被任何
agent 直接用（扁平静放，与 anthropics/skills 等社区仓库同构）。

发布路径结构排除（P-8，评审 F2/F3/F5 修订版）：
  1. publish 只枚举「public 区 且 sidecar visibility=public」的技能（双条件，白名单制）；
  2. private/ 与 quarantine/ 目录按路径二次排除；
  3. --public 前置守卫：redact 硬红线扫描 + 产物树断言 + 干跑预览；
  4. 硬规则：hub repo 本身永不直接翻转可见性——公开只走 --public 导出过滤树。
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from . import hubloc, meta, redact
from .hubloc import PRIVATE_DIR, QUARANTINE_DIR, RESERVED_DIRS
from .util import copy_tree, dir_hash, today

README_TMPL = """# Skills Hub

个人技能 hub——lichen 框架的使用积累层（SSOT）。

- 公开区（根目录）：技能扁平静放，标准 Agent Skills 格式，任何 agent 可直接消费
- `private/`：私有桶。visibility=private，随本仓库版本化/同步/备份，但发布路径结构排除
- `quarantine/`：隔离桶。外部来源技能先进这里，T1 审查（`framework hub promote`）后才可分发

## 硬规则

本仓库**永不直接翻转可见性**——在托管平台上手动设 public 会连 `private/` 一起暴露。
公开只走 `framework hub publish --public`：导出过滤树到独立公开仓库。
"""

GITIGNORE_TMPL = ".DS_Store\n"


# ---------- 结构与索引 ----------

def is_skill_dir(p: Path) -> bool:
    return p.is_dir() and (p / "SKILL.md").is_file()


def looks_like_hub(p: Path) -> bool:
    """宽松判断：目录存在且像 hub（.git / 保留区 / 任一技能目录）。"""
    p = Path(p)
    if not p.is_dir():
        return False
    if (p / ".git").exists():
        return True
    if any((p / n).is_dir() for n in RESERVED_DIRS):
        return True
    for child in p.iterdir():
        if child.is_dir() and child.name not in RESERVED_DIRS and not child.name.startswith(".") \
                and (child / "SKILL.md").is_file():
            return True
    return False


def list_hub_skills(root: Path | None = None) -> list:
    """扫描 hub 三区，返回 [{zone,id,dir,meta,fm}]。zone ∈ public|private|quarantine。

    quarantine/ 是隔离区：可被列出（供审查），永不进入物化与发布（评审 F3）。
    """
    root = Path(root) if root else hubloc.hub_root()
    out = []
    if not root.is_dir():
        return out
    for zone, base in (("public", root),
                       ("private", root / PRIVATE_DIR),
                       ("quarantine", root / QUARANTINE_DIR)):
        if not base.is_dir():
            continue
        for child in sorted(base.iterdir()):
            if child.name.startswith(".") or child.name in RESERVED_DIRS or not child.is_dir():
                continue
            if not is_skill_dir(child):
                continue
            out.append({
                "zone": zone, "id": child.name, "dir": child,
                "meta": meta.read_sidecar(child),
                "fm": meta._read_fm(child / "SKILL.md"),
            })
    return out


def publishable(root: Path | None = None) -> list:
    """发布集 = public 区 且 visibility=public（双条件白名单，F2 fail-safe）。"""
    return [s for s in list_hub_skills(root)
            if s["zone"] == "public"
            and str((s["meta"] or {}).get("visibility", "private")) == "public"]


# ---------- init / use / status ----------

def init() -> list:
    """建 hub 仓库并注册（幂等）。返回消息列表。"""
    root = hubloc.hub_root()
    msgs = []
    if not root.exists():
        msgs.append(f"创建目录 {root}")
    root.mkdir(parents=True, exist_ok=True)
    hubloc.register(str(root))
    msgs.append(f"已登记为生效 hub（config.hub.path；LICHEN_HUB 环境变量可临时覆盖）")
    readme = root / "README.md"
    if not readme.exists():
        readme.write_text(README_TMPL, encoding="utf-8")
        msgs.append("写入门面 README（含公开硬规则）")
    gi = root / ".gitignore"
    if not gi.exists():
        gi.write_text(GITIGNORE_TMPL, encoding="utf-8")
    if not (root / ".git").exists():
        r = _git(root, "init")
        if r.returncode == 0:
            msgs.append("git init 完成")
            _git(root, "add", "-A")
            c = _git(root, "commit", "-m", "hub init（lichen）", "--allow-empty",
                     "--quiet")
            if c.returncode != 0:
                msgs.append("（首次 commit 未完成：配置 git user.name/email 后手动补）")
        else:
            msgs.append("（git 不可用——纯目录 hub 也能工作，仅无版本历史）")
    msgs.append(f"hub 就绪：{root}")
    return msgs


def use(path_like: str) -> Path:
    """把已有目录注册为 hub（如 clone 别人的 hub）。校验结构，写入机器本地 config。"""
    loc = hubloc.parse_hub_uri(path_like)
    p = loc.local_path
    if not p.is_dir():
        raise SystemExit(f"ERROR: 目录不存在: {p}")
    if p.iterdir() and not looks_like_hub(p):
        raise SystemExit(
            f"ERROR: {p} 不像 hub（无 .git、无私有/隔离区、无技能目录）。\n"
            "空目录可直接注册；坚持注册请先 framework hub init（幂等，补 README/版本化）。")
    return hubloc.register(str(p))


def _git(root: Path, *args) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(["git", *args], cwd=str(root),
                              capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return subprocess.CompletedProcess(["git"], 127, "", "git 不可用")


def status() -> None:
    """一屏看全：三区计数 / 场景分布 / git 状态与 remote。"""
    root = hubloc.hub_root()
    print(f"hub 状态：{root}")
    if not root.is_dir():
        print("└─ 尚未初始化（framework hub init）")
        return
    skills = list_hub_skills(root)
    zones = {}
    for s in skills:
        zones[s["zone"]] = zones.get(s["zone"], 0) + 1
    print("├─ 技能 " + str(len(skills)) + " 个：" +
          " · ".join(f"{z} {n}" for z, n in sorted(zones.items())) if skills else "├─ 技能 0 个")
    vis = {}
    for s in skills:
        v = str((s["meta"] or {}).get("visibility", "未登记"))
        vis[v] = vis.get(v, 0) + 1
    print("├─ 可见性：" + (" · ".join(f"{k} {v}" for k, v in sorted(vis.items())))
          + "（publish 白名单 = public 区 且 visibility=public）")
    cats = {}
    for s in skills:
        for c in ((s["meta"] or {}).get("categories") or ["未分类"]):
            cats[c] = cats.get(c, 0) + 1
    if cats:
        print("├─ 场景分布：" + " · ".join(f"{c} {n}" for c, n in
                                          sorted(cats.items(), key=lambda kv: (-kv[1], kv[0]))))
    st = _git(root, "status", "--porcelain")
    dirty = len([ln for ln in st.stdout.splitlines() if ln.strip()]) if st.returncode == 0 else -1
    if dirty >= 0:
        remotes = (_git(root, "remote").stdout or "").split()
        print(f"├─ git：{'干净' if dirty == 0 else f'{dirty} 项未提交'} · "
              f"remote {'/'.join(remotes) if remotes else '未配置（私有 remote 起步：git -C ' + str(root) + ' remote add origin <url>）'}")
    else:
        print("├─ git：不可用")
    print("└─ 发布集：" + (f"{len(publishable(root))} 个（framework hub publish --public 导出过滤树）"
                          if publishable(root) else "空（迁移默认全 private；公开走白名单提升）"))


# ---------- migrate ----------

def migrate(dry: bool = False) -> list:
    """一次性：仓库内 skills/local/* → hub 根，skills/.private/* → hub/private/。

    迁移一律把 sidecar visibility 置为 private（评审 F2 fail-safe：迁移集先全私有，
    公开走白名单显式提升）。源桶整个移除；.gitignore 两行保留作防御双保险。
    调用方负责持有 evolve.lock（迁移与 hook 并发进化互斥）。
    """
    from . import paths
    root = hubloc.hub_root()
    if not root.is_dir():
        raise SystemExit("ERROR: hub 尚未初始化（先 framework hub init）")
    msgs = []
    plan = []
    for src_root, zone in ((paths.SKILLS_ROOT / "local", ""),
                           (paths.PRIVATE_ROOT, PRIVATE_DIR)):
        if not src_root.is_dir():
            continue
        for child in sorted(src_root.iterdir()):
            if not is_skill_dir(child):
                continue  # 旧落点规则 README 等随源桶一起移除
            dst = (root / zone / child.name) if zone else (root / child.name)
            plan.append((child, dst))
    if not plan:
        msgs.append("仓库内没有待迁移的个人层技能（skills/local 与 skills/.private 无技能）")
        return msgs
    if dry:
        for src, dst in plan:
            msgs.append(f"[dry-run] {src.name} → {dst}")
        msgs.append(f"[dry-run] 共 {len(plan)} 个技能；源桶将整体移除（gitignore 保留）")
        return msgs
    moved = flipped = 0
    for src, dst in plan:
        if dst.exists():
            msgs.append(f"跳过 {src.name}（hub 已有同名，人工裁决后手动处理）")
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        moved += 1
        m = meta.read_sidecar(dst)
        if m and str(m.get("visibility", "")) != "private":
            m["visibility"] = "private"
            m = meta.append_changelog(
                m, "hub 迁移：visibility → private（fail-safe；公开走白名单提升）", bump=False)
            meta.write_sidecar(dst, m)
            flipped += 1
    removed = []
    for d in (paths.SKILLS_ROOT / "local", paths.PRIVATE_ROOT):
        if d.is_dir():
            shutil.rmtree(d, ignore_errors=True)
            removed.append(str(d.relative_to(paths.REPO_ROOT)))
    msgs.append(f"迁移 {moved} 个技能进 hub（visibility→private {flipped} 个）")
    if removed:
        msgs.append("框架仓库源桶已移除：" + ", ".join(removed)
                    + "（.gitignore 两行保留作防御）")
    return msgs


# ---------- publish ----------

def publish(out: str | None = None, public: bool = False, dry: bool = False) -> int:
    """无参 = 私有 push（commit + push origin）；--public = 导出过滤树建干净公开 repo。"""
    root = hubloc.hub_root()
    if not root.is_dir():
        raise SystemExit("ERROR: hub 尚未初始化（framework hub init）")
    if public:
        return _export_public(root, out, dry)
    return _push_private(root, dry)


def _push_private(root: Path, dry: bool) -> int:
    st = _git(root, "status", "--porcelain")
    remotes = (_git(root, "remote").stdout or "").split()
    if dry:
        print(f"[dry-run] {'将提交 ' + str(len(st.stdout.splitlines())) + ' 项变更，' if st.stdout.strip() else ''}"
              f"push → {remotes[0] if remotes else '（无 remote）'}")
        return 0
    if st.stdout.strip():
        _git(root, "add", "-A")
        c = _git(root, "commit", "-m", f"hub sync（lichen）")
        if c.returncode != 0:
            print("FAIL commit 失败：" + (c.stderr or "").strip()[:200])
            return 1
        print(f"OK 已提交 {len(st.stdout.splitlines())} 项变更")
    if not remotes:
        print("FAIL hub 没有配置 remote。私有 remote 起步：")
        print(f"  git -C {root} remote add origin git@github.com:<you>/<repo>.git")
        return 1
    r = _git(root, "push")
    if r.returncode != 0:
        print("FAIL push 失败：" + (r.stderr or "").strip()[:300])
        return 1
    print(f"OK 已 push → {remotes[0]}")
    return 0


def _export_public(root: Path, out: str | None, dry: bool) -> int:
    out_dir = Path(os.path.expanduser(out)) if out else root.parent / (root.name + "-public")
    skills = publishable(root)
    # 结构排除断言（belt and suspenders）：发布集绝不含保留区路径
    for boundary in (PRIVATE_DIR, QUARANTINE_DIR):
        b = (root / boundary).resolve()
        for s in skills:
            try:
                s["dir"].resolve().relative_to(b)
                raise SystemExit(f"FAIL 发布集混入 {boundary}/ 区技能: {s['id']}（守卫拦截）")
            except ValueError:
                pass
    if not skills:
        print("发布集为空（public 区且 visibility=public 的技能一个都没有）。")
        print("白名单提升：编辑技能 sidecar visibility → public（private/ 区技能请先移出）")
        return 1
    # redact 硬红线扫描（复用收编同款守卫）
    hits = []
    for s in skills:
        hits += [f"{s['id']}/{h}" for h in redact.scan_tree(s["dir"], max_hits=5)]
    if hits:
        print("FAIL redact 硬红线命中，拒绝导出：")
        for h in hits[:10]:
            print("  · " + h)
        return 1
    if dry:
        print(f"[dry-run] 将导出 {len(skills)} 个技能 → {out_dir}/（干净新 repo）")
        for s in skills:
            print(f"  · {s['id']}")
        return 0
    if out_dir.exists() and any(out_dir.iterdir()):
        raise SystemExit(f"ERROR: 目标目录非空: {out_dir}（换 --out 或手动清空）")
    out_dir.mkdir(parents=True, exist_ok=True)
    n = 0
    for s in skills:
        copy_tree(s["dir"], out_dir / s["id"])
        n += 1
    (out_dir / "README.md").write_text(
        f"# Skills（公开精选集）\n\n由 lichen hub 从私有 hub 导出的公开技能子集"
        f"（{today()}，{n} 个）。标准 Agent Skills 格式。\n", encoding="utf-8")
    _git(out_dir, "init")
    _git(out_dir, "add", "-A")
    _git(out_dir, "commit", "-m", "publish：hub 公开精选集", "--quiet", "--allow-empty")
    print(f"OK 导出 {n} 个技能 → {out_dir}/（干净新 repo，git 已 init+commit）")
    print("发布（人工执行）：")
    print(f"  git -C {out_dir} remote add origin git@github.com:<you>/<公开repo>.git")
    print(f"  git -C {out_dir} push -u origin main --allow-unrelated-histories 2>/dev/null || git -C {out_dir} push -u origin master")
    print("提醒：hub 本体（含 private/）永不推到这个 remote。")
    return 0


# ---------- import（隔离）与 promote（审查晋升） ----------

def import_skill(src_like: str) -> str:
    """外部来源技能 → 隔离桶（F3：外部内容永不直接进入分发面）。

    接受技能目录（含 SKILL.md）。redact 命中只提示不拦——隔离区本来就是给人看的。
    """
    src = Path(os.path.expanduser(src_like)).resolve()
    if not is_skill_dir(src):
        raise SystemExit(f"ERROR: {src} 不是技能目录（缺 SKILL.md）")
    root = hubloc.hub_root()
    if not root.is_dir():
        raise SystemExit("ERROR: hub 尚未初始化（framework hub init）")
    qdir = root / QUARANTINE_DIR
    qdir.mkdir(parents=True, exist_ok=True)
    dst = qdir / src.name
    if dst.exists():
        raise SystemExit(f"ERROR: 隔离区已有同名技能: {dst}（先审查处理）")
    copy_tree(src, dst)
    m = meta.read_sidecar(dst)
    if not m:
        m = {"kind": "skill", "visibility": "private", "execution": "hybrid",
             "categories": [], "origin": "adopted", "source": str(src),
             "license": None, "invocation": "model", "generation": 1,
             "changelog": [{"gen": 1, "date": today(),
                            "change": f"外部导入进隔离区（来源 {src}）；T1 审查后 hub promote"}],
             "base_sha256": dir_hash(dst)}
        meta.write_sidecar(dst, m)
    hits = redact.scan_tree(dst, max_hits=5)
    msg = f"已隔离 {src.name} → {dst}"
    if hits:
        msg += "（redact 提示：" + "; ".join(hits[:3]) + "）"
    msg += "\n审查要点：内容 diff、来源可信度、scripts/ 是否可执行代码。\n晋升：framework hub promote " + src.name
    return msg


def promote(skill_id: str) -> str:
    """隔离区 → hub 公开区（T1，仅显式调用）。落地默认 visibility=private（F2）。"""
    root = hubloc.hub_root()
    src = root / QUARANTINE_DIR / skill_id
    if not is_skill_dir(src):
        raise SystemExit(f"ERROR: 隔离区无此技能: {skill_id}（hub status 查看隔离区）")
    dst = root / skill_id
    if dst.exists():
        raise SystemExit(f"ERROR: 公开区已有同名: {dst}")
    shutil.move(str(src), str(dst))
    m = meta.read_sidecar(dst) or {}
    m["visibility"] = "private"
    m = meta.append_changelog(
        m, "隔离区审查通过，晋升到 hub 公开区（visibility=private；公开需显式提升）", bump=False)
    meta.write_sidecar(dst, m)
    meta.snapshot(dst)
    return f"晋升 {skill_id} → hub 公开区（visibility=private，已入版本快照）"
