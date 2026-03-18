"""
日常记忆模块

存储每日的关键事件总结，自动从会话记忆压缩而来。
"""

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional


class DailyMemory:
    """
    日常记忆管理器

    职责：
    - 存储每日关键事件总结
    - 自动压缩会话记忆
    - 保留 30 天
    - Markdown 格式存储

    存储格式：
    ~/.heimaclaw/agents/{agent}/memory/YYYY-MM-DD.md
    """

    def __init__(
        self,
        agent_id: str,
        retention_days: int = 30,
        memory_dir: Optional[Path] = None,
    ):
        """
        初始化日常记忆

        参数:
            agent_id: Agent ID
            retention_days: 保留天数（默认 30 天）
            memory_dir: 记忆目录（默认 ~/.heimaclaw/agents/{agent}/memory）
        """
        self.agent_id = agent_id
        self.retention_days = retention_days

        # 记忆目录
        if memory_dir is None:
            memory_dir = Path.home() / ".heimaclaw" / "agents" / agent_id / "memory"
        self.memory_dir = Path(memory_dir)
        self.memory_dir.mkdir(parents=True, exist_ok=True)

    def add_event(
        self,
        event: str,
        date: Optional[str] = None,
        event_type: str = "general",
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        """
        添加事件

        参数:
            event: 事件描述
            date: 日期（YYYY-MM-DD，默认今天）
            event_type: 事件类型（general/important/decision/preference）
            metadata: 元数据
        """
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        memory_file = self.memory_dir / f"{date}.md"

        # 读取现有内容
        content = ""
        if memory_file.exists():
            content = memory_file.read_text(encoding="utf-8")

        # 构建事件块
        timestamp = datetime.now().strftime("%H:%M")
        event_block = f"\n### {timestamp} - {event_type}\n{event}\n"

        if metadata:
            event_block += "\n**元数据：**\n"
            for key, value in metadata.items():
                event_block += f"- {key}: {value}\n"

        # 追加事件
        if not content:
            # 新文件，添加标题
            content = f"# {date} - 日常记忆\n\n## 📋 今日事件{event_block}\n"
        else:
            # 追加到现有文件
            content = content.rstrip() + event_block + "\n"

        # 保存
        memory_file.write_text(content, encoding="utf-8")

    def get_events(self, date: Optional[str] = None) -> str:
        """
        获取某日的事件

        参数:
            date: 日期（YYYY-MM-DD，默认今天）

        返回:
            事件内容（Markdown 格式）
        """
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        memory_file = self.memory_dir / f"{date}.md"

        if not memory_file.exists():
            return ""

        return memory_file.read_text(encoding="utf-8")

    def get_recent_events(self, days: int = 7) -> dict[str, str]:
        """
        获取最近 N 天的事件

        参数:
            days: 天数（默认 7 天）

        返回:
            日期到事件内容的映射
        """
        events = {}
        today = datetime.now()

        for i in range(days):
            date = (today - timedelta(days=i)).strftime("%Y-%m-%d")
            content = self.get_events(date)
            if content:
                events[date] = content

        return events

    def search_events(self, keyword: str, days: int = 30) -> list[dict[str, str]]:
        """
        搜索事件

        参数:
            keyword: 关键词
            days: 搜索范围（默认 30 天）

        返回:
            匹配的事件列表
        """
        results = []
        today = datetime.now()

        for i in range(days):
            date = (today - timedelta(days=i)).strftime("%Y-%m-%d")
            content = self.get_events(date)

            if keyword.lower() in content.lower():
                results.append(
                    {
                        "date": date,
                        "content": content,
                    }
                )

        return results

    def cleanup_expired(self) -> int:
        """
        清理过期记忆

        返回:
            清理的文件数量
        """
        cutoff_date = datetime.now() - timedelta(days=self.retention_days)
        cleaned_count = 0

        for memory_file in self.memory_dir.glob("*.md"):
            try:
                # 从文件名提取日期
                date_str = memory_file.stem
                file_date = datetime.strptime(date_str, "%Y-%m-%d")

                if file_date < cutoff_date:
                    memory_file.unlink()
                    cleaned_count += 1
            except (ValueError, OSError):
                # 文件名格式错误或删除失败，跳过
                pass

        return cleaned_count

    def get_summary(self, date: Optional[str] = None) -> str:
        """
        获取某日的摘要（简化版，仅提取标题和关键信息）

        参数:
            date: 日期（YYYY-MM-DD，默认今天）

        返回:
            摘要文本
        """
        content = self.get_events(date)

        if not content:
            return "无记录"

        # 提取关键行
        lines = content.split("\n")
        summary_lines = []

        for line in lines:
            # 提取标题和重要事件
            if line.startswith("#") or line.startswith("###"):
                summary_lines.append(line)
            elif line.startswith("- ") and len(line) > 20:
                # 提取重要列表项
                summary_lines.append(line)

        return "\n".join(summary_lines[:20])  # 最多返回20行
