"""自动记忆摘要模块"""
import re
from typing import Any


class AutoSummary:
    """自动摘要器"""

    DEFAULT_MESSAGE_THRESHOLD = 50
    DEFAULT_TOKEN_THRESHOLD = 32000

    SUMMARY_PROMPT = """请将以下对话压缩为简洁的摘要，保留关键信息：

{messages}

请生成一个 200-300 字的摘要，包含：
1. 对话主题
2. 用户的主要需求
3. 已完成的操作
4. 未完成的任务
5. 重要的用户偏好

摘要："""

    EVENT_PATTERNS = [
        (r"记住.*?(?:我|用户).*?", "用户偏好", 8),
        (r"(?:以后|将来).*?(?:用|选择|采用).*?", "用户决策", 7),
        (r"(?:不要|别|停止).*?(?:做|使用|给).*?", "用户禁止", 9),
        (r"我喜欢.*?", "用户偏好", 7),
        (r"之前.*?(?:失败|错误|不行).*?", "历史问题", 6),
        (r"决定.*?(?:用|选择).*?", "用户决策", 7),
    ]

    def __init__(
        self,
        message_threshold: int = DEFAULT_MESSAGE_THRESHOLD,
        token_threshold: int = DEFAULT_TOKEN_THRESHOLD,
    ):
        self.message_threshold = message_threshold
        self.token_threshold = token_threshold

    def should_summarize(
        self,
        message_count: int,
        token_count: int,
        has_end_marker: bool = False,
    ) -> bool:
        if has_end_marker:
            return True
        if message_count > self.message_threshold:
            return True
        if token_count > self.token_threshold:
            return True
        return False

    def extract_events(
        self,
        messages: list[dict[str, str]],
    ) -> list[dict[str, Any]]:
        events = []
        seen_contents = set()

        for msg in messages:
            if msg.get("role") != "user":
                continue

            content = msg.get("content", "")

            for pattern, event_type, importance in self.EVENT_PATTERNS:
                matches = re.findall(pattern, content, re.IGNORECASE)
                for match in matches:
                    if match not in seen_contents:
                        seen_contents.add(match)
                        events.append({
                            "type": event_type,
                            "content": match,
                            "importance": importance,
                        })

        events.sort(key=lambda x: x["importance"], reverse=True)
        return events

    def build_summary_prompt(
        self,
        messages: list[dict[str, str]],
    ) -> str:
        recent = messages[-self.message_threshold:]
        text = "\n".join([
            f"[{msg.get('role', 'unknown')}]: {msg.get('content', '')[:200]}"
            for msg in recent
        ])
        return self.SUMMARY_PROMPT.format(messages=text)
