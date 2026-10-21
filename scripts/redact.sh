#!/usr/bin/env bash
# redact.sh — 敏感信息扫描器（CI 与本地发布前共用）
#
# 用法：
#   bash scripts/redact.sh           扫描 skills/ + scripts/，硬红线命中即失败（exit 1）
#   bash scripts/redact.sh --quiet   只输出计数
#
# 两级模式：
#   [硬] 真实凭据/密钥 → 直接 fail，没有"确认后放过"这一说
#   [软] 个人路径/内网地址 → 提示应套用 scripts/redact.rules 的占位符
#
# 扫描范围含 scripts/（2026-10-20 安全评审整改 C-1）：此前的盲区是
# "脱敏规则自己藏着明文秘密"——redact.rules 与 redact.sh 的 ID_PATTERNS
# 曾被 git 跟踪，一推远程即全员泄漏。现在这两个本地秘密存储进 .gitignore、
# 仓库只提交模板（*.template），扫描中显式排除；publish.sh 另有守卫
# 检查它们未被 git 跟踪。
set -u
cd "$(dirname "$0")/.."

TARGET="${1:-skills/}"
QUIET=0
[[ "${1:-}" == "--quiet" ]] && QUIET=1

# 本地秘密存储：gitignore，扫描显式排除（它们是密钥库，不是泄漏点；
# 防泄漏靠 .gitignore + publish.sh 的跟踪守卫，不靠扫描自己）。
# .private 同理排除（--exclude-dir 才能剪掉目录）：本地治理区永远不进仓库，
# 扫它只会制造噪声；它若被强推入库，由 check.sh 的 git 跟踪守卫拦截。
SCAN_EXCLUDES=(--exclude=redact.rules --exclude=id-watchlist.txt --exclude-dir=.private)

# ---------- 硬红线：命中即失败 ----------
HARD_PATTERNS=(
  'ghp_[A-Za-z0-9]{36,}'
  'gho_[A-Za-z0-9]{36,}'
  'github_pat_[A-Za-z0-9_]{36,}'
  'sk-[A-Za-z0-9]{20,}'
  'AKIA[0-9A-Z]{16}'
  'BEGIN (RSA|OPENSSH|EC|DSA) PRIVATE KEY'
  'xox[baprs]-[A-Za-z0-9-]{10,}'
  'AIza[0-9A-Za-z_-]{35}'
  '1[3-9][0-9]{9}'
  '[a-zA-Z0-9._%+-]+@(gmail|qq|163|outlook|foxmail|icloud|msn|hotmail|yahoo|sina|sohu|139|189)\.(com|cn)'
)
hard_hits=0
for pat in "${HARD_PATTERNS[@]}"; do
  while IFS= read -r hit; do
    [[ -z "$hit" ]] && continue
    echo "[HARD] $hit"
    hard_hits=$((hard_hits + 1))
  done < <(grep -rEn "${SCAN_EXCLUDES[@]}" -- "$pat" "$TARGET" scripts/ 2>/dev/null || true)
done

# ---------- 软提示：应已套用占位符 ----------
SOFT_PATTERNS=(
  '/Users/[a-z][a-z0-9_]+'
  '192\.168\.'
  '10\.[0-9]+\.[0-9]+\.[0-9]+'
  '172\.(1[6-9]|2[0-9]|3[01])\.[0-9]+\.[0-9]+'
)
soft_hits=0
for pat in "${SOFT_PATTERNS[@]}"; do
  while IFS= read -r hit; do
    [[ -z "$hit" ]] && continue
    echo "[SOFT] $hit"
    soft_hits=$((soft_hits + 1))
  done < <(grep -rEn "${SCAN_EXCLUDES[@]}" -- "$pat" "$TARGET" scripts/ 2>/dev/null || true)
done

# ---------- 个人标识符监视清单（本地维护，永不入库） ----------
# 拥有者的 GitHub handle / 真实姓名 / 已知凭据值放 scripts/id-watchlist.txt
# （gitignore，一行一个 grep -E 正则）；仓库只提交 id-watchlist.template.txt。
# 没有本地清单时监视降级并提示，硬红线不受影响。
# 除仓库自有引用（owner/repo、安装命令）外，这些值出现在任何地方都视为泄漏。
ID_WATCHLIST="scripts/id-watchlist.txt"
ID_PATTERNS=()
if [[ -f "$ID_WATCHLIST" ]]; then
  while IFS= read -r pat; do
    [[ -z "$pat" || "$pat" == \#* ]] && continue
    ID_PATTERNS+=("${pat#cred:}")  # cred: 前缀只对 publish.sh 的历史守卫有意义
  done < "$ID_WATCHLIST"
else
  echo "（未见 $ID_WATCHLIST——个人标识符监视降级；复制 id-watchlist.template.txt 启用）" >&2
fi
ID_ALLOW='(lichengwu/skills|github\.com/lichengwu|npx skills add lichengwu|claude plugin (marketplace )?add lichengwu|claude plugin install lichengwu)'
for pat in "${ID_PATTERNS[@]}"; do
  while IFS= read -r hit; do
    [[ -z "$hit" ]] && continue
    echo "$hit" | grep -qE "$ID_ALLOW" && continue
    echo "[SOFT] $hit"
    soft_hits=$((soft_hits + 1))
  done < <(grep -rEn "${SCAN_EXCLUDES[@]}" -- "$pat" "$TARGET" scripts/ 2>/dev/null || true)
done

if [[ $QUIET -eq 0 ]]; then
  echo "---"
  echo "hard: $hard_hits  soft: $soft_hits"
fi

if [[ $hard_hits -gt 0 ]]; then
  echo "FAIL: 发现 $hard_hits 处硬红线命中。先脱敏再提交。" >&2
  exit 1
fi
if [[ $soft_hits -gt 0 ]]; then
  echo "WARN: 发现 $soft_hits 处软敏感（个人路径/内网地址）。确认已在 redact.rules 中占位，或补充规则后跑 bash scripts/apply-redaction.sh。" >&2
fi
exit 0
