# framework/ — 自进化运行时

技能系统的"免疫系统 + 神经系统"。挂在 agent 的生命周期事件上，无感知地采集信号、执行进化、在有事时注入一行摘要。设计宪法：[.agents/adr/0002-self-evolving-framework.md](../.agents/adr/0002-self-evolving-framework.md)。

```
framework/
├── bin/lichen          CLI（唯一人类入口）
├── lib/                   stdlib-only Python 库
│   ├── paths.py           仓库定位、运行目录、默认配置
│   ├── meta.py            技能索引、sidecar、版本快照
│   ├── signals.py         信号层（state/signals.jsonl）
│   ├── scan.py            本地技能发现、意图词元、覆盖启发式
│   ├── analyze.py         信号 → 决策（纯函数）
│   ├── evolve.py          执行 T0、更新进化账本、候选晋升
│   ├── validate.py        propose→validate→land 的 validate 段
│   ├── lifecycle.py       probation 试用期 / trust 门 / 归档复活
│   ├── evaluate.py        相邻两代指标对比 / 快照回滚
│   ├── digest.py          摘要渲染（静默纪律的出口）
│   ├── merge3.py          逐行三方合并
│   ├── exchange.py        skillpack/1 导出 / 导入 / 校验
│   ├── redact.py          硬红线扫描（与 scripts/redact.sh 同源）
│   └── install_hooks.py   hooks 注册 / 注销（幂等，带备份）
├── hooks/                 5 个事件的钩子脚本（永远 exit 0）
├── templates/             候选骨架模板
├── config.default.json    默认配置（用户覆盖写 state/config.json）
└── state/                 本地运行数据（gitignore）
    ├── signals.jsonl      信号流
    ├── evolution.json     进化账本（计数器 / pending / 技能统计 / 摘要）
    ├── versions/<id>/<时间>-<sha8>/   版本快照（导入合并的 base 来源）
    ├── candidates/        候选骨架（scaffold 产物，待锻造）
    └── incoming/          导入暂存（冲突的对方版本 / 解包的 zip）
```

## CLI 参考

| 命令 | 作用 | 写文件？ |
|---|---|---|
| `framework init` | 初始化运行状态（幂等） | 是（state/） |
| `framework status` | 技能盘点 + 进化统计 + 候选 + 待人工裁决 | 否 |
| `framework list [--category X] [--bucket Y] [--origin Z] [--json]` | 按场景分组浏览（多标签技能出现在多组） | 否 |
| `framework categorize <技能> <场景...> \| --auto \| --backfill` | 场景轴打标 / 修正 / 全量回填 | 是（sidecar，带锁） |
| `framework evolve [--apply]` | 分析信号；`--apply` 执行 T0（Stop hook 自动跑的是 apply） | 是 |
| `framework doctor` | 自检：hooks 注册 / sidecar 完整性 / 状态文件 | 否 |
| `framework export [选项]` | 导出 skillpack/1 包到 dist/ | 是（dist/ + 快照） |
| `framework import <包>` | 导入并三方合并 | 是（冲突只暂存） |
| `framework promote <候选>` | 候选骨架晋升为 skills/local/ 正式技能 | 是 |
| `framework adopt <路径> [--in-place]` | 手动收编本地技能 | 是 |
| `framework run <技能>` | 手动执行入口：记录使用信号（loads+1）+ 打印提示。手动执行的技能靠它进入 probation/trust 生命周期 | 是（信号） |
| `framework install-hooks` / `uninstall-hooks` | 注册 / 注销 hooks（认 framework/ 与 lichen/ 两种 marker，R0 改名后旧注册仍卸得掉） | 是（settings.json，带备份） |
| `framework update-check` | borrowed 技能上游漂移检测（只读，需网络） | 否 |
| `framework digest` | 打印当前摘要（调试） | 否 |
| `framework evaluate <技能>` | 相邻两代指标对比 → IMPROVED/NO CHANGE/DEGRADED | 否 |
| `framework rollback <技能> [--to sha8]` | 从版本快照回滚（当前版本先入快照库） | 是 |
| `framework archive <技能>` | 归档到 `skills/.archive/`（可复活，永不删除） | 是 |
| `framework unarchive <技能>` | 从归档区复活 | 是 |
| `framework trust <技能> <confirm\|revoke>` | 人工确认 / 撤销信任 | 是 |

## 信号 → 决策 → 动作

| 信号 | 采集点 | 阈值（默认） | 自动动作（T0） |
|---|---|---|---|
| `skill_write`（patch） | PostToolUse 写入落在技能目录 | 7 天内同技能 ≥3 次 | `generation++` + changelog + 快照 |
| `skill_use`（load） | PostToolUse 工具为 Skill | — | 三态计数；速率 = loads/请求数（status 可见） |
| `skill_use`（view） | PostToolUse 工具为 Read 且落在技能目录 | — | 查看计数（人/模型在翻这个技能） |
| `local_seen` | SessionStart 扫描 scan_dirs | 出现即收编 | validate 过检 → 公开桶 copy 进 `skills/local/`（sidecar origin=adopted + 30 天试用期）；`exclude_skills` 命中 → 进 `skills/.private/` 私有桶（纳入治理、永不公开）；未过检 → 暂存候选 |
| `intent` | UserPromptSubmit（只存哈希+词元） | 30 天内同类 ≥3 次且无技能覆盖 | scaffold 候选骨架（含证据，strict 自检后才留） |
| 卫生问题 | evolve 时扫描 | 出现即修 | 补 sidecar / 修 invocation / 补触发语 / 场景标签回填（关键词计分，不占自动预算） |
| probation / trust | evolve 时按 loads 统计 | 试用期 30 天、loads≥3 转正；loads≥5 解除 trust=false | mature + trust 转正（T0） |

**T1（人工门，不自动做）**：上游技能合并、导入冲突、probation 到期未达标（充实或归档）、容量超限归档、删除技能、场景标签猜不出来（uncategorized：`framework categorize <名> <场景>` 补）、任何 push。T1 进入 `state/evolution.json` 的 `pending`，摘要里点名；uncategorized 在补上标签后自动销账。

## 并发与爆炸半径（2026-10-20 评审整改）

- **写路径串行化**：多个 harness / 会话的 Stop hook 会并发跑 `evolve --apply`。所有 read-modify-write（账本、sidecar、快照）在 `state/evolve.lock` 排他锁内完成（stdlib fcntl）；锁外只做只读分析。拿不到锁 → 本次跳过，下轮补上，绝不交叉写。
- **每日自动执行上限**：`thresholds.max_auto_per_day`（默认 10，0=不限）。防"信号抖动一夜改半个仓库"；达到上限当日改为预演，status/digest 可见。

## 生命周期治理（ADR 0002 §2.4.1）

```
自动产物（收编/晋升）→ probation 30 天 → loads≥3 转正 mature+trust
                                    ↘ 到期不足 → T1：人工充实 或 framework archive
trust=false 的产物 → loads≥5 或 framework trust confirm → 转正
容量竞争 → local 桶超 40 → T1 点名最冷门 → framework archive → framework unarchive 复活
evaluate → 相邻两代指标（files/refs/lines/desc_len/hygiene）→ rollback 从快照恢复
```

## 场景轴：分类体系（2026-10-21，DDR-5）

技能多起来之后，单靠桶（治理轴）不够用——桶回答"从哪来、走哪条治理路径"，
不回答"用户想干什么时该想到它"。场景轴是第二根轴，存在 sidecar 的
`categories` 多标签里：

```
bucket（治理轴，物理目录）        category（场景轴，sidecar 多标签）
infra / macos / making / …  ←→  infra / coding / design / office / …
"它从哪来"                    "你想干什么"
```

**为什么不建场景目录**：目录是单亲的而技能天然跨场景（fusion-mcp = making +
coding；macos-nas-ops = infra + macos）；治理轴已占物理目录，再切一层会让
sync/archive/update-check 全链路复杂化；场景演化时改标签是一行 sidecar，
改目录是 git mv + sync map 全改。另外 SKILL.md frontmatter 是 agentskills.io
开放标准（规范无 category 字段），lichen 私有元数据一律进 sidecar——borrowed
同步覆盖 frontmatter 但不覆盖 sidecar，标签活得久。

**受控词表 + 自动分类**：词表在 `config.default.json` 的 `taxonomy`（label +
关键词），用户可在 `state/config.json` 增量扩展（deep_merge，不用抄全表）。
evolve 的卫生预跑对缺标签技能做确定性关键词计分（id/name 命中 2 分、
description 1 分、正文 reinforcing 1 分；≥2 分入标签，最多 3 个），猜不出来
就留空并挂 T1 请人工分类——宁缺勿滥，不硬贴。自动分类不消耗
`max_auto_per_day` 预算（元数据卫生 ≠ 内容进化），预演模式只计数不落盘。

**日常用法**：

```bash
framework list                          # 按场景分组浏览全部技能
framework list --category coding        # 只看编程场景
framework categorize windmill-ops infra coding   # 手动打标（替换式）
framework categorize grilling --auto    # 用关键词结果打标
framework categorize --backfill         # 全量回填（首次迁移/改词表后）
framework export --category office      # 导出整个场景包分享
```

**词表外标签**：手动指定的词表外场景仍会写入（自己的词汇不该被挡），doctor
警告并提示收编进词表；导入时对方机器的标签取并集，词表外原样保留。

## 配置（state/config.json 覆盖默认值）

```json
{
  "auto": {"adopt_local_skills": true, "hygiene_fix": true,
           "scaffold_candidates": true, "generation_bump": true},
  "thresholds": {"edit_burst": 3, "edit_burst_days": 7,
                 "intent_repeat": 3, "intent_repeat_days": 30,
                 "probation_days": 30, "probation_min_uses": 3,
                 "trust_min_loads": 5, "capacity": 40,
                 "max_auto_per_day": 10},
  "scan_dirs": ["~/.workbuddy/skills", "~/.claude/skills", "~/.agents/skills", "..."],
  "exclude_skills": ["alipay-wealth-sync", "phone-daily-rewards", "testin-crowdtest"],
  "ignore_skills": ["xlsx", "pptx"],
  "digest_max_lines": 3
}
```

双名单（治理/发布分离）：`exclude_skills` = 不公开但纳入治理（自动收编进 `.private/` 私有桶）；`ignore_skills` = 噪声，连私有桶也不进。均与 SCOPE.md 同源。

## skillpack/1 交换协议

```
dist/<pack>/
├── MANIFEST.json     # format/name/时间/逐技能 sha256/逐文件 sha256
├── skills/<id>/...   # 含 .skill-meta.json（来源登记随包携带）
└── config/...        # --include-config 时带 .agents/ 树
```

导入决策树（每个技能）：

```
本地没有            → 安装，记 imported_from
内容哈希相同        → 跳过
本地未动、包更新    → 快进
包未动、本地已更新  → 保留本地
双方都改过          → base=state/versions 快照，逐行三方合并
  ├─ 合并干净       → 应用 + changelog + 快照
  └─ 有冲突         → 对方版本暂存 state/incoming/<id>/ + T1 pending（本地不动）
origin=upstream     → 不自动合并，挂 T1（走 skill-forge update 工作流）
```

宪法：**本地 generation > 0 的技能永不因导入被静默覆盖。**

## 隐私与安全

- 意图信号只存 `sha256(prompt)` + coarse 词元（ASCII 词 + CJK 二元组），prompt 原文永不落盘；
- `state/` 整体 gitignore——运行数据是你的，不是仓库的；
- 收编 / 导出前过硬红线扫描（密钥、手机号、私钥、个人邮箱），命中即拒绝自动动作；
- hooks 任何异常静默 exit 0——**框架永远不许弄坏你的会话**；
- 唯一的网络动作是 `update-check`（显式命令，默认不自动跑）。
