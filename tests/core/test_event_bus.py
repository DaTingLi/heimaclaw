"""
Event Bus 单元测试
"""

import asyncio
import json
import pytest
from pathlib import Path
from datetime import datetime
import tempfile

from heimaclaw.core.event_bus import (
    EventBus,
    Event,
    EventType,
    EventLevel,
)


@pytest.fixture
def temp_event_bus():
    """创建临时 Event Bus"""
    with tempfile.TemporaryDirectory() as tmpdir:
        bus = EventBus(base_dir=Path(tmpdir) / "event-bus")
        yield bus


@pytest.mark.asyncio
async def test_emit_event(temp_event_bus):
    """测试发射事件"""
    event = Event(
        type=EventType.TASK_ASSIGNED,
        level=EventLevel.INFO,
        agent_id="test-agent",
        data={"task": "test task"},
    )
    
    await temp_event_bus.emit(event)
    
    # 验证文件已创建
    event_file = temp_event_bus._get_event_file("test-agent")
    assert event_file.exists()
    
    # 验证内容
    with open(event_file) as f:
        line = f.readline()
        loaded = json.loads(line)
        assert loaded["type"] == "task.assigned"
        assert loaded["data"]["task"] == "test task"


@pytest.mark.asyncio
async def test_subscribe_events(temp_event_bus):
    """测试订阅事件"""
    received_events = []
    
    async def on_event(event):
        received_events.append(event)
    
    # 订阅
    temp_event_bus.subscribe("test-agent", on_event)
    
    # 发射事件
    event = Event(
        type=EventType.TASK_ASSIGNED,
        agent_id="test-agent",
        data={"task": "test"},
    )
    await temp_event_bus.emit(event)
    
    # 验证收到
    assert len(received_events) == 1
    assert received_events[0].type == EventType.TASK_ASSIGNED


@pytest.mark.asyncio
async def test_read_events_with_filtering(temp_event_bus):
    """测试事件过滤"""
    # 发射多个事件
    await temp_event_bus.emit(Event(
        type=EventType.TASK_ASSIGNED,
        level=EventLevel.INFO,
        agent_id="main",
        data={"id": 1},
    ))
    
    await temp_event_bus.emit(Event(
        type=EventType.MESSAGE_SENT,
        level=EventLevel.DEBUG,
        agent_id="main",
        data={"msg": "hello"},
    ))
    
    await temp_event_bus.emit(Event(
        type=EventType.ERROR,
        level=EventLevel.ERROR,
        agent_id="main",
        data={"error": "failed"},
    ))
    
    # 读取（自动过滤 DEBUG 和聊天）
    events = await temp_event_bus.read_events(
        agent_id="main",
        subscriber_id="test-sub",
        min_level=EventLevel.INFO,
        skip_chatter=True,
    )
    
    # 应该只有 2 个事件（TASK_ASSIGNED 和 ERROR）
    assert len(events) == 2
    assert events[0].type == EventType.TASK_ASSIGNED
    assert events[1].type == EventType.ERROR


@pytest.mark.asyncio
async def test_checkpoint_resume(temp_event_bus):
    """测试断点恢复"""
    # 第一次发射
    await temp_event_bus.emit(Event(
        type=EventType.TASK_ASSIGNED,
        agent_id="main",
        data={"id": 1},
    ))
    
    # 读取并更新检查点
    events1 = await temp_event_bus.read_events(
        agent_id="main",
        subscriber_id="test-sub",
        update_checkpoint=True,
    )
    assert len(events1) == 1
    
    # 第二次发射
    await temp_event_bus.emit(Event(
        type=EventType.TASK_COMPLETED,
        agent_id="main",
        data={"id": 2},
    ))
    
    # 再次读取（应该只返回新事件）
    events2 = await temp_event_bus.read_events(
        agent_id="main",
        subscriber_id="test-sub",
        update_checkpoint=True,
    )
    assert len(events2) == 1
    assert events2[0].type == EventType.TASK_COMPLETED


@pytest.mark.asyncio
async def test_event_serialization():
    """测试事件序列化"""
    event = Event(
        type=EventType.SUBAGENT_COMPLETED,
        level=EventLevel.INFO,
        agent_id="test",
        session_key="session-123",
        run_id="run-456",
        data={"result": "success"},
    )
    
    # 序列化
    data = event.to_dict()
    assert data["type"] == "subagent.completed"
    assert data["agent_id"] == "test"
    assert data["run_id"] == "run-456"
    
    # 反序列化
    loaded = Event.from_dict(data)
    assert loaded.type == EventType.SUBAGENT_COMPLETED
    assert loaded.agent_id == "test"
    assert loaded.run_id == "run-456"


@pytest.mark.asyncio
async def test_level_weight_filtering(temp_event_bus):
    """测试日志级别过滤"""
    # 发射不同级别的事件
    levels = [
        (EventLevel.DEBUG, EventType.HEARTBEAT),
        (EventLevel.INFO, EventType.TASK_ASSIGNED),
        (EventLevel.WARNING, EventType.STATUS_REPORT),
        (EventLevel.ERROR, EventType.ERROR),
        (EventLevel.CRITICAL, EventType.TASK_FAILED),
    ]
    
    for level, event_type in levels:
        await temp_event_bus.emit(Event(
            type=event_type,
            level=level,
            agent_id="main",
            data={},
        ))
    
    # 读取 WARNING 及以上
    events = await temp_event_bus.read_events(
        agent_id="main",
        subscriber_id="test-sub",
        min_level=EventLevel.WARNING,
        skip_chatter=False,
    )
    
    # 应该有 2 个（WARNING 和 ERROR 和 CRITICAL）
    assert len(events) == 3
    assert events[0].level == EventLevel.WARNING
    assert events[1].level == EventLevel.ERROR
    assert events[2].level == EventLevel.CRITICAL
