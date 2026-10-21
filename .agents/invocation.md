# 调用协议（invocation）

每个 `SKILL.md` 都是一个技能。把它们分开的唯一轴是**调用（invocation）**：谁能触达它。

- **User-invoked**：只有人类打字输入名字才触达。frontmatter 设 `disable-model-invocation: true`（Claude Code）。`description` 是**面向人**的：一行给浏览 slash 命令的人看的摘要，剥掉触发词列表。职责是**编排**。
- **Model-invoked**：模型或用户都能触达。默认：不设 `disable-model-invocation`。`description` 是**面向模型**的，保留丰富的触发措辞（"当用户想…、提到…、说…时使用"），让自动触发生效。职责是承载**可复用的纪律**。

一个 user-invoked 技能可以调用 model-invoked 技能，但永远不能调用另一个 user-invoked 技能。

## 跨技能调用

技能之间的依赖用显式的 **"Call the Skill tool with <name>"** 指令表达，不用散文里提一句 `/skill` 盼着它触发，也不用跨文件夹的深链接。命名工具才是让它 firing 的东西：多数 harness 把技能调用暴露为模型可调的 tool，写明它比在散文里丢一个 `/name` 命中率高。

Skill tool 一次只接受一个技能名。一步需要两个技能，就是两次调用（"Call the Skill tool twice, for X and Y"），不是一次带俩名。

## borrowed/ 桶的特殊规则

`skills/borrowed/` 全部是 model-invoked。它们来自 mattpocock/skills（MIT），`scripts/sync.sh` **永不覆盖**它们；上游更新时人工评估后重新改编。

## local/ 桶的特殊规则

`skills/local/` 是 framework 自动层（hooks + CLI）的产物桶：自动收编的本地技能与晋升的候选骨架。它们不参与 `sync.sh`（不是同步目标，是进化产物）；调用模式由各技能 frontmatter 自己声明，sidecar 的 `invocation` 字段必须与之一致（framework 的 T0 卫生修补会自动对齐）。

## 与上游的差异

本仓库不照搬上游的 `agents/openai.yaml` 双 harness 元数据方案（那是为 Claude Code + Codex 双官方市场准备的）。本仓库面向 skills.sh 生态（`npx skills` 安装），元数据从简；如果未来进入官方插件市场，再补 ADR 记录这个决策。
