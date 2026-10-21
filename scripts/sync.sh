#!/usr/bin/env bash
# sync.sh — 本地 ~/.workbuddy/skills → 本仓库：同步 + 脱敏 + 暂存
#
# 设计原则：
#   - 只同步白名单技能（见下方 SYNC_MAP），个人向技能永不进公开仓库
#   - 同步后自动套用 redact.rules 脱敏，并跑 redact.sh 硬红线扫描
#   - 只 git add 暂存，**不 commit、不 push**——发布必须走 scripts/publish.sh 的人工确认门
#
# 用法：
#   bash scripts/sync.sh           全量同步（按你的 SYNC_MAP）
#   bash scripts/sync.sh <skill>   只同步指定技能
#
# fork 者注意：SYNC_MAP 默认是空的——上游框架不带任何个人技能。
# 把你自己 ~/.workbuddy/skills 里的技能按「桶|技能名」填进来，这个脚本才为你工作。
# 框架的自动收编（evolve → skills/local/）不依赖本脚本；本脚本服务的是
# 「把本地权威副本同步进仓库」的人工工作流。
set -eu
cd "$(dirname "$0")/.."

SRC="${SKILLS_SRC:-$HOME/.workbuddy/skills}"

# 白名单：桶|技能名（不在此表的本地技能永不入库）。示例：
#   SYNC_MAP=("infra|my-server-ops" "macos|my-disk-tool")
SYNC_MAP=()

# 个人向技能名单（与 config.default.json 的 exclude_skills 同源）：
# 命中的技能不被自动收编进 local/，而是进 .private/ 私有桶（gitignore，永不公开）。
EXCLUDED=()

# 手工维护：本地版含不适公开内容，公开版是裁剪后的整理版。
# 不参与自动同步，防止 rsync --delete 把整改成果覆盖掉（见 SCOPE.md「结构裁剪的技能」）。
# 更新方式：本地改完后人工比对差异、手工移植，再走 publish.sh。
CURATED=()

only="${1:-}"
changed=0
# bash 3.2（macOS 自带）+ set -u 下空数组展开会炸，用 ${arr[@]+...} 守卫
for entry in ${SYNC_MAP[@]+"${SYNC_MAP[@]}"}; do
  bucket="${entry%%|*}"
  skill="${entry#*|}"
  [[ -n "$only" && "$skill" != "$only" ]] && continue
  # 手工维护的技能不参与自动同步
  curated=0
  for c in ${CURATED[@]+"${CURATED[@]}"}; do
    [[ "$bucket|$skill" == "$c" ]] && curated=1
  done
  if [[ "$curated" = "1" ]]; then
    echo "SKIP  $skill（手工维护版，不自动同步，见 SCOPE.md「结构裁剪的技能」）"
    continue
  fi
  src="$SRC/$skill"
  dst="skills/$bucket/$skill"
  if [[ ! -d "$src" ]]; then
    echo "SKIP  $skill（本地不存在: $src）"
    continue
  fi
  before=$(find "$dst" -type f 2>/dev/null | wc -l | tr -d ' ')
  rsync -a --delete \
    --exclude '_meta.json' \
    --exclude '_skillhub_meta.json' \
    --exclude '_icon.png' \
    --exclude '*.pyc' \
    --exclude '__pycache__' \
    "$src/" "$dst/"
  after=$(find "$dst" -type f | wc -l | tr -d ' ')
  echo "SYNC  $bucket/$skill（$before → $after 文件）"
  changed=1
done

if [[ $changed -eq 0 ]]; then
  if [[ ${#SYNC_MAP[@]} -eq 0 ]]; then
    echo "SYNC_MAP 为空：本仓库是框架骨架，不带个人技能。"
    echo "把你自己 ~/.workbuddy/skills 里的技能按「桶|技能名」填进脚本顶部的 SYNC_MAP 再跑。"
  else
    echo "没有同步任何技能（only=$only 不在白名单？）"
  fi
  exit 1
fi

# 脱敏 + 硬红线扫描
echo "--- 应用脱敏规则 ---"
bash scripts/apply-redaction.sh --dry-run | tail -3
bash scripts/apply-redaction.sh >/dev/null

echo "--- 硬红线扫描 ---"
bash scripts/redact.sh || { echo "同步中止：先解决红线问题"; exit 1; }

# 暂存但不提交
git add -A skills/
echo "--- 已暂存（未提交、未推送）---"
git diff --cached --stat | tail -25
echo ""
echo "下一步：bash scripts/publish.sh（含人工确认门）"
