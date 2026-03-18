# 🤖 WeCom OpenClaw Plugin

**WeCom channel plugin for [OpenClaw](https://github.com/openclaw)** — by the Tencent WeCom team.

> A bot plugin powered by WeCom AI Bot WebSocket persistent connections. Supports direct messages & group chats, streaming replies, and proactive messaging.

---

📖 [WeCom AI Bot Official Documentation](https://open.work.weixin.qq.com/help?doc_id=21657)


## ✨ Features

- 🔗 WebSocket persistent connection for stable communication
- 💬 Supports both direct messages (DM) and group chat
- 📤 Proactive messaging to specific users or groups
- 🖼️ Receives and processes image and file messages with automatic downloading
- ⏳ Streaming replies with "thinking" placeholder messages
- 📝 Markdown formatting support for replies
- 🔒 Built-in access control: DM Policy (pairing / open / allowlist / disabled) and Group Policy (open / allowlist / disabled)
- ⚡ Auto heartbeat keep-alive and reconnection (up to 100 reconnect attempts)
- 🧙 Interactive CLI setup wizard

---

## 🚀 Getting Started

### Requirements

- OpenClaw `>= 2026.2.13`

### Quick Install

Use the CLI tool to automatically install the plugin and complete bot configuration in one step:

```shell
npx -y @wecom/wecom-openclaw-cli install
```

### Manual Install

```shell
openclaw plugins install @wecom/wecom-openclaw-plugin
```

### Configuration

#### Option 1: Interactive Setup

```shell
openclaw channels add
```

Follow the prompts to enter your WeCom bot's **Bot ID** and **Secret**.

#### Option 2: CLI Quick Setup

```shell
openclaw config set channels.wecom.botId <YOUR_BOT_ID>
openclaw config set channels.wecom.secret <YOUR_BOT_SECRET>
openclaw config set channels.wecom.enabled true
openclaw gateway restart
```

### Configuration Reference

| Config Path | Description | Options | Default |
|---|---|---|---|
| `channels.wecom.botId` | WeCom bot ID | — | — |
| `channels.wecom.secret` | WeCom bot secret | — | — |
| `channels.wecom.enabled` | Enable the channel | `true` / `false` | `false` |
| `channels.wecom.websocketUrl` | WebSocket endpoint | — | `wss://openws.work.weixin.qq.com` |
| `channels.wecom.dmPolicy` | DM access policy | `pairing` / `open` / `allowlist` / `disabled` | `open` |
| `channels.wecom.allowFrom` | DM allowlist (user IDs) | — | `[]` |
| `channels.wecom.groupPolicy` | Group chat access policy | `open` / `allowlist` / `disabled` | `open` |
| `channels.wecom.groupAllowFrom` | Group allowlist (group IDs) | — | `[]` |
| `channels.wecom.sendThinkingMessage` | Send "thinking" placeholder | `true` / `false` | `true` |

---

## 🔒 Access Control

### DM (Direct Message) Access

**Default**: `dmPolicy: "open"` — all users can send direct messages without approval.

#### Approve Pairing

```shell
openclaw pairing list wecom            # View pending pairing requests
openclaw pairing approve wecom <CODE>  # Approve a pairing request
```

#### Allowlist Mode

Configure allowed user IDs via `channels.wecom.allowFrom`:

```json
{
  "channels": {
    "wecom": {
      "dmPolicy": "allowlist",
      "allowFrom": ["user_id_1", "user_id_2"]
    }
  }
}
```

#### Open Mode

Set `dmPolicy: "open"` to allow all users to send direct messages without approval.

#### Disabled Mode

Set `dmPolicy: "disabled"` to completely block all direct messages.

### Group Access

#### Group Policy (`channels.wecom.groupPolicy`)

- `"open"` — Allow messages from all groups (default)
- `"allowlist"` — Only allow groups listed in `groupAllowFrom`
- `"disabled"` — Disable all group messages

### Group Configuration Examples

#### Allow All Groups (Default Behavior)

```json
{
  "channels": {
    "wecom": {
      "groupPolicy": "open"
    }
  }
}
```

#### Allow Only Specific Groups

```json
{
  "channels": {
    "wecom": {
      "groupPolicy": "allowlist",
      "groupAllowFrom": ["group_id_1", "group_id_2"]
    }
  }
}
```

#### Allow Only Specific Senders Within a Group (Sender Allowlist)

In addition to the group allowlist, you can restrict which members within a group are allowed to interact with the bot. Only messages from users listed in `groups.<chatId>.allowFrom` will be processed; messages from other members will be silently ignored. This is a sender-level allowlist that applies to **all messages**.

```json
{
  "channels": {
    "wecom": {
      "groupPolicy": "allowlist",
      "groupAllowFrom": ["group_id_1"],
      "groups": {
        "group_id_1": {
          "allowFrom": ["user_id_1", "user_id_2"]
        }
      }
    }
  }
}
```

---

## 📦 Update

```shell
openclaw plugins update wecom-openclaw-plugin
```

---

## 📄 License

MIT
