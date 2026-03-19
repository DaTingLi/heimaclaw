"""
HeiMaClaw Core - Event Bus + Subagent 架构

核心特性：
- 基于 JSONL 的轻量级事件总线
- 子 Agent 独立上下文窗口
- 并行任务执行
- 事件持久化和断点恢复
"""

from .event_bus import EventBus, Event, EventType, EventLevel
from .subagent_registry import (
    SubagentRegistry,
    SubagentRun,
    SubagentStatus,
)
from .subagent_spawn import SubagentSpawner, SpawnConfig, SpawnResult

__all__ = [
    # Event Bus
    "EventBus",
    "Event",
    "EventType",
    "EventLevel",
    
    # Subagent Registry
    "SubagentRegistry",
    "SubagentRun",
    "SubagentStatus",
    
    # Subagent Spawner
    "SubagentSpawner",
    "SpawnConfig",
    "SpawnResult",
]
