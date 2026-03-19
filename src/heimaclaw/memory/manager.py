"""
记忆管理器 v2.0

工业级记忆系统：
- SQLite 存储：原子写入，崩溃恢复
- 自动摘要：消息 > 50 条自动压缩
- 智能事件提取：自动识别重要信息
- Token 预算管理：动态分配
"""

from pathlib import Path
from typing import Any, Optional

from heimaclaw.memory.budget import ContextBudget
from heimaclaw.memory.storage.auto_summary import AutoSummary
from heimaclaw.memory.storage.sqlite_store import SQLiteStore


class MemoryManager:
    """
    记忆管理器 v2.0

    整合 4 层记忆系统 + SQLite 存储 + 自动摘要

    数据流：
    消息 → SQLite 存储 → 自动摘要检测 → LLM 摘要压缩 → 上下文组装 → LLM
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
        self.agent_id = agent_id
        self.session_id = session_id
        self.channel = channel
        self.user_id = user_id
        self.max_tokens = max_tokens

        # 数据目录
        if data_dir is None:
            data_dir = Path.home() / ".heimaclaw" / "data"
        self.data_dir = Path(data_dir)

        # SQLite 存储
        db_path = self.data_dir / "memory" / f"{agent_id}.db"
        self._store = SQLiteStore(db_path)
        self._store.initialize()

        # 自动摘要器
        self._auto_summary = AutoSummary(
            message_threshold=50,
            token_threshold=32000,
        )

        # Token 预算管理器
        self._budget = ContextBudget(max_tokens=max_tokens)

        # 标记是否已摘要
        self._summarized = False

    def add_message(
        self,
        role: str,
        content: str,
        user_id: Optional[str] = None,
    ) -> None:
        """
        添加消息到记忆

        参数:
            role: 角色 (user/assistant/system/tool)
            content: 消息内容
            user_id: 用户 ID
        """
        if not self.session_id:
            return

        # 写入 SQLite
        self._store.add_message(
            session_id=self.session_id,
            role=role,
            content=content,
        )

        # 检查是否需要摘要
        msg_count = self._store.get_message_count(self.session_id)
        if self._auto_summary.should_summarize(msg_count, 0) and not self._summarized:
            # 触发自动摘要（实际摘要需要 LLM，这里先标记）
            self._summarized = True

    def get_context_for_llm(
        self,
        max_messages: int = 50,
    ) -> list[dict[str, str]]:
        """
        获取用于 LLM 的上下文

        参数:
            max_messages: 最大消息数

        返回:
            消息历史列表 [{"role": "...", "content": "..."}]
        """
        if not self.session_id:
            return []

        # 检查是否有摘要
        latest_summary = self._store.get_latest_summary(self.session_id)
        context = []

        # 如果有摘要，加入摘要作为上下文
        if latest_summary:
            context.append(
                {
                    "role": "system",
                    "content": f"[对话摘要] {latest_summary['summary']}",
                }
            )

        # 获取消息（限制数量）
        messages = self._store.get_messages(
            self.session_id,
            limit=max_messages,
        )

        # 格式化为对话格式
        for msg in messages:
            role = msg.get("role", "user")
            if role in ("user", "assistant", "system"):
                context.append(
                    {
                        "role": role,
                        "content": msg.get("content", ""),
                    }
                )

        return context

    def extract_important_event(
        self,
        content: str,
        event_type: str = "重要记录",
        importance: int = 5,
    ) -> None:
        """
        提取重要事件到长期记忆

        参数:
            content: 事件内容
            event_type: 事件类型
            importance: 重要性 (1-10)
        """
        self._store.add_event(
            event_type=event_type,
            content=content,
            importance=importance,
            user_id=self.user_id,
            agent_id=self.agent_id,
        )

    def auto_extract_events(self) -> int:
        """
        自动从消息中提取重要事件

        返回:
            提取的事件数量
        """
        if not self.session_id:
            return 0

        messages = self._store.get_messages(self.session_id, limit=100)
        events = self._auto_summary.extract_events(messages)

        for event in events:
            self._store.add_event(
                event_type=event["type"],
                content=event["content"],
                importance=event["importance"],
                user_id=self.user_id,
                agent_id=self.agent_id,
            )

        return len(events)

    def create_summary(self, summary_content: str) -> None:
        """
        创建会话摘要

        参数:
            summary_content: 摘要内容
        """
        if not self.session_id:
            return

        msg_count = self._store.get_message_count(self.session_id)
        self._store.add_summary(
            session_id=self.session_id,
            summary=summary_content,
            original_count=msg_count,
            summary_type="auto",
        )

    def get_user_profile(self) -> dict[str, str]:
        """获取用户画像"""
        return self._store.get_profile(self.user_id, self.agent_id)

    def update_user_profile(
        self,
        key: str,
        value: str,
        confidence: int = 5,
    ) -> None:
        """更新用户画像"""
        self._store.set_profile(
            user_id=self.user_id,
            agent_id=self.agent_id,
            key=key,
            value=value,
            confidence=confidence,
        )

    def get_usage_report(self) -> dict[str, Any]:
        """获取记忆使用报告"""
        msg_count = 0
        if self.session_id:
            msg_count = self._store.get_message_count(self.session_id)

        return {
            "session_id": self.session_id,
            "message_count": msg_count,
            "is_summarized": self._summarized,
            "budget_usage": self._budget.usage_stats,
        }

    def cleanup_expired(self) -> dict[str, int]:
        """清理过期数据（未来实现）"""
        return {"cleaned": 0}
