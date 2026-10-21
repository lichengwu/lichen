---
"skills": patch
---

feat: 社区对标 P1 借鉴全量落地（0.5.2）

- 三态计数：skill_use 带 subtype（load/view/patch），速率进 status
- propose→validate→land：lib/validate.py，BLOCK 不过不落盘
- probation 试用期 + 容量竞争归档（framework archive/unarchive）
- trusted 门：sidecar trust 字段 + loads 阈值自动转正
- evaluate/rollback 子命令（相邻两代指标 + 快照恢复）
- publish.sh 发布链接 gitleaks
- 修复：adopt 误拦海拔 WARN、unarchive 空目录残留、check.sh 归档计数
