"""
Agent 事件流系统

基于 pi-mono EventStream 设计理念：
- 事件驱动架构
- 支持流式输出
- 类型安全的事件
"""
import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional


class EventType(str, Enum):
    """事件类型"""
    AGENT_START = "agent_start"
    TURN_START = "turn_start"
    MESSAGE_START = "message_start"
    MESSAGE_END = "message_end"
    MESSAGE_CONTENT = "message_content"
    TOOL_CALL_START = "tool_call_start"
    TOOL_CALL_END = "tool_call_end"
    TOOL_RESULT = "tool_result"
    TURN_END = "turn_end"
    AGENT_END = "agent_end"
    ERROR = "error"
    STREAMING = "streaming"


@dataclass
class AgentEvent:
    """Agent 事件"""
    type: EventType
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "type": self.type.value,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
        }


class EventStream:
    """
    事件流

    支持：
    - 事件发射
    - 事件监听
    - 流式处理
    - 异步迭代
    """

    def __init__(self, end_check: Callable[[AgentEvent], bool] = None):
        self._queue: asyncio.Queue[Optional[AgentEvent]] = asyncio.Queue()
        self._end_check = end_check or (lambda e: e.type == EventType.AGENT_END)
        self._ended = False
        self._listeners: list[Callable[[AgentEvent], None]] = []
        self._events: list[AgentEvent] = []

    def push(self, event: AgentEvent) -> None:
        """发射事件"""
        self._events.append(event)
        for listener in self._listeners:
            listener(event)
        self._queue.put_nowait(event)

    def end(self, final_data: Any = None) -> None:
        """结束事件流"""
        if not self._ended:
            self._ended = True
            self._queue.put_nowait(None)

    async def get_event(self) -> Optional[AgentEvent]:
        """获取事件（异步）"""
        event = await self._queue.get()
        return event

    def add_listener(self, listener: Callable[[AgentEvent], None]) -> None:
        """添加监听器"""
        self._listeners.append(listener)

    def remove_listener(self, listener: Callable[[AgentEvent], None]) -> None:
        """移除监听器"""
        self._listeners.remove(listener)

    def is_ended(self) -> bool:
        """是否已结束"""
        return self._ended

    def get_events(self) -> list[AgentEvent]:
        """获取所有事件"""
        return self._events.copy()

    def __aiter__(self):
        """异步迭代器"""
        return self

    async def __anext__(self) -> AgentEvent:
        """异步获取下一个事件"""
        if self._ended and self._queue.empty():
            raise StopAsyncIteration
        event = await self.get_event()
        if event is None:
            raise StopAsyncIteration
        return event


class StreamingText:
    """流式文本收集器"""

    def __init__(self):
        self._text = ""
        self._delta_callbacks: list[Callable[[str], None]] = []

    def append(self, delta: str) -> None:
        """追加文本片段"""
        self._text += delta
        for cb in self._delta_callbacks:
            cb(delta)

    @property
    def text(self) -> str:
        """获取完整文本"""
        return self._text

    def add_delta_callback(self, cb: Callable[[str], None]) -> None:
        """添加增量回调"""
        self._delta_callbacks.append(cb)

    def reset(self) -> None:
        """重置"""
        self._text = ""
        self._delta_callbacks = []


def create_event_stream() -> EventStream:
    """创建事件流"""
    return EventStream()
