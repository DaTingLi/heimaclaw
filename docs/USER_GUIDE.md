# HeiMaClaw 完整用户指南

**版本**: v1.0  
**创建日期**: 2026-03-19  
**目标**: 让小白用户能够构建高级全栈开发 Agent

---

## 📚 目录

1. [HeiMaClaw 是什么？](#1-heimaclaw-是什么)
2. [安装 HeiMaClaw](#2-安装-heimaclaw)
3. [创建你的第一个 Agent](#3-创建你的第一个-agent)
4. [配置 Agent 的灵魂 (SOUL.md)](#4-配置-agent-的灵魂-soulmd)
5. [配置 Agent 的身份 (IDENTITY.md)](#5-配置-agent-的-identity-文件)
6. [配置工具能力 (TOOLS.md)](#6-配置工具能力-toolsmd)
7. [编译 Agent 配置](#7-编译-agent-配置)
8. [启动 Agent 服务](#8-启动-agent-服务)
9. [热重载功能](#9-热重载功能)
10. [完整工作流示例](#10-完整工作流示例)

---

## 1. HeiMaClaw 是什么？

HeiMaClaw 是一个**生产级企业 AI Agent 平台**。

### 核心特性

| 特性 | 说明 |
|------|------|
| 🏠 **隔离安全** | 每个 Agent 运行在独立 microVM (Firecracker) 中 |
| 💬 **双渠道** | 支持飞书和企业微信 |
| 🧠 **记忆系统** | 4层记忆架构 |
| ⚡ **热重载** | 配置修改无需重启 |
| 🚀 **高性能** | 编译后配置，加载更快 |

### 系统架构

```
用户 (飞书/企微)
    ↓
AgentRunner (运行时)
    ↓
MemoryManager (记忆)
    ↓
LLM (大模型)
    ↓
沙箱隔离 (Firecracker microVM)
```

---

## 2. 安装 HeiMaClaw

### 前置要求

- Python 3.10+
- Conda (推荐) 或 pip
- Git

### 方式一：使用 Conda (推荐)

```bash
# 1. 克隆项目
git clone https://github.com/DaTingLi/heimaclaw.git
cd heimaclaw

# 2. 创建环境
conda env create -f environment.yml

# 3. 激活环境
conda activate heimaclaw

# 4. 安装
pip install -e .
```

### 方式二：直接 pip

```bash
git clone https://github.com/DaTingLi/heimaclaw.git
cd heimaclaw
pip install -e .
```

### 验证安装

```bash
heimaclaw --version
heimaclaw doctor
```

---

## 3. 创建你的第一个 Agent

### 3.1 环境诊断

```bash
heimaclaw doctor
```

预期输出：
```
┃ 检查项      ┃ 状态       ┃ 详情                              ┃
│ Python 版本 │ OK         │ 3.10+                             │
│ KVM 支持    │ OK         │ 硬件虚拟化已启用                  │
│ Firecracker │ OK         │ /usr/local/bin/firecracker        │
│ 配置文件    │ OK         │ /opt/heimaclaw/config/config.toml │
│ 端口 8000   │ 可用       │ 服务默认端口                      │
```

### 3.2 创建 Agent

```bash
heimaclaw agent create my-dev-agent
```

输出：
```
创建 Agent: my-dev-agent
Agent 创建成功: my-dev-agent
配置文件: /opt/heimaclaw/data/agents/my-dev-agent/agent.json
```

### 3.3 查看 Agent 列表

```bash
heimaclaw agent list
```

---

## 4. 配置 Agent 的灵魂 (SOUL.md)

SOUL.md 定义了 Agent 的**核心定位、能力、风格**。

### 4.1 创建 SOUL.md

在 Agent 目录下创建 `SOUL.md`：

```bash
nano /opt/heimaclaw/data/agents/my-dev-agent/SOUL.md
```

### 4.2 SOUL.md 完整示例

```markdown
# SOUL.md - 全栈开发 Agent 核心定位

## 🎯 核心定位

**全栈开发专家**，专注于帮助用户构建高质量的全栈应用。
- 熟练掌握 Python, JavaScript/TypeScript, React, Node.js
- 理解微服务架构、数据库设计、API 设计
- 追求代码可维护性、性能优化、安全性

## 💪 核心能力

### 代码开发
- 快速原型开发
- 前后端分离架构
- RESTful API 设计
- 数据库建模

### 问题诊断
- 快速定位 bug
- 性能瓶颈分析
- 安全漏洞检测

### 架构设计
- 微服务架构
- 分布式系统
- 云原生应用

## 🤝 协作风格

- 主动建议最佳实践
- 代码审查和改进
- 文档编写指导

## ⚠️ 边界

- 不直接操作生产数据库
- 危险操作需要确认
- 保护用户隐私

## 🌟 氛围

专业、高效、严谨

## 🔄 成长

我会记住用户的偏好和项目特点，提供越来越精准的建议。
```

### 4.3 关键字段说明

| 字段 | 说明 | 示例 |
|------|------|------|
| `## 🎯 核心定位` | Agent 的主要职责 | 全栈开发专家 |
| `## 💪 核心能力` | 具体技能列表 | 代码开发、问题诊断 |
| `## 🤝 协作风格` | 交互方式 | 主动建议、代码审查 |
| `## ⚠️ 边界` | 不能做的事 | 不操作生产数据库 |
| `## 🌟 氛围` | 沟通风格 | 专业、高效 |

---

## 5. 配置 Agent 的身份 (IDENTITY.md)

IDENTITY.md 定义了 Agent 的**外在形象**。

### IDENTITY.md 完整示例

```markdown
# IDENTITY.md - Agent 身份信息

## 基本信息
- **姓名**：DevMaster
- **生物**：全栈开发 AI
- **氛围**：专业、高效
- **表情符号**：🚀
- **头像**：avatars/devmaster.png

## 自我介绍

👋 你好！我是 **DevMaster** 🚀

我是一个专注于全栈开发的 AI 助手。我可以帮助你：
- 🏗️ 构建现代化的 Web 应用
- 🔧 解决技术难题
- 📐 设计系统架构
- 🔍 审查和优化代码
- 📚 编写技术文档
```

---

## 6. 配置工具能力 (TOOLS.md)

TOOLS.md 定义了 Agent 可以使用的**工具**。

### TOOLS.md 完整示例

```markdown
# TOOLS.md - 工具能力定义

## 🔧 可用工具

### 1. 文件操作
- **read_file**: 读取文件内容
- **write_file**: 写入或创建文件
- **edit_file**: 编辑文件（精确替换）
- **exec**: 执行 Shell 命令

### 2. 代码执行
- **python_run**: 执行 Python 代码
- **javascript_run**: 执行 JavaScript 代码

### 3. Git 操作
- **git_clone**: 克隆仓库
- **git_commit**: 提交代码
- **git_push**: 推送代码

### 4. Web 操作
- **web_fetch**: 获取网页内容
- **web_search**: 搜索信息

## ⚙️ 使用约束

- 所有代码执行前需要用户确认
- 生产环境操作需要双重确认
- 敏感信息不可记录
```

---

## 7. 编译 Agent 配置

Markdown 配置文件需要编译成 JSON 才能被 Agent 使用。

### 7.1 编译单个 Agent

```bash
heimaclaw agent compile my-dev-agent
```

输出：
```
开始编译 Agent: my-dev-agent
Agent my-dev-agent 编译完成
```

### 7.2 验证编译结果

```bash
ls -la /opt/heimaclaw/data/agents/my-dev-agent/.compiled/
```

应该看到：
```
agent.compiled.json   # 编译后的配置
hashes.json           # 文件哈希（用于增量编译）
```

### 7.3 编译所有 Agent

```bash
heimaclaw agent compile
```

### 7.4 强制重新编译

```bash
heimaclaw agent compile my-dev-agent --force
```

---

## 8. 启动 Agent 服务

### 8.1 配置渠道

#### 飞书配置

```bash
heimaclaw channel setup feishu
```

按提示输入：
- App ID
- App Secret
- 回调 URL

#### 企业微信配置

```bash
heimaclaw channel setup wecom
```

### 8.2 启动服务

#### 方式一：HTTP 服务

```bash
heimaclaw start --port 8000
```

#### 方式二：WebSocket 长连接 (飞书)

```bash
heimaclaw start-ws
```

#### 开发模式（热重载）

```bash
heimaclaw start --reload
```

---

## 9. 热重载功能

HeiMaClaw 支持**配置文件热重载**，修改后无需重启。

### 9.1 热重载触发条件

| 文件类型 | 触发 |
|----------|------|
| `.toml` | 配置重载 |
| `.yaml/.yml` | 配置重载 |
| `.json` | 配置重载 |
| `.md` | Markdown 重新编译 |

### 9.2 监听模式

```bash
heimaclaw agent compile --watch
```

在监听模式下：
- 修改 Markdown 文件 → 自动重新编译
- 修改 agent.json → 自动重载

### 9.3 热重载架构

```
ConfigWatcher (文件监听)
    ↓
配置文件变化
    ↓
ConfigLoader (重新加载)
    ↓
MemoryManager (通知各模块)
```

---

## 10. 完整工作流示例

### 场景：构建一个 Python 开发助手

### Step 1: 创建 Agent

```bash
heimaclaw agent create python-helper
```

### Step 2: 创建 SOUL.md

```bash
nano /opt/heimaclaw/data/agents/python-helper/SOUL.md
```

内容：
```markdown
# SOUL.md - Python 开发助手

## 🎯 核心定位

专业的 Python 开发助手，精通：
- Django, Flask, FastAPI
- 异步编程
- 性能优化
- 测试驱动开发

## 💪 核心能力

- Python 代码审查
- 架构设计建议
- Bug 定位和修复
- 单元测试编写
```

### Step 3: 创建 IDENTITY.md

```bash
nano /opt/heimaclaw/data/agents/python-helper/IDENTITY.md
```

内容：
```markdown
# IDENTITY.md

## 基本信息
- **姓名**：PyMaster
- **生物**：Python 专家
- **表情符号**：🐍
```

### Step 4: 创建 TOOLS.md

```bash
nano /opt/heimaclaw/data/agents/python-helper/TOOLS.md
```

内容：
```markdown
# TOOLS.md

## 🔧 工具

### 代码执行
- **python_run**: 执行 Python 代码
- **pytest_run**: 运行测试

### 文件操作
- **read_file**: 读取文件
- **write_file**: 写入文件
```

### Step 5: 编译

```bash
heimaclaw agent compile python-helper
```

### Step 6: 启动

```bash
heimaclaw start
```

### Step 7: 开发模式（热重载）

```bash
# 终端 1: 启动 Agent
heimaclaw agent compile python-helper --watch

# 终端 2: 启动服务
heimaclaw start
```

现在你可以：
1. 修改 SOUL.md 调整 Agent 性格
2. 修改 TOOLS.md 调整工具能力
3. 修改 IDENTITY.md 调整形象

所有修改都会**自动重载**！

---

## 📋 常用命令速查

| 操作 | 命令 |
|------|------|
| 创建 Agent | `heimaclaw agent create <name>` |
| 列出 Agent | `heimaclaw agent list` |
| 编译 Agent | `heimaclaw agent compile <name>` |
| 监听模式 | `heimaclaw agent compile <name> --watch` |
| 查看配置 | `heimaclaw config show` |
| 设置配置 | `heimaclaw config set <key> <value>` |
| 启动服务 | `heimaclaw start` |
| 环境诊断 | `heimaclaw doctor` |
| 绑定用户 | `heimaclaw bindings bind-user <user_id> --agent <name>` |
| Token 统计 | `heimaclaw monitoring token-stats` |

---

## ❓ 常见问题

### Q: 编译失败怎么办？

检查 Markdown 文件语法是否正确，确保：
- 标题格式正确 (`#`, `##`)
- 无未闭合的代码块
- 文件编码为 UTF-8

### Q: Agent 无法启动？

```bash
heimaclaw doctor
```
检查各项是否 OK。

### Q: 热重载不生效？

确保使用 `--reload` 或 `--watch` 模式启动服务。

---

**恭喜！🎉 你已经掌握 HeiMaClaw 的完整使用流程！**

---

_文档版本: v1.0 | 最后更新: 2026-03-19_
