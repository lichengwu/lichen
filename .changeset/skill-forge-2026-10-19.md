---
"@skills/skill-forge": minor
---

新增元技能 skill-forge（2026-10-19）

- 五个工作流：inspect（盘点+调用控制治理）/ forge（项目感知生成）/ evolve（受控进化）/ adopt（收编本地技能）/ update（上游三路合并），全部带人工确认门
- 来源登记模型：`.skill-meta.json` sidecar，origin 三态（local-forged / upstream / adopted），本次已登记全部 24 个技能
- 新脚本：inspect_skills.py（只读盘点+治理建议）、forge.py（项目扫描+候选生成）
- 修复 host-precheck.sh 脱敏占位符在 bash 上下文的语法错误
