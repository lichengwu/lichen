# 借鉴与致谢（CREDITS）

`skills/borrowed/` 下的技能来自三个开源仓库，均为宽松许可证（MIT / Apache-2.0），允许修改再分发。
本仓库是**框架骨架**，borrowed 只保留「如何写好 skill」这一类——它们是种子演示的一部分，
fork 后随你处置。

## 来源一：mattpocock/skills（MIT，中文化改编）

- 仓库：https://github.com/mattpocock/skills
- 作者：Matt Pocock（Total TypeScript / aihero.dev）
- 许可证：MIT License

| 本仓库技能 | 原始技能 | 改编内容 |
|---|---|---|
| `borrowed/writing-for-agents` | `productivity/writing-for-agents` | 中文化，末节改为指向本仓库的 `.agents/invocation.md` |

## 来源二：anthropics/skills（Apache-2.0，保留英文原文）

- 仓库：https://github.com/anthropics/skills
- 作者：Anthropic
- 许可证：Apache License 2.0（完整文本见 `borrowed/skill-creator/LICENSE.txt`）

| 本仓库技能 | 原始技能 | 改编内容 |
|---|---|---|
| `borrowed/skill-creator` | `skills/skill-creator` | 原文照录 + 中文适配说明块；eval/benchmark 脚本链完整保留 |

## 来源三：obra/superpowers（MIT，保留英文原文）

- 仓库：https://github.com/obra/superpowers
- 作者：Jesse Vincent
- 许可证：MIT License

| 本仓库技能 | 原始技能 | 改编内容 |
|---|---|---|
| `borrowed/writing-skills` | `skills/writing-skills` | 原文照录 + 中文适配说明块；跨技能相对引用已内联化 |

## 为什么借鉴而不是造轮子

「如何写好 skill」是生态里被验证最充分的一类实践，且这三个来源覆盖了互补的视角：
`skill-creator` 是 Anthropic 官方权威（自带 eval 工具链）；`writing-skills` 提供
TDD-for-skills 视角（先看 agent 在没有技能时失败，再写技能）；`writing-for-agents`
讲给 agent 写文档的杠杆（指针、负载、层级）。本仓库的原创价值在 `framework/` 运行时、
`scripts/` 工具链与 `starter/` 种子技能——技能内容本身是 fork 者自己的进化空间。

## 同步时的注意事项

- `borrowed/` 下的技能**不参与** `scripts/sync.sh` 的本地同步（它们来自上游，不是本地 `.agents` 目录）。
- 上游更新走 `framework update-check`（只读漂移检查）+ 人工三路合并。
- 每个 SKILL.md 保留出处/适配声明，删除声明视为违规（`scripts/check.sh` 会检查）。
- 各来源许可证要求保留版权声明：
  - MIT：https://github.com/mattpocock/skills/blob/main/LICENSE 、 https://github.com/obra/superpowers/blob/main/LICENSE
  - Apache-2.0：`borrowed/skill-creator/LICENSE.txt`
