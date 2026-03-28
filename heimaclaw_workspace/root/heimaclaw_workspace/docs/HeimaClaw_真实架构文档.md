# HeiMaClaw 系统架构文档

> **文档版本**: v1.0  
> **更新时间**: 2025-03-24  
> **源码路径**: `/root/dt/ai_coding/heimaclaw/src/heimaclaw/`

---

## 📋 目录

1. [系统概述](#1-系统概述)
2. [核心架构](#2-核心架构)
3. [目录结构](#3-目录结构)
4. [核心模块详解](#4-核心模块详解)
5. [接口契约](#5-接口契约)
6. [技术栈](#6-技术栈)
7. [部署架构](#7-部署架构)
8. [配置管理](#8-配置管理)
9. [扩展开发](#9-扩展开发)

---

## 1. 系统概述

### 1.1 项目定位

**HeiMaClaw** 是一个**生产级企业 AI Agent 平台**，核心特性：

- 🔒 **硬件级隔离** - 每个 Agent 运行在独立 microVM (Firecracker) 中
- 🌐 **双渠道支持** - 飞书和企业微信无缝接入
- 🧠 **多层记忆系统** - 会话记忆、日常记忆、长期记忆、向量记忆
- 🤖 **多模型支持** - OpenAI、Claude、GLM、DeepSeek、Qwen、vLLM、Ollama
- 🔄 **事件驱动架构** - 基于 JSONL 的轻量级事件总线
- 🚀 **子 Agent 机制** - 独立上下文窗口，并行任务执行

### 1.2 项目信息

| 项目 | 详情 |
|------|------|
| **项目名称** | heimaclaw |
| **版本** | 0.1.0 |
| **许可证** | MIT |
| **Python 版本** | >=3.10 |
| **入口命令** | `heimaclaw` |

---

## 2. 核心架构

### 2.1 架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                        用户交互层                                │
│  ┌──────────────┐          ┌──────────────┐                   │
│  │   飞书渠道    │          │  企业微信渠道  │                   │
│  │  (Feishu)    │          │   (WeCom)    │                   │
│  └──────┬───────┘          └──────┬───────┘                   │
└─────────┼──────────────────────────┼───────────────────────────┘
          │                          │
          └──────────┬───────────────┘
                     │
          ┌──────────▼──────────┐
          │   FastAPI Server    │
          │   (Webhook 接收)     │
          └──────────┬──────────┘
                     │
┌────────────────────▼────────────────────────────────────────────┐
│                     Agent 运行时层                               │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  AgentRunner - 生命周期管理                               │  │
│  │  ├─ SessionManager - 会话管理                            │  │
│  │  ├─ PolicyManager - 策略配置                              │  │
│  │  ├─ ToolRegistry - 工具注册表                             │  │
│  │  └─ MemoryManager - 记忆管理器                            │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────────┬────────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────────┐
│                      核心引擎层                                  │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────────────┐  │
│  │  EventBus   │   │ Subagent    │   │   LLM Registry      │  │
│  │ (事件总线)   │   │  Spawner    │   │ (多模型统一接口)     │  │
│  └─────────────┘   └─────────────┘   └─────────────────────┘  │
└────────────────────┬────────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────────┐
│                     沙箱隔离层                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐ │
│  │ Firecracker  │  │    Docker    │  │    Process (开发)     │ │
│  │  (microVM)   │  │  Container   │  │   (本地降级模式)      │ │
│  └──────────────┘  └──────────────┘  └──────────────────────┘ │
│              暖池预热 (Warm Pool)                               │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 分层职责

| 层级 | 职责 | 关键模块 |
|------|------|----------|
| **用户交互层** | 接收用户消息，返回响应 | `channel.feishu`, `channel.wecom` |
| **服务层** | Webhook 处理，路由分发 | `server.py` |
| **Agent 运行时层** | Agent 生命周期、会话、策略、工具 | `agent.runner`, `agent.session` |
| **核心引擎层** | 事件驱动、子 Agent、LLM 调用 | `core.event_bus`, `llm.registry` |
| **沙箱隔离层** | 安全隔离执行环境 | `sandbox.firecracker`, `sandbox.docker` |

---

## 3. 目录结构

```
src/heimaclaw/
├── __init__.py              # 包入口，定义 __version__
├── cli.py                   # 命令行接口 (71KB)
├── server.py                # FastAPI 服务
├── server_monitoring.py     # 服务监控
├── console.py               # 终端输出工具
├── paths.py                 # 路径配置
├── interfaces.py            # 核心接口契约定义
├── SPEC.md                  # CLI 模块规范文档
│
├── agent/                   # Agent 运行时模块
│   ├── __init__.py
│   ├── runner.py            # Agent 运行器
│   ├── session.py           # 会话管理
│   ├── policy.py            # 策略管理
│   ├── events.py            # Agent 事件
│   ├── router.py            # 路由器
│   ├── planner.py           # 计划器
│   ├── react.py             # ReAct 模式
│   ├── tools.py             # 工具系统
│   ├── system_prompt.py     # 系统提示词
│   ├── todos/               # 任务管理
│   │   ├── manager.py
│   │   ├── memory_tools.py
│   │   └── types.py
│   └── tools/               # 内置工具
│       ├── exec_tool.py
│       ├── read_tool.py
│       ├── write_tool.py
│       ├── docker_tool.py
│       ├── feishu_doc_tool.py  # 飞书文档工具
│       └── interactive_shell.py
│
├── core/                    # 核心引擎
│   ├── __init__.py
│   ├── event_bus.py         # 事件总线
│   ├── subagent_registry.py # 子 Agent 注册表
│   └── subagent_spawn.py    # 子 Agent 生成器
│
├── sandbox/                 # 沙箱模块
│   ├── __init__.py
│   ├── base.py              # 基类
│   ├── firecracker.py       # Firecracker microVM
│   ├── docker.py            # Docker 容器
│   ├── pool.py              # 暖池预热
│   ├── vsock_agent.py       # vsock 代理
│   └── vsock/               # vsock 通信
│       ├── client.py
│       ├── server.py
│       └── manager.py
│
├── llm/                     # LLM 集成模块
│   ├── __init__.py
│   ├── base.py              # 基类和协议
│   ├── registry.py          # LLM 注册表
│   ├── openai_compatible.py # OpenAI 兼容适配器
│   └── providers/           # 各厂商实现
│       ├── openai.py
│       ├── claude.py
│       ├── glm.py
│       ├── deepseek.py
│       ├── qwen.py
│       ├── vllm.py
│       └── ollama.py
│
├── memory/                  # 记忆系统
│   ├── __init__.py
│   ├── manager.py           # 记忆管理器
│   ├── session.py           # 会话记忆
│   ├── daily.py             # 日常记忆
│   ├── longterm.py          # 长期记忆
│   ├── budget.py            # Token 预算
│   └── storage/             # 存储后端
│       └── auto_summary.py
│
├── channel/                 # 渠道适配器
│   ├── __init__.py
│   ├── feishu.py            # 飞书适配器
│   ├── feishu_ws.py         # 飞书 WebSocket
│   └── wecom.py             # 企业微信适配器
│
├── feishu/                  # 飞书集成
│   └── (飞书专用工具)
│
├── config/                  # 配置管理
│   ├── __init__.py
│   └── loader.py            # 配置加载器
│
├── monitoring/              # 监控模块
│   └── __init__.py
│
├── tool/                    # 通用工具
│   └── __init__.py
│
└── vision/                  # 视觉模块
    ├── __init__.py
    ├── service.py
    └── tool.py
```

---

## 4. 核心模块详解

### 4.1 CLI 模块 (`cli.py`)

**职责**: 提供统一的命令行接口

**主要命令**:

| 命令 | 功能 | 参数 |
|------|------|------|
| `heimaclaw init` | 初始化项目 | `--path`, `--force` |
| `heimaclaw start` | 启动服务 | `--host`, `--port`, `--workers` |
| `heimaclaw status` | 显示状态 | - |
| `heimaclaw doctor` | 环境诊断 | - |
| `heimaclaw config show` | 显示配置 | `[key]` |
| `heimaclaw config set` | 设置配置 | `<key> <value>` |
| `heimaclaw agent create` | 创建 Agent | `<name> --channel` |
| `heimaclaw channel setup` | 配置渠道 | `<channel>` |

**技术栈**: Typer (CLI 框架) + Rich (终端输出)

**示例**:
```bash
# 初始化
heimaclaw init --path /opt/heimaclaw

# 启动服务
heimaclaw start --host 0.0.0.0 --port 8000

# 创建 Agent
heimaclaw agent create my-agent --channel feishu
```

---

### 4.2 Server 模块 (`server.py`)

**职责**: FastAPI 服务，处理 Webhook 请求

**生命周期**:
1. **启动时**: 初始化渠道适配器 → 加载 Agent → 启动 Agent
2. **运行时**: 接收 Webhook → 路由到对应 Agent → 返回响应
3. **关闭时**: 停止 Agent → 清理资源

**核心端点**:
- `GET /` - 健康检查
- `POST /webhook/feishu/{agent_name}` - 飞书回调
- `POST /webhook/wecom/{agent_name}` - 企业微信回调

---

### 4.3 Agent 运行时 (`agent/`)

#### 4.3.1 AgentRunner

**职责**: Agent 生命周期管理

**核心方法**:
```python
async def start(agent_id: str) -> None
async def stop(agent_id: str) -> None
async def process_message(agent_id: str, message: Message) -> Message
async def get_status(agent_id: str) -> AgentStatus
```

#### 4.3.2 SessionManager

**职责**: 会话状态管理

**功能**:
- 创建/获取/更新/删除会话
- 列出活跃会话
- 会话持久化

#### 4.3.3 ToolRegistry

**职责**: 工具注册和调度

**内置工具**:
- `exec_tool` - 命令执行
- `read_tool` - 文件读取
- `write_tool` - 文件写入
- `docker_tool` - Docker 操作
- `feishu_doc_tool` - 创建飞书文档
- `interactive_shell` - 交互式 Shell

---

### 4.4 Core 核心引擎 (`core/`)

#### 4.4.1 EventBus

**职责**: 基于 JSONL 的轻量级事件总线

**特性**:
- 事件持久化
- 断点恢复
- 异步处理

#### 4.4.2 Subagent Spawner

**职责**: 子 Agent 生成和管理

**特性**:
- 独立上下文窗口
- 并行任务执行
- 状态跟踪

---

### 4.5 Sandbox 沙箱模块 (`sandbox/`)

#### 4.5.1 后端类型

| 后端 | 隔离级别 | 适用场景 |
|------|----------|----------|
| **Firecracker** | 硬件级 (microVM) | 生产环境，最高安全性 |
| **Docker** | 容器级 | 测试环境，平衡性能与安全 |
| **Process** | 进程级 | 开发环境，快速迭代 |

#### 4.5.2 Warm Pool 暖池

**职责**: 预热沙箱实例，减少冷启动延迟

**工作流程**:
1. 预创建 N 个沙箱实例
2. Agent 请求时从池中取出
3. 使用完毕后归还或销毁

---

### 4.6 LLM 模块 (`llm/`)

#### 4.6.1 支持的模型提供商

| 厂商 | 模型 | Provider |
|------|------|----------|
| OpenAI | GPT-4, GPT-3.5 | `openai` |
| Anthropic | Claude 3 | `claude` |
| 智谱 | GLM-4 | `glm` |
| DeepSeek | DeepSeek | `deepseek` |
| 阿里 | 通义千问 | `qwen` |
| 自部署 | vLLM | `vllm` |
| 本地 | Ollama | `ollama` |

#### 4.6.2 统一接口

```python
# 创建适配器
adapter = create_adapter(LLMConfig(
    provider="openai",
    model_name="gpt-4",
    api_key="..."
))

# 调用
response = await adapter.chat(messages, tools=tools)
```

---

### 4.7 Memory 记忆系统 (`memory/`)

#### 4.7.1 四层记忆架构

```
┌─────────────────────────────────────────┐
│  Session Memory (会话记忆)              │
│  - 当前会话完整历史                      │
│  - Token 预算: 40%                       │
├─────────────────────────────────────────┤
│  Daily Memory (日常记忆)                │
│  - 每日事件总结                          │
│  - Token 预算: 20%                       │
├─────────────────────────────────────────┤
│  Long-Term Memory (长期记忆)            │
│  - 重要事件、用户画像                    │
│  - Token 预算: 20%                       │
├─────────────────────────────────────────┤
│  Vector Memory (向量记忆，可选)          │
│  - 语义检索                              │
│  - Token 预算: 20%                       │
└─────────────────────────────────────────┘
```

#### 4.7.2 Token 预算管理

```python
budget = ContextBudget(total_tokens=8000)
budget.allocate(
    session=0.4,    # 3200 tokens
    daily=0.2,      # 1600 tokens
    longterm=0.2,   # 1600 tokens
    vector=0.2      # 1600 tokens
)
```

---

### 4.8 Channel 渠道模块 (`channel/`)

#### 4.8.1 飞书适配器

**功能**:
- Webhook 验证
- 消息解析
- 消息发送
- WebSocket 长连接

#### 4.8.2 企业微信适配器

**功能**:
- 回调验证
- 消息加解密
- 消息发送

---

## 5. 接口契约

所有核心接口定义在 `interfaces.py` 中：

### 5.1 枚举类型

```python
class ChannelType(str, Enum):
    FEISHU = "feishu"
    WECOM = "wecom"

class SandboxBackend(str, Enum):
    FIRECRACKER = "firecracker"
    DOCKER = "docker"
    PROCESS = "process"

class AgentStatus(str, Enum):
    CREATING = "creating"
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"
```

### 5.2 数据模型

```python
class AgentConfig(BaseModel):
    name: str
    description: str = ""
    channel: ChannelType
    enabled: bool = True
    model_provider: str = "openai"
    model_name: str = "gpt-4"
    sandbox_enabled: bool = True
    sandbox_backend_type: SandboxBackend = SandboxBackend.FIRECRACKER
    sandbox_memory_mb: int = 128
    sandbox_cpu_count: int = 1
    context_mode: str = "minimal"
```

### 5.3 Protocol 接口

| 接口 | 职责 | 核心方法 |
|------|------|----------|
| `ConfigProvider` | 配置提供者 | `load()`, `get()`, `set()`, `save()` |
| `SandboxBackendProtocol` | 沙箱后端 | `create_instance()`, `execute()`, `destroy_instance()` |
| `ChannelAdapter` | 渠道适配器 | `verify_webhook()`, `parse_message()`, `send_message()` |
| `SessionStore` | 会话存储 | `create()`, `get()`, `update()`, `delete()` |
| `ToolRegistry` | 工具注册表 | `register()`, `get()`, `list_all()` |
| `AgentRunner` | Agent 运行器 | `start()`, `stop()`, `process_message()` |

---

## 6. 技术栈

### 6.1 核心依赖

| 类别 | 技术 | 版本 |
|------|------|------|
| **CLI 框架** | Typer | >=0.9.0 |
| **终端输出** | Rich | >=13.0.0 |
| **数据验证** | Pydantic | >=2.0.0 |
| **配置管理** | Pydantic Settings | >=2.0.0 |
| **配置文件** | tomli / tomli-w | >=2.0.0 |
| **Web 框架** | FastAPI | >=0.109.0 |
| **ASGI 服务器** | Uvicorn | >=0.27.0 |
| **HTTP 客户端** | httpx | >=0.26.0 |
| **异步文件** | aiofiles | >=23.0.0 |
| **文件监控** | watchdog | >=3.0.0 |

### 6.2 可选依赖

| 类别 | 技术 | 用途 |
|------|------|------|
| **Firecracker** | requests | microVM 管理 |
| **飞书 SDK** | lark-oapi | 飞书 API 调用 |

### 6.3 开发依赖

- pytest + pytest-asyncio - 测试框架
- ruff - Linter
- mypy - 类型检查
- black - 代码格式化

---

## 7. 部署架构

### 7.1 安装方式

```bash
# 从源码安装
git clone https://github.com/DaTingLi/heimaclaw
cd heimaclaw
pip install -e .

# 或使用 pip
pip install heimaclaw
```

### 7.2 初始化

```bash
# 初始化项目
heimaclaw init --path /opt/heimaclaw

# 配置飞书渠道
heimaclaw channel setup feishu

# 创建 Agent
heimaclaw agent create my-bot --channel feishu
```

### 7.3 启动服务

```bash
# 开发模式
heimaclaw start --reload

# 生产模式
heimaclaw start --host 0.0.0.0 --port 8000 --workers 4
```

### 7.4 目录布局

```
/opt/heimaclaw/              # 安装根目录
├── config/
│   └── config.toml          # 主配置文件
├── logs/                    # 日志目录
├── data/                    # 数据目录
├── sandboxes/               # 沙箱实例
└── agents/                  # Agent 配置
    └── my-agent/
        └── agent.json

~/.heimaclaw/                # 用户配置目录
└── agents/                  # 本地 Agent 配置
```

---

## 8. 配置管理

### 8.1 主配置文件 (`config.toml`)

```toml
[server]
host = "0.0.0.0"
port = 8000
workers = 4

[channels.feishu]
app_id = "cli_xxx"
app_secret = "xxx"
encrypt_key = "xxx"

[channels.wecom]
corp_id = "xxx"
agent_id = "xxx"
secret = "xxx"

[llm]
provider = "openai"
model_name = "gpt-4"
api_key = "sk-xxx"

[sandbox]
backend = "firecracker"
memory_mb = 128
cpu_count = 1
pool_size = 5
```

### 8.2 Agent 配置 (`agent.json`)

```json
{
  "name": "my-agent",
  "description": "智能客服机器人",
  "channel": "feishu",
  "enabled": true,
  "llm": {
    "provider": "openai",
    "model_name": "gpt-4"
  },
  "sandbox": {
    "enabled": true,
    "type": "firecracker",
    "memory_mb": 128
  }
}
```

---

## 9. 扩展开发

### 9.1 添加新的 LLM Provider

```python
# src/heimaclaw/llm/providers/my_provider.py

from heimaclaw.llm.base import LLMAdapter, LLMConfig

class MyProviderAdapter(LLMAdapter):
    async def chat(self, messages, tools=None):
        # 实现调用逻辑
        pass

# 注册到 registry
PROVIDER_ADAPTERS["my_provider"] = MyProviderAdapter
```

### 9.2 添加新工具

```python
# src/heimaclaw/agent/tools/my_tool.py

from heimaclaw.interfaces import ToolDefinition

MY_TOOL_DEF = {
    "name": "my_tool",
    "description": "我的自定义工具",
    "parameters": {
        "type": "object",
        "properties": {
            "input": {"type": "string"}
        }
    }
}

async def my_tool_handler(input: str) -> str:
    # 实现工具逻辑
    return f"处理结果: {input}"
```

### 9.3 添加新渠道

```python
# src/heimaclaw/channel/my_channel.py

from heimaclaw.interfaces import ChannelAdapter

class MyChannelAdapter(ChannelAdapter):
    async def verify_webhook(self, request):
        pass
    
    async def parse_message(self, request):
        pass
    
    async def send_message(self, session, content):
        pass
```

---

## 📊 性能指标

| 指标 | 目标值 |
|------|--------|
| CLI 启动时间 | < 100ms |
| Webhook 响应时间 | < 200ms |
| 沙箱冷启动 (Firecracker) | < 125ms |
| 沙箱暖启动 (预热) | < 10ms |
| 消息处理吞吐量 | > 100 msg/s |

---

## 🔐 安全特性

- ✅ **硬件级隔离** - Firecracker microVM
- ✅ **敏感信息保护** - API Key 不记录日志
- ✅ **输入校验** - Agent 名称严格验证
- ✅ **Webhook 验证** - 签名校验
- ✅ **沙箱资源限制** - CPU/内存配额

---

## 📚 参考资料

- **GitHub**: https://github.com/DaTingLi/heimaclaw
- **Typer 文档**: https://typer.tiangolo.com/
- **Rich 文档**: https://rich.readthedocs.io/
- **FastAPI 文档**: https://fastapi.tiangolo.com/
- **Firecracker**: https://firecracker-microvm.github.io/

---

**文档生成时间**: 2025-03-24  
**源码版本**: v0.1.0
