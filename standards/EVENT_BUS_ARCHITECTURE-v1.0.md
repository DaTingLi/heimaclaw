# Event Bus + Subagent 架构标准 v1.0

## 架构概述

HeiMaClaw 采用 **Event Bus + Subagent** 架构， 提供生产级多 Agent 协作能力。

### 核心组件

```
┌─────────────────────────────────────────────────────────────────┐
│                          主 Agent                                │
│  上下文: 2K tokens（始终保持干净）                                │
│  模型: claude-opus-4（贵）                                       │
└───────────────┬──────────────┬──────────────┬──────────────────┘
                │              │              │
         spawnSubagent  spawnSubagent  spawnSubagent
                │              │              │
                ▼              ▼              ▼
┌──────────────┐ ┌────────────┐ ┌────────────┐
│ Subagent A   │ │ Subagent B │ │ Subagent C │
│ 任务: 审查    │ │ 任务: 文档  │ │ 任务: 部署 │
│ 模型: Sonnet │ │ 模型: Haiku│ │ 模型: Sonnet│
│ 上下文: 50K  │ │ 上下文: 20K│ │ 上下文: 30K│
└──────┬───────┘ └─────┬──────┘ └─────┬──────┘
       │               │               │
       │ 完成后只返回 summary (500 tokens)
       │               │               │
       └───────────────┴───────────────┘
                       │
                       ▼
              ┌────────────────┐
              │   Event Bus    │
              │  (事件总线)     │
              │                │
              │ • subagent.completed
              │ • tool.invoked
              │ • error.occurred
              └────────┬───────┘
                       │
                       ▼
              ┌────────────────┐
              │   主 Agent      │
              │ 接收 3 个总结    │
              │ 上下文: 3.5K     │
              │ （依然很干净）   │
              └────────────────┘
```

## 核心特性

### 1. Event Bus（事件总线）

#### 特性
- 📁 文件持久化（JSONL 格式）
- 🔍 日志级别过滤（DEBUG/INFO/WARNING/ERROR/CRITICAL）
- 🚫 聊天消息自动过滤（节省 tokens）
- ⏰ 时间戳索引（支持断点恢复）
- 🔄 双向同步（30 分钟轮询 + 即时通知）

#### 事件类型
- **必须读取**（任务相关）
  - `task.assigned` - 新任务分配
  - `task.accepted` - 任务接受
  - `task.completed` - 任务完成
  - `task.failed` - 任务失败
  - `subagent.spawned` - 子 Agent 派生
  - `subagent.completed` - 子 Agent 完成
  - `subagent.failed` - 子 Agent 失败

- **自动过滤**（聊天消息）
  - `message.sent` - 聊天消息
  - `message.received` - 接收消息
  - `status.report` - 状态报告
  - `heartbeat` - 心跳

### 2. Subagent（子 Agent）

#### 生命周期

```
PENDING → RUNNING → COMPLETED/FAILED/KILLED/TIMEOUT
```

#### 状态管理
- `PENDING` - 等待启动
- `RUNNING` - 运行中
- `COMPLETED` - 已完成
- `FAILED` - 失败
- `KILLED` - 被杀死
- `TIMEOUT` - 超时

#### 关键特性
- 🪟 每个子任务独立上下文（不污染父 Agent）
- 🚀 并行执行（多个子 Agent 同时运行）
- 💰 模型分层（简单任务用便宜模型，省钱 70%+）
- 🛡️ 故障隔离（子任务失败不影响全局）
- 📊 可观测性（事件全程追踪）

## 性能对比

| 维度 | 传统 ReAct | Event Bus + Subagent |
|------|-----------|---------------------|
| **上下文管理** | 所有历史塞进 200K | 每个子任务独立窗口 |
| **执行模式** | 串行执行 | 并行派生多个 Subagent |
| **模型成本** | 全程用同一个贵模型 | 简单任务用便宜模型（省钱 70%+） |
| **容错性** | 一个工具失败，整个链路中断 | 子任务失败只影响局部 |
| **可观测性** | 黑盒执行，难以调试 | 事件总线全程可追溯 |
| **断点恢复** | 不支持 | 基于时间戳索引自动恢复 |

## 使用示例

### 1. 初始化系统

```python
from heimaclaw.core import EventBus, SubagentRegistry, SubagentSpawner

# 创建 Event Bus
event_bus = EventBus(base_dir=".openclaw/event-bus")

# 创建 Registry
registry = SubagentRegistry(state_dir=".openclaw/subagent-state")

# 创建 Spawner
spawner = SubagentSpawner(
    event_bus=event_bus,
    registry=registry,
    agent_runner_factory=your_runner_factory,
)
```

### 2. 并行派生子 Agent

```python
import asyncio
from heimaclaw.core import SpawnConfig

# 任务 1: 代码审查（用 Sonnet）
task1 = SpawnConfig(
    task="审查代码安全性",
    model="claude-sonnet-4.5",  # $3/M
)

# 任务 2: 写文档（用 Haiku，更便宜）
task2 = SpawnConfig(
    task="生成 API 文档",
    model="claude-haiku-3.5",  # $0.25/M (12x 便宜)
)

# 并行派生
results = await asyncio.gather(
    spawner.spawn(task1, session_key, "main"),
    spawner.spawn(task2, session_key, "main"),
)
```

### 3. 订阅事件

```python
async def on_event(event):
    if event.type == EventType.SUBAGENT_COMPLETED:
        print(f"✅ 子 Agent {event.run_id} 完成!")
        print(f"结果: {event.data['result_text'][:100]}")

# 订阅
event_bus.subscribe("main", on_event)
```

### 4. 读取事件（带过滤）

```python
# 只读取任务相关事件（自动过滤聊天）
events = await event_bus.read_events(
    agent_id="main",
    subscriber_id="coordinator",
    min_level=EventLevel.INFO,
    skip_chatter=True,  # 自动过滤 message.sent/status.report 等
    update_checkpoint=True,  # 自动更新检查点
)

for event in events:
    print(f"[{event.ts}] {event.type.value}: {event.data}")
```

## 成本优化策略

### 模型分层

```python
# 简单任务：用 Haiku（$0.25/1M tokens）
simple_task = SpawnConfig(
    task="格式化 JSON",
    model="claude-haiku-3.5",  # 60x 便宜
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

### 成本对比

**场景：审查代码 + 写文档 + 部署（共 100K tokens）**

- **传统方案**：全程用 Opus → **$1.50**
- **Subagent 方案**：80% 任务用 Haiku → **$0.40**
- **节省：73%**

## 并发控制

### 默认限制

- **最大并发**：5 个子 Agent/会话
- **超时控制**：可配置 `timeout_seconds`
- **失败处理**：自动标记为 `FAILED` 或 `TIMEOUT`

### 自定义限制

```python
spawner = SubagentSpawner(
    event_bus=event_bus,
    registry=registry,
    agent_runner_factory=runner_factory,
    max_concurrent_per_session=10,  # 自定义最大并发
)
```

## 文件结构

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

## 最佳实践

### 1. 断点恢复

```python
# 读取时自动使用上次的时间戳
events = await event_bus.read_events(
    agent_id="main",
    subscriber_id="my-subscriber",
    update_checkpoint=True,  # 自动更新检查点
)

# 如果服务崩溃， 下次启动会从上次的位置继续
```

### 2. 错误处理

```python
async def on_event(event):
    if event.type == EventType.SUBAGENT_FAILED:
        error = event.data.get("error")
        print(f"❌ 子 Agent {event.run_id} 失败: {error}")
        # 可以选择重试或降级
```

### 3. 资源清理

```python
# 清理旧记录（超过 24 小时的）
registry.cleanup_old_runs(max_age_hours=24)
```

## 集成到 ReAct 引擎

```python
from heimaclaw.agent.react import ReActEngine
from heimaclaw.core import SubagentSpawner, SpawnConfig

class EnhancedReActEngine(ReActEngine):
    def __init__(self, *args, spawner, **kwargs):
        super().__init__(*args, **kwargs)
        self.spawner = spawner
    
    async def _handle_subagent_task(self, task: str, model: str = None):
        """处理需要派生子 Agent 的任务"""
        config = SpawnConfig(task=task, model=model)
        result = await self.spawner.spawn(
            config,
            self.session_key,
            self.agent_id,
        )
        return f"子 Agent 已派生 (run_id: {result.run_id}). 完成后会通知。"
```

## 监控和调试

### 1. 查看所有活动子 Agent

```python
active_runs = registry.list_active()
for run in active_runs:
    print(f"  - {run.run_id}: {run.status.value} | {run.task}")
```

### 2. 查看特定会话的子 Agent

```python
runs = registry.list_for_requester(session_key)
print(f"共 {len(runs)} 个子 Agent")
```

### 3. 查看事件日志

```python
events = await event_bus.read_events(
    agent_id="main",
    subscriber_id="debug",
    skip_chatter=False,  # 包含所有事件
)
```

## 性能优化建议

1. **并行化**：尽可能并行派生多个子 Agent
2. **模型选择**：简单任务务必使用 Haiku
3. **缓存**：对重复任务，考虑缓存结果
4. **超时设置**：根据任务复杂度设置合理超时
5. **监控**：定期检查活动子 Agent 数量

## 故障排查

### 问题：子 Agent 长时间 PENDING

**可能原因**：
- 达到并发限制
- Agent Runner 工厂返回 None
- 缺少必要的配置

**解决方案**：
```python
# 检查并发数量
active_count = registry.count_active_for_session(session_key)
print(f"活动子 Agent: {active_count}/{spawner.max_concurrent_per_session}")
```

### 问题：事件未收到

**可能原因**：
- 未订阅
- 事件被过滤
- 事件文件损坏

**解决方案**：
```python
# 读取所有事件（不过滤）
events = await event_bus.read_events(
    agent_id="main",
    subscriber_id="debug",
    skip_chatter=False,
    min_level=EventLevel.DEBUG,
)
```

## 测试

```bash
# 运行单元测试
pytest tests/core/ -v

# 运行集成示例
python -m heimaclaw.core.integration_example

# 验证系统
python verify_event_bus.py
```

## 参考资料

- OpenClaw Event Bus 实现
- Open edX Event Bus (OEP-52)
- Kafka Pub/Sub 模式
- Python asyncio 并发控制

---

**版本**: v1.0
**更新日期**: 2026-03-19
**维护者**: HeiMaClaw Team
