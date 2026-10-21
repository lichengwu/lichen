# ADR 0001：user-invoked / model-invoked 双层调用模型

- 状态：已接受（2026-10-18）
- 决策者：佐井

## 背景

Agent Skills 生态（SKILL.md 格式）里，一个常见失败是所有技能平铺：模型该自己伸手用的纪律（TDD、诊断循环）和只该由人类明确发起的编排（对齐访谈、发布流程）混在一起，结果是模型在不该自动触发的时候触发了编排型流程，或反过来，该自动复用的纪律永远在等人类想起它。

mattpocock/skills 用 `disable-model-invocation` + `.agents/invocation.md` 不变式解决了这个问题，是目前生态里最成熟的方案。

## 决策

采用双层调用模型：

1. **user-invoked**（`disable-model-invocation: true`）：只有人类键入才触发。职责限定为**编排**——把多个 model-invoked 原语串成流程。
2. **model-invoked**（默认）：模型可自主触达。职责限定为**可复用的纪律**——单一关注点、无编排。
3. 不变量：user-invoked 只能调 model-invoked，不能调 user-invoked。
4. 跨技能调用一律显式写 "Call the Skill tool with <name>"，一次一个。

## 理由

- 编排流程（访谈、发布、交接）有副作用和上下文成本，必须由人显式发起。
- 纪律原语（TDD、脱敏、诊断）应该在任务匹配时自动就位，不该靠人记。
- 显式工具调用比散文提及的触发命中率高，且 harness 中立。

## 后果

- 新技能提案必须先回答"它是编排还是纪律"，再决定调用层。
- `scripts/check.sh` 校验 frontmatter 完整性；调用层的语义正确性靠 code review 保证。
