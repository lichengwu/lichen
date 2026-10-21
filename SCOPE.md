# 范围（SCOPE）

本仓库是**可克隆的技能进化框架骨架**：一个无感知自进化运行时（`framework/`）+ 种子演示技能（`skills/starter/`、`skills/borrowed/`）。任何人 clone 下来，正常用 agent，技能系统会在使用中自动生长（`skills/local/`）；积累后 `framework export` 导出，`framework import` 导入到其他项目 / 电脑 / 人的 clone。

**上游不收个人技能。** 你的 infra/macos/making 等场景技能属于你的 fork，不属于上游——
详见下方「上游收录政策」。

## 上游收录政策（这个仓库收什么）

上游 lichen 只收四类内容：

| 类别 | 位置 | 说明 |
|---|---|---|
| 框架运行时 | `framework/` | hooks + lib（stdlib-only Python）+ CLI。**框架的核心价值在这** |
| 工具链 | `scripts/` | sync / publish / redact / check / CI 辅助 |
| 种子技能 | `skills/starter/` | 上游自产的演示技能（当前：`lichen-ops`——管理框架自身）。fork 后可改可删 |
| 写作类 borrowed | `skills/borrowed/` | 「如何写好 skill」的三个外部来源（见 CREDITS.md），演示 borrowed 机制 |

**PR 回上游的个人技能会被拒绝。** 个人进化成果的流通渠道是 `export` / `import`
（skillpack/1 协议）和你自己的 fork——那不是上游该收藏的东西。

## fork 模型（这个仓库怎么被用）

```
上游 lichen（本仓库）
   │  git clone / fork
   ▼
你的 clone
   ├── framework/        merge 上游更新（框架层，小且稳定）
   ├── skills/starter/   种子技能（你的了，可改可删）
   ├── skills/borrowed/  外部同步（人工评估上游更新）
   ├── skills/local/     你的进化产物（**永不与上游冲突**）
   └── framework/state/  本地运行数据（gitignore，**永不与上游冲突**）
   │
   │  git push origin <你的 repo>
   ▼
你的专属进化版 Lichen
```

上游更新合并：`git fetch upstream && git merge upstream/main`。
冲突的预期形态与处置见 `skills/starter/lichen-ops` 第 4 节。

## 收录门槛（对 starter/ 与 borrowed/ 的新增）

1. **真实使用。** 它在真实会话里被反复调用过，不是想象中会有用的东西。
2. **可公开。** 不含个人财务、个人账号、业务线数据。
3. **已脱敏。** 不含真实内网地址、本机用户名路径、凭据（`scripts/redact.sh` 硬红线零命中）。
4. **自包含或可自包含。** 技能依赖的环境信息走占位符（`<nas-ip>`、`$HOME`），读者能替换成自己的。
5. **种子级定位。** 只收「演示框架能力」或「教人写好 skill」的；场景专业技能（infra/macos/making 的具体实现）留给 fork。

## .private/ 桶（本地治理区）

`skills/.private/` 是 gitignore 的私有技能桶：个人向、手动执行（要手机/GUI/凭据、agent 不能全自动）的技能在这里被治理。

- 纳入方式：`exclude_skills` 名单命中 → evolve 自动收编；或 `framework adopt <路径>` 后手工移入。
- 守卫：`check.sh` 检查它未被 git 跟踪（被 `git add -f` 强推即 FAIL）；`export` 默认不含它，只有显式 `--skill <id>` / `--bucket .private` 才打私有包（自用迁移场景）。
- 手动执行的技能靠 `framework run <名>` 记录使用信号——没有它，手动技能对 probation/trust 生命周期是隐形的，永远无法转正。

## 脱敏政策

- `scripts/redact.rules` 是脱敏规则表（glob|sed 模式|占位符），新增个人路径/内网地址时必须先加规则再同步。**该文件含真实凭据的匹配原串，属本地秘密存储：gitignore，永不入库；仓库只提交 `redact.rules.template` 占位模板**（2026-10-20 评审 C-1 整改——此前它被 git 跟踪，一推远程即全员泄漏）。
- `scripts/redact.sh` 分两级，扫描范围含 `scripts/`（排除上述本地秘密存储与 `.private/`）：
  - **硬红线**（真实密钥、私钥、手机号、个人邮箱）：命中即失败，CI 与发布门都过不了。
  - **软敏感**（`/Users/<name>`、`192.168.*` 等）：提示套用占位符；确认为示例值（如 `127.0.0.1`、RFC1918 文档示例）可保留，但要在 PR 里说明。
- 原则：宁可多套一个占位符，不可漏一个真地址。
- **个人标识符监视**：真实值放本地 `scripts/id-watchlist.txt`（gitignore；`cred:` 前缀 = 凭据类，额外受 push 时的 git 历史守卫检查）。除仓库自有引用（owner/repo、安装命令）外出现即报警。仓库只提交 `id-watchlist.template.txt`。
- **两道 secrets 守卫**（`publish.sh`）：① 两个本地秘密存储文件一旦被 git 跟踪即中止；② `--push` 时凭据类监视值若还存在于任何历史提交即拒绝推送（先 `git filter-repo` 洗历史再推）。

## 桶总览（治理轴，与场景轴分离）

| 桶 | 语义 | git 跟踪 |
|---|---|---|
| `starter/` | 上游种子技能（fork 后可改可删） | 是 |
| `borrowed/` | 外部仓库同步来的技能（保留出处） | 是 |
| `local/` | 个人进化产物：自动收编 + 候选晋升 | 是（fork 后由你填） |
| `.private/` | 私有治理区：纳入管理、永不公开 | 否（gitignore） |
| `.archive/` | 归档墓地，可复活，永不删除 | 否（gitignore） |

场景轴是 sidecar 的 `categories` 多标签（`framework list` 分组），不建场景目录——
目录是单亲的，技能天然跨场景（fusion-mcp = making + coding）。

## 策略分级：T0 自动 / T1 人工门

| 级别 | 动作 | 确认 |
|---|---|---|
| **T0**（Stop hook 自动执行） | 自动收编过检技能、`generation++` 留痕、候选 scaffold、卫生修补（补 sidecar / 修 invocation / 补触发语 / 场景轴回填）、版本快照、digest 生成 | 无。全部本地、可 git 回滚、留 changelog |
| **T1**（人工门） | 上游三路合并、导入冲突裁决、未分类技能、probation 到期未达标（充实或归档）、容量超限归档、删除技能、**任何 push** | 有。挂 `state/evolution.json` 的 `pending`，摘要点名 |

T0 的边界性质：**只做可从 git 历史完整恢复的本地写操作**。凡是可能丢失信息的动作（合并、删除、外发）一律 T1。

## 运行状态不入库

`framework/state/`（信号、进化账本、版本快照、候选、导入暂存）是本地运行数据，已 gitignore。它含你的使用痕迹（哈希化的意图信号），属于你，不属于仓库。

## 发布机制（人工确认门）

- `scripts/sync.sh`：本地 → 仓库同步 + 脱敏 + 暂存。**不 commit、不 push。** SYNC_MAP 默认空（上游不带个人技能）。
- `scripts/publish.sh`：唯一允许 commit/push 的入口。推送前必须人工输入确认短语，且 check.sh + redact.sh 全过才进入确认环节。
- 没有任何自动化（cron、hook、CI）可以绕过 `publish.sh` 直接推送。
