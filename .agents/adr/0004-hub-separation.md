# ADR 0004：Hub 独立成仓——积累与框架物理隔离

- 状态：已接受（2026-10-21，方向确认；v1.2 修订：私有桶入 hub、远程扩展位预留、先不做配置）
- 决策者：佐井
- 上游：[0003-framework-refactor.md](./0003-framework-refactor.md)（技能出库与 starter 桶）、`lichen-多Agent技能分发设计方案-v1.md` §4

## 1. 背景

0003 把个人技能清出上游，但「个人层」仍寄居在框架仓库内（`skills/local/` + `skills/.private/`，gitignore）。多 agent 分发设计暴露出这个寄居的三个问题：

1. **发布即混框架**：fork-as-hub 模式下，push 自有 repo 发布的是「框架副本 + 个人技能」的混合体——别人拿到的是带着某人框架代码的快照，不是一个技能集。
2. **生命周期耦合**：框架仓库要 orphan 重写（洗 cred 历史）、改名、甚至被删了重 clone——个人积累不该跟着这些动作承担风险。
3. **fork-merge 靠纪律**：「local/ 上游永远只有 README」是一条约定，不是结构保证；约定会被 `git add -A`、误配置、手滑打破。

## 2. 决策

**积累进独立 hub 仓库；框架仓库永远干净。** 三分模型：

- **框架仓库**：`framework/` + `scripts/` + `skills/starter` + `skills/borrowed` + 文档。可推上游。
- **Hub 仓库**（默认 `~/Skills`，env `LICHEN_HUB` 可覆盖；**v1 无配置文件**）：公开技能扁平静放 + `private/` 私有桶 + README + .git。私有 remote 起步；`lichen hub publish [--public]` 未来公开。
- **运行时**：`framework/state/`（信号账本）+ `~/.lichen/hub-cache/`（远程模式物化缓存，预留）。

导入导出以 hub 为基本面：export 默认源 hub、import 默认目标 hub；skillpack/1 不变，MANIFEST 增 `hub` 溯源字段。别人的 hub 可 clone + `lichen hub use` 直接接入——hub 内容是标准 Agent Skills 格式，**不装 lichen 也能用**。

**隐私保证换轨（v1.2）**：私有桶从「hub 外运行时层」移入 hub `private/`（佐井拍板：hub 承接一切积累，含私有）。P-8 从物理隔离改为**发布路径结构排除**：export/publish 只枚举 `visibility=public` + `private/` 目录按路径二次排除 + `publish --public` 前置守卫（脱敏扫描 + 显式确认 remote 公开）。硬规则：hub repo 本身永不直接翻转可见性，公开只走 `publish --public`（推独立 public remote，发布物为过滤树）。

**远程扩展位（v1.2）**：hub 位置抽象先行（`parse_hub_uri` → `HubLocation{kind, uri, local_path}`），v1 只实现 local；`git+https` / `git+ssh` / `webdav` / `sftp` 为预留 URI scheme，`hubloc.py` 立桩不填实现。所有 hub 操作只面对本地工作路径，远程差异压缩进 resolve/sync 两个动作。明确不做：认证管理、分布式锁、配置 schema、daemon。

## 3. 后果

**好的**：

- 「merge 上游零冲突」从纪律变成结构保证（两个仓库）。
- 发布物是纯公开技能集（与 anthropics/skills、vercel-labs/agent-skills 同构）——lichen 的差异化回到机制（hooks/治理/交换/分发），不在收藏。
- 私有桶随 hub 版本化/备份/跨机器同步，一个 repo 管全部积累；发布路径结构排除，泄露面为零。
- 框架仓库的 orphan 重写（R0）失去最后顾虑——树本来就纯。
- 远程模式不改上层代码：位置抽象把「hub 在哪」压缩成一个本地路径。

**代价**：

- 两个仓库要管（clone/备份/推送双份）——缓解：`lichen hub status` 一屏看全；hub 首次 push 与框架首推解耦，hub 现在就能推私有 remote。
- 私有桶入 hub 后，「主动公开」成为唯一暴露动作——缓解：结构排除 + 守卫拦底；私有 remote 阶段零暴露。误操作面（手动翻转 repo 可见性）靠 README 硬规则 + doctor 提示收敛。
- `LICHEN_HUB` 指错 = 物化/收编打错地方——缓解：doctor 校验 hub 存在性与目录结构。
- 远程缓存分叉（未来形态）——git 无此问题（pull/push 即同步）；文件协议靠 skillpack/1 快照检测。

**兼容**：hub 位置可指向仓库内 `skills/local`（单仓库党），不推荐——失去「发布即纯技能集」的好处。

**验证计划**：R-B1 实装后跑 `hub migrate`（15 + 2 技能）→ `agents add` 全量物化 → export/import round-trip → `publish --public` 干跑（守卫拦截演练，含 private/ 排除断言）。
