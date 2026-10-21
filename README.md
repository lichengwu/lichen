<p>
  <a href="https://github.com/lichengwu/lichen">
    <img alt="lichen" src="https://img.shields.io/github/stars/lichengwu/lichen?style=flat" width="96">
  </a>
</p>

# lichen

> A self-evolving skill framework. Clone it, use your agent as usual — the framework watches, learns, and grows **your** skill system in the background. Export when ready; import anywhere. Fork it and it becomes yours.

**这不只是一个技能库，是一个可以自己进化的技能系统框架。** clone 下来 → 正常用 agent → 框架在后台自动识别值得沉淀的模式、收编本地技能、修补技能卫生问题 → 积累一段时间后一键导出，导入到其他项目 / 电脑 / 给其他人。使用过程中你不需要感知它的存在——除非有事必须找你。

**上游不带任何个人技能。** 仓库里只有框架本身和几个种子演示技能；你的技能在你的 fork 里长出来。架构决策见 [.agents/adr/0002-self-evolving-framework.md](./.agents/adr/0002-self-evolving-framework.md)。

## 快速开始（30 秒）

```bash
git clone https://github.com/lichengwu/lichen.git
cd lichen

python3 framework/bin/lichen init           # 初始化本地运行状态
python3 framework/bin/lichen install-hooks  # 注册无感知自动层（写 settings.json，带备份）
python3 framework/bin/lichen status         # 查看系统状态
```

装完就正常用 agent。框架会：

- **自动收编**：本地 `~/.workbuddy/skills` 等目录出现新技能 → 过检后自动收进 `skills/local/`
- **自动进化留痕**：一个技能被反复编辑 → `generation++` + changelog + 版本快照
- **自动沉淀候选**：同一意图重复出现 3 次以上且无技能覆盖 → 生成候选骨架，摘要里提醒你锻造
- **自动卫生修补**：缺 sidecar、invocation 登记不一致、description 缺触发语、场景标签缺失 → 确定性修复

需要它说话时（有待人工裁决的事项），它只在会话开始时注入**最多 3 行**摘要，且自带下一步命令。

## 变成你自己的进化版 Lichen

```
clone 上游 ──► 正常用 agent ──► skills/local/ 慢慢长出来
                                    │
                                    ▼
                        git push origin <你的 repo>
                                    │
                                    ▼
                         你的专属进化版 Lichen
                                    ▲
                                    │  git merge upstream/main（框架更新）
                                  上游 lichen
```

```bash
#  fork 后第一次
python3 framework/bin/lichen init && python3 framework/bin/lichen install-hooks

#  沉淀丰富后，push 到自己的 repo
git remote add origin git@github.com:<you>/<your>-lichen.git
git push -u origin main

#  上游框架更新时合并回来
git remote add upstream https://github.com/lichengwu/lichen.git
git fetch upstream && git merge upstream/main
```

`framework/`（框架层）和 `framework/state/`（本地运行数据）与你的技能进化**永不冲突**；
`skills/starter/`（种子技能）你已拥有，可改可删。冲突处置的完整预案在内置技能
[`skills/starter/lichen-ops`](./skills/starter/lichen-ops/SKILL.md) 第 4 节。

**给上游做贡献**：框架代码（`framework/`、`scripts/`、文档）走 PR；个人技能不要 PR 回上游——
上游只收种子级技能，个人成果的流通靠 `export` / `import`。

## 内置演示技能（fork 后随你处置）

| 技能 | 演示什么 |
|---|---|
| `starter/lichen-ops` | **如何管理这个框架自身**：CLI 全命令、桶语义、T0/T1、fork-merge、发布纪律、排障。框架自产的「框架管理对象」活样本 |
| `borrowed/writing-skills` | 如何写好 skill（TDD-for-skills：先看 agent 没有技能时怎么失败） |
| `borrowed/skill-creator` | 如何写好 skill（Anthropic 官方闭环：草稿→eval→迭代→description 优化） |
| `borrowed/writing-for-agents` | 如何写好 skill 的文档（指针、负载、层级） |

这些技能同时演示了框架的完整治理面：sidecar 账本、场景标签、生命周期、borrowed 同步纪律。
`skills/local/` 是空的——那是你的进化产物落点（里面有个 README 说明规则）。

## 框架怎么工作（无感知自进化）

```
你的 agent 会话（任何项目目录）
   │  hooks：SessionStart / UserPromptSubmit / PostToolUse / Stop / PreCompact
   ▼
framework/（runtime 层——你感知不到它）
   │  信号：技能写入 · 技能调用 · 本地新技能 · 重复意图
   ▼
analyze → 决策分级
   ├─ T0 自动执行：收编 / generation++ 留痕 / 候选 scaffold / 卫生修补 / 场景轴回填
   └─ T1 人工门：上游合并 / 导入冲突 / 未分类 / 删除技能 / 任何 push
   ▼
摘要（≤3 行，自包含指令）——只在有正事时出现
```

- **hooks 是加速器，不是依赖**：不支持的 harness（如 Codex）用 CLI 手动跑 `framework evolve`，或挂 cron。所有自动能力在 CLI 里完整存在。
- **隐私铁律**：意图信号只存 prompt 的 sha256 与粗词元，原文永不落盘。
- **静默纪律**：默认沉默；PostToolUse/UserPromptSubmit 只记录不输出；Stop 最多一行。
- **兼容 harness**：Claude Code / CodeBuddy / WorkBuddy（hooks 格式同构）；详见 [framework/hooks/README.md](./framework/hooks/README.md)。

## 导出与导入（进化成果走出去）

```bash
# 导出（本地包，不推送）
python3 framework/bin/lichen export --name my-skills --include-config
#   → dist/my-skills/ + dist/my-skills.zip（MANIFEST + 逐文件 sha256）

# 导入（其他电脑 / 其他项目 / 其他人）
python3 framework/bin/lichen import path/to/my-skills.zip
```

导入规则（宪法级）：**本地已进化（generation > 0）的技能永不因导入被静默覆盖**。双方都改过的走逐行三方合并；合并不了就双方暂存、挂人工裁决，不许猜。协议细节见 [framework/README.md](./framework/README.md)。

## 这个仓库自己的纪律

- **[SCOPE.md](./SCOPE.md)**：上游收录政策 + fork 模型 + 脱敏政策 + T0/T1 策略分级。
- **[GLOSSARY.md](./GLOSSARY.md)**：领域语言，技能文档统一使用。
- **[.agents/invocation.md](./.agents/invocation.md)**：user-invoked（编排）/ model-invoked（纪律）双层调用协议。
- **[skills/starter/lichen-ops](./skills/starter/lichen-ops/SKILL.md)**：管理这个框架的使用说明书（内置技能）。
- **[framework/](./framework/)**：自进化运行时。hooks + lib（stdlib-only Python）+ CLI。设计宪法在 [.agents/adr/](./.agents/adr/)。
- **scripts/**：`sync.sh`（本地→仓库同步+脱敏+暂存）、`publish.sh`（唯一发布入口，**人工确认门**）、`redact.sh`（敏感信息扫描，硬红线命中即失败）、`check.sh`（结构检查 + 框架编译检查）。

### 同步与发布（人工确认门）

```
本地 ~/.workbuddy/skills
   │  bash scripts/sync.sh        # rsync 白名单技能 + 自动脱敏 + git add（不提交）
   ▼
仓库暂存区
   │  bash scripts/publish.sh     # check + redact + 变更摘要 + 人工输入 CONFIRM
   ▼
git commit →（--push 时）git push origin
```

没有任何 cron、hook 或 CI 能绕过 `publish.sh` 直接推送。框架的 hooks 与 CLI 只写本地。CI 只做检查（secret scan + 结构检查 + 框架编译），不做发布。

## 许可证

MIT，见 [LICENSE](./LICENSE)。`skills/borrowed/` 内各技能的原始版权归其上游作者：Matt Pocock（mattpocock/skills，MIT）、Anthropic（anthropics/skills，Apache-2.0，随附 LICENSE.txt）、Jesse Vincent（obra/superpowers，MIT）。明细见 [`skills/borrowed/CREDITS.md`](./skills/borrowed/CREDITS.md)。
