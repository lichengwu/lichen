# Changesets

本仓库用 [changesets](https://github.com/changesets/changesets) 管理技能变更的版本与 CHANGELOG。

## 规则

- 任何改变 `skills/` 内容的提交，必须带一个 changeset 文件（`npx changeset` 生成）。
- changeset 的 `summary` 写人话：改了什么、为什么。
- 合并到 main 后，release workflow 自动开版本 bump PR；**版本 bump PR 的合并不做自动 push 到任何外部渠道**，与 `scripts/publish.sh` 的人工确认门一致。

## 为什么用 changesets

技能是被 agent 加载的行为定义，变更即行为变更。消费者（装了插件的用户）需要知道"这次自动更新改了什么"，CHANGELOG 是他们的信任来源。
