# 术语表（GLOSSARY）

本仓库自身的领域语言。技能文档和代码注释统一使用这些词，新增概念先加进这里。

| 术语 | 含义 |
|---|---|
| 技能（skill） | 一个 `SKILL.md` + 同目录的引用文件/脚本，agent 可加载的一次性能力包 |
| 桶（bucket） | `skills/` 下的一级分类。框架定义：`starter`（上游种子）/ `borrowed`（外部同步）/ `local`（个人进化产物）/ `.private`（私有治理）/ `.archive`（归档）；`infra`、`macos`、`making` 等场景桶由 fork 者自建 |
| 编排（orchestration） | 把多个纪律原语串成流程的职责；只允许 user-invoked 技能承担 |
| 纪律（discipline） | 单一关注点的可复用实践（TDD、脱敏、诊断循环）；model-invoked 技能的职责 |
| 接缝（seam） | 测试在其上观察行为的公共接口边界（TDD 纪律词汇） |
| frontier | 访谈中前提已 settled、当前可问的问题集合（结构化访谈词汇） |
| 脱敏规则（redact rule） | `scripts/redact.rules` 里的一行：glob \| sed 模式 \| 占位符 |
| 硬红线（hard pattern） | `scripts/redact.sh` 里命中即失败的真实凭据/个人标识模式 |
| 软敏感（soft pattern） | 提示级模式：个人路径、内网地址，套占位符后放行 |
| 同步（sync） | `scripts/sync.sh`：本地 `~/.workbuddy/skills` → 本仓库，只暂存不提交 |
| 发布门（publish gate） | `scripts/publish.sh`：唯一允许 commit/push 的入口，带人工确认 |
| borrowed | 外部仓库同步来的技能（mattpocock/skills、anthropics/skills、obra/superpowers，均宽松许可证），保留出处声明，不参与本地同步 |
| 框架（framework） | `framework/` 目录：挂在 agent 生命周期事件上的无感知自进化运行时（hooks + lib + CLI） |
| 信号（signal） | 框架采集的进化原料：`skill_write` / `skill_use` / `local_seen` / `intent`，落 `state/signals.jsonl` |
| T0 / T1 | 进化策略分级：T0 自动执行（本地、可回滚、留痕）；T1 人工门（合并/删除/外发） |
| 摘要（digest） | 框架注入会话的唯一出口：≤3 行、自包含指令、有正事才出现 |
| 候选（candidate） | `state/candidates/` 里的 scaffold 骨架，证据充分后 `framework promote` 晋升 |
| 版本快照（snapshot） | `state/versions/<id>/<时间>-<sha8>/`：技能的历史版本，导入三方合并的 base 来源 |
| 技能包（skillpack） | `framework export` 产出的交换格式（skillpack/1）：MANIFEST + sha256 + zip |
| 三态计数 | `skill_use` 的 subtype：load（Skill 调用）/ view（Read 翻阅）/ patch（写入编辑）；速率 = loads / 期间请求数 |
| validate 段 | propose→validate→land 三段式的中间段：BLOCK 不过不落盘（转候选暂存），`[提示]` 级对自产产物升级为 BLOCK |
| 试用期（probation） | sidecar `probation_until` / `mature`：自动产物默认 30 天，期内 loads ≥3 自动转正；到期不足挂 T1 |
| 信任门（trust） | sidecar `trust`：自动产物默认 false，loads ≥5 或人工 `framework trust confirm` 转正 |
| 归档（archive） | `framework archive` 移入 `skills/.archive/<桶>/<id>`：容量竞争/试用期落选的去向，`framework unarchive` 复活，永不删除 |
| starter | `skills/starter/`：上游随框架分发的种子技能（fork 后可改可删），与 `local/`（个人进化产物）目录级分离，保证 fork-merge 零冲突 |
| fork 模型 | clone 上游 → 本地进化（local/ 生长）→ push 自己的 repo → merge 上游更新的生命周期；上游只收框架代码与种子技能，不收个人技能 |
| evaluate / rollback | `framework evaluate` 对比相邻两代指标（files/refs/lines/desc_len/hygiene）出 IMPROVED/NO CHANGE/DEGRADED；`rollback` 从版本快照恢复 |
| 场景轴（category） | sidecar `categories` 多标签：一个技能可同时属于 infra + coding；`framework list` 按它分组，与治理轴（桶）分离 |

## 命名约定

- 技能名：小写连字符（`macos-disk-cleanup`），与目录名一致。
- 占位符：`<尖括号>`（`<nas-ip>`、`<proxy-host>`），表示读者必须替换的值。
- 本机路径：一律 `$HOME`，不写 `/Users/<任何人>`。
