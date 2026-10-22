"""framework/lib/paths.py — 仓库定位与运行路径。

框架不依赖 cwd：hooks 在任何项目目录里被触发，统一用 __file__ 定位仓库根。
"""

from __future__ import annotations

import copy
from pathlib import Path

# framework/lib/paths.py → parents[0]=lib, parents[1]=framework, parents[2]=repo root
REPO_ROOT = Path(__file__).resolve().parents[2]
FRAMEWORK_DIR = REPO_ROOT / "framework"
LIB_DIR = FRAMEWORK_DIR / "lib"
HOOKS_DIR = FRAMEWORK_DIR / "hooks"
TEMPLATES_DIR = FRAMEWORK_DIR / "templates"

SKILLS_ROOT = REPO_ROOT / "skills"

# 私有技能桶（gitignore）：个人向 / 手动执行技能纳入治理但永不公开。
# 治理（sidecar/生命周期/交换）与发布（git/publish.sh）在此分离——见 PRD v2 P-8。
PRIVATE_BUCKET = ".private"
PRIVATE_ROOT = SKILLS_ROOT / PRIVATE_BUCKET

# 本地运行状态（gitignore）：信号、进化账本、版本快照、候选、待裁决
STATE_DIR = FRAMEWORK_DIR / "state"
SIGNALS_FILE = STATE_DIR / "signals.jsonl"
EVOLUTION_FILE = STATE_DIR / "evolution.json"
VERSIONS_DIR = STATE_DIR / "versions"
CANDIDATES_DIR = STATE_DIR / "candidates"
INCOMING_DIR = STATE_DIR / "incoming"
CONFIG_USER = STATE_DIR / "config.json"
CONFIG_DEFAULT = FRAMEWORK_DIR / "config.default.json"

# evolve 写路径的跨进程排他锁（多会话并发 Stop hook 的串行化，见 lib/lock.py）
EVOLUTION_LOCK = STATE_DIR / "evolve.lock"
LOCK_TIMEOUT = 10.0  # 秒；超时即放弃本次自动执行（下轮/CLI 补上），绝不硬等

DIST_DIR = REPO_ROOT / "dist"

# 信号文件超过这个行数就截断到 KEEP（运行数据，不是审计数据）
SIGNALS_MAX_LINES = 10000
SIGNALS_KEEP_LINES = 5000
# Stop hook 每次分析最多回看的信号条数（时间预算）
SIGNALS_ANALYZE_LIMIT = 5000

DEFAULT_CONFIG = {
    "auto": {
        "adopt_local_skills": True,   # 本地新技能过检后自动收编进 skills/local/
        "hygiene_fix": True,          # 自动修补确定性卫生问题（补 sidecar、修 invocation、补触发语）
        "scaffold_candidates": True,  # 重复意图自动生成候选骨架
        "generation_bump": True       # 编辑爆发自动 generation++ 留痕
    },
    "thresholds": {
        "edit_burst": 3,              # 7 天内同技能编辑次数达到即算一次爆发
        "edit_burst_days": 7,
        "intent_repeat": 3,           # 30 天内同一意图出现次数达到即 scaffold
        "intent_repeat_days": 30,
        "probation_days": 30,         # 自动产物试用期天数（AutoHarness probation）
        "probation_min_uses": 3,      # 试用期内 loads 达到即转正 mature
        "trust_min_loads": 5,         # loads 达到即解除 trust=false（SkillMaxxing trusted 门）
        "capacity": 40,               # skills/local/ 容量上限，超出触发归档竞争（T1 提示）
        "max_auto_per_day": 10        # 每日自动执行（T0 落盘）上限，0=不限（爆炸半径控制）
    },
    # 本地技能扫描目录（~ 展开；相对路径相对 hook 触发时的 cwd）
    "scan_dirs": [
        "~/.workbuddy/skills",
        "~/.claude/skills",
        "~/.agents/skills",
        ".workbuddy/skills",
        ".claude/skills",
        ".agents/skills"
    ],
    # 双名单（治理与发布分离，PRD v2 P-8）：
    #   exclude_skills = 不公开但纳入治理——发现后收编进 skills/.private/（gitignore），
    #                    个人向 / 手动执行技能在这里获得完整的 sidecar/生命周期/交换能力
    #   ignore_skills  = 完全不理会——内置副本等噪声，连私有桶也不进
    "exclude_skills": [
        "alipay-wealth-sync",
        "phone-daily-rewards",
        "testin-crowdtest"
    ],
    "ignore_skills": [
        "xlsx",
        "pptx"
    ],
    "digest_max_lines": 3
}


def _deep_merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (override or {}).items():
        # 空列表视为未设置：上游模板（config.default.json）不含真实治理名单，
        # 空键不得把代码默认值（DEFAULT_CONFIG 的 exclude/ignore 等）抹掉——
        # C-1 整改后的教训：标准安装 state 为空时曾因此漏放 ignore 名单。
        if isinstance(v, list) and not v:
            continue
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def load_config() -> dict:
    """默认配置 ← 用户覆盖（state/config.json）。"""
    from .util import read_json
    cfg = _deep_merge(DEFAULT_CONFIG, read_json(CONFIG_DEFAULT, {}) or {})
    cfg = _deep_merge(cfg, read_json(CONFIG_USER, {}) or {})
    return cfg


def resolve_scan_dirs(cfg: dict, cwd: Path | None = None) -> list:
    """展开 scan_dirs；相对路径相对 cwd（hook 触发时的项目目录）。"""
    import os
    cwd = Path(cwd) if cwd else Path.cwd()
    out = []
    for d in cfg.get("scan_dirs", []):
        p = Path(os.path.expanduser(d))
        if not p.is_absolute():
            p = (cwd / p)
        if p.is_dir() and p not in out:
            out.append(p)
    return out


def ensure_state() -> None:
    """幂等创建运行目录。"""
    for d in (STATE_DIR, VERSIONS_DIR, CANDIDATES_DIR, INCOMING_DIR):
        d.mkdir(parents=True, exist_ok=True)


def empty_evolution() -> dict:
    return {
        "version": 1,
        "created": "",
        "last_evolve": None,
        "counters": {"signals": 0, "requests": 0, "adoptions": 0, "evolutions": 0, "candidates": 0, "imports": 0, "exports": 0},
        "baseline": {"adoptions": 0, "evolutions": 0, "candidates": 0},
        "pending": [],
        "skills": {},
        "config_seen": {},
        "digest": ""
    }
