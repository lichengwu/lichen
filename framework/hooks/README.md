# framework/hooks/ — 无感知层的执行体

5 个事件钩子，把框架挂在 agent 生命周期上。格式与 Claude Code / CodeBuddy / WorkBuddy 同构（settings.json 的 `hooks` 字段，stdin 传 JSON）。

## 注册

```bash
python3 framework/bin/lichen install-hooks [--target claude|codebuddy|workbuddy|auto]
                                          [--scope user|project] [--plain] [--dry-run]
python3 framework/bin/lichen uninstall-hooks [--target ...] [--scope ...]
```

- `auto`（默认）：探测配置目录已存在的 harness；本机实测命中 `~/.workbuddy/settings.json`；
- 写入前自动备份（`settings.json.bak-<时间戳>`）；幂等（已注册则跳过）；卸载只删框架自己的条目；
- `--plain`：命令写绝对路径（适配不经过 shell 的 hook runner）；默认 `${LICHEN_HOME:-<绝对路径>}` 形式，shell 会展开；
- **settings 变更不热加载**——注册后重启会话生效；
- 仓库移动位置后重跑 install-hooks（或设置 `LICHEN_HOME` 环境变量指向新位置）。

## 事件与职责

| 事件 | 脚本 | 匹配 | 职责 | 预算 |
|---|---|---|---|---|
| SessionStart | `session_start.py` | `startup` | 扫本地技能目录记 `local_seen`；注入 ≤3 行摘要；注入后消费摘要 | <2s |
| PreCompact | `session_start.py` | `*` | 长会话压缩后重注入摘要 | <2s |
| UserPromptSubmit | `user_prompt_submit.py` | `*` | 记 `intent` 信号（哈希+词元，去重） | <0.5s |
| PostToolUse | `post_tool_use.py` | `Skill\|Read\|Write\|Edit\|MultiEdit\|NotebookEdit` | 三态计数：Skill→`skill_use(load)`；Read→`skill_use(view)`；写入→`skill_write(patch)` | <0.5s |
| Stop | `stop.py` | `*` | 分析信号 → 执行 T0 → 更新摘要（stderr 最多一行） | <20s |

## 纪律（为什么可以无感知）

1. **默认沉默**：没有待办就零输出。PostToolUse / UserPromptSubmit 只记录、不输出——它们的 stdout 会进上下文，即 token 成本；
2. **永不破坏会话**：任何异常静默 `exit 0`。hooks 是观察者，不是参与者；
3. **摘要自包含**：注入的摘要带下一步命令（`framework promote X`），模型不需要知道基础技能的存在；
4. **只写本地**：hooks 不碰 git、不碰网络、不推任何东西。

## 不支持的 harness

 hooks 不可用时（Codex 等），框架降级为 CLI 驱动——能力完全一致，只是从"自动"变"手动/定时"：

```bash
python3 framework/bin/lichen evolve --apply   # 手动跑一轮进化
# 或挂 cron / launchd，例如每小时：
# 0 * * * * cd /path/to/skills && python3 framework/bin/lichen evolve --apply --quiet
```

## 排障

| 现象 | 检查 |
|---|---|
| hooks 不触发 | `framework doctor` 看注册状态；确认重启过会话；`/hooks` 面板确认 |
| 注册了但没摘要 | `framework digest` 看当前摘要；摘要只在"有增量/有待办"时非空 |
| python3 找不到 | hook 命令用 `python3`——确认 PATH 里有；或用 `install-hooks --plain` 后手工改命令为绝对路径 |
| 想暂停自动层 | `framework uninstall-hooks`（保留全部本地数据）；或 `state/config.json` 里把 `auto.*` 全设 false |
| 想暂停某个自动动作 | `state/config.json` 的 `auto.*` 单独关（如 `generation_bump: false`）；阈值都在 `thresholds` 段 |
