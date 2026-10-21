---
"framework": minor
---

社区横向对比后的借鉴落地（2026-10-20）：

- MANIFEST 新增 `base_hint` 字段：originating 机器（从未导入祖先包、last_seen 为空）
  也能定位三方合并基线，修复"找不到共同基线"退化为挂人工的问题
- 导入哈希相同的包时登记 last_seen，保持版本图连通
- description 触发语前置（AutoHarness 截断教训）：索引表面按行截断，尾部 cue 会丢
- 三方合并前对本地版快照（合并无法用一次原子改名撤销）
- 模板增加撰写纪律：触发前置 / 正文海拔 ≤25 非空行 / 步骤可执行
- community-landscape.md 增补自进化框架赛道深调（10 个项目过决策门槛）
