#!/usr/bin/env bash
# check.sh — 仓库健康检查（CI 与本地发布前共用）
#
# 检查项：
#   1. 每个技能目录有 SKILL.md，且 frontmatter 含 name + description
#   2. name 与目录名一致
#   3. borrowed/ 下每个技能按 sidecar 来源保留出处声明（上游许可证要求），Apache 技能随附 LICENSE
#   4. borrowed/ 不在 sync 白名单里（防同步覆盖上游改编）
#   5. skills/ 下没有 _meta.json / _skillhub_meta.json / _icon.png 等本地元数据
set -u
cd "$(dirname "$0")/.."

errors=0
err() { echo "ERROR: $1"; errors=$((errors + 1)); }

# 1+2: frontmatter 与命名
while IFS= read -r skillmd; do
  dir=$(dirname "$skillmd")
  base=$(basename "$dir")
  name=$(awk '/^---/{f=!f; next} f && /^name:/{print $2; exit}' "$skillmd")
  desc=$(awk '/^---/{f=!f; next} f && /^description:/{print $2; exit}' "$skillmd")
  [[ -z "$name" ]] && err "$skillmd 缺少 frontmatter name"
  [[ -z "$desc" ]] && err "$skillmd 缺少 frontmatter description"
  if [[ -n "$name" && "$name" != "$base" ]]; then
    err "$skillmd name=$name 与目录名 $base 不一致"
  fi
done < <(find skills -name SKILL.md -not -path '*/.archive/*' | sort)

# 3: borrowed 出处声明——按每个技能 sidecar 记录的实际来源校验（多上游友好）
#    来源标识映射：source 里的 github:<owner>/<repo> → SKILL.md 必须包含该 <owner>/<repo>
python3 - <<'PYEOF' || exit 1
import json, re, sys
from pathlib import Path

errors = 0
for skillmd in sorted(Path("skills/borrowed").rglob("SKILL.md")):
    d = skillmd.parent
    text = skillmd.read_text(encoding="utf-8")
    sidecar_p = d / ".skill-meta.json"
    if not sidecar_p.exists():
        print(f"ERROR: {skillmd} 缺少 .skill-meta.json 来源登记")
        errors += 1
        continue
    sidecar = json.loads(sidecar_p.read_text(encoding="utf-8"))
    source = sidecar.get("source") or ""
    m = re.search(r"github:([^/]+)/([^/#]+)", source)
    if not m:
        print(f"ERROR: {skillmd} sidecar source 无法解析上游: {source!r}")
        errors += 1
        continue
    upstream = f"{m.group(1)}/{m.group(2)}"
    if upstream not in text:
        print(f"ERROR: {skillmd}缺少 {upstream} 出处声明（上游许可证要求）")
        errors += 1
    # 许可证文本随附检查（Apache-2.0 的 skill-creator）
    if (sidecar.get("license") or "").startswith("Apache"):
        if not (d / "LICENSE.txt").exists():
            print(f"ERROR: {skillmd} Apache-2.0 技能缺少随附 LICENSE.txt")
            errors += 1
sys.exit(1 if errors else 0)
PYEOF

# 4: 本地元数据不得入库
meta=$(find skills -name '_meta.json' -o -name '_skillhub_meta.json' -o -name '_icon.png' | head -5)
if [[ -n "$meta" ]]; then
  err "发现本地元数据文件（应被 sync.sh 排除）: $meta"
fi

# 4b: 私有桶绝不入库（PRD v2 P-8 治理/发布分离的守卫）。
#     .private 是 gitignore 的本地治理区；被 git add -f 强推 = 发布事故，
#     这里在 CI 与本地发布门双重拦截。内容卫生（空目录/脱敏）不查 .private——
#     它永远不进仓库，查了只会制造狼来了噪声（防泄漏靠 gitignore + 本检查）。
if git ls-files --error-unmatch skills/.private >/dev/null 2>&1; then
  err "skills/.private 被 git 跟踪——私有桶（个人向技能）绝不入库"
fi

# 5: 空目录（.private/.archive 除外：本地治理区，非发布内容）
while IFS= read -r d; do
  err "空目录: $d"
done < <(find skills -type d -empty -not -path 'skills/.private/*' -not -path 'skills/.private' -not -path '*/.archive/*')

# 6: framework 编译与配置有效性（自进化运行时）
if ! python3 -m py_compile framework/lib/*.py framework/hooks/*.py framework/bin/lichen 2>/tmp/.fw-compile.err; then
  err "framework Python 编译失败: $(cat /tmp/.fw-compile.err | head -3)"
fi
rm -f /tmp/.fw-compile.err
python3 - <<'PYEOF' || exit 1
import json, sys
errors = 0
for f in ("framework/config.default.json", "framework/hooks/settings.fragment.json"):
    try:
        json.load(open(f, encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        print(f"ERROR: {f} 不是合法 JSON: {e}")
        errors += 1
sys.exit(1 if errors else 0)
PYEOF

if [[ $errors -gt 0 ]]; then
  echo "---"
  echo "FAIL: $errors 个问题" >&2
  exit 1
fi
echo "OK: 所有检查通过 ($(find skills -name SKILL.md -not -path '*/.archive/*' | wc -l | tr -d ' ') 个技能)"
