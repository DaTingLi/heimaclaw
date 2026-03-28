"""
Event Bus - 基于 JSONL 的轻量级事件总线

参考：
- OpenClaw Event Bus (TypeScript 实现)
- Open edX Event Bus (OEP-52)
- Kafka 的 Pub/Sub 模式

特性：
- 文件持久化（JSONL 格式）
- 日志级别过滤（DEBUG/INFO/WARNING/ERROR/CRITICAL）
- 事件类型过滤
- 聊天消息自动过滤
- 时间戳索引（支持断点恢复）
- 订阅者管理
"""

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional
import aiofiles
from collections import defaultdict


class EventType(str, Enum):
    """事件类型"""

    # 任务相关（必须读取）
    TASK_ASSIGNED = "task.assigned"
    TASK_ACCEPTED = "task.accepted"
    TASK_COMPLETED = "task.completed"
    TASK_FAILED = "task.failed"

    # Subagent 相关
    SUBAGENT_SPAWNED = "subagent.spawned"
    SUBAGENT_STARTED = "subagent.started"
    SUBAGENT_COMPLETED = "subagent.completed"
    SUBAGENT_FAILED = "subagent.failed"
    SUBAGENT_KILLED = "subagent.killed"

    # 工具调用
    TOOL_INVOKED = "tool.invoked"
    TOOL_RESULT = "tool.result"

    # 配置变更（必须读取）
    SKILL_INSTALLED = "skill.installed"
    CONFIG_CHANGED = "config.changed"
    ENV_UPDATED = "env.updated"

    # 聊天消息（自动过滤）
    MESSAGE_SENT = "message.sent"
    MESSAGE_RECEIVED = "message.received"

    # 状态报告（自动过滤）
    STATUS_REPORT = "status.report"
    HEARTBEAT = "heartbeat"
    PROGRESS_REPORT = "progress.report"

    # 错误和生命周期
    ERROR = "error"
    AGENT_START = "agent.start"
    AGENT_END = "agent.end"


class EventLevel(str, Enum):
    """事件级别"""
    DEBUG = "DEBUG"        # 权重 0
    INFO = "INFO"          # 权重 1
    WARNING = "WARNING"    # 权重 2
    ERROR = "ERROR"        # 权重 3
    CRITICAL = "CRITICAL"  # 权重 4


# 级别权重映射
LEVEL_WEIGHTS = {
    EventLevel.DEBUG: 0,
    EventLevel.INFO: 1,
    EventLevel.WARNING: 2,
    EventLevel.ERROR: 3,
    EventLevel.CRITICAL: 4,
}

# 自动过滤的聊天事件类型（权重 <= 1）
SKIP_CHAT_TYPES = {
    EventType.MESSAGE_SENT,
    EventType.MESSAGE_RECEIVED,
    EventType.STATUS_REPORT,
    EventType.HEARTBEAT,
    EventType.PROGRESS_REPORT,
}


@dataclass
class Event:
    """事件结构"""

    type: EventType
    level: EventLevel = EventLevel.INFO
    data: dict[str, Any] = field(default_factory=dict)
    ts: str = field(default_factory=lambda: datetime.now().isoformat())
    agent_id: Optional[str] = None
    session_key: Optional[str] = None
    run_id: Optional[str] = None

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "type": self.type.value,
            "level": self.level.value,
            "ts": self.ts,
            "agent_id": self.agent_id,
            "session_key": self.session_key,
            "run_id": self.run_id,
            "data": self.data,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Event":
        """从字典创建"""
        return cls(
            type=EventType(data["type"]),
            level=EventLevel(data.get("level", "INFO")),
            ts=data.get("ts", datetime.now().isoformat()),
            agent_id=data.get("agent_id"),
            session_key=data.get("session_key"),
            run_id=data.get("run_id"),
            data=data.get("data", {}),
        )


class EventBus:
    """
    事件总线
    
    基于 JSONL 文件的 Pub/Sub 系统，专为多 Agent 协作设计。
    """

    def __init__(self, base_dir: Path | str = ".openclaw/event-bus"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

        # 订阅者映射：agent_id -> [callbacks]
        self._subscribers: dict[str, list[Callable[[Event], None]]] = defaultdict(list)

        # 索引文件路径
        self.index_file = self.base_dir / "index.json"

        # 异步监听器映射：listener_id -> callback
        self._async_listeners: dict[str, Callable] = {}

        # 确保索引文件存在
        if not self.index_file.exists():
            self._save_index({})

    def _get_event_file(self, agent_id: str) -> Path:
        """获取 Agent 的事件文件路径"""
        return self.base_dir / f"{agent_id}.jsonl"

    def _load_index(self) -> dict:
        """加载索引"""
        try:
            with open(self.index_file) as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _save_index(self, index: dict):
        """保存索引"""
        with open(self.index_file, "w") as f:
            json.dump(index, f, indent=2)

    async def emit(self, event: Event):
        """
        发射事件
        
        1. 持久化到 JSONL 文件
        2. 通知所有订阅者
        """
        # 确定写入哪个 Agent 的事件文件
        agent_id = event.agent_id or "main"
        event_file = self._get_event_file(agent_id)

        # 异步写入 JSONL
        async with aiofiles.open(event_file, mode="a") as f:
            await f.write(json.dumps(event.to_dict()) + "\n")

        # 通知订阅者
        for callback in self._subscribers.get(agent_id, []):
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(event)
                else:
                    callback(event)
            except Exception as e:
                # 订阅者失败不应该影响事件发射
                error(f"EventBus subscriber error: {e}")

    def subscribe(self, agent_id: str, callback: Callable[[Event], None]):
        """
        订阅事件
        
        Args:
            agent_id: 要订阅的 Agent ID
            callback: 事件回调函数
        """
        self._subscribers[agent_id].append(callback)

    def unsubscribe(self, agent_id: str, callback: Callable[[Event], None]):
        """取消订阅"""
        if callback in self._subscribers[agent_id]:
            self._subscribers[agent_id].remove(callback)

    async def read_events(
        self,
        agent_id: str,
        subscriber_id: str,
        min_level: EventLevel = EventLevel.INFO,
        event_types: Optional[list[EventType]] = None,
        skip_chatter: bool = True,
        update_checkpoint: bool = False,
    ) -> list[Event]:
        """
        读取事件（支持过滤和断点恢复）
        
        Args:
            agent_id: 要读取的 Agent ID
            subscriber_id: 订阅者身份（用于断点恢复）
            min_level: 最小日志级别
            event_types: 指定事件类型（None 表示不限制）
            skip_chatter: 是否自动过滤聊天消息
            update_checkpoint: 是否更新检查点
        
        Returns:
            事件列表
        """
        event_file = self._get_event_file(agent_id)
        if not event_file.exists():
            return []

        # 加载上次读取的时间戳
        index = self._load_index()
        last_ts = index.get("last_read", {}).get(agent_id, {}).get(f"by_{subscriber_id}", "")

        min_weight = LEVEL_WEIGHTS.get(min_level, 1)
        target_types = set(event_types) if event_types else None

        events = []

        async with aiofiles.open(event_file, mode="r") as f:
            async for line in f:
                line = line.strip()
                if not line:
                    continue

                try:
                    event_dict = json.loads(line)
                    event = Event.from_dict(event_dict)

                    # 1. 时间戳过滤（断点恢复）
                    if last_ts and event.ts <= last_ts:
                        continue

                    # 2. 日志级别过滤
                    event_weight = LEVEL_WEIGHTS.get(event.level, 1)
                    if event_weight < min_weight:
                        continue

                    # 3. 事件类型过滤
                    if target_types:
                        if event.type not in target_types:
                            continue
                    elif skip_chatter and event_weight <= 1:
                        # 自动过滤聊天消息
                        if event.type in SKIP_CHAT_TYPES:
                            continue

                    events.append(event)

                except json.JSONDecodeError:
                    continue

        # 按时间戳排序
        events.sort(key=lambda e: e.ts)

        # 更新检查点
        if update_checkpoint and events:
            last_event_ts = events[-1].ts
            if "last_read" not in index:
                index["last_read"] = {}
            if agent_id not in index["last_read"]:
                index["last_read"][agent_id] = {}
            index["last_read"][agent_id][f"by_{subscriber_id}"] = last_event_ts
            self._save_index(index)

        return events

    def get_checkpoint(self, agent_id: str, subscriber_id: str) -> str:
        """获取检查点时间戳"""
        index = self._load_index()
        return index.get("last_read", {}).get(agent_id, {}).get(f"by_{subscriber_id}", "")

    def clear_checkpoint(self, agent_id: str, subscriber_id: str):
        """清除检查点"""
        index = self._load_index()
        if "last_read" in index and agent_id in index["last_read"]:
            index["last_read"][agent_id].pop(f"by_{subscriber_id}", None)
            self._save_index(index)


# 添加异步监听器支持

    def add_async_listener(self, listener_id: str, callback):
        """
        添加异步监听器
        
        Args:
            listener_id: 监听器唯一 ID
            callback: 回调函数（可以是异步的）
        """
        self._async_listeners = getattr(self, '_async_listeners', {})
        if listener_id not in self._async_listeners:
            self._async_listeners[listener_id] = callback
            info(f"[EventBus] 添加监听器: {listener_id}")
    
    def remove_listener(self, listener_id: str):
        """移除监听器"""
        self._async_listeners = getattr(self, '_async_listeners', {})
        if listener_id in self._async_listeners:
            del self._async_listeners[listener_id]
            info(f"[EventBus] 移除监听器: {listener_id}")
    
    def get_async_listener_ids(self) -> list:
        """获取所有监听器 ID"""
        self._async_listeners = getattr(self, '_async_listeners', {})
        return list(self._async_listeners.keys())
    
    async def emit(self, event: Event):
        """
        发射事件
        
        1. 持久化到 JSONL 文件
        2. 通知所有订阅者（包括异步监听器）
        """
        # 调试日志
        信息(f"[EventBus DEBUG] emit called: type={event.type.value}, agent_id={event.agent_id}")
        信息(f"[EventBus DEBUG] _async_listeners id={id(self._async_listeners)}, keys={list(self._async_listeners.keys())}")
        
        # 确定写入哪个 Agent 的事件文件
        agent_id = event.agent_id or "main"
        event_file = self._get_event_file(agent_id)

        # 异步写入 JSONL
        async with aiofiles.open(event_file, mode="a") as f:
            await f.write(json.dumps(event.to_dict()) + "\n")

        # 通知订阅者（原有逻辑）
        for callback in self._subscribers.get(agent_id, []):
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(event)
                else:
                    callback(event)
            except Exception as e:
                error(f"EventBus subscriber error: {e}")
        
        # 通知异步监听器（新增）
        信息(f"[EventBus DEBUG] 准备通知 {len(self._async_listeners)} 个异步监听器")
        for listener_id, callback in self._async_listeners.items():
            信息(f"[EventBus DEBUG]   -> 通知监听器: {listener_id}")
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(event)
                else:
                    callback(event)
            except Exception as e:
                error(f"EventBus async listener error: {e}")
