# ADR 0002：自进化技能框架（Self-Evolving Skill Framework）

- 状态：已接受（2026-10-20）
- 上游：[0001-invocation-model.md](./0001-invocation-model.md)（调用协议）、[SCOPE.md](../../SCOPE.md)（收录门槛）
- 触发需求：「任何人 clone 下来都可以在使用过程中进化自己的技能系统；积累后导出所有进化后的技能和配置，其他人或项目可以导入；使用过程无需感知到这个基础技能，它自动识别进化并执行。」

## 1. 问题

0001 解决了「技能怎么被触达」，skill-forge 解决了「技能怎么被管理」，但都隐含一个前提：**人知道框架的存在，并主动驱动它**（跑 sync / 喊元技能 / 手动打包）。

新需求把这个前提拆掉：

1. **零感知**：使用者 clone 后正常用 agent，不需要知道有个"基础技能"在管理一切；
2. **自动识别**：进化信号（新技能出现、技能被反复改、重复手工模式）要被自动捕获并执行对应动作；
3. **可交换**：进化成果（技能 + 配置）能整体导出，被其他项目 / 电脑 / 人导入，且**导入不覆盖本地已进化的内容**。

## 2. 决策

### 2.1 三层架构

```
┌─────────────────────────────────────────────────────┐
│ Exchange 层  framework export / import              │
│   skillpack/1：MANIFEST + sha256 + zip + 三方合并     │
├─────────────────────────────────────────────────────┤
│ Skill 层     skills/<bucket>/<id>/（带 .skill-meta.json）│
│   种子技能（borrowed + 各桶）+ 用户进化产物            │
├─────────────────────────────────────────────────────┤
│ Runtime 层   framework/（hooks + lib + state）        │
│   采集信号 → 分析 → T0 自动执行 → 注入一行摘要        │
└─────────────────────────────────────────────────────┘
```

- **Runtime 层是"无感知"的承载者**：它不是一个需要被调用的技能，而是挂在 agent 生命周期事件上的脚本。人感知不到它，它也从不主动说话——除非有事必须说（见 2.5 静默纪律）。
- **Skill 层是基因库**：clone 时拿到种子；使用中长出 local-forged / adopted 新技能。仓库即系统记录（system of record），git 即进化史。
- **Exchange 层是交换协议**：进化成果的出口与入口。

### 2.2 Runtime 层：hooks 驱动，CLI 兜底

支持的 harness（Claude Code / CodeBuddy / WorkBuddy）hooks 格式同构：`settings.json` 的 `hooks` 字段，按事件注册 `command` 钩子，stdin 传 JSON，SessionStart/UserPromptSubmit 可用 `hookSpecificOutput.additionalContext` 回注上下文。注册 5 个事件：

| 事件 | 脚本 | 职责 | 预算 |
|---|---|---|---|
| SessionStart | `session_start.py` | 扫本地技能目录、读状态、**注入 ≤3 行摘要** | <2s |
| UserPromptSubmit | `user_prompt_submit.py` | 记录意图信号（仅哈希 +  coarse 词元，**永不存原文**） | <0.5s |
| PostToolUse | `post_tool_use.py` | 匹配 `Write\|Edit\|MultiEdit\|Skill`：记录技能写入/调用信号 | <0.5s |
| Stop | `stop.py` | 分析信号 → 执行 T0 进化 → 更新摘要 | <20s |
| PreCompact | `session_start.py`（复用） | 长会话压缩后重注入摘要 | <2s |

**不支持 hooks 的 harness**（Codex 等）不降级为"没有框架"：同一套逻辑由 CLI 驱动——`framework evolve` 手动跑，或挂 cron/launchd 定时跑。hooks 是加速器，不是依赖。这条是硬约束：所有自动能力必须在 CLI 里完整存在。

安全约束：任何 hook 异常都必须 `exit 0` 静默吞掉——**hooks 永远不许弄坏用户的会话**。hook 里不做网络请求（上游检查默认关闭，见 2.4）。

### 2.3 信号分类学（自动识别什么）

信号追加写入 `framework/state/signals.jsonl`（本地运行数据，gitignore）：

| 信号 | 采集点 | 自动动作 |
|---|---|---|
| `skill_write` | PostToolUse 写入目标是某技能目录内的文件（subtype=patch） | 无 sidecar → 补登记；同技能 7 天内 ≥3 次编辑 → `generation++` + 快照 |
| `skill_use` | PostToolUse：Skill 工具调用记 subtype=load；Read 落在技能目录记 subtype=view | 三态计数（loads/views/writes）+ 使用速率（loads/请求数）→ 收编优先级、probation 转正、trust 门、冷门提示 |
| `local_seen` | SessionStart 扫描 `scan_dirs` | 本地出现仓库没有的技能 → 过检后**自动收编**（copy 进 `skills/local/`，origin=adopted） |
| `intent_repeat` | UserPromptSubmit 的 prompt 哈希聚类 | 同一意图 30 天内 ≥3 次且无技能覆盖 → **scaffold 候选骨架**到 `state/candidates/` |
| `upstream_drift` | CLI `framework update-check`（默认关） | borrowed 技能上游有更新 → 三路合并（T1） |

隐私铁律：`intent_repeat` 只存 `sha256(prompt)` 与 coarse 词元（长度 ≥4、去停用词），**prompt 原文永不落盘**。这条写进代码注释和文档。

### 2.4 策略分级：T0 自动 / T1 人工门

| 级别 | 动作 | 确认 |
|---|---|---|
| **T0**（Stop hook 自动执行） | 补 sidecar、hygiene 修补（description 补触发语等确定性修复）、自动收编过检本地技能、`generation++` 留痕、scaffold 候选骨架、版本快照、digest 生成、probation 达标转正（mature+trust）、loads 达标解除 trust=false | 无。全部本地、可 git 回滚、留 changelog |
| **T1**（人工门） | 上游三路合并、导入冲突裁决、probation 到期未达标（充实 or 归档二选一）、容量超限归档、删除技能、**任何 push**（仍是 `publish.sh` 的 CONFIRM 门） | 有。进入 `state/evolution.json` 的 `pending`，digest 里点名 |

T0 的边界由一条性质划定：**只做"可从 git 历史完整恢复"的本地写操作**。凡是可能丢失信息的动作（合并、删除、外发）一律 T1。

### 2.4.1 生命周期治理（2026-10-20 社区对标后新增）

| 机制 | 字段/落点 | 规则 |
|---|---|---|
| **propose→validate→land** | `lib/validate.py` | 任何 T0 落盘前过检：BLOCK（结构缺失/硬红线/海拔超限）不过不落盘，转候选区暂存；`[提示]` 级（海拔）对 adopt 放行、对自产产物（scaffold/promote）升级为 BLOCK |
| **probation 试用期** | sidecar `probation_until` / `mature` | 自动产物（收编/晋升）默认 30 天试用；期内 loads ≥3 → 自动转正；到期未达标 → T1 挂人工（充实或归档，**不自动删**） |
| **trusted 门** | sidecar `trust` | 自动产物 trust=false；loads ≥5 或人工 `framework trust confirm` 后转正 |
| **容量竞争归档** | `skills/.archive/<桶>/<id>` | local 桶超 capacity（默认 40）→ T1 点名最冷门技能，`framework archive` 归档；`framework unarchive` 复活，**归档永不删除** |
| **evaluate / rollback** | `framework evaluate/rollback` | 对比 `state/versions/` 相邻两代指标（files/refs/lines/desc_len/hygiene）→ IMPROVED/NO CHANGE/DEGRADED；rollback 从快照恢复（当前版本先入快照库，可再回滚） |

### 2.5 静默纪律（无感知原则）

1. SessionStart 最多注入 3 行；没有待办就注入空——零感知的默认状态是**沉默**；
2. PostToolUse / UserPromptSubmit 只记录，**永不输出**（stdout 会被追加进上下文，即 token 成本）；
3. Stop 静默执行，最多留一行进度；
4. 需要模型动作时，digest 必须是**自包含指令**（"候选 X 待锻造，证据：…，执行 `framework promote X`"），不依赖模型去调用基础技能——这是"无需感知基础技能"的关键：digest 自己就是入口；
5. skill-forge 元技能退居"大脑"：digest 点名复杂任务时模型按需调用它取参考库，日常进化不经过它。

### 2.6 交换协议 skillpack/1

导出（`framework export`）：

```
dist/<pack-name>/
├── MANIFEST.json          # format/name/时间/逐技能 sha256/逐文件 sha256
├── skills/<id>/...        # 含 .skill-meta.json（来源登记是迁移质量的一部分）
└── config/…               # --include-config 时带上 .agents/invocation.md 等
```

- 导出前硬红线扫描，命中即拒绝（复用 `lib/redact.py`，与 `scripts/redact.sh` 同源）；
- `--mine` 只导 local-forged + adopted（borrowed 可从上游重新获得，不重复搬运）；
- 打包即快照：每个入选技能的当前版本进 `state/versions/<id>/<sha8>/`，这是导入时三方合并的 base 来源；
- MANIFEST 每个条目带 `base_hint`（导出方该版本所基于的上一版哈希）—— originating 机器从未导入过祖先包、`last_seen` 为空时，导入方靠它定位共同基线。

导入（`framework import <pack>`）：

1. 校验 MANIFEST 与全部文件 sha256（防篡改）；
2. 逐技能决策：
   - 本地没有 → 直接安装，记 `imported_from`；
   - 哈希相同 → 跳过，但**登记 last_seen**（版本图连通；否则日后对方再变时找不到基线，可自动的合并会退化成挂人工）；
   - 本地未动（= 上次见过的版本）、包更新 → **快进**合并；
   - 双方都动过 → 以 `last_seen` 版本为 base 做**逐行三方合并**（`lib/merge3.py`）；base 缺失时回退到包内 `base_hint`，再缺失才挂人工；合并前对本地版快照（合并无法用一次原子改名撤销）；
   - 冲突 → 两侧都落 `state/incoming/<id>/`，挂 T1 pending，**不许猜**；
   - origin=upstream 且 upstream_ref 不一致 → 不自动合并，挂 T1（ borrowed 的更新纪律不变）；
3. 进化成果保护是宪法级规则：**本地 generation > 0 的技能永不因导入被静默覆盖**。

配置（`config/`）走同样的三方合并。

### 2.7 与既有机制的关系

- **provenance 三态不变**，`adopted` 语义微调：旧定义"只登记不覆盖、权威副本留原位"；框架版 **copy 进仓库作为系统记录**（export/import 需要单一事实源），原位置不动、`source` 记录原路径。需要原地登记时 `framework adopt --in-place` 保留旧行为。
- **CURATED 名单不变**（防 sync.sh rsync --delete 覆盖手工整理版）；Runtime 的自动收编只从 `scan_dirs` 进 `skills/local/`，**永不碰已有桶**，两条防线互不重叠。
- **publish.sh 仍是唯一 push 入口**，hooks 与 CLI 都只写本地。
- **skill-forge 保留**，职责重构为：digest 点名的复杂任务执行者 + 参考库（provenance/invocation-policy/authoring/distribution）。它的 forge/adopt/export 工作流描述更新为"自动层优先，人工层兜底"。

### 2.8 明确不做

- **不做常驻守护进程**。hooks + CLI 足够；常驻进程是复杂度和故障源。
- **不自动推送、不自动上游更新**。网络动作全部 T1 或默认关闭。
- **不做跨 clone 的进化图谱合并**（多台电脑各自进化后合并是研究问题，不是工程问题）。当前答案：导出→导入→冲突人工裁。
- **不存 prompt 原文**（隐私优先于模式识别精度）。

## 3. 备选方案与拒绝理由

| 方案 | 拒绝理由 |
|---|---|
| 全部进化靠元技能模型调用 | 违背"零感知"；且每次调用都是 token 成本 |
| 常驻 watcher 守护进程 | 故障面大、跨平台差、与 agent 生命周期事件重复 |
| 导入用 git merge/rebase | 要求双方都是同一 git 仓库；zip + sha256 + 显式三方合并对"发给任何人"更普适 |
| 进化信号存原始 prompt | 隐私红线；哈希 + coarse 词元已足够支撑聚类 |

## 4. 后果

- clone 后 `framework install-hooks` 一次，之后无感知；`framework status` 随时可查；
- 进化全部留痕于 sidecar changelog + git，`git log` 即技能进化史；
- 换电脑/换人/换项目 = `framework export` → 传输 → `framework import`；
- 新增 harness 只需补一个 hooks 安装目标，lib 层零改动。
