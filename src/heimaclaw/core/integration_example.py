"""
HeiMaClaw Event Bus + Subagent 集成示例

展示如何在 HeiMaClaw 中使用新的 Event Bus + Subagent 架构
"""

import asyncio
from pathlib import Path
from typing import Optional

from .event_bus import EventBus, Event, EventType, EventLevel
from .subagent_registry import SubagentRegistry, SubagentRun
from .subagent_spawn import SubagentSpawner, SpawnConfig, SpawnResult


# ============ 示例 1: 初始化系统 ============

async def init_event_bus_system():
    """初始化 Event Bus 系统"""

    # 1. 创建 Event Bus
    event_bus = EventBus(base_dir=".openclaw/event-bus")

    # 2. 创建 Subagent Registry
    registry = SubagentRegistry(state_dir=".openclaw/subagent-state")

    # 3. 创建 Subagent Spawner（需要注入 Agent Runner 工厂）
    def agent_runner_factory(**kwargs):
        """Agent Runner 工厂函数"""
        # 这里应该返回实际的 Agent Runner
        # from heimaclaw.agent.runner import AgentRunner
        # return AgentRunner(**kwargs)
        pass

    spawner = SubagentSpawner(
        event_bus=event_bus,
        registry=registry,
        agent_runner_factory=agent_runner_factory,
        max_concurrent_per_session=5,
    )

    return event_bus, registry, spawner


# ============ 示例 2: 订阅事件 ============

async def subscribe_to_events(event_bus: EventBus, agent_id: str = "main"):
    """订阅事件"""

    async def on_event(event: Event):
        """事件回调"""
        print(f"[{event.ts}] [{event.level.value}] {event.type.value}: {event.data}")

        # 处理子 Agent 完成事件
        if event.type == EventType.SUBAGENT_COMPLETED:
            run_id = event.run_id
            result = event.data.get("result_text")
            print(f"✅ Subagent {run_id} 完成: {result[:100]}...")

        # 处理子 Agent 失败事件
        elif event.type == EventType.SUBAGENT_FAILED:
            run_id = event.run_id
            error = event.data.get("error")
            print(f"❌ Subagent {run_id} 失败: {error}")

    # 订阅
    event_bus.subscribe(agent_id, on_event)


# ============ 示例 3: 派生子 Agent ============

async def spawn_subagents_example(spawner: SubagentSpawner, requester_session_key: str):
    """派生多个子 Agent（并行执行）"""

    # 任务 1: 代码审查（用 Sonnet）
    config1 = SpawnConfig(
        task="审查这段代码的安全性问题，重点关注 SQL 注入和 XSS 漏洞",
        model="claude-sonnet-4.5",  # 用便宜模型
        mode="run",
    )

    # 任务 2: 写文档（用 Haiku）
    config2 = SpawnConfig(
        task="为这个 API 接口编写详细的 Markdown 文档",
        model="claude-haiku-3.5",  # 更便宜
        mode="run",
    )

    # 任务 3: 性能优化（用 Opus）
    config3 = SpawnConfig(
        task="分析代码性能瓶颈并提供优化建议",
        model="claude-opus-4",  # 贵模型
        mode="run",
    )

    # 并行派生
    results = await asyncio.gather(
        spawner.spawn(config1, requester_session_key, "main"),
        spawner.spawn(config2, requester_session_key, "main"),
        spawner.spawn(config3, requester_session_key, "main"),
    )

    print(f"已派生 {len(results)} 个子 Agent:")
    for i, result in enumerate(results, 1):
        print(f"  {i}. {result.status} - {result.run_id}")

    return results


# ============ 示例 4: 读取事件（带过滤） ============

async def read_filtered_events(event_bus: EventBus):
    """读取事件（带过滤和断点恢复）"""

    # 读取任务相关事件（自动过滤聊天消息）
    events = await event_bus.read_events(
        agent_id="main",
        subscriber_id="coordinator",
        min_level=EventLevel.INFO,
        skip_chatter=True,  # 自动过滤聊天
        update_checkpoint=True,  # 更新检查点
    )

    print(f"读取到 {len(events)} 个事件:")
    for event in events:
        print(f"  - {event.type.value}: {event.data}")

    return events


# ============ 示例 5: 监听子 Agent 完成并收集结果 ============

async def collect_subagent_results(
    event_bus: EventBus,
    registry: SubagentRegistry,
    requester_session_key: str,
    timeout_seconds: int = 300,
):
    """
    监听子 Agent 完成并收集结果
    
    这是一个阻塞函数，会等待所有子 Agent 完成。
    """
    results = {}
    pending_runs = set(
        run.run_id for run in registry.list_for_requester(requester_session_key)
        if run.status in {SubagentRun.STATUS_PENDING, SubagentRun.STATUS_RUNNING}
    )

    if not pending_runs:
        return results

    async def on_subagent_completed(event: Event):
        """子 Agent 完成回调"""
        if event.type == EventType.SUBAGENT_COMPLETED:
            run_id = event.run_id
            results[run_id] = event.data.get("result_text")
            pending_runs.discard(run_id)

    # 临时订阅
    event_bus.subscribe("main", on_subagent_completed)

    # 等待所有完成或超时
    start_time = asyncio.get_event_loop().time()

    while pending_runs:
        elapsed = asyncio.get_event_loop().time() - start_time
        if elapsed >= timeout_seconds:
            print(f"⏱️ 等待超时，仍有 {len(pending_runs)} 个子 Agent 未完成")
            break

        await asyncio.sleep(1)

    # 取消订阅
    event_bus.unsubscribe("main", on_subagent_completed)

    return results


# ============ 示例 6: 在 ReAct 循环中集成 ============

async def react_with_subagents(
    user_message: str,
    event_bus: EventBus,
    spawner: SubagentSpawner,
    requester_session_key: str,
):
    """
    在 ReAct 循环中使用子 Agent
    
    这是实际的 Agent 推理流程示例。
    """
    from heimaclaw.agent.react import ReActEngine

    # 创建 ReAct 引擎
    engine = ReActEngine(
        tool_registry=None,  # 需要实际的 ToolRegistry
        llm_callable=None,   # 需要实际的 LLM
    )

    # 注入 spawn_subagent 工具
    async def spawn_subagent_tool(task: str, model: Optional[str] = None) -> str:
        """工具：派生子 Agent"""
        config = SpawnConfig(task=task, model=model)
        result = await spawner.spawn(config, requester_session_key, "main")

        if result.status == "accepted":
            return f"子 Agent 已派生 (run_id: {result.run_id})。完成后会通过事件通知。"
        else:
            return f"派生失败: {result.error}"

    # 执行推理
    result = await engine.execute(
        user_message=user_message,
        context=[],
        system_prompt="你可以使用 spawn_subagent 工具来派生子 Agent 并行处理任务。",
    )

    return result


# ============ 完整示例：并行代码审查 + 文档生成 + 部署 ============

async def complete_workflow_example():
    """完整工作流示例"""

    print("🚀 初始化 Event Bus + Subagent 系统...")
    event_bus, registry, spawner = await init_event_bus_system()

    # 订阅事件
    await subscribe_to_events(event_bus, "main")

    requester_session_key = "session:main:example"

    print("\n📋 派生 3 个并行子 Agent...")
    await spawn_subagents_example(spawner, requester_session_key)

    print("\n⏳ 等待所有子 Agent 完成...")
    results = await collect_subagent_results(
        event_bus, registry, requester_session_key, timeout_seconds=300
    )

    print(f"\n✅ 收集到 {len(results)} 个结果:")
    for run_id, result in results.items():
        print(f"  - {run_id}: {result[:100]}...")

    print("\n📊 最终统计:")
    active = registry.list_active()
    print(f"  - 活动子 Agent: {len(active)}")

    all_runs = registry.list_for_requester(requester_session_key)
    print(f"  - 总运行数: {len(all_runs)}")


# ============ 运行示例 ============

if __name__ == "__main__":
    asyncio.run(complete_workflow_example())
