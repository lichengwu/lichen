#!/usr/bin/env bash
# apply-redaction.sh — 按 scripts/redact.rules 对 skills/ 应用脱敏替换
# 用法：bash scripts/apply-redaction.sh [--dry-run]
# 兼容 macOS bash 3.2；sed 兼容 GNU / BSD 两种 -i 语法
set -eu
cd "$(dirname "$0")/.."

# portable in-place sed: GNU 用 `sed -i`，BSD 用 `sed -i ''`
if sed --version 2>/dev/null | grep -q GNU; then
  sed_i() { sed -i "$@"; }
else
  sed_i() { sed -i '' "$@"; }
fi

DRY_RUN=0
[[ "${1:-}" == "--dry-run" ]] && DRY_RUN=1

# 规则表解析：优先本地 redact.rules（gitignore，含真实值）；
# 缺失则套用提交的 template（占位规则，无实际替换）并提示——
# 全新 clone 没有本地秘密存储是正常状态，不该让同步链路断掉。
RULES="scripts/redact.rules"
if [[ ! -f "$RULES" ]]; then
  if [[ -f "scripts/redact.rules.template" ]]; then
    echo "（未见 $RULES——本地秘密存储未配置；套用 template（占位规则，无实际替换）。" >&2
    echo " 需要真实脱敏时：cp scripts/redact.rules.template scripts/redact.rules 后填入本地规则）" >&2
    RULES="scripts/redact.rules.template"
  else
    echo "ERROR: 既无 scripts/redact.rules 也无 scripts/redact.rules.template" >&2
    exit 1
  fi
fi

applied=0
while IFS='|' read -r glob pat rep; do
  [[ -z "${pat:-}" ]] && continue
  [[ "$pat" == \#* ]] && continue
  if [[ -z "$glob" ]]; then
    src="skills/"
  else
    src="$glob"
  fi
  while IFS= read -r f; do
    [[ -z "$f" ]] && continue
    if [[ $DRY_RUN -eq 1 ]]; then
      echo "[dry-run] $f  <=  s|$pat|$rep|g"
    else
      sed_i "s|$pat|$rep|g" "$f"
      echo "redacted: $f  (s|$pat|$rep|g)"
    fi
    applied=$((applied + 1))
  done < <(grep -rl -- "$pat" $src 2>/dev/null || true)
done < "$RULES"

echo "---"
echo "total files touched: $applied"
