---
"@lichengwu/skills": minor
---

feat: 社区吸纳 + 迁移分发机制（0.4.0）

- 引入 borrowed/skill-creator（anthropics/skills，Apache-2.0）与 borrowed/writing-skills（obra/superpowers，MIT），borrowed 扩至 7 个技能
- skill-forge 新增 export 工作流 + pack_skills.py：zip 打包 + MANIFEST，三种迁移场景（其他电脑/其他项目/给他人）见 references/distribution.md
- evolve 吸收触发信号表 + 静默纪律 + 成熟度自检（理念来自社区 skill-evolution / Self-Improving-Agent）
- 新增 community-landscape.md：8 个社区项目盘点 + 决策门槛六条
- 26 个技能全部 sidecar 登记；.gitignore 增加 dist/
