"""framework/lib/lock.py — 跨进程排他锁（stdlib fcntl；仅 macOS/Linux）。

为什么需要：多个 harness / 多个会话的 Stop hook 会并发跑 evolve --apply，
对 evolution.json 和 sidecar 做 read-modify-write。无锁时后写的会话会覆盖
先写会话的账本更新（计数器丢失、changelog 竞态、双收编）。

纪律（与 hooks 一致）：
  - 拿不到锁 / 平台不支持 → 绝不抛异常，yield False 让调用方跳过写路径
  - 锁文件是运行状态，放 state/（gitignore，不进仓库）
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from pathlib import Path

try:
    import fcntl
except ImportError:  # 无 fcntl 的平台（Windows）：降级为无锁。产品只承诺 macOS/Linux。
    fcntl = None  # type: ignore[assignment]


@contextmanager
def file_lock(lock_path, timeout: float = 10.0, poll: float = 0.05):
    """尝试获取排他锁。成功 yield True；超时/失败 yield False（调用方应放弃本次写）。

    用法：
        with file_lock(paths.EVOLUTION_LOCK) as ok:
            if not ok:
                return skipped_report()
            ... 读-改-写 ...
    """
    if fcntl is None:
        yield False
        return
    p = Path(lock_path)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        fd = open(p, "a+b")  # noqa: SIM115 — finally 里统一关闭
    except OSError:
        yield False
        return
    acquired = False
    deadline = time.monotonic() + max(0.0, float(timeout))
    try:
        while True:
            try:
                fcntl.flock(fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
                break
            except OSError:
                if time.monotonic() >= deadline:
                    break
                time.sleep(poll)
        yield acquired
    finally:
        try:
            if acquired:
                fcntl.flock(fd.fileno(), fcntl.LOCK_UN)
        except OSError:
            pass
        try:
            fd.close()
        except OSError:
            pass
