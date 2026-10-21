---
"@lichengwu/skills": minor
---

feat: 自进化技能框架（0.5.0）

- 新增 framework/ 运行时：5 个 hooks（无感知层）+ stdlib-only lib + CLI；信号四类（写入/调用/本地发现/重复意图），T0 自动 / T1 人工门分级
- 新增 skillpack/1 交换协议：export 整包（MANIFEST+sha256+zip）/ import 三方合并，本地 generation>0 永不静默覆盖
- 新增 skills/local/ 桶（自动收编 + 候选晋升落点）；首个自动收编产物 scrcpy-mirror
- 隐私：意图信号只存 prompt 哈希 + 粗词元；framework/state/ gitignore
- adopted 语义改为 copy 进仓库（系统记录），--in-place 保留旧行为；sidecar 新增 base/source/last_seen 哈希字段
- skill-forge 重构为"自动层优先，元技能兜底"（version 2.0.0）；check.sh 增加 framework 编译检查
