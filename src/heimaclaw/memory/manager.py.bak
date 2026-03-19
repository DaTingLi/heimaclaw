"""
记忆管理器

整合 4 层记忆系统，提供统一的接口。
数据流：消息 → SessionMemory → DailyMemory → LongTermMemory → 上下文组装 → LLM
"""

from pathlib import Path
from typing import Any, Optional

from heimaclaw.memory.budget import ContextBudget
from heimaclaw.memory.daily import DailyMemory
from heimaclaw.memory.longterm import LongTermMemory
from heimaclaw.memory.session import Message, SessionMemory


class MemoryManager:
    """
    记忆管理器

    数据流：
    1. 消息输入 → add_message() → SessionMemory
    2. 会话压缩 → DailyMemory（自动/手动）
    3. 重要事件 → LongTermMemory（手动提取）
    4. 上下文组装 → get_context_for_llm() → Token预算管理 → LLM

    使用示例：
        memory = MemoryManager(
            agent_id="my-agent",
            session_id="session-123",
            channel="feishu",
            user_id="user-456",
        )

        # 添加消息
        memory.add_message("user", "你好")
        memory.add_message("assistant", "Hi!")

        # 获取上下文（自动组装 4 层记忆）
        context = memory.get_context_for_llm()

        # 提取重要事件到长期记忆
        memory.extract_important_event("用户偏好使用中文")
    """

    def __init__(
        self,
        agent_id: str,
        session_id: str,
        channel: str,
        user_id: str,
        max_session_messages: int = 1000,
        daily_retention_days: int = 30,
        session_retention_days: int = 7,
        max_tokens: int = 128000,
        data_dir: Optional[Path] = None,
    ):
        """
        初始化记忆管理器

        参数:
            agent_id: Agent ID
            session_id: 会话 ID
            channel: 渠道（feishu/wecom）
            user_id: 用户 ID
            max_session_messages: 会话最大消息数（默认 1000）
            daily_retention_days: 日常记忆保留天数（默认 30）
            session_retention_days: 会话记忆保留天数（默认 7）
            max_tokens: 最大 Token 数（默认 128K）
            data_dir: 数据目录（默认 ~/.heimaclaw/data）
        """
        self.agent_id = agent_id
        self.session_id = session_id
        self.channel = channel
        self.user_id = user_id

        # 数据目录
        if data_dir is None:
            data_dir = Path.home() / ".heimaclaw" / "data"
        self.data_dir = Path(data_dir)

        # 初始化 3 层记忆
        # Level 1: 会话记忆
        self.session_memory = SessionMemory(
            agent_id=agent_id,
            session_id=session_id,
            channel=channel,
            user_id=user_id,
            max_messages=max_session_messages,
            retention_days=session_retention_days,
            data_dir=self.data_dir / "sessions",
        )

        # Level 2: 日常记忆
        self.daily_memory = DailyMemory(
            agent_id=agent_id,
            retention_days=daily_retention_days,
            memory_dir=self.data_dir / "agents" / agent_id / "memory",
        )

        # Level 3: 长期记忆
        self.longterm_memory = LongTermMemory(
            agent_id=agent_id,
            memory_file=self.data_dir / "agents" / agent_id / "MEMORY.md",
        )

        # Token 预算管理
        self.budget_manager = ContextBudget(max_tokens=max_tokens)

    def add_message(
        self,
        role: str,
        content: str,
        metadata: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Message:
        """
        添加消息到会话记忆

        参数:
            role: 角色（user/assistant/system/tool）
            content: 消息内容
            metadata: 元数据
            **kwargs: 其他字段

        返回:
            Message 对象
        """
        return self.session_memory.add_message(role, content, metadata, **kwargs)

    def get_context_for_llm(self, max_messages: int = 20) -> dict[str, Any]:
        """
        获取用于 LLM 的上下文（自动组装 4 层记忆）

        参数:
            max_messages: 最大消息数（默认 20）

        返回:
            上下文字典（包含系统提示、消息历史等）
        """
        # 1. 获取最近消息
        recent_messages = self.session_memory.get_recent_messages(max_messages)
        messages_text = [
            {"role": msg.role, "content": msg.content} for msg in recent_messages
        ]

        # 2. 获取今天的日常记忆
        daily_memory_text = self.daily_memory.get_summary()

        # 3. 获取长期记忆（用户画像 + 重要事件）
        longterm_text = self.longterm_memory.get_section("用户画像")
        if not longterm_text:
            longterm_text = self.longterm_memory.get_section("重要事件记录")

        # 4. 构建系统提示
        system_prompt = self._build_system_prompt(
            daily_memory=daily_memory_text,
            longterm_memory=longterm_text,
        )

        # 5. Token 预算分配
        allocated = self.budget_manager.allocate(
            system_prompt=system_prompt,
            recent_messages=[msg.content for msg in recent_messages],
            daily_memory=daily_memory_text,
            longterm_memory=longterm_text,
        )

        # 6. 返回完整上下文
        return {
            "system_prompt": allocated["system_prompt"],
            "messages": messages_text,
            "context_info": {
                "session_messages": len(recent_messages),
                "has_daily_memory": bool(daily_memory_text),
                "has_longterm_memory": bool(longterm_text),
                "token_usage": self.budget_manager.usage_stats["total_used"],
            },
        }

    def extract_important_event(
        self,
        event: str,
        event_type: str = "milestone",
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        """
        提取重要事件到长期记忆

        参数:
            event: 事件描述
            event_type: 事件类型（milestone/decision/preference）
            metadata: 元数据
        """
        self.longterm_memory.add_important_event(event, event_type, metadata)

    def add_daily_event(
        self,
        event: str,
        event_type: str = "general",
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        """
        添加日常事件

        参数:
            event: 事件描述
            event_type: 事件类型（general/important/decision）
            metadata: 元数据
        """
        self.daily_memory.add_event(event, event_type=event_type, metadata=metadata)

    def get_usage_report(self) -> dict[str, Any]:
        """
        获取使用报告

        返回:
            使用统计字典
        """
        return self.budget_manager.get_usage_report()

    def cleanup_expired(self) -> dict[str, int]:
        """
        清理过期记忆

        返回:
            各层清理数量
        """
        # 清理会话记忆
        session_cleaned = 0  # SessionMemory.cleanup_expired() returns None

        # 清理日常记忆
        daily_cleaned = self.daily_memory.cleanup_expired()

        return {
            "session": session_cleaned,
            "daily": daily_cleaned,
            "total": session_cleaned + daily_cleaned,
        }

    def _build_system_prompt(
        self,
        daily_memory: str = "",
        longterm_memory: str = "",
    ) -> str:
        """
        构建系统提示

        参数:
            daily_memory: 日常记忆
            longterm_memory: 长期记忆

        返回:
            系统提示文本
        """
        parts = []

        # 基础信息
        parts.append(f"Agent ID: {self.agent_id}")
        parts.append(f"User ID: {self.user_id}")

        # 长期记忆
        if longterm_memory:
            parts.append(f"\n长期记忆:\n{longterm_memory}")

        # 日常记忆
        if daily_memory:
            parts.append(f"\n今日事件:\n{daily_memory}")

        return "\n".join(parts)
