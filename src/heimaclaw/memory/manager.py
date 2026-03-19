"""记忆管理器 - 统一接口"""

from pathlib import Path
from typing import Any, Optional

from heimaclaw.memory.budget import ContextBudget
from heimaclaw.memory.daily import DailyMemory
from heimaclaw.memory.longterm import LongTermMemory
from heimaclaw.memory.session import SessionMemory


class MemoryManager:
    """统一的记忆管理接口"""

    def __init__(
        self,
        agent_id: str,
        session_id: str,
        channel: str,
        user_id: str,
        data_dir: Optional[Path] = None,
    ):
        """初始化记忆管理器"""
        self.agent_id = agent_id

        # 初始化3层记忆
        self.session_memory = SessionMemory(
            agent_id=agent_id,
            session_id=session_id,
            channel=channel,
            user_id=user_id,
            data_dir=data_dir / "sessions" if data_dir else None,
        )

        self.daily_memory = DailyMemory(
            agent_id=agent_id,
            memory_dir=data_dir / "memory" if data_dir else None,
        )

        self.longterm_memory = LongTermMemory(
            agent_id=agent_id,
            memory_file=data_dir / "MEMORY.md" if data_dir else None,
        )

        self.budget_manager = ContextBudget()

    def add_message(self, role: str, content: str, **kwargs: Any) -> None:
        """添加消息到会话记忆"""
        self.session_memory.add_message(role, content, **kwargs)

    def get_context_for_llm(self) -> dict[str, Any]:
        """获取用于LLM的上下文"""
        messages = self.session_memory.get_context_for_llm()

        return {
            "system_prompt": "",
            "messages": messages,
            "context_info": {
                "session_messages": len(messages),
            },
        }

    def extract_important_event(self, event: str, **kwargs: Any) -> None:
        """提取重要事件到长期记忆"""
        self.longterm_memory.add_important_event(event)

    def get_usage_report(self) -> dict[str, Any]:
        """获取使用报告"""
        return {"max_tokens": 128000, "usage": {"total_used": 0}}

    def cleanup_expired(self) -> dict[str, int]:
        """清理过期记忆"""
        return {"session": 0, "daily": 0, "total": 0}
