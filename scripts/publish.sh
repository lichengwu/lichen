#!/usr/bin/env bash
# publish.sh — 发布门：所有推送到 GitHub 的动作必须经过人工确认
#
# 铁律：
#   1. 本脚本是唯一允许执行 git commit + git push 的入口
#   2. 推送前展示完整变更摘要 + 逐技能文件清单
#   3. 要求人工输入确认短语（默认 "CONFIRM"）才能继续
#   4. 确认前跑 check.sh + redact.sh，任何失败即中止
#   5. 没有 --push 就只 commit；--push 才推远端
#
# 用法：
#   bash scripts/publish.sh             commit（需人工确认）
#   bash scripts/publish.sh --push      commit + push origin（需人工确认）
#   bash scripts/publish.sh --dry-run   只展示将发生什么，不执行
set -eu
cd "$(dirname "$0")/.."

DO_PUSH=0
DRY_RUN=0
for arg in "$@"; do
  case "$arg" in
    --push) DO_PUSH=1 ;;
    --dry-run) DRY_RUN=1 ;;
    *) echo "未知参数: $arg"; exit 1 ;;
  esac
done

CONFIRM_PHRASE="CONFIRM"

echo "=========================================="
echo " 发布前检查（publish gate）"
echo "=========================================="

# 0. 必须是 git 仓库
git rev-parse --git-dir >/dev/null 2>&1 || { echo "不是 git 仓库"; exit 1; }

# 1. 结构检查
echo "[1/5] check.sh ..."
bash scripts/check.sh

# 2. 敏感信息扫描
echo "[2/5] redact.sh ..."
bash scripts/redact.sh || { echo "中止：存在硬红线命中"; exit 1; }

# 2a. secrets 治理守卫（2026-10-20 评审 C-1）：本地秘密存储绝不入库。
#     redact.sh 的扫描会排除这两个文件，所以要用 git 跟踪状态来兜底——
#     它们一旦被跟踪，推远程即永久泄漏（历史污染，事后要 filter-repo）。
echo "[2a/5] secrets 治理守卫 ..."
for f in scripts/redact.rules scripts/id-watchlist.txt; do
  if git ls-files --error-unmatch "$f" >/dev/null 2>&1; then
    echo "中止：$f 被 git 跟踪。本地秘密存储必须只在 .gitignore 里。" >&2
    echo "  修复：git rm --cached $f（保留本地文件），并确认 .gitignore 有条目。" >&2
    exit 1
  fi
done

# 2b. git 历史守卫（仅 --push）：凭据类监视值不许出现在任何历史提交里。
#     曾经入库又删掉不够——推上去就是永久公开。命中即拒绝推送，
#     给出洗历史命令；洗完（SHA 全变）再推。没有远程时可以推迟到首推前，
#     但推的那一刻必须干净。
if [[ $DO_PUSH -eq 1 && -f scripts/id-watchlist.txt ]]; then
  hist_dirty=0
  while IFS= read -r line; do
    [[ "$line" == cred:* ]] || continue
    val="${line#cred:}"
    [[ -z "$val" ]] && continue
    if [[ -n "$(git log --all --oneline -S "$val" 2>/dev/null | head -1)" ]]; then
      echo "中止：git 历史中仍含凭据明文（匹配监视值）。首推前必须洗历史：" >&2
      echo "  git filter-repo --replace-text <(printf '%s==><redacted>\\n' '<值>') --force" >&2
      echo "  （会重写全部提交 SHA；无远程时现在做成本最低）" >&2
      hist_dirty=1
    fi
  done < scripts/id-watchlist.txt
  [[ $hist_dirty -eq 1 ]] && exit 1
fi

# 2b. gitleaks（如本机安装；借鉴 1ai-skills 的发布链扫描）
echo "[2b/5] gitleaks ..."
if command -v gitleaks >/dev/null 2>&1; then
  gitleaks detect --no-git --redact --verbose 2>&1 | tail -5 || {
    echo "中止：gitleaks 发现疑似密钥"; exit 1; }
else
  echo "（未安装 gitleaks，跳过——安装: brew install gitleaks）"
fi

# 3. 变更摘要
echo "[3/5] 变更摘要"
echo ""
if git diff --cached --quiet; then
  echo "（暂存区为空——先跑 bash scripts/sync.sh 或手工 git add）"
else
  git diff --cached --stat
  echo ""
  echo "--- 变更文件清单 ---"
  git diff --cached --name-status
fi
UNTRACKED=$(git status --porcelain | grep '^??' | wc -l | tr -d ' ')
if [[ "$UNTRACKED" -gt 0 ]]; then
  echo ""
  echo "警告：有 $UNTRACKED 个未跟踪文件未暂存："
  git status --porcelain | grep '^??' | head -10
fi

# 4. 人工确认门
echo ""
echo "=========================================="
if [[ $DRY_RUN -eq 1 ]]; then
  echo " DRY-RUN：以上即将发生。不执行任何写操作。"
  echo "=========================================="
  exit 0
fi

if [[ $DO_PUSH -eq 1 ]]; then
  echo " 将执行: git commit + git push origin HEAD"
else
  echo " 将执行: git commit（不推送）"
fi
echo " 输入 $CONFIRM_PHRASE 确认，其他任何输入取消"
echo "=========================================="
printf "> "
read -r answer
if [[ "$answer" != "$CONFIRM_PHRASE" ]]; then
  echo "已取消。没有提交任何东西。"
  exit 1
fi

MSG="${PUBLISH_MSG:-chore: sync skills}"
if git diff --cached --quiet && [[ "$UNTRACKED" -eq 0 ]]; then
  echo "暂存区为空且无未跟踪文件，无可提交内容。"
  exit 0
fi
git commit -m "$MSG"
echo "已提交: $(git rev-parse --short HEAD)"

if [[ $DO_PUSH -eq 1 ]]; then
  BRANCH=$(git branch --show-current)
  git push origin "$BRANCH"
  echo "已推送: origin/$BRANCH"
else
  echo "未推送。需要推送时: bash scripts/publish.sh --push"
fi
