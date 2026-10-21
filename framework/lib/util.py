"""framework/lib/util.py — 通用工具：哈希、原子写、frontmatter 解析、目录拷贝。

全框架只依赖 Python 标准库（3.8+）。任何函数都不允许抛异常穿透到 hook 调用方——
hooks 的纪律是"永远 exit 0"，异常在调用处吞。
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

CHUNK = 65536

# 拷贝/打包时永不携带的条目（与 scripts/sync.sh、skill-forge/pack_skills.py 对齐）
EXCLUDE_NAMES = {".git", "__pycache__", ".DS_Store", "node_modules", ".pytest_cache", ".scratch"}
EXCLUDE_FILES = {"_meta.json", "_skillhub_meta.json", "_icon.png"}
EXCLUDE_SUFFIX = {".pyc", ".pyo", ".tmp", ".bak"}


def now_iso() -> str:
    """本地时区 ISO 时间（秒级）。"""
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def today() -> str:
    return datetime.now(timezone.utc).astimezone().date().isoformat()


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_text(s: str) -> str:
    return sha256_bytes(s.encode("utf-8"))


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(CHUNK), b""):
            h.update(chunk)
    return h.hexdigest()


def read_json(p: Path, default=None):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError):
        return default


def write_json_atomic(p: Path, obj) -> None:
    """原子写 JSON：先写临时文件再 os.replace，避免半截文件。"""
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(p.parent), prefix=".tmp-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp, p)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def append_jsonl(p: Path, obj) -> None:
    """追加一行 JSON。单行 <4KB 时 os.write 追加在 macOS/Linux 上原子，够用。"""
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(obj, ensure_ascii=False) + "\n"
    with open(p, "a", encoding="utf-8") as f:
        f.write(line)


def read_jsonl(p: Path, limit: int = 0) -> list:
    """读 JSONL；limit>0 只取最后 limit 行。坏行跳过（运行数据，容错优先）。"""
    p = Path(p)
    if not p.exists():
        return []
    try:
        lines = p.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    if limit and len(lines) > limit:
        lines = lines[-limit:]
    out = []
    for ln in lines:
        ln = ln.strip()
        if not ln:
            continue
        try:
            out.append(json.loads(ln))
        except json.JSONDecodeError:
            continue
    return out


def parse_frontmatter(text: str) -> dict:
    """最小 frontmatter 解析：仅 `key: value` 标量行。无 YAML 依赖，够框架用。"""
    if not text.startswith("---"):
        return {}
    fm = {}
    for line in text.split("\n")[1:120]:
        if line.strip() == "---":
            break
        m = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
        if m:
            key, val = m.group(1), m.group(2).strip()
            if len(val) >= 2 and val[0] in "\"'" and val[-1] == val[0]:
                val = val[1:-1]
            fm[key] = val
    return fm


def read_frontmatter_file(p: Path) -> dict:
    try:
        return parse_frontmatter(Path(p).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError):
        return {}


def _ignore(_dir, names):
    ignored = set()
    for n in names:
        if n in EXCLUDE_NAMES or n in EXCLUDE_FILES or Path(n).suffix in EXCLUDE_SUFFIX:
            ignored.add(n)
    return ignored


def copy_tree(src: Path, dst: Path) -> int:
    """拷贝目录树（应用排除规则），返回拷贝的文件数。

    拷贝后清理空目录：源技能里的空 assets/ 之类的占位目录复制过来只会
    触发 check.sh 的空目录 FAIL（git 也不跟踪空目录），没有保留价值。
    """
    src, dst = Path(src), Path(dst)
    if not src.is_dir():
        return 0
    shutil.copytree(src, dst, ignore=_ignore, dirs_exist_ok=True)
    n = sum(1 for p in dst.rglob("*") if p.is_file())
    for p in sorted((q for q in dst.rglob("*") if q.is_dir()), reverse=True):
        if not any(p.iterdir()):
            p.rmdir()
    return n


def dir_hash(root: Path) -> str:
    """目录内容哈希：sorted(relpath:filesha) 的 sha256。确定性、跨平台（posix 路径）。

    排除 .skill-meta.json：sidecar 是"关于技能的元数据"（changelog/来源），
    不是技能内容。排除它同时打破自引用（sidecar 里存着 base_sha256），
    让"导入时改写 sidecar"不改变技能的内容版本号。
    """
    root = Path(root)
    parts = []
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(root)
        if any(part in EXCLUDE_NAMES for part in rel.parts):
            continue
        if p.name in EXCLUDE_FILES or p.suffix in EXCLUDE_SUFFIX:
            continue
        if p.name == ".skill-meta.json":
            continue
        parts.append(f"{rel.as_posix()}:{sha256_file(p)}")
    return sha256_text("\n".join(parts))


def slugify(text: str, maxlen: int = 40) -> str:
    """把任意文本转成技能名可用的 slug（小写连字符）。"""
    s = text.strip().lower()
    s = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "-", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s[:maxlen] or "candidate"
