"""
会话记忆模块

存储当前会话的完整消息历史，支持快速访问最近消息。
"""

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass
class Message:
    """消息数据结构"""

    role: str  # user / assistant / system / tool
    content: str
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    # 可选字段
    message_id: Optional[str] = None
    tool_name: Optional[str] = None
    tool_call_id: Optional[str] = None

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
    channel: str
    user_id: str
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    messages: list[Message] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "session_id": self.session_id,
            "agent_id": self.agent_id,
            "channel": self.channel,
            "user_id": self.user_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "messages": [m.to_dict() for m in self.messages],
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Session":
        """从字典创建"""
        messages = [Message.from_dict(m) for m in data.get("messages", [])]
        return cls(
            session_id=data["session_id"],
            agent_id=data["agent_id"],
            channel=data["channel"],
            user_id=data["user_id"],
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
            messages=messages,
            metadata=data.get("metadata", {}),
        )


class SessionMemory:
    """
    会话记忆管理器

    职责：
    - 存储当前会话的完整消息历史
    - 快速访问最近消息
    - 自动过期清理（7天）
    - 持久化到磁盘

    存储格式：~/.heimaclaw/data/sessions/{session_id}.json
    """

    def __init__(
        self,
        agent_id: str,
        session_id: str,
        channel: str,
        user_id: str,
        max_messages: int = 1000,
        retention_days: int = 7,
        data_dir: Optional[Path] = None,
    ):
        """
        初始化会话记忆

        参数:
            agent_id: Agent ID
            session_id: 会话 ID
            channel: 渠道（feishu/wecom）
            user_id: 用户 ID
            max_messages: 最大消息数（默认 1000）
            retention_days: 保留天数（默认 7 天）
            data_dir: 数据目录（默认 ~/.heimaclaw/data/sessions）
        """
        self.agent_id = agent_id
        self.session_id = session_id
        self.channel = channel
        self.user_id = user_id
        self.max_messages = max_messages
        self.retention_days = retention_days

        # 数据目录
        if data_dir is None:
            data_dir = Path.home() / ".heimaclaw" / "data" / "sessions"
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # 会话文件路径
        self.session_file = self.data_dir / f"{session_id}.json"

        # 加载或创建会话
        self.session = self._load_or_create_session()

    def _load_or_create_session(self) -> Session:
        """加载或创建会话"""
        if self.session_file.exists():
            try:
                data = json.loads(self.session_file.read_text(encoding="utf-8"))
                return Session.from_dict(data)
            except Exception:
                # 加载失败，创建新会话
                pass

        # 创建新会话
        return Session(
            session_id=self.session_id,
            agent_id=self.agent_id,
            channel=self.channel,
            user_id=self.user_id,
        )

    def add_message(
        self,
        role: str,
        content: str,
        metadata: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Message:
        """
        添加消息

        参数:
            role: 角色（user/assistant/system/tool）
            content: 消息内容
            metadata: 元数据
            **kwargs: 其他字段（message_id, tool_name, tool_call_id）

        返回:
            Message 对象
        """
        message = Message(
            role=role,
            content=content,
            metadata=metadata or {},
            **kwargs,
        )

        self.session.messages.append(message)
        self.session.updated_at = time.time()

        # 检查是否超过最大消息数
        if len(self.session.messages) > self.max_messages:
            # 保留最近的消息
            self.session.messages = self.session.messages[-self.max_messages :]

        # 持久化
        self._save()

        return message

    def get_messages(
        self,
        limit: Optional[int] = None,
        roles: Optional[list[str]] = None,
    ) -> list[Message]:
        """
        获取消息列表

        参数:
            limit: 限制数量（默认返回全部）
            roles: 角色过滤（如 ["user", "assistant"]）

        返回:
            Message 列表
        """
        messages = self.session.messages

        # 角色过滤
        if roles:
            messages = [m for m in messages if m.role in roles]

        # 限制数量
        if limit:
            messages = messages[-limit:]

        return messages

    def get_recent_messages(self, count: int = 10) -> list[Message]:
        """
        获取最近的消息

        参数:
            count: 消息数量（默认 10 条）

        返回:
            Message 列表
        """
        return self.session.messages[-count:]

    def clear_messages(self) -> None:
        """清空消息"""
        self.session.messages = []
        self.session.updated_at = time.time()
        self._save()

    def get_message_count(self) -> int:
        """获取消息数量"""
        return len(self.session.messages)

    def get_context_for_llm(self, max_messages: int = 20) -> list[dict[str, str]]:
        """
        获取用于 LLM 的上下文

        参数:
            max_messages: 最大消息数（默认 20）

        返回:
            消息列表（OpenAI 格式）
        """
        messages = self.get_recent_messages(max_messages)

        # 转换为 OpenAI 格式
        result = []
        for msg in messages:
            result.append(
                {
                    "role": msg.role,
                    "content": msg.content,
                }
            )

        return result

    def _save(self) -> None:
        """持久化会话"""
        try:
            data = self.session.to_dict()
            self.session_file.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            # 保存失败，记录错误但不中断
            import logging

            logging.error(f"保存会话失败: {e}")

    def cleanup_expired(self) -> None:
        """清理过期会话"""
        # 清理超过 retention_days 的会话文件
        cutoff_time = time.time() - (self.retention_days * 86400)

        for session_file in self.data_dir.glob("*.json"):
            try:
                data = json.loads(session_file.read_text(encoding="utf-8"))
                updated_at = data.get("updated_at", 0)

                if updated_at < cutoff_time:
                    session_file.unlink()
            except Exception:
                # 读取失败，跳过
                pass

    @staticmethod
    def cleanup_all_expired(
        data_dir: Optional[Path] = None, retention_days: int = 7
    ) -> int:
        """
        清理所有过期会话（静态方法）

        参数:
            data_dir: 数据目录
            retention_days: 保留天数

        返回:
            清理的会话数量
        """
        if data_dir is None:
            data_dir = Path.home() / ".heimaclaw" / "data" / "sessions"

        data_dir = Path(data_dir)
        if not data_dir.exists():
            return 0

        cutoff_time = time.time() - (retention_days * 86400)
        cleaned_count = 0

        for session_file in data_dir.glob("*.json"):
            try:
                data = json.loads(session_file.read_text(encoding="utf-8"))
                updated_at = data.get("updated_at", 0)

                if updated_at < cutoff_time:
                    session_file.unlink()
                    cleaned_count += 1
            except Exception:
                # 读取失败，跳过
                pass

        return cleaned_count
