# Changelog

本仓库的所有 notable 变更。格式遵循 [changesets](https://github.com/changesets/changesets) 生成的记录。

## 0.5.2

社区对标 P1 借鉴全量落地（2026-10-20）。上一轮（0.5.1）列出的 6 项 P1 补课本次全部实装，
各自独立可验证。详细对比仍见工作区 `社区同类项目横向对比报告.md`。

### 新增

- **use/view/patch 三态计数**（借鉴 AutoHarness MNG）：`skill_use` 带 subtype——Skill 调用记
  load、Read 落在技能目录记 view、写入编辑记 patch（`skill_write`）。速率 = loads / 期间
  请求数，`framework status` 出 Top5 速率表；loads 同时驱动 probation 与 trust 判定。
- **propose→validate→land 三段式**（借鉴 AutoHarness promoter）：`lib/validate.py` 落盘前
  过检。BLOCK（frontmatter 缺失 / 硬红线 / 海拔超限）不过不落盘，转候选区暂存挂人工；
  海拔等 `[提示]` 级对 adopt 放行、对自产产物（scaffold/promote）升级为 BLOCK。
- **probation 试用期 + 容量竞争归档**（借鉴 AutoHarness curator）：自动产物（收编/晋升）
  默认 30 天试用（sidecar `probation_until`/`mature`），期内 loads ≥3 自动转正；到期不足
  挂 T1（人工充实或归档，**不自动删**）。local 桶超 capacity（默认 40）→ T1 点名最冷门，
  `framework archive` 归档到 `skills/.archive/`，`framework unarchive` 复活——归档永不删除。
- **trusted 门**（借鉴 SkillMaxxing）：sidecar `trust` 字段，自动产物默认 false；
  loads ≥5 自动转正或人工 `framework trust confirm|revoke`。
- **evaluate / rollback 子命令**（借鉴 unisone）：`framework evaluate <技能>` 对比
  `state/versions/` 相邻两代指标（files/refs/lines/desc_len/hygiene）→ IMPROVED /
  NO CHANGE / DEGRADED；`framework rollback <技能> [--to sha8]` 从快照恢复
  （当前版本先入快照库，可再回滚，恢复动作本身留 changelog）。
- **发布链 gitleaks**（借鉴 1ai-skills）：`publish.sh` 在 CONFIRM 门前扫一道
  （本机装有则启用，未装提示跳过）。
- 新 CLI：`evaluate` / `rollback` / `archive` / `unarchive` / `trust`；
  新配置阈值：`probation_days` / `probation_min_uses` / `trust_min_loads` / `capacity`。

### 修复

- `_do_adopt` 曾把海拔 WARN 当 BLOCK，导致超 25 行的既有本地技能被误拒收编——
  现按 `blocking()` 分级放行（测试实抓）。
- `unarchive` 后归档桶残留空目录触发 check.sh 空目录检查失败——复活后清理空桶
  （沙箱拒绝删除时包容错，不影响复活本身）。
- `check.sh` 技能计数排除 `skills/.archive/`（归档区不是现役技能）。

### 机制

- PostToolUse matcher 增加 `Read`（view 信号的采集前提）；hooks 注册片段与
  `install_hooks.py` 同步更新，本机 `~/.workbuddy/settings.json` 已重装生效。
- ADR 0002 增补 §2.4.1「生命周期治理」；sidecar schema（provenance.md）增补
  `probation_until` / `mature` / `trust` 字段（旧 sidecar 无这些字段视为已成熟已信任）。
- `community-landscape.md` P1 清单全部标记已落地。

## 0.5.1

社区横向对比后的借鉴落地（2026-10-20）。调研 9 个同类自进化框架（AutoHarness / SkillClaw /
Hermes / 1ai-skills / self-improving-skills / darwin / SkillMaxxing / Claudeception / EvoSkill
/ SkillFoundry），完整报告在工作区 `社区同类项目横向对比报告.md`。

### 新增

- MANIFEST 条目带 `base_hint`（导出方该版本所基于的上一版哈希）：originating 机器从未导入过
  祖先包（`last_seen` 为空）时，导入方靠它定位三方合并的共同基线——此前这类场景只能挂人工。

### 修复

- **originating 机器三方合并基线断链**：导出方本地进化后再导入回包，因 `last_seen` 为空、
  快照库无基线而退化为"找不到共同基线"。现按 `last_seen → base_hint` 两级解析。
- **版本图断链**：导入哈希相同的包时不再只跳过——同时登记 `last_seen` 并确保快照存在，
  否则日后对方再变时找不到基线，本可自动的合并会退化成挂人工。

### 机制

- description 触发语**前置**（借鉴 AutoHarness 截断教训）：索引/扫描表面按行截断，
  追加在尾部的触发 cue 会整段丢失。`_do_fix_triggers` / `_do_scaffold` 改为前置插入。
- 导入三方合并前对本地版快照（借鉴 AutoHarness curator 纪律：合并是原子改名撤不回的操作）。
- `templates/SKILL.md.tmpl` 增加「撰写纪律」：触发条件前置、正文 ≤25 非空行（海拔控制，
  细节进 references/）、步骤必须可执行可验证。
- `skill-forge/references/community-landscape.md` 增补第六节：自进化框架赛道深调，
  10 个项目逐一过决策门槛；P1 借鉴清单（use/view/patch 三态、propose→validate→land、
  probation 归档、trusted 门、evaluate/rollback、gitleaks）待下轮实装。

## 0.5.0

自进化技能框架（2026-10-20）。仓库从"个人技能收藏"重构为"可克隆进化的基础框架"。

### 新增

- **framework/ 运行时**（ADR 0002）：挂在 agent 生命周期事件上的无感知自进化层。5 个 hook（SessionStart / PreCompact / UserPromptSubmit / PostToolUse / Stop）+ stdlib-only Python 库 + CLI（`framework/bin/framework`：init/status/evolve/doctor/export/import/promote/adopt/install-hooks/uninstall-hooks/update-check/digest）。
- **信号 → 决策 → 动作**：技能写入/调用、本地新技能发现、重复意图（只存 prompt 哈希 + 粗词元，原文永不落盘）四类信号；T0 自动执行（收编、generation++ 留痕、候选 scaffold、卫生修补）与 T1 人工门（上游合并、导入冲突、删除、push）分级。
- **skillpack/1 交换协议**：`framework export` 整包导出（MANIFEST + 逐文件 sha256 + zip，可带 .agents/ 配置）；`framework import` 三方合并导入——本地已进化（generation>0）的技能永不静默覆盖，合并不了双方暂存挂人工。共同基线来自 `state/versions/` 版本快照。
- **`skills/local/` 桶**：框架自动收编与候选晋升的统一落点。首个自动收编产物：`scrcpy-mirror`（自 `~/.workbuddy/skills` 过检后自动入桶）。
- **候选机制**：重复意图 ≥3 次且无技能覆盖 → 自动生成带 EVIDENCE.md 的候选骨架；`framework promote <名>` 晋升。
- 文档：ADR 0002（设计宪法）、framework/README.md、framework/hooks/README.md（harness 兼容矩阵 + 排障）。

### 机制

- `exclude_skills` 配置与 SCOPE「排除清单」同源：个人向 / 内置副本技能永不自动收编。
- `.gitignore` 增加 `framework/state/`（运行数据本地化：信号、进化账本、快照、候选）。
- sidecar 新增 `base_sha256` / `source_sha256` / `last_seen_sha256` / `imported_from` 字段（向后兼容）；`dir_hash` 排除 sidecar 自身，打破自引用。
- adopted 语义更新：收编 = copy 进 `skills/local/` 作为系统记录（export/import 需要单一事实源），原位置不动；旧行为保留为 `framework adopt --in-place`。
- skill-forge 重构为"自动层优先，元技能兜底"：日常进化归 framework，复杂操作（forge/update/export/冲突裁决）归它；version 2.0.0。
- `check.sh` 扩展：framework 全部 Python 编译检查 + JSON 配置有效性；`package.json` 增加 `fw:*` 脚本。

## 0.4.0

社区吸纳 + 迁移分发机制（2026-10-20）。

### 新增

- `skills/borrowed/skill-creator`：自 [anthropics/skills](https://github.com/anthropics/skills) 完整引入（Apache-2.0，随附 LICENSE.txt），「撰写技能」的官方权威——草稿→eval→迭代→description 优化闭环 + eval/benchmark 脚本链。保留英文原文便于三路合并，顶部加中文适配说明块。
- `skills/borrowed/writing-skills`：自 [obra/superpowers](https://github.com/obra/superpowers) 引入（MIT，Jesse Vincent），TDD 应用于技能编写——先看 agent 没有技能时怎么失败，再写技能。跨技能相对引用已内联化；补 `anthropic-best-practices.md`、`testing-skills-with-subagents.md`、`persuasion-principles.md` 与图表脚本。
- `skill-forge` 第六工作流 **export** + `scripts/pack_skills.py`：单技能/多技能/整桶/全仓打包为 zip（zip 内以技能名为根，解压即用），生成 MANIFEST.json（origin/来源/许可证/sha256 汇总）。打包前自动硬红线扫描，命中即拒绝。脚本只写本地 `dist/`，不推送不上传——分发动作永远由人执行。
- `skill-forge/references/distribution.md`：三种迁移场景的操作路径——其他电脑（git clone）、其他项目（解压到 `.claude/skills/` 或 `.agents/skills/`）、给其他人（zip 私发 / 公开仓库 / 技能市场上架）。
- `skill-forge/references/community-landscape.md`：外部生态地图。盘点 8 个社区项目（撰写类/进化类/框架类），记录吸纳决策与理由；新增「决策门槛」六条（许可证/重叠度/可运行性/无硬外部依赖/维护活跃/理念相容），以后评估新项目照此执行。
- `evolve` 工作流吸收三条社区理念：触发信号表（失败/纠正/重复/过期/复盘五类）+ 静默纪律（防 token 黑洞）+ 成熟度自检四项（真实使用验证/触发退出条件/自包含/失败模式已记录，四项不全不进入 export）。

### 机制

- `borrowed/CREDITS.md` 扩展为三上游结构（mattpocock MIT / anthropics Apache-2.0 / superpowers MIT），更新时的许可证义务逐条列明。
- 全部 26 个技能完成 sidecar 登记（upstream 7 / adopted 18 / local-forged 1）。
- `.gitignore` 增加 `dist/`（打包产物本地生成，不入库）。
- skill-forge 自身进化至 generation 2（frontmatter version 1.1.0）。

## 0.3.0

新增元技能 skill-forge 与来源登记机制（2026-10-19）。

### 新增

- `skills/agent/skill-forge`：元技能，管理技能全生命周期。五个工作流——inspect（盘点 + 调用控制治理，只读）、forge（项目感知生成）、evolve（受控进化，generation 递增 + changelog 留痕）、adopt（收编本地技能，只登记不覆盖）、update（上游三路合并，冲突人工裁决）。铁律：所有写操作人工确认门、upstream 永不静默覆盖、敏感信息零容忍。
- 来源登记模型：每个技能目录带 sidecar `.skill-meta.json`，origin 三态（local-forged / upstream / adopted）+ source + local_edits + generation + changelog。本次已为全部 24 个技能完成登记（borrowed 5 个登记为 upstream@`49dd158d1076`，其余 18 个为 adopted，skill-forge 自身为 local-forged gen1）。
- `scripts`：`inspect_skills.py`（frontmatter 解析、sidecar 校验、description 双读者检查、相对引用验尸、shebang 感知的脚本语法检查、高副作用启发式分 STRONG/WEAK 两级）与 `forge.py`（扫描 slash 命令 / package.json / Makefile / pyproject / 文档重复命令产出候选，`--apply` 生成骨架）。

### 修复

- `docker-osx-vnc-drive`：`host-precheck.sh` 第 163 行脱敏占位符 `<ssh-port>` 在 bash 上下文不是合法 token（`for p in <ssh-port>` 被解析为重定向），改为 `${SSH_PORT:-2222}`——上一轮脱敏引入的真 bug，由 inspect_skills.py 的语法检查抓出。

## 0.2.0

安全评审整改（2026-10-18）：公开版清除了全部实测凭据与不适公开的内容。

### 修复

- `docker-osx-vnc-drive`：清除实测附录与脚本中的真实凭据（VNC 密码、登录账号口令、kcpassword 密文、SSH 端口），替换为占位符；kcpassword 自检向量改用通用示例（`example`）；`osx-ctl.sh` 的 VNC 密码从默认值改为必填；补充 VNC 绑 `0.0.0.0` 的安全提示（仅限可信内网，外网访问走 SSH 隧道）。
- `agent-browser-ops`：移除反检测/指纹伪装层（patchright、Camoufox、`stealth_chrome.py` / `stealth_firefox.py`、`references/antidetect.md`、L3/L4 阶梯与反爬分层参考），保留 L0–L2 与全部 token 账单纪律；`verify.sh` / `bench.sh` / 基线文件同步裁剪。
- `adb-phone-control`：移除业务线引用（`phone-daily-rewards` / `alipay-wealth-sync` / `testin-crowdtest`）与「金融/理财类 App 全量取数」专篇；App 名中性化为框架术语（H5 页 / Flutter 页）；移除腾讯 CDN 的 JS 质询求解配方，保留换 URL 形态的正当解法。

### 机制

- `scripts/redact.rules`：补充 `docker-osx-vnc-drive` 的凭据类占位规则（顺序敏感：先具体后通用），防止下次同步回灌。
- `scripts/redact.sh`：硬红线补充 msn/hotmail/yahoo/sina 等邮箱域；新增个人标识符监视清单（GitHub handle / 真实姓名 / 已知凭据值，仓库自有引用白名单除外）。
- `scripts/sync.sh`：新增 CURATED 机制——`agent-browser-ops` 与 `adb-phone-control` 的公开版为手工维护，不再被自动同步覆盖。
- `.gitignore`：补充 `__pycache__/` 与 `*.pyc`。
- `LICENSE`：版权行改用 GitHub handle。

## 0.1.0

初始公开版本。

### 新增

- 四个原创桶：`infra`（5 个技能）、`macos`（3 个）、`making`（4 个）、`agent`（6 个），全部来自佐井日常 `.agents` 目录，经脱敏后公开。
- `borrowed` 桶：5 个改编自 mattpocock/skills（MIT）的工程纪律技能，中文化并保留出处声明。
- 仓库自身纪律：`SCOPE.md`（收录门槛 + 排除清单 + 脱敏政策）、`GLOSSARY.md`、`.agents/invocation.md`（双层调用协议）、`.agents/adr/0001`。
- 发布机制：`scripts/sync.sh`（同步 + 脱敏 + 暂存）、`scripts/publish.sh`（人工确认门）、`scripts/redact.sh`（硬红线/软敏感扫描）、`scripts/check.sh`（结构检查）、`scripts/apply-redaction.sh`（脱敏规则应用）。
- CI：PR 上跑结构检查 + secret scan + changeset 强制；release workflow 只开版本 PR，不自动对外发布。
