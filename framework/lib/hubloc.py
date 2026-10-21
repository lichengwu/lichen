"""framework/lib/hubloc.py — hub 位置解析（本地优先，远程扩展位预留）。

v1 只实现 local：默认 ~/Skills，解析顺序 LICHEN_HUB 环境变量 > config(hub.path)
（state/config.json，gitignore，机器本地）> 默认值。v1 无配置 schema（佐井拍板）。

URI 抽象（ADR 0004）：parse_hub_uri 是唯一的 scheme 入口。所有 hub 操作只面对
local_path——远程模式（git+https / git+ssh / webdav / sftp）的差异将来被压缩进
resolve/sync 两个动作，上层零改动。未知 scheme 在此明确报错，不做静默降级。
"""

from __future__ import annotations

import os
from pathlib import Path

DEFAULT_HUB = "~/Skills"

# hub 内的两个保留目录（非技能区）：
#   private/    私有桶——visibility=private 技能，随 hub 版本化，发布结构排除（P-8）
#   quarantine/ 隔离桶——外部来源技能，T1 审查（hub promote）后才可分发（评审 F3）
PRIVATE_DIR = "private"
QUARANTINE_DIR = "quarantine"
RESERVED_DIRS = {PRIVATE_DIR, QUARANTINE_DIR}

# 预留的远程 scheme（只报错提示用，v1 不解析）
RESERVED_SCHEMES = ("git+https://", "git+ssh://", "webdav://", "sftp://")


class HubLocation:
    """hub 位置。v1 恒为 kind=local；远程形态 future：resolve()/sync() 两动作。"""

    def __init__(self, kind: str, uri: str, local_path: Path):
        self.kind = kind
        self.uri = uri
        self.local_path = Path(local_path)

    def __repr__(self) -> str:
        return f"HubLocation(kind={self.kind}, uri={self.uri!r}, local_path={self.local_path})"


def parse_hub_uri(uri: str) -> HubLocation:
    """解析 hub 位置。v1 只识别 local（裸路径 / local: 前缀 / ~ 展开）。

    未知 scheme 报 SystemExit 并指向 ADR——这是扩展位契约：现在就明确"不认识"，
    将来填实现时只改这里（评审 F 系列的"上层零改动"）。
    """
    s = str(uri or "").strip()
    if not s:
        s = DEFAULT_HUB
    low = s.lower()
    if low.startswith(RESERVED_SCHEMES) or "://" in s:
        raise SystemExit(
            f"ERROR: 暂不支持的 hub 位置: {uri}\n"
            "远程模式是预留扩展位（git/webdav/sftp），见 .agents/adr/0004-hub-separation.md。"
            "当前请使用本地目录路径。")
    if low.startswith("local:"):
        s = s[len("local:"):]
    if not s:
        s = DEFAULT_HUB
    return HubLocation("local", s, Path(os.path.expanduser(s)))


def registered_path() -> str:
    """config（state/config.json）里登记的 hub 路径；未登记返回空串。"""
    from . import paths
    cfg = paths.load_config()
    return str((cfg.get("hub") or {}).get("path") or "")


def hub_root() -> Path:
    """生效 hub 根：LICHEN_HUB > config hub.path > 默认 ~/Skills。"""
    env = os.environ.get("LICHEN_HUB")
    if env:
        return parse_hub_uri(env).local_path
    reg = registered_path()
    if reg:
        return parse_hub_uri(reg).local_path
    return parse_hub_uri(DEFAULT_HUB).local_path


def register(path_like: str) -> Path:
    """把路径登记进机器本地 config（不入库）。返回生效 hub 根。"""
    from . import paths
    from .util import read_json, write_json_atomic
    loc = parse_hub_uri(path_like)
    cfg = read_json(paths.CONFIG_USER, {}) or {}
    if not isinstance(cfg, dict):
        cfg = {}
    cfg.setdefault("hub", {})["path"] = str(loc.local_path)
    write_json_atomic(paths.CONFIG_USER, cfg)
    return loc.local_path
