# 更好的QQ聊天交互 · `astrbot_plugin_better_qq_chat`

给 [AstrBot](https://github.com/AstrBotDevs/AstrBot) 的 QQ Bot 增加更自然的互动能力：

- **戳一戳**：LLM 可自主调用 `qq_poke`；被唤醒时只给一句可选提示，不强制；
- **跟戳**：别人戳别人时，按低概率和冷却自动跟戳；
- **表情回应**：`qq_react` 给当前/被引用消息贴 QQ 小表情；可选跟贴；
- **撤回**：`qq_recall` 撤回用户直接引用的消息；
- **头像**：`qq_avatar` 获取 QQ 用户高清头像，可选直接发到聊天。

> 仅支持 **aiocqhttp / OneBot v11（NapCat / Lagrange）**。  
> 不修改消息链，不额外调用 LLM 生成跟戳/跟贴内容。

## 安装

```bash
cd <AstrBot根目录>/data/plugins
git clone https://github.com/AcceleratorYue/astrbot_plugin_better_qq_chat
```

或复制到 AstrBot 插件目录；市场发布后再补市场搜索入口。

安装后在插件管理页重载插件，或重启 AstrBot。

## 工具

| 工具 | 说明 |
|---|---|
| `qq_poke` | 戳一戳，支持 sender / quoted_sender / at / at:N / QQ 号 |
| `qq_react` | 给 quoted / current 消息贴小表情 |
| `qq_recall` | 撤回用户直接引用的消息 |
| `qq_avatar` | 获取 QQ 头像，可选发送到聊天 |

### `qq_poke`

```text
qq_poke(user="sender", times=1)
```

- 群聊优先 `group_poke`，失败尝试 `send_poke`；
- 私聊优先 `friend_poke`，失败尝试 `send_poke`；
- 不能戳 Bot 自己；
- `times` 受 `poke_max_times` 限制。

### `qq_react`

```text
qq_react(emoji="heart", message="quoted")
```

- `emoji` 支持语义名或数字 ID；
- `message` 支持 `quoted` / `current`；
- 常用表情：`heart`、`thumbs_up`、`laugh_cry`、`rose`、`hug`、`ok`、`applause` 等。

### `qq_recall`

```text
qq_recall(message="quoted")
```

只支持撤回**用户直接引用的消息**：

- Bot 自己的被引用消息：任何用户可请求；
- 他人的被引用消息：需要 AstrBot 管理员或群管理员；
- 不记录 Bot 主动发出消息的 ID，不能撤回“Bot 刚才那句”，只能按引用操作。

### `qq_avatar`

```text
qq_avatar(user="sender", send_to_chat=False)
```

- 使用 `https://q1.qlogo.cn/g?b=qq&nk={qq}&s=640`；
- 默认返回 URL；
- `send_to_chat=true` 时直接发送头像图片。

## 自动行为

### 被唤醒提示

当消息是 @、引用 Bot、私聊或唤醒词触发时，`on_llm_request` 只追加一句：

```text
[互动提示] 如果当前语气和氛围合适，可以考虑用 qq_poke 戳一下唤醒你的人；
不要强行使用，也不要连续戳。
```

是否戳完全由模型决定；可通过 `poke_wake_hint_enabled=false` 关闭。

### 主动回复

AstrBot 的群聊主动回复触发时，本插件会识别 `active_reply_triggered` 标记，并追加：

```text
[互动提示] 这是一次群聊主动回复。如果当前语气和氛围合适，
可以考虑用 qq_poke 戳一下发言人，或用 qq_react 给当前消息贴一个小表情；
不要强行使用，也不要连续互动。
```

同样只给提示，不自动戳/贴；可通过 `active_reply_hint_enabled=false` 关闭。

### 跟戳

别人戳别人时：

```text
概率 0.15 + 每群 30 秒冷却 + 群白名单/黑名单
```

默认目标是“原来被戳的人”，可改为戳发起者。

- Bot 被戳：默认只记录，不主动回应；
- Bot 自己发出的戳：忽略；
- 关闭：`follow_poke_enabled=false` 或 `follow_poke_probability=0`。

### 跟贴表情

别人给消息贴表情时，可选按概率跟贴同一表情：

```text
默认关闭，reaction_follow_enabled=false
```

同一条消息同一表情会去重，不会因重复调用取消。

## 配置

配置文件：`data/config/astrbot_plugin_better_qq_chat_config.json`

| 键 | 默认 | 说明 |
|---|---|---|
| `enable` | `true` | 总开关 |
| `audit_enabled` | `true` | 写审计日志 |
| `poke_tool_enabled` | `true` | 启用 `qq_poke` |
| `poke_wake_hint_enabled` | `true` | 被唤醒时注入可选提示 |
| `active_reply_hint_enabled` | `true` | 主动回复轮次注入互动提示 |
| `poke_max_times` | `2` | 单次最多戳几次（1-3） |
| `poke_allow_private` | `true` | 允许私聊戳 |
| `follow_poke_enabled` | `true` | 别人戳别人时自动跟戳 |
| `follow_poke_probability` | `0.15` | 跟戳概率 |
| `follow_poke_cooldown` | `30` | 跟戳冷却（秒/群） |
| `follow_poke_target` | `original` | `original` 或 `sender` |
| `follow_poke_groups` | 空 | 群白名单，逗号分隔 |
| `blocked_groups` | 空 | 群黑名单 |
| `blocked_users` | 空 | 用户黑名单 |
| `reaction_tool_enabled` | `true` | 启用 `qq_react` |
| `reaction_follow_enabled` | `false` | 自动跟贴表情 |
| `reaction_follow_probability` | `0.1` | 跟贴概率 |
| `reaction_follow_cooldown` | `30` | 跟贴冷却（秒/群） |
| `reaction_max_faces` | `1` | 一次最多跟贴几个 |
| `recall_tool_enabled` | `true` | 启用 `qq_recall` |
| `recall_allow_others` | `true` | 允许管理员/群管撤回他人被引用消息 |
| `avatar_tool_enabled` | `true` | 启用 `qq_avatar` |

## 权限与安全

- 撤回他人消息需要 AstrBot 管理员或群主/群管理员；
- 撤回自己的消息也需要用户先引用；
- 不支持任意 URL 下载，头像固定 qlogo 域名；
- 跟戳有概率、冷却和黑白名单，避免刷屏；
- 戳一戳/表情回应属于协议端扩展，失败会返回明确原因；
- 所有主动操作写审计日志：

```text
data/plugin_data/astrbot_plugin_better_qq_chat/audit.log
```

## 已知限制

- 仅支持 aiocqhttp / OneBot v11；
- `set_msg_emoji_like` 需要 NapCat / Lagrange 支持；
- 表情 ID 来自公开表情表，需在目标协议端真机验证；
- AstrBot 不暴露 Bot 发消息 ID，撤回只支持“被引用消息”；
- 与 `astrbot_plugin_poke_to_llm` 同时启用时：对方仍会响应“Bot 被戳”，本插件只记录，不会重复文本回复；如果希望被戳只记录，需要关闭对方插件。
- 与 `astrbot_plugin_face_echo` 同时启用时可能重复跟贴，建议只开一个。

## 开发

```bash
python -m unittest discover -s tests -v
```

测试覆盖：notice 解析、目标解析、表情映射、撤回权限、跟戳概率/冷却、工具调用。

## 致谢与许可证

MIT License。

参考：

- [astrbot_plugin_napcat_tools](https://github.com/Dracowyn/astrbot_plugin_napcat_tools)（MIT）：OneBot 调用封装、目标解析、表情 ID 表、头像 URL、撤回权限思路；
- [astrbot_plugin_poke_to_llm](https://github.com/muyouzhi6/astrbot_plugin_poke_to_llm)（MIT）：戳一戳 notice 解析与触发思路；
- [astrbot_plugin_face_echo](https://github.com/wjn1121/astrbot_plugin_face_echo)：`group_msg_emoji_like` 协议字段参考；
- [astrbot_plugin_litepoke](https://github.com/kazamisama/astrbot_plugin_litepoke)：跟戳产品行为参考（AGPL，未复制代码）。
