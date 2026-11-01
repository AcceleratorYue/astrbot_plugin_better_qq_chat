# Changelog

## 0.1.1

- 主动回复轮次支持本插件互动提示（`active_reply_hint_enabled`）；
- 主动回复可提示模型考虑 `qq_poke` / `qq_react`，但不自动执行；
- 修正与 `poke_to_llm` 共存说明。

## 0.1.0

- 首个版本；
- `qq_poke`、`qq_react`、`qq_recall`、`qq_avatar` 四个 LLM 工具；
- 被唤醒提示；
- 别人戳别人时低概率跟戳（默认 15% / 30 秒冷却）；
- 被戳只记录；
- 被引用的消息撤回；
- QQ 头像获取；
- aiocqhttp 平台适配。
