---
"agent-browser-ops": patch
"adb-phone-control": patch
"docker-osx-vnc-drive": patch
---

安全评审整改（2026-10-18）：公开版清除全部实测凭据与不适公开内容——docker-osx-vnc-drive 脱敏（VNC 密码/登录口令/kcpassword 密文/SSH 端口 → 占位符）；agent-browser-ops 移除反检测层（保留 L0–L2 与 token 纪律）；adb-phone-control 移除业务线引用与金融取数专篇。机制侧：redact.rules 补凭据规则、redact.sh 加个人标识符监视、sync.sh 加 CURATED 手工维护机制。详见 CHANGELOG 0.2.0。
