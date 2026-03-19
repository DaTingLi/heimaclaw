# 飞书群组 ID 获取指南

**版本**: v1.0  
**创建日期**: 2026-03-19  
**目标**: 帮助用户获取飞书群组 ID 并配置多 Agent

---

## 1. 飞书群组 ID 简介

| 类型 | 前缀 | 说明 |
|------|------|------|
| 群聊 ID | `oc_` | Group Chat ID |
| 用户 Open ID | `ou_` | User Open ID |
| 用户 Union ID | `on_` | User Union ID |

---

## 2. 获取群组 ID 的方法

### 方法一：从飞书开放平台（推荐）

1. 打开 [飞书开放平台](https://open.feishu.cn/)
2. 进入你的应用
3. 点击「事件与回调」→「事件配置」
4. 在「请求地址 URL」下方可以看到测试工具
5. 点击「测试」→ 选择「接收消息」事件
6. 在「event.chat.*」中可以获取群信息

### 方法二：从机器人消息（最简单）

当机器人在群中收到消息时，每条消息都包含 `chat_id`：

```
你邀请机器人进群后，给机器人发一条消息
机器人收到的消息中就包含群的 chat_id
```

#### 查看日志

```bash
# 查看飞书消息日志
tail -f /opt/heimaclaw/logs/heimaclaw.log | grep chat_id
```

或者在代码中添加日志：

```python
# 在处理消息时打印 chat_id
print(f"收到消息 - chat_id: {message.chat_id}")
```

### 方法三：通过飞书开放平台 API

```bash
# 调用飞书 API 获取群列表
curl -X GET "https://open.feishu.cn/open-apis/im/v1/chats?page_size=20" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

响应中会包含 `chat_id` 列表。

---

## 3. 实际工作流

### Step 1: 创建 Agent

```bash
heimaclaw agent create python-helper
heimaclaw agent create frontend-helper
```

### Step 2: 邀请机器人进群

1. 打开飞书
2. 创建群聊（或选择已有群）
3. 点击「添加机器人」
4. 搜索并添加你的 Agent 机器人

### Step 3: 获取群组 ID

**方式 A：看日志**

机器人收到消息后，查看日志中的 `chat_id`

```bash
tail -f /opt/heimaclaw/logs/heimaclaw.log
```

找到类似这样的输出：
```
收到消息 - chat_id: oc_x01x01x01x01x01x01
```

**方式 B：让机器人告诉你**

在群中发送：
```
@机器人 /info
```

机器人回复中会包含群组 ID。

### Step 4: 配置群组多 Agent

```bash
# 配置群组
heimaclaw bindings setup-group oc_x01x01x01x01x01x01 \
    --agents python-helper,frontend-helper \
    --default python-helper
```

### Step 5: 重启服务

```bash
heimaclaw start
```

---

## 4. 常用命令

```bash
# 查看所有群组配置
heimaclaw bindings list-group

# 查看当前绑定
heimaclaw bindings list

# 移除群组配置
heimaclaw bindings remove-group <群ID>
```

---

## 5. 注意事项

### 机器人必须被邀请进群

只有被邀请进群的机器人才会收到该群的消息。

### 不同群的 chat_id 不同

每个群都有独立的 `chat_id`，即使是同一个机器人加入不同群，群 ID 也不同。

### chat_id 格式

- 飞书群聊 ID 通常以 `oc_` 开头
- 示例：`oc_a1b2c3d4e5f6g7h8`

---

## 6. 故障排除

### Q: 机器人收不到群消息？

1. 检查机器人是否被邀请进群
2. 检查事件订阅是否配置正确
3. 检查机器人的「机器人群」权限是否开启

### Q: 如何确认机器人已收到消息？

查看日志：
```bash
tail -f /opt/heimaclaw/logs/heimaclaw.log
```

### Q: 群组 ID 填错了怎么办？

```bash
# 移除错误的配置
heimaclaw bindings remove-group <错误的群ID>

# 重新配置
heimaclaw bindings setup-group <正确的群ID> ...
```

---

## 7. nanobot 的 groupPolicy 参考

nanobot 提供了更简单的配置方式：

```json
{
  "channels": {
    "feishu": {
      "token": "YOUR_BOT_TOKEN",
      "groupPolicy": "mention"  // mention / open
    }
  }
}
```

**groupPolicy 选项**：
- `"mention"` - 只有 @机器人 时才响应
- `"open"` - 响应所有消息

未来可以考虑在 HeiMaClaw 中添加类似的简化配置。

---

_文档创建: 2026-03-19_
