#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HeiMaClaw Event Bus + Subagent 简单演示
"""

import asyncio
import tempfile
from pathlib import Path

# 导入核心模块
from heimaclaw.core import (
    EventBus, Event, EventType, EventLevel,
    SubagentRegistry, SubagentRun, SubagentStatus,
    SpawnConfig
)


async def demo_event_bus():
    """演示 Event Bus 基本功能"""
    print("\n" + "="*60)
    print("Event Bus 基本功能演示")
    print("="*60)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # 1. 创建 Event Bus
        bus = EventBus(base_dir=Path(tmpdir) / "event-bus")
        print("✓ Event Bus 已创建")
        
        # 2. 订阅事件
        received_events = []
        
        async def on_event(event: Event):
            received_events.append(event)
            print(f"  📨 收到事件: {event.type.value}")
        
        bus.subscribe("main", on_event)
        print("✓ 已订阅 main Agent 事件")
        
        # 3. 发射不同类型的事件
        events = [
            Event(
                type=EventType.TASK_ASSIGNED,
                level=EventLevel.INFO,
                agent_id="main",
                data={"task": "测试任务1"},
            ),
            Event(
                type=EventType.SUBAGENT_SPAWNED,
                level=EventLevel.INFO,
                agent_id="main",
                run_id="run-001",
                data={"task": "代码审查"},
            ),
            Event(
                type=EventType.MESSAGE_SENT,
                level=EventLevel.DEBUG,  # 这个会被过滤
                agent_id="main",
                data={"msg": "hello"},
            ),
        ]
        
        print("\n发射 3 个事件...")
        for event in events:
            await bus.emit(event)
        
        print(f"\n✓ 共接收 {len(received_events)} 个事件")
        
        # 4. 读取事件（带过滤）
        print("\n读取事件（自动过滤聊天消息）...")
        filtered = await bus.read_events(
            agent_id="main",
            subscriber_id="demo",
            min_level=EventLevel.INFO,
            skip_chatter=True,
            update_checkpoint=True,
        )
        
        print(f"✓ 过滤后剩余 {len(filtered)} 个事件:")
        for event in filtered:
            print(f"  - {event.type.value}: {event.data}")


async def demo_subagent_registry():
    """演示 Subagent Registry 功能"""
    print("\n" + "="*60)
    print("Subagent Registry 功能演示")
    print("="*60)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # 1. 创建 Registry
        registry = SubagentRegistry(state_dir=Path(tmpdir) / "subagent-state")
        print("✓ Subagent Registry 已创建")
        
        # 2. 注册 3 个子 Agent
        session_key = "session:main:demo"
        
        runs = []
        for i in range(3):
            run = SubagentRun(
                task=f"测试任务 {i+1}",
                requester_session_key=session_key,
                model="claude-sonnet-4.5" if i % 2 == 0 else "claude-haiku-3.5",
            )
            run_id = registry.register(run)
            runs.append(run_id)
            print(f"  ✓ 注册子 Agent {run_id}: {run.task}")
        
        # 3. 启动第一个子 Agent
        registry.mark_started(runs[0])
        print(f"\n✓ 子 Agent {runs[0]} 已启动")
        
        # 4. 完成第一个子 Agent
        registry.mark_completed(runs[0], "任务 1 完成！")
        print(f"✓ 子 Agent {runs[0]} 已完成")
        
        # 5. 查询统计
        active = registry.count_active_for_session(session_key)
        all_runs = registry.list_for_requester(session_key)
        
        print(f"\n📊 统计信息:")
        print(f"  - 活动子 Agent: {active}")
        print(f"  - 总运行数: {len(all_runs)}")
        
        # 6. 显示详情
        print(f"\n📋 子 Agent 详情:")
        for run_id in runs:
            run = registry.get(run_id)
            print(f"  - {run_id}: {run.status.value} | {run.task}")


async def demo_parallel_spawning():
    """演示并行派生概念"""
    print("\n" + "="*60)
    print("并行派生演示（概念示例）")
    print("="*60)
    
    tasks = [
        ("代码审查", "claude-sonnet-4.5"),
        ("写文档", "claude-haiku-3.5"),
        ("性能优化", "claude-opus-4"),
    ]
    
    print("\n准备派生 3 个并行子 Agent:")
    for i, (task, model) in enumerate(tasks, 1):
        cost = {"claude-sonnet-4.5": "$3/M", "claude-haiku-3.5": "$0.25/M", "claude-opus-4": "$15/M"}
        print(f"  {i}. {task} ({model}, {cost[model]})")
    
    print("\n⏱️ 传统串行执行:")
    print("  0s ──[代码审查 30s]── 30s")
    print("  30s ──[写文档 20s]──── 50s")
    print("  50s ──[性能优化 40s]── 90s")
    print("  总耗时: 90秒, 成本: $1.50 (全程 Opus)")
    
    print("\n🚀 Subagent 并行执行:")
    print("  0s ──[代码审查 30s]── 30s")
    print("    └─[写文档 20s]──── 20s")
    print("    └─[性能优化 40s]── 40s")
    print("  总耗时: 40秒, 成本: $0.40 (分层模型)")
    print("  ⚡ 节省 55% 时间 + 73% 成本")


async def main():
    """主函数"""
    print("="*60)
    print("HeiMaClaw Event Bus + Subagent 演示")
    print("="*60)
    
    # 1. Event Bus 演示
    await demo_event_bus()
    
    # 2. Subagent Registry 演示
    await demo_subagent_registry()
    
    # 3. 并行派生演示
    await demo_parallel_spawning()
    
    print("\n" + "="*60)
    print("✅ 所有演示完成！")
    print("="*60)
    print("\n📖 更多信息:")
    print("  - 文档: cat docs/EVENT_BUS_SUBAGENT.md")
    print("  - 测试: pytest tests/core/ -v")
    print("  - 示例: cat src/heimaclaw/core/integration_example.py")


if __name__ == "__main__":
    asyncio.run(main())
