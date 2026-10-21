# ADR 0003：框架化重构——技能出库与 starter 桶

- 状态：已接受（2026-10-21）
- 决策者：佐井
- 上游：[0002-self-evolving-framework.md](./0002-self-evolving-framework.md)（自进化框架架构）、[SCOPE.md](../../SCOPE.md)（收录政策）

## 1. 背景

0002 把仓库定位为「可克隆的技能进化框架」，但实现里混入了两样东西：

1. **佐井的个人技能库**（27 个现役：infra/macos/making/agent/local 桶）——这是「内容」，
   不是「框架」。上游带着它们，意味着每个 clone 的人都被强制接收一个人的家庭实验室技能，
   且上游的收录门槛（可公开、已脱敏）给框架分发增加了持续的人工治理负担。
2. **个人工作流耦合**：`sync.sh` 的 SYNC_MAP、`exclude_skills`、`ignore_skills`、
   `category_defaults` 全是佐井本机的映射。

同时，fork 模型（clone → 本地进化 → push 自有 repo → merge 上游）需要一个目录级保证：
**个人进化产物与上游内容永不冲突**。当时的桶设计（infra/macos/making/agent + local）把
「上游内容」和「个人产物」混在同一个命名空间里——fork 者在 infra/ 里放自己的技能，
与上游 infra/ 的技能在 git 层面同域，merge 时冲突。

## 2. 决策

### 2.1 技能出库

上游 lichen 只保留四类内容：框架运行时（`framework/`）、工具链（`scripts/`）、
种子技能（`skills/starter/`）、写作类 borrowed（`skills/borrowed/`）。
佐井的 22 个个人技能导出为 skillpack（`framework export` 全桶，含 .private），
存放于仓库外，由个人渠道分发。**上游收录政策写入 SCOPE.md，PR 回上游的个人技能被拒绝。**

理由：

- 框架的价值在机制（hooks/自动化/管理/交换），不在内容；内容应该长在 fork 里。
- 出库消除上游的持续治理负担（脱敏、收录门槛、许可证审查都只对框架自身负责）。
- 个人技能进上游 = 每个人 clone 时被迫接收 + 上游历史永久携带。

### 2.2 starter 桶（新）

`skills/starter/` = 上游随框架分发的种子技能。与 `local/`（个人进化产物）**目录级分离**：

- fork 者 merge 上游时，`starter/` 的更新正常 merge（种子技能用户已拥有，可改可删，
  冲突时 sidecar 选上游权威、SKILL.md 人工裁量）；
- `local/` 上游永远只有 README，**零冲突**；`framework/state/` gitignore，**零冲突**。

首个种子技能 `lichen-ops`（自产，origin=local-forged，execution=manual）是
「如何管理这个框架自身」的说明书，同时是「框架如何管理一个技能」的活样本：
完整 sidecar、场景标签、changelog 一应俱全。fork 者改它、删它都随意。

### 2.3 borrowed 收缩

`borrowed/` 从 7 个收缩到 3 个，只留「如何写好 skill」类
（writing-skills / skill-creator / writing-for-agents）。tdd/code-review/
diagnosing-bugs/grilling 出库——它们是工程纪律，属于 fork 者的个人选择，
不是框架演示的必要内容。（出库前已导出进佐井个人包。）

### 2.4 fork 工作流成文

README 新增「变成你自己的进化版 Lichen」：clone → init → install-hooks →
local/ 生长 → push 自有 repo → merge 上游。贡献规则：框架代码走 PR，
个人技能走 export/import，不 PR 回上游。

## 3. 后果

**好的**：

- 上游仓库体积与治理面大幅收缩（29 技能 → 4 演示技能）。
- fork-merge 的冲突面从「整个 skills/ 命名空间」收缩到「starter/ 一个桶」。
- 新 clone 者的第一体验是「框架 + 说明书」，不是「别人的技能库」。
- SYNC_MAP / exclude_skills 等个人配置清空为模板，fork 者填自己的。

**代价**：

- 上游失去「内容吸引力」（star  magnet 从 27 个技能变成 4 个演示）——
  接受：框架的价值主张是机制，且 export/import 让成果流通不依赖上游收藏。
- starter 技能被 fork 者改坏后，上游更新时的 sidecar 冲突需要人工裁量——
  缓解：lichen-ops 第 4 节给出 `git checkout --theirs` 的明确指引。
- sync.sh 空 SYNC_MAP 时 exit 1（带指引文案）——这是特性：提醒 fork 者填自己的白名单。

**验证**：出库后 init/evolve/hooks/export/import/doctor 全链路在小技能集上通过；
fork 模拟（干净 clone → import 佐井个人包 → 29 技能进入 local/ 与 .private/ →
再 export round-trip）通过。详见 PRD v2.2 附录 B。
