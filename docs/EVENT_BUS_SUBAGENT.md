# HeiMaClaw Event Bus + Subagent 架构

## 🌟 核心特性

### 1. Event Bus - 轻量级事件总线

**基于 JSONL 文件**，无需 Kafka/Redis 等外部依赖。

**关键优势：**
- 📁 文件持久化（JSONL 格式）
- 🔍 日志级别过滤（DEBUG/INFO/WARNING/ERROR/CRITICAL）
- 🚫 聊天消息自动过滤（节省 tokens）
- ⏰ 时间戳索引（支持断点恢复）
- 🔄 双向同步（30 分钟轮询 + 即时通知）

### 2. Subagent - 子 Agent 系统

**独立上下文窗口**，彻底解决传统 ReAct 的上下文爆炸问题。

**关键优势：**
- 🪟 每个子任务独立上下文（不污染父 Agent）
- 🚀 并行执行（多个子 Agent 同时运行）
- 💰 模型分层（简单任务用便宜模型，省钱 70%+）
- 🛡️ 故障隔离（子任务失败不影响全局）
- 📊 可观测性（事件全程追踪）

---

## 🚀 快速开始

### 1. 初始化系统

```python
from heimaclaw.core import EventBus, SubagentRegistry, SubagentSpawner

# 创建 Event Bus
event_bus = EventBus(base_dir=".openclaw/event-bus")

# 创建 Registry
registry = SubagentRegistry(state_dir=".openclaw/subagent-state")

# 创建 Spawner（需要注入 Agent Runner 工厂）
def agent_runner_factory(**kwargs):
    from heimaclaw.agent.runner import AgentRunner
    return AgentRunner(**kwargs)

spawner = SubagentSpawner(
    event_bus=event_bus,
    registry=registry,
    agent_runner_factory=agent_runner_factory,
)
```

### 2. 订阅事件

```python
async def on_event(event: Event):
    if event.type == EventType.SUBAGENT_COMPLETED:
        print(f"✅ 子 Agent {event.run_id} 完成!")
        print(f"结果: {event.data['result_text'][:100]}")

# 订阅
event_bus.subscribe("main", on_event)
```

### 3. 派生子 Agent（并行）

```python
import asyncio

# 任务 1: 代码审查（用 Sonnet）
task1 = SpawnConfig(
    task="审查代码安全性",
    model="claude-sonnet-4.5",
)

# 任务 2: 写文档（用 Haiku，更便宜）
task2 = SpawnConfig(
    task="生成 API 文档",
    model="claude-haiku-3.5",
)

# 并行派生
results = await asyncio.gather(
    spawner.spawn(task1, session_key, "main"),
    spawner.spawn(task2, session_key, "main"),
)

print(f"已派生 {len(results)} 个子 Agent")
```

### 4. 读取事件（带过滤）

```python
# 只读取任务相关事件（自动过滤聊天）
events = await event_bus.read_events(
    agent_id="main",
    subscriber_id="coordinator",
    min_level=EventLevel.INFO,
    skip_chatter=True,  # 自动过滤 message.sent/status.report 等
    update_checkpoint=True,
)

for event in events:
    print(f"[{event.ts}] {event.type.value}: {event.data}")
```

---

## 📊 架构对比

### 传统 ReAct vs Event Bus + Subagent

| 维度 | 传统 ReAct | Event Bus + Subagent |
|------|-----------|---------------------|
| **上下文** | 所有历史塞进 200K | 子任务独立窗口 |
| **执行** | 串行（工具1 → 工具2） | 并行派生多个 Subagent |
| **成本** | 全程用同一个模型 | 简单任务用便宜模型 |
| **容错** | 一个工具失败，全局中断 | 子任务失败只影响局部 |
| **可观测** | 黑盒执行 | 事件全程可追溯 |

### 成本对比示例

**场景：审查代码 + 写文档 + 部署（共 100K tokens）**

- **传统方案**：全程用 Opus → $1.50
- **Subagent 方案**：80% 任务用 Haiku → $0.40
- **节省：73%**

---

## 🎯 事件类型

### 必须读取（任务相关）

- `task.assigned` - 新任务分配
- `task.accepted` - 任务接受
- `task.completed` - 任务完成
- `task.failed` - 任务失败
- `subagent.spawned` - 子 Agent 派生
- `subagent.completed` - 子 Agent 完成
- `subagent.failed` - 子 Agent 失败

### 自动过滤（聊天消息）

这些事件默认会被跳过（节省 tokens）：

- `message.sent` - 聊天消息
- `message.received` - 接收消息
- `status.report` - 状态报告
- `heartbeat` - 心跳

**如需读取，设置 `skip_chatter=False`**。

---

## 🔧 高级用法

### 1. 等待所有子 Agent 完成

```python
async def collect_results(registry, event_bus, session_key):
    results = {}
    pending = {
        run.run_id for run in registry.list_for_requester(session_key)
        if run.status in {"pending", "running"}
    }
    
    async def on_complete(event):
        if event.type == EventType.SUBAGENT_COMPLETED:
            results[event.run_id] = event.data["result_text"]
            pending.discard(event.run_id)
    
    event_bus.subscribe("main", on_complete)
    
    # 等待所有完成或超时
    while pending:
        await asyncio.sleep(1)
    
    return results
```

### 2. 模型分层策略

```python
# 简单任务：用 Haiku（$0.25/1M tokens）
simple_task = SpawnConfig(
    task="格式化 JSON",
    model="claude-haiku-3.5",
)

# 中等任务：用 Sonnet（$3/1M tokens）
medium_task = SpawnConfig(
    task="代码审查",
    model="claude-sonnet-4.5",
)

# 复杂任务：用 Opus（$15/1M tokens）
complex_task = SpawnConfig(
    task="系统架构设计",
    model="claude-opus-4",
)
```

### 3. 断点恢复

```python
# 读取时自动使用上次的时间戳
events = await event_bus.read_events(
    agent_id="main",
    subscriber_id="my-subscriber",
    update_checkpoint=True,  # 自动更新检查点
)

# 如果服务崩溃，下次启动会从上次的位置继续
```

---

## 📁 文件结构

```
.openclaw/
├── event-bus/
│   ├── main.jsonl        # 主 Agent 事件
│   ├── work.jsonl        # Work Agent 事件
│   └── index.json        # 检查点索引
│
└── subagent-state/
    └── registry.json     # 子 Agent 注册表
```

---

## 🧪 测试

```bash
# 运行单元测试
pytest tests/core/test_event_bus.py
pytest tests/core/test_subagent.py

# 运行集成示例
python -m heimaclaw.core.integration_example
```

---

## 📖 参考实现

本架构参考了以下项目：

- **OpenClaw TypeScript 实现** (`src/infra/agent-events.ts`, `src/agents/subagent-registry.ts`)
- **Open edX Event Bus** (OEP-52)
- **Kafka** (Pub/Sub 模式)

---

## 🤝 贡献

欢迎提交 Issue 和 PR！

---

## 📄 License

MIT License
