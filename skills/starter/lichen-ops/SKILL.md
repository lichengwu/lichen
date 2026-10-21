---
name: lichen-ops
description: 管理 lichen 自进化技能框架本身。当用户要查看框架状态、处理待人工裁决事项、导出/导入技能包、把 clone 变成自己的进化版仓库、排查 hooks 不触发或进化异常、或要给框架本身做贡献（改 framework/ 代码）时使用。覆盖 CLI 全命令、桶语义、T0/T1 分级、fork-merge 工作流与发布纪律。
---

# lichen-ops：管理这个框架本身

你是 lichen 仓库的管理者。本技能是框架的自述说明书——**它管理框架，框架管理其他技能**。
日常进化由 Stop hook 自动完成；本技能覆盖「必须有人知道自己在干什么」的时刻。

## 1. 先看状态，再动手

```bash
python3 framework/bin/lichen status     # 技能盘点 + 进化统计 + 待人工裁决
python3 framework/bin/lichen doctor     # 自检：hooks 注册 / sidecar 完整性 / 状态文件
python3 framework/bin/lichen list       # 按场景分组浏览全部技能
```

纪律：**任何手动操作前先 status**。digest（会话开始时注入的 ≤3 行摘要）说有正事时，
优先处理 `pending` 里的事项——那是框架唯一允许自己打扰你的渠道。

## 2. 桶语义（治理轴，与场景轴分离）

| 桶 | 语义 | 谁写 |
|---|---|---|
| `starter/` | 上游随框架分发的种子技能（本技能就在这） | 上游；fork 后可改可删 |
| `borrowed/` | 外部仓库同步来的技能（保留出处，见 CREDITS.md） | 人工同步 + 改编 |
| `local/` | **你的个人进化产物**：自动收编 + 候选晋升的统一落点 | 框架自动层 |
| `.private/` | 本地治理区（gitignore）：个人向技能，纳入管理但永不公开 | 框架自动层（exclude_skills 命中） |
| `.archive/` | 归档墓地（容量竞争/试用期落选），`unarchive` 可复活 | 框架 + 人工 |

场景轴（`framework list` 的分组）是 sidecar 里的 `categories` 多标签——
一个技能可以同时属于 infra + coding。不要用场景建目录。

## 3. 日常管理命令

```bash
# 进化（Stop hook 自动跑的是 evolve --apply；手动跑建议先预演）
python3 framework/bin/lichen evolve            # 预演：只报告不落盘
python3 framework/bin/lichen evolve --apply    # 执行 T0 动作

# 手动执行一个技能（手动型技能靠它进入 probation/trust 生命周期）
python3 framework/bin/lichen run <技能名>

# 场景标签：自动分类 + 人工修正
python3 framework/bin/lichen list --category coding
python3 framework/bin/lichen categorize <技能> <场景...>   # 词表外标签也写入，doctor 会提示收编

# 交换
python3 framework/bin/lichen export --name my-pack [--include-config]
python3 framework/bin/lichen import path/to/pack.zip      # 本地已进化的技能永不覆盖

# 生命周期
python3 framework/bin/lichen promote <候选>      # 候选骨架 → local/ 正式技能
python3 framework/bin/lichen adopt <路径>        # 手动收编
python3 framework/bin/lichen evaluate <技能>     # 相邻两代指标对比
python3 framework/bin/lichen rollback <技能>     # 从版本快照回滚
python3 framework/bin/lichen archive <技能>      # 归档（不删除）
python3 framework/bin/lichen trust <技能> confirm  # 人工确认信任

# hooks
python3 framework/bin/lichen install-hooks      # 注册（带备份、幂等、marker 双兼容）
python3 framework/bin/lichen uninstall-hooks    # 注销（只删自己的条目）
```

## 4. 把 clone 变成你自己的进化版（fork 模型）

```
git clone <lichen 上游> → cd lichen
python3 framework/bin/lichen init            # 初始化本地状态（幂等）
python3 framework/bin/lichen install-hooks   # 注册无感知自动层
# 然后正常用 agent——local/ 桶会随使用长出来
```

沉淀丰富后，把这个 fork push 到**你自己的 repo**，它就是你的专属进化版 Lichen：

```bash
git remote add origin git@github.com:<you>/<your>-lichen.git
git push -u origin main
```

上游框架更新（新版本 framework/、新种子技能）合并回来：

```bash
git remote add upstream <lichen 上游 URL>
git fetch upstream && git merge upstream/main
```

合并冲突的预期形态与处置：

| 冲突位置 | 原因 | 处置 |
|---|---|---|
| `framework/` | 你改过框架代码 | 正常人工 merge；框架是小而稳定的层，冲突应罕见 |
| `skills/starter/` | 上游更新了种子技能且你改过它 | sidecar 冲突选 `git checkout --theirs`（上游权威）；SKILL.md 冲突二选一或都留 |
| `skills/local/` | — | **永不冲突**：上游没有这个桶的内容 |
| `framework/state/` | — | **永不冲突**：gitignore，纯本地 |
| 文档（README/SCOPE） | 你写了自己的版本 | 保留你的；上游变更值得吸收时手工摘 |

**给上游做贡献的正确姿势**：框架代码（framework/、scripts/、文档）走 PR；
你的个人技能**不要** PR 回上游——上游只收种子/演示级技能，
个人进化成果的流通靠 `export` / `import`（skillpack/1 协议）。

## 5. 发布纪律（上游维护者 / fork 维护者通用）

- `scripts/publish.sh` 是唯一允许 commit/push 的入口：check.sh + redact.sh 全过 → 人工输入确认短语。
- `scripts/sync.sh`：本地 `~/.workbuddy/skills` → 本仓库的白名单同步 + 脱敏 + 暂存（不提交）。
  SYNC_MAP 在脚本顶部，填你自己的桶|技能映射。
- secrets 铁律：`scripts/redact.rules` 与 `scripts/id-watchlist.txt` 是本地秘密存储（gitignore），
  仓库只提交 `.template`。push 时 publish.sh 会检查跟踪守卫与 git 历史守卫。
- 改 framework/ 后的自检清单：`python3 -m py_compile framework/bin/lichen framework/lib/*.py framework/hooks/*.py`
  （用系统最老的 Python 验证兼容，如 3.9）→ `bash scripts/check.sh` → `bash scripts/redact.sh`
  → `framework doctor` → `framework evolve --apply` → 确认 hooks 全部 exit 0。

## 6. 排障

| 症状 | 第一诊断 |
|---|---|
| 进化没发生 | `framework doctor` 看 hooks 是否注册；Stop 事件是否真的触发 |
| digest 不出现 | pending 为空 = 系统静默（正常）；`framework digest` 手动打印 |
| evolve 锁被占用 | 另一会话正在进化（`state/evolve.lock`），超时自动跳过，不硬等 |
| 手动技能无法转正 | 它有没有被 `framework run` 调用过？没有 load 信号，probation 永远不达标 |
| 导入后技能没出现 | `framework status` 的 pending：版本相同（skipped）或冲突（待裁决） |
| 场景分组不对 | `framework categorize <技能> <正确场景>` 人工修正；词表在 config.default.json 的 taxonomy |

## 7. 设计宪法

完整架构决策在 `.agents/adr/`（ADR 纪律：已接受的不改，新决策写新号）。
术语表在 `GLOSSARY.md`——写技能文档前先查，用仓库统一的词。
