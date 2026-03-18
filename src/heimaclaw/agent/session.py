"""
会话管理模块

管理 Agent 会话的生命周期、状态持久化。
"""

import asyncio
import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

from heimaclaw.console import agent_event, info, warning
from heimaclaw.interfaces import ChannelType, SessionContext, SessionStatus


@dataclass
class Message:
    """消息数据结构"""

    message_id: str
    session_id: str
    role: str  # user / assistant / system / tool
    content: str
    timestamp: float
    tool_name: Optional[str] = None
    tool_call_id: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict[str, Any])

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Message":
        """从字典创建"""
        return cls(**data)


@dataclass
class Session:
    """会话数据结构"""

    session_id: str
    agent_id: str
    channel: ChannelType
    user_id: str
    status: SessionStatus
    created_at: float
    updated_at: float
    messages: list[Message] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict[str, Any])
    sandbox_instance_id: Optional[str] = None

    def to_context(self) -> SessionContext:
        """转换为 SessionContext"""
        return SessionContext(
            session_id=self.session_id,
            agent_id=self.agent_id,
            channel=self.channel,
            user_id=self.user_id,
            status=self.status,
            metadata=self.context,
        )

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "session_id": self.session_id,
            "agent_id": self.agent_id,
            "channel": self.channel.value,
            "user_id": self.user_id,
            "status": self.status.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "messages": [m.to_dict() for m in self.messages],
            "context": self.context,
            "sandbox_instance_id": self.sandbox_instance_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Session":
        """从字典创建"""
        messages = [Message.from_dict(m) for m in data.get("messages", [])]
        return cls(
            session_id=data["session_id"],
            agent_id=data["agent_id"],
            channel=ChannelType(data["channel"]),
            user_id=data["user_id"],
            status=SessionStatus(data["status"]),
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            messages=messages,
            context=data.get("context", {}),
            sandbox_instance_id=data.get("sandbox_instance_id"),
        )


class SessionManager:
    """
    会话管理器

    负责会话的创建、查询、更新、持久化。
    """

    def __init__(
        self,
        data_dir: str = "/opt/heimaclaw/data/sessions",
        auto_save: bool = True,
    ):
        """
        初始化会话管理器

        参数:
            data_dir: 会话数据存储目录
            auto_save: 是否自动保存
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.auto_save = auto_save

        self._sessions: dict[str, Session] = {}
        self._lock = asyncio.Lock()

    async def create(
        self,
        agent_id: str,
        channel: ChannelType,
        user_id: str,
    ) -> Session:
        """
        创建新会话

        参数:
            agent_id: Agent ID
            channel: 渠道类型
            user_id: 用户 ID

        返回:
            新创建的会话
        """
        async with self._lock:
            session_id = str(uuid.uuid4())[:8]
            now = time.time()

            session = Session(
                session_id=session_id,
                agent_id=agent_id,
                channel=channel,
                user_id=user_id,
                status=SessionStatus.ACTIVE,
                created_at=now,
                updated_at=now,
            )

            self._sessions[session_id] = session

            agent_event(f"创建会话: {session_id} (agent={agent_id}, user={user_id})")

            if self.auto_save:
                await self._save_session(session)

            return session

    async def get(self, session_id: str) -> Optional[Session]:
        """
        获取会话

        参数:
            session_id: 会话 ID

        返回:
            会话对象，不存在则返回 None
        """
        # 先从内存中查找
        if session_id in self._sessions:
            return self._sessions[session_id]

        # 从文件加载
        session = await self._load_session(session_id)
        if session:
            self._sessions[session_id] = session

        return session

    async def update(self, session: Session) -> None:
        """
        更新会话

        参数:
            session: 要更新的会话
        """
        async with self._lock:
            session.updated_at = time.time()
            self._sessions[session.session_id] = session

            if self.auto_save:
                await self._save_session(session)

    async def delete(self, session_id: str) -> None:
        """
        删除会话

        参数:
            session_id: 会话 ID
        """
        async with self._lock:
            # 从内存中移除
            if session_id in self._sessions:
                del self._sessions[session_id]

            # 删除文件
            session_file = self.data_dir / f"{session_id}.json"
            if session_file.exists():
                session_file.unlink()

            agent_event(f"删除会话: {session_id}")

    async def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        tool_name: Optional[str] = None,
        tool_call_id: Optional[str] = None,
    ) -> Message:
        """
        添加消息到会话

        参数:
            session_id: 会话 ID
            role: 角色（user/assistant/system/tool）
            content: 消息内容
            tool_name: 工具名称（可选）
            tool_call_id: 工具调用 ID（可选）

        返回:
            新创建的消息
        """
        session = await self.get(session_id)

        if not session:
            raise ValueError(f"会话不存在: {session_id}")

        message = Message(
            message_id=str(uuid.uuid4())[:8],
            session_id=session_id,
            role=role,
            content=content,
            timestamp=time.time(),
            tool_name=tool_name,
            tool_call_id=tool_call_id,
        )

        session.messages.append(message)
        await self.update(session)

        return message

    async def get_messages(
        self,
        session_id: str,
        limit: int = 50,
    ) -> list[Message]:
        """
        获取会话消息

        参数:
            session_id: 会话 ID
            limit: 最大消息数

        返回:
            消息列表
        """
        session = await self.get(session_id)

        if not session:
            return []

        return session.messages[-limit:]

    async def list_active(
        self,
        agent_id: Optional[str] = None,
    ) -> list[Session]:
        """
        列出活跃会话

        参数:
            agent_id: 可选的 Agent ID 过滤

        返回:
            活跃会话列表
        """
        sessions = [
            s for s in self._sessions.values() if s.status == SessionStatus.ACTIVE
        ]

        if agent_id:
            sessions = [s for s in sessions if s.agent_id == agent_id]

        return sessions

    async def close_idle(self, max_idle_seconds: int = 3600) -> int:
        """
        关闭空闲会话

        参数:
            max_idle_seconds: 最大空闲时间（秒）

        返回:
            关闭的会话数
        """
        now = time.time()
        closed_count = 0

        async with self._lock:
            for session in list(self._sessions.values()):
                idle_time = now - session.updated_at

                if idle_time > max_idle_seconds:
                    session.status = SessionStatus.CLOSED
                    await self._save_session(session)
                    closed_count += 1
                    info(f"关闭空闲会话: {session.session_id}")

        return closed_count

    async def _save_session(self, session: Session) -> None:
        """保存会话到文件"""
        session_file = self.data_dir / f"{session.session_id}.json"

        with open(session_file, "w", encoding="utf-8") as f:
            json.dump(session.to_dict(), f, ensure_ascii=False, indent=2)

    async def _load_session(self, session_id: str) -> Optional[Session]:
        """从文件加载会话"""
        session_file = self.data_dir / f"{session_id}.json"

        if not session_file.exists():
            return None

        try:
            with open(session_file, encoding="utf-8") as f:
                data = json.load(f)
            return Session.from_dict(data)
        except Exception as e:
            warning(f"加载会话失败: {session_id}, 错误: {e}")
            return None
