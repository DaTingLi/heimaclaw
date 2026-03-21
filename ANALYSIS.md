# HeiMaClaw 记忆能力与长时任务处理问题分析

## 问题概述

用户通过飞书发送任务："帮我运行/tmp/hello_flask.py，如遇环境问题请自行解决"
default agent 回复了步骤和超时错误，但系统缺少：
1. **记忆能力** - 无法记住之前的操作和结果
2. **长时任务处理** - subagent 之间无法协作完成长时任务

## 根本原因分析

### 1. 记忆系统缺陷

#### 现状
- ✅ 有 `MemoryManager` 实现（SQLite 存储、自动摘要）
- ✅ 在 `runner.py:500-513` 中有记忆上下文注入
- ❌ **缺少跨会话记忆共享**
- ❌ **缺少事件驱动的记忆更新**
- ❌ **缺少任务状态持久化**

#### 具体问题
```python
# runner.py:500-513 - 记忆上下文注入
if self._memory_manager and self._context_mode != "minimal":
    self._memory_manager.session_id = session.session_id
    memory_context = self._memory_manager.get_context_for_llm()
    if memory_context:
        history = memory_context + history
```

**问题**：
- 只注入当前 session 的消息历史
- 没有从 EventBus 读取重要事件
- 没有跨 session 的任务状态恢复
- 没有记录 subagent 执行结果到长期记忆

### 2. Subagent 协作缺陷

#### 现状
- ✅ 有 `SubagentSpawner` 实现
- ✅ 有 `EventBus` 事件系统
- ✅ ReAct 引擎支持分派 subagent
- ❌ **Subagent 执行逻辑过于简化**
- ❌ **事件监听范围过窄**
- ❌ **缺少任务状态恢复机制**

#### 具体问题

**问题 1：Subagent 执行逻辑简化**
```python
# subagent_spawn.py:138 - _execute_command
async def _execute_command(self, runner, task: str) -> str:
    # 直接执行命令，不使用 ReAct 循环
    tool_result = await runner.tool_registry.execute(
        name="exec",
        parameters={"command": command},
    )
```

**问题**：
- 只能执行简单命令
- 无法处理复杂任务（如"环境问题自行解决"）
- 没有 ReAct 循环来迭代解决问题
- 没有记忆上下文传递

**问题 2：事件监听范围过窄**
```python
# react.py:222-232 - 事件监听
async def on_subagent_event(event):
    event_session_key = event.data.get("session_key") or event.session_key
    if event_session_key != session_id:  # 只监听当前 session
        return
```

**问题**：
- 只监听当前 session 的事件
- 无法接收跨 session 的 subagent 结果
- EventBus 使用 `agent_id` 作为文件名，无法跨进程通信

**问题 3：缺少任务状态恢复**
- 没有"任务分解 → 持久化 → 恢复执行"的机制
- Subagent 超时后无法从中断点继续
- 没有任务依赖图和状态追踪

## 对比其他系统

### OpenClaw 的优势
1. **事件驱动的任务状态机**
   - 任务状态持久化到 EventBus
   - 任意 Agent 可以读取并恢复任务
   - 支持任务分解和并行执行

2. **全局事件总线**
   - 所有 Agent 共享同一个 EventBus
   - 使用文件系统持久化（JSONL）
   - 支持断点续传和过滤

3. **Subagent 任务队列**
   - 任务队列持久化
   - 支持重试和超时处理
   - 结果缓存避免重复执行

## 解决方案

### 方案 1：增强记忆系统

#### 1.1 事件驱动的记忆更新
```python
# 在 MemoryManager 中添加 EventBus 监听
class MemoryManager:
    def __init__(self, ..., event_bus: EventBus):
        self._event_bus = event_bus
        # 监听所有事件，自动记录重要信息
        self._event_bus.subscribe(self._on_event)

    def _on_event(self, event: Event):
        # 自动记录任务事件到长期记忆
        if event.type in [EventType.TASK_COMPLETED, EventType.SUBAGENT_COMPLETED]:
            self._store.add_event(...)
```

#### 1.2 跨会话记忆共享
```python
# get_context_for_llm 增强版
def get_context_for_llm(self, ..., include_global: bool = True):
    context = []

    # 1. 全局任务历史（跨 session）
    if include_global:
        recent_tasks = self._store.get_recent_tasks(
            agent_id=self.agent_id,
            user_id=self.user_id,
            limit=10
        )
        context.append({"role": "system", "content": f"[最近任务] {recent_tasks}"})

    # 2. 当前 session 消息
    messages = self._store.get_messages(self.session_id, limit=max_messages)
    ...
```

### 方案 2：增强 Subagent 协作

#### 2.1 Subagent 使用完整 ReAct 循环
```python
# subagent_spawn.py 改进
async def _run_subagent(self, run: SubagentRun, config: SpawnConfig, event_key: str):
    runner = self.agent_runner_factory(...)
    await runner.start()

    # 使用完整 ReAct 循环，而不是直接执行
    result = await runner.process_message(
        user_id=run.requester_session_key,
        channel="internal",
        content=run.task,
        session_id=run.child_session_key,
    )

    # 将完整执行过程写入 EventBus
    await self._emit_execution_trace(run, result)
```

#### 2.2 全局事件监听
```python
# react.py 改进
async def _execute_via_subagent(self, step: ExecutionStep, session_id: str):
    # 监听所有相关事件，不仅限于当前 session
    listener_id = f"react:global:{step.step_id}"

    async def on_subagent_event(event):
        # 匹配 run_id 或 task
        if event.run_id == run_id or event.data.get("task") == step.subagent_task:
            await result_queue.put(event.data.get("result_text"))

    self.event_bus.add_async_listener(listener_id, on_subagent_event)
```

#### 2.3 任务状态持久化
```python
# 新增 TaskStateManager
class TaskStateManager:
    def __init__(self, event_bus: EventBus):
        self._event_bus = event_bus
        self._store = TaskStore()  # SQLite 存储

    async def save_task(self, task: Task):
        self._store.save(task)
        await self._event_bus.emit(Event(
            type=EventType.TASK_CREATED,
            data={"task_id": task.task_id, "steps": task.steps}
        ))

    async def resume_task(self, task_id: str) -> Optional[Task]:
        # 从存储恢复任务状态
        task = self._store.get(task_id)
        # 恢复执行...
        return task
```

### 方案 3：改进 EventBus

#### 3.1 跨进程事件共享
```python
# event_bus.py 改进
class EventBus:
    def __init__(self, base_dir: Path | str = "/tmp/heimaclaw_events"):
        # 使用全局路径，所有 Agent 共享
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _get_event_file(self, agent_id: str) -> Path:
        # 使用共享文件，而不是 per-agent 文件
        return self.base_dir / "shared.jsonl"
```

#### 3.2 任务事件过滤
```python
async def read_events(
    self,
    agent_id: str,
    subscriber_id: str,
    task_id: Optional[str] = None,  # 新增：按任务过滤
    ...
):
    events = []
    async with aiofiles.open(event_file, mode="r") as f:
        async for line in f:
            event = Event.from_dict(json.loads(line))

            # 过滤任务相关事件
            if task_id and event.data.get("task_id") != task_id:
                continue

            events.append(event)

    return events
```

## 实施优先级

### 高优先级（核心能力）
1. ✅ **Subagent 使用完整 ReAct 循环** - 解决长时任务处理
2. ✅ **任务状态持久化** - 支持任务恢复和重试
3. ✅ **跨会话记忆共享** - 提供历史上下文

### 中优先级（协作能力）
4. **全局事件监听** - 支持跨 session 的 subagent 结果接收
5. **事件驱动的记忆更新** - 自动记录重要事件
6. **任务分解可视化** - 让用户看到任务进度

### 低优先级（优化体验）
7. **任务缓存** - 避免重复执行相同任务
8. **智能重试** - 失败后自动调整策略
9. **进度报告** - 实时反馈任务状态

## 测试用例

### 测试 1：记忆能力
```python
# 用户在 session A 中运行脚本
await agent.process_message(
    session_id="session_a",
    content="运行 /tmp/hello_flask.py"
)

# 用户在 session B 中询问历史
await agent.process_message(
    session_id="session_b",  # 不同 session
    content="我之前运行过什么脚本？"
)

# 期望：Agent 应该记住 session_a 中的操作
```

### 测试 2：长时任务
```python
# 用户发送复杂任务
await agent.process_message(
    content="运行 /tmp/hello_flask.py，如果遇到依赖问题请自行安装"
)

# 期望：
# 1. Agent 分解任务：检查依赖 → 安装 Flask → 运行脚本
# 2. 持久化任务状态
# 3. Subagent 使用 ReAct 循环解决依赖问题
# 4. 返回完整的执行结果和 URL
```

### 测试 3：任务恢复
```python
# 任务执行中模拟崩溃
# ... 启动任务
# ... 模拟崩溃

# 重启后，用户询问任务状态
await agent.process_message(
    content="我之前的任务完成了吗？"
)

# 期望：Agent 从 EventBus 恢复任务状态并继续执行
```

## 总结

HeiMaClaw 的记忆能力和长时任务处理问题主要源于：
1. **记忆系统**：只实现了基础存储，缺少事件驱动和跨会话共享
2. **Subagent 协作**：执行逻辑简化，无法处理复杂任务
3. **事件总线**：监听范围过窄，无法支持跨 Agent 协作

**关键改进方向**：
- Subagent 必须使用完整 ReAct 循环
- 记忆系统必须监听 EventBus 自动更新
- 任务状态必须持久化到 EventBus/SQLite
- 事件监听必须支持跨 session 和按任务过滤

通过这些改进，HeiMaClaw 可以实现类似 OpenClaw 的长时任务处理能力。
