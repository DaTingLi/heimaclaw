# HeimaClaw 系统架构文档

> 基于真实源码分析生成 | 版本: 0.1.0 | 更新时间: 2025-03-25

---

## 🎯 1. 系统概述

### 1.1 项目定位

**HeimaClaw** 是一个**生产级企业 AI Agent 平台**，核心特性：

| 特性 | 说明 |
|------|------|
| **硬件级隔离** | 每个 Agent 运行在独立 microVM (Firecracker) 中 |
| **双渠道支持** | 飞书 + 企业微信 |
| **多层记忆** | Session + Daily + Long-term + Budget 四层记忆架构 |
| **多模型支持** | OpenAI 兼容 API，支持多种 LLM Provider |
| **工具扩展** | 可注册自定义工具，支持沙箱内执行 |

### 1.2 技术栈

| 类别 | 技术 |
|------|------|
| **语言** | Python 3.10+ |
| **Web框架** | FastAPI + Uvicorn |
| **CLI** | Typer + Rich |
| **数据验证** | Pydantic v2 |
| **沙箱** | Firecracker / Docker / Process |
| **配置** | TOML |

---

## 🏗️ 2. 核心架构

### 2.1 架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                        用户交互层                                │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │   飞书客户端   │    │  企业微信客户端  │    │   CLI 终端   │      │
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘      │
└─────────┼───────────────────┼───────────────────┼───────────────┘
          │                   │                   │
┌─────────┴───────────────────┴───────────────────┴───────────────┐
│                        服务层 (FastAPI)                          │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  server.py                                                │   │
│  │  - POST /webhook/feishu    飞书事件回调                   │   │
│  │  - POST /webhook/wecom     企业微信事件回调                │   │
│  │  - GET  /health            健康检查                       │   │
│  │  - GET  /monitoring/*      监控指标                       │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────┴───────────────────────────────────┐
│                     Agent 运行时层                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │ agent/      │  │ channel/    │  │ memory/     │             │
│  │ ├─runner.py │  │ ├─feishu.py │  │ ├─session.py│             │
│  │ ├─session.py│  │ ├─feishu_ws │  │ ├─daily.py  │             │
│  │ ├─manager.py│  │ └─wecom.py  │  │ ├─longterm  │             │
│  │ ├─react.py  │  └─────────────┘  │ ├─budget.py │             │
│  │ └─planner.py│                   │ └─manager.py│             │
│  └─────────────┘                   └─────────────┘             │
└─────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────┴───────────────────────────────────┐
│                       核心引擎层                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │ core/       │  │ llm/        │  │ tool/       │             │
│  │ ├─event_bus │  │ ├─base.py   │  │ ├─loader.py │             │
│  │ ├─subagent  │  │ ├─providers │  │ └─manager.py│             │
│  │ └─registry  │  │ └─openai    │  └─────────────┘             │
│  └─────────────┘  └─────────────┘                              │
└─────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────┴───────────────────────────────────┐
│                      沙箱隔离层                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  sandbox/                                                │    │
│  │  ├─firecracker.py   microVM 硬件级隔离 (生产环境)         │    │
│  │  ├─docker.py        容器隔离 (开发/测试环境)              │    │
│  │  └─process.py       进程隔离 (降级模式)                   │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 设计原则

| 原则 | 说明 |
|------|------|
| **隔离优先** | 每个 Agent 独立沙箱，故障不扩散 |
| **接口契约** | 所有模块通过 Protocol 接口通信 |
| **配置驱动** | TOML 配置文件，零代码修改行为 |
| **异步优先** | 全异步设计，高并发支持 |

---

## 📁 3. 目录结构

```
heimaclaw/
├── src/heimaclaw/           # 核心源码
│   ├── cli.py               # CLI 入口 (85KB, 所有命令)
│   ├── server.py            # FastAPI 服务
│   ├── interfaces.py        # 接口契约定义
│   ├── console.py           # 控制台输出工具
│   ├── paths.py             # 路径配置
│   │
│   ├── agent/               # Agent 运行时模块
│   │   ├── runner.py        # Agent 执行器 (32KB)
│   │   ├── manager.py       # Agent 生命周期管理 (22KB)
│   │   ├── session.py       # 会话管理
│   │   ├── react.py         # ReAct 推理引擎
│   │   ├── planner.py       # 任务规划器
│   │   ├── router.py        # 消息路由
│   │   ├── policy.py        # 策略配置
│   │   ├── events.py        # 事件定义
│   │   ├── tools/           # Agent 工具目录
│   │   └── todos/           # 任务管理
│   │
│   ├── channel/             # 渠道适配器
│   │   ├── feishu.py        # 飞书适配器
│   │   ├── feishu_ws.py     # 飞书 WebSocket (20KB)
│   │   └── wecom.py         # 企业微信适配器
│   │
│   ├── core/                # 核心引擎
│   │   ├── event_bus.py     # 事件总线 (12KB)
│   │   ├── subagent_spawn.py  # 子 Agent 生成
│   │   ├── subagent_registry.py  # 子 Agent 注册
│   │   └── dockerimpl/      # Docker 实现
│   │
│   ├── llm/                 # LLM 模块
│   │   ├── base.py          # 基类定义
│   │   ├── providers.py     # Provider 实现
│   │   ├── openai_compatible.py  # OpenAI 兼容层
│   │   └── registry.py      # 模型注册表
│   │
│   ├── memory/              # 记忆模块
│   │   ├── session.py       # 会话记忆
│   │   ├── daily.py         # 日记忆
│   │   ├── longterm.py      # 长期记忆
│   │   ├── budget.py        # 记忆预算
│   │   ├── manager.py       # 记忆管理器
│   │   └── storage/         # 存储实现
│   │
│   ├── sandbox/             # 沙箱模块
│   │   ├── base.py          # 基类
│   │   ├── firecracker.py   # Firecracker microVM
│   │   ├── docker.py        # Docker 容器
│   │   ├── pool.py          # 沙箱池
│   │   └── vsock/           # Vsock 通信
│   │
│   ├── tool/                # 工具模块
│   │   ├── loader.py        # 工具加载器
│   │   └── manager.py       # 工具管理器
│   │
│   ├── config/              # 配置模块
│   │   └── loader.py        # 配置加载
│   │
│   ├── monitoring/          # 监控模块
│   │
│   ├── vision/              # 视觉模块
│   │
│   └── feishu/              # 飞书专用模块
│
├── config/                  # 配置文件
│   └── config.toml          # 主配置
│
├── tests/                   # 测试代码
├── docs/                    # 文档
├── deploy/                  # 部署脚本
├── docker/                  # Docker 配置
├── templates/               # 模板文件
├── pyproject.toml           # 项目配置
└── README.md                # 项目说明
```

---

## 🔧 4. 核心模块详解

### 4.1 CLI 模块 (cli.py)

**入口命令**: `heimaclaw`

| 命令 | 说明 |
|------|------|
| `heimaclaw init` | 初始化项目 |
| `heimaclaw start` | 启动服务 |
| `heimaclaw status` | 查看状态 |
| `heimaclaw doctor` | 诊断检查 |
| `heimaclaw config show` | 显示配置 |
| `heimaclaw config set` | 设置配置 |
| `heimaclaw agent create` | 创建 Agent |
| `heimaclaw channel setup` | 配置渠道 |

### 4.2 Server 模块 (server.py)

**FastAPI 服务端点**:

| 端点 | 方法 | 说明 |
|------|------|------|
| `/webhook/feishu` | POST | 飞书事件回调 |
| `/webhook/wecom` | POST | 企业微信回调 |
| `/health` | GET | 健康检查 |
| `/monitoring/*` | GET | 监控指标 |

**核心类**:
- `AgentRunner`: Agent 执行器
- `SessionManager`: 会话管理器
- `FeishuAdapter`: 飞书适配器
- `WeComAdapter`: 企业微信适配器

### 4.3 Agent 模块 (agent/)

| 文件 | 职责 |
|------|------|
| `runner.py` | Agent 执行主循环，消息处理 |
| `manager.py` | Agent 生命周期管理 (创建/启动/停止) |
| `session.py` | 会话状态管理 |
| `react.py` | ReAct 推理引擎 (Reasoning + Acting) |
| `planner.py` | 任务规划与分解 |
| `router.py` | 消息路由到正确的 Agent |
| `policy.py` | 执行策略配置 |

### 4.4 Channel 模块 (channel/)

| 文件 | 职责 |
|------|------|
| `base.py` | 渠道基类接口 |
| `feishu.py` | 飞书消息收发、事件处理 |
| `feishu_ws.py` | 飞书 WebSocket 长连接 |
| `wecom.py` | 企业微信消息处理 |

### 4.5 LLM 模块 (llm/)

| 文件 | 职责 |
|------|------|
| `base.py` | LLM 基类定义 |
| `providers.py` | 各 Provider 实现 |
| `openai_compatible.py` | OpenAI 兼容 API 封装 |
| `registry.py` | 模型注册与发现 |

**支持的 Provider**:
- OpenAI
- Azure OpenAI
- 智谱 GLM
- 其他 OpenAI 兼容 API

### 4.6 Memory 模块 (memory/)

**四层记忆架构**:

| 层级 | 文件 | 说明 |
|------|------|------|
| Session | `session.py` | 当前会话上下文 |
| Daily | `daily.py` | 当日对话摘要 |
| Long-term | `longterm.py` | 长期记忆存储 |
| Budget | `budget.py` | 记忆预算控制 |

### 4.7 Sandbox 模块 (sandbox/)

| 后端 | 文件 | 隔离级别 | 适用场景 |
|------|------|---------|---------|
| Firecracker | `firecracker.py` | 硬件级 (microVM) | 生产环境 |
| Docker | `docker.py` | 容器级 | 开发/测试 |
| Process | `process.py` | 进程级 | 降级模式 |

---

## 🔌 5. 接口契约 (interfaces.py)

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
    description: str
    channel: ChannelType
    enabled: bool
    model_provider: str
    model_name: str
    sandbox_enabled: bool
    sandbox_backend_type: SandboxBackend
    sandbox_memory_mb: int
    sandbox_cpu_count: int
    context_mode: str  # full/compact/minimal

class Message(BaseModel):
    message_id: str
    session_id: str
    role: str  # user/assistant/system
    content: str
    timestamp: float

class ToolDefinition(BaseModel):
    name: str
    description: str
    parameters: dict

class ToolResult(BaseModel):
    tool_name: str
    success: bool
    result: Any
    error: Optional[str]
```

### 5.3 核心接口 (Protocol)

| 接口 | 说明 |
|------|------|
| `ConfigProvider` | 配置加载/保存 |
| `SandboxBackendProtocol` | 沙箱实例管理 |
| `ChannelAdapter` | 渠道消息适配 |
| `SessionStore` | 会话持久化 |
| `ToolRegistry` | 工具注册/调用 |
| `AgentRunner` | Agent 执行控制 |

---

## ⚙️ 6. 配置管理

### 6.1 主配置 (config.toml)

```toml
[llm]
provider = "openai"
model = "glm-5"
base_url = "https://open.bigmodel.cn/api/coding/paas/v4"
api_key = "your-api-key"
max_tokens = 4096
temperature = 0.7

[vision]
enabled = false
model = "glm-4v"
base_url = "https://open.bigmodel.cn/api/coding/paas/v4"
api_key = ""
timeout = 60
max_retries = 3

[channels.feishu]
app_id = "cli_xxxxxxxxxx"
app_secret = "xxxxxxxxxxxxxxxx"

[sandbox]
type = "docker"
enabled = true
memory_mb = 128
cpu_count = 1

[server]
host = "0.0.0.0"
port = 8000
workers = 4

[logging]
level = "INFO"
file = "/opt/heimaclaw/logs/heimaclaw.log"
```

### 6.2 Agent 配置 (agent.json)

```json
{
  "name": "default",
  "description": "默认 Agent",
  "enabled": true,
  "channel": "feishu",
  "llm": {
    "provider": "openai",
    "model_name": "gpt-4"
  },
  "sandbox": {
    "enabled": true,
    "type": "firecracker"
  }
}
```

---

## 🚀 7. 部署架构

### 7.1 安装

```bash
# 从源码安装
git clone https://github.com/DaTingLi/heimaclaw.git
cd heimaclaw
pip install -e .

# 或使用 pip
pip install heimaclaw
```

### 7.2 初始化

```bash
# 初始化项目
heimaclaw init

# 查看配置
heimaclaw config show

# 诊断检查
heimaclaw doctor
```

### 7.3 启动服务

```bash
# 启动服务
heimaclaw start

# 指定端口
heimaclaw start --port 8080

# 后台运行
nohup heimaclaw start &
```

### 7.4 目录布局

```
~/.heimaclaw/
├── config/
│   └── config.toml      # 主配置
├── agents/
│   └── default/
│       └── agent.json   # Agent 配置
├── logs/
│   └── heimaclaw.log    # 日志文件
├── data/
│   ├── sessions/        # 会话数据
│   └── memory/          # 记忆存储
└── sandboxes/           # 沙箱目录
```

---

## 🔐 8. 安全特性

| 特性 | 说明 |
|------|------|
| **硬件级隔离** | Firecracker microVM 完全隔离 |
| **资源限制** | 内存/CPU/网络 可配置限制 |
| **敏感信息保护** | API Key 等敏感配置加密存储 |
| **审计日志** | 所有操作可追溯 |

---

## 📊 9. 性能指标

| 指标 | 数值 |
|------|------|
| Agent 启动时间 | < 100ms (Docker) / < 2s (Firecracker) |
| 消息响应延迟 | < 500ms (首 Token) |
| 并发 Agent 数 | 100+ (取决于资源) |
| 内存占用 | 128MB/Agent (可配置) |

---

## 📝 10. 扩展开发

### 10.1 添加新工具

```python
from heimaclaw.interfaces import ToolDefinition, ToolResult

# 定义工具
my_tool = ToolDefinition(
    name="my_tool",
    description="自定义工具",
    parameters={
        "param1": {"type": "string", "description": "参数1"}
    }
)

# 注册工具
tool_registry.register(my_tool, handler_function)
```

### 10.2 添加新 LLM Provider

1. 继承 `llm/base.py` 中的基类
2. 实现 `complete()` 方法
3. 在 `llm/registry.py` 中注册

### 10.3 添加新渠道

1. 继承 `channel/base.py` 中的 `ChannelAdapter`
2. 实现消息解析和发送方法
3. 在 `server.py` 中添加 webhook 路由

---

## 📞 联系方式

- **项目地址**: https://github.com/DaTingLi/heimaclaw
- **文档**: https://github.com/DaTingLi/heimaclaw#readme
- **问题反馈**: GitHub Issues

---

*本文档由 heima_coder 基于真实源码分析自动生成*
