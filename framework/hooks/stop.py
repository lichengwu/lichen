#!/usr/bin/env python3
"""framework/hooks/stop.py — Stop 钩子：一轮会话结束，执行 T0 自进化。

这是"无感知自动执行"的落点：
  分析本轮累积的信号 → 执行 T0（收编/进化留痕/候选 scaffold/卫生修补）
  → 更新摘要供下次 SessionStart 注入。

纪律：
  - 只执行 T0（本地、可 git 回滚、留 changelog）；T1 挂 pending 不自动做
  - 整个流程 <20s（timeout 30s）；单动作失败不影响其他
  - 最多输出一行到 stderr（Stop 的 stdout 会进 transcript，不注入上下文）
  - 任何异常静默 exit 0
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # framework/

from lib import evolve, paths  # noqa: E402


def main() -> int:
    try:
        report = evolve.run_evolve(apply=True, quiet=True, source="stop-hook")
        n = len(report.get("applied") or [])
        if n:
            sys.stderr.write(f"[skill-evolution] 自动执行 {n} 项 T0 进化\n")
    except Exception:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
