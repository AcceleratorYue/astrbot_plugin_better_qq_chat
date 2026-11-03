# Changelog

## 0.1.3

- 新增“被戳反戳”：Bot 被戳时按概率反戳发起者，支持群聊/私聊、概率、冷却和黑白名单；
- 新增 `poke_back_mode`：`coexist` 与 `poke_to_llm` 的文本响应共存，`only_if_no_llm_poke` 在检测到对方启用时只记录不反戳，避免双重响应；
- 新增 `poke_back_enabled`、`poke_back_probability`、`poke_back_cooldown`、`poke_back_allow_private` 配置；
- 反戳成功/跳过/失败写入审计日志。

## 0.1.2

- 修复群表情回应只响应管理员账号的问题：表情 notice 改为独立 `GROUP_MESSAGE` 监听，避免混在通用 notice 入口里被过滤；
- 反应归属使用 AstrBot 事件提供的 bot `self_id`，不再直接信任部分适配器可能不含 `self_id` 的 raw 字段，避免把用户反应误判为 bot 自己的反应；
- 新增 `reaction_seen` 审计记录（群、用户、消息 ID），便于核对非管理员反应是否上报；
- 保持原有跟贴概率、冷却、去重行为不变。

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
