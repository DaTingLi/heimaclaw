# HeiMaClaw 小白完全使用指南

**版本**: v1.0  
**创建日期**: 2026-03-19  
**目标**: 从零开始，手把手教小白用户使用 HeiMaClaw

---

## 📋 目录

1. [HeiMaClaw 是什么？](#1-heimaclaw-是什么)
2. [快速安装（5分钟）](#2-快速安装5分钟)
3. [创建你的第一个 Agent](#3-创建你的第一个-agent)
4. [配置 Agent 模型](#4-配置-agent-模型)
5. [配置飞书渠道](#5-配置飞书渠道)
6. [开始对话](#6-开始对话)
7. [高级：多 Agent 配置](#7-高级多-agent-配置)
8. [常见问题](#8-常见问题)

---

## 1. HeiMaClaw 是什么？

**HeiMaClaw** 是一个**企业级 AI Agent 平台**，可以让您创建多个有不同专长的 AI 助手。

### 核心概念

| 概念 | 说明 |
|------|------|
| **Agent** | 一个 AI 助手，有自己的角色、能力、记忆 |
| **模型** | Agent 思考的大脑（GPT-4、GLM-4、Claude 等） |
| **渠道** | Agent 接收消息的地方（飞书、企微） |
| **记忆** | Agent 记住对话内容的能力 |

### 一图理解架构

```
你是用户（小白）
    ↓ 发送消息
飞书/企微
    ↓ 接收消息
HeiMaClaw 系统
    ↓ 路由
Agent（根据绑定）
    ↓ 调用
AI 模型（GPT-4/GLM-4/Claude）
    ↓ 返回
Agent 处理
    ↓ 回复
飞书/企微
    ↓
你收到回复
```

---

## 2. 快速安装（5分钟）

### 第一步：克隆项目

```bash
git clone https://github.com/DaTingLi/heimaclaw.git
cd heimaclaw
```

### 第二步：一键安装

```bash
bash scripts/install.sh
```

安装脚本会检测：
- ✅ Python 版本（需要 3.10+）
- ✅ pip 是否安装
- ✅ 端口 8000 是否可用
- ⚠️ Firecracker（可选，沙箱隔离）

### 第三步：验证安装

```bash
heimaclaw doctor
```

---

## 3. 创建你的第一个 Agent

### 创建 Agent

```bash
heimaclaw agent create my-python-helper
```

### 创建后你有了什么？

```
/opt/heimaclaw/data/agents/my-python-helper/
├── agent.json          ← Agent 配置文件（模型、渠道）
├── SOUL.md            ← Agent 的「灵魂」（性格、专长）
├── IDENTITY.md        ← Agent 的「身份」（名字、头像）
├── TOOLS.md           ← Agent 的「工具」（会什么技能）
└── memory/            ← Agent 的「记忆」
```

### 配置 Agent 的灵魂（SOUL.md）

```bash
nano /opt/heimaclaw/data/agents/my-python-helper/SOUL.md
```

写入内容：
```markdown
# SOUL.md - Python 开发助手

## 🎯 核心定位

你是一个专业的 **Python 开发助手**，专注于帮助用户：
- 编写高质量 Python 代码
- 解决 Bug 和技术问题
- 设计 Python 项目架构

## 💪 核心能力

### 擅长领域
- Python 3.10+ 特性
- FastAPI, Django, Flask
- 异步编程 (asyncio)

## 🤝 服务风格

- 主动给出最佳实践建议
- 代码示例清晰、注释完整

## 🌟 沟通风格

专业、高效、有耐心。用中文交流。
```

---

## 4. 配置 Agent 模型

**每个 Agent 可以使用不同的 AI 模型！**

### 支持的模型

| 提供商 | 模型 | 说明 |
|--------|------|------|
| **OpenAI** | GPT-4, GPT-4-turbo | 需要 API Key |
| **Claude** | Claude-3.5-sonnet | 需要 API Key |
| **GLM (智谱)** | GLM-4, GLM-4-flash | 国内，推荐 |
| **DeepSeek** | deepseek-chat | 国内，性价比高 |
| **Qwen (通义)** | qwen-turbo, qwen-plus | 国内，阿里 |

### 配置示例

编辑 agent.json：

```bash
nano /opt/heimaclaw/data/agents/my-python-helper/agent.json
```

```json
{
  "name": "my-python-helper",
  "llm": {
    "provider": "glm",
    "model_name": "glm-4-flash",
    "api_key": "你的API-Key",
    "temperature": 0.7,
    "max_tokens": 4096
  }
}
```

---

## 5. 配置飞书渠道

### 第一步：创建飞书应用

1. 打开 [飞书开放平台](https://open.feishu.cn/)
2. 点击「创建企业自建应用」
3. 获取 **App ID** 和 **App Secret**

### 第二步：在 HeiMaClaw 中配置

```bash
heimaclaw channel setup feishu
```

按提示输入 App ID 和 App Secret。

或者直接修改 agent.json：

```json
{
  "channels": [
    {
      "type": "feishu",
      "app_id": "cli_xxxxxxx",
      "app_secret": "xxxxxxx",
      "enabled": true
    }
  ]
}
```

### 第三步：编译并重启

```bash
# 编译
heimaclaw agent compile my-python-helper

# 启动服务
heimaclaw start
```

---

## 6. 开始对话

### 在飞书中找到你的机器人

1. 打开飞书
2. 搜索你的应用名称
3. 点击「开始聊天」

### 私聊示例

```
用户: 你好
Agent: 👋 你好！我是 PyMaster，Python 开发助手。

用户: 帮我写一个快速排序
Agent: 好的！以下是 Python 实现的快速排序：
（代码回复）
```

---

## 7. 高级：多 Agent 配置

### 绑定 Agent 到群

```bash
# 绑定到群聊
heimaclaw bindings bind-group tech-group-123 --agent my-python-helper

# 绑定到用户
heimaclaw bindings bind-user user-456 --agent my-python-helper

# 设置默认 Agent
heimaclaw bindings set-default my-python-helper
```

### 群内多 Agent 通信

**当前设计**：每个群**只能绑定一个 Agent**

如果想在一个群里使用多个 Agent：
- 方案一：创建「路由 Agent」作为入口
- 方案二：创建多个群，每个 Agent 一个群

---

## 8. 常见问题

### Q1: 图片支持吗？

**当前版本暂不支持图片输入**。

**未来计划**：v0.2 支持 GPT-4V/Claude Vision

### Q2: 需要重启服务吗？

**需要！** 每次修改配置后：

```bash
# Ctrl+C 停止
heimaclaw start  # 重启
```

### Q3: 如何更新 Agent 配置？

```bash
# 1. 修改配置文件
nano /opt/heimaclaw/data/agents/你的agent/SOUL.md

# 2. 重新编译
heimaclaw agent compile 你的agent

# 3. 重启服务
heimaclaw start
```

---

## 🚀 快速参考卡

```bash
# 安装
bash scripts/install.sh

# 创建 Agent
heimaclaw agent create my-agent

# 配置 SOUL.md（灵魂）
nano /opt/heimaclaw/data/agents/my-agent/SOUL.md

# 编译
heimaclaw agent compile my-agent

# 启动
heimaclaw start

# 查看状态
heimaclaw status
heimaclaw agent list
heimaclaw doctor

# 绑定
heimaclaw bindings bind-user 用户ID --agent my-agent
heimaclaw bindings bind-group 群ID --agent my-agent
heimaclaw bindings list
```

---

_祝你使用愉快！🎉_
