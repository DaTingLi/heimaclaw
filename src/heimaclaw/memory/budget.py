"""
Token 预算管理模块

智能分配 128K Token 预算到不同的上下文部分。
"""

from dataclasses import dataclass, field
from typing import Any, Optional


def count_tokens(text: str) -> int:
    """
    估算 Token 数量（简化版）
    
    规则：
    - 英文：约 1 token = 4 字符
    - 中文：约 1 token = 1.5 字符
    - 混合：加权平均
    """
    if not text:
        return 0
    
    # 统计中英文字符
    chinese_chars = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
    english_chars = len(text) - chinese_chars
    
    # 估算 token
    chinese_tokens = chinese_chars / 1.5
    english_tokens = english_chars / 4
    
    return int(chinese_tokens + english_tokens)


@dataclass
class TokenBudget:
    """Token 预算分配"""
    
    system_prompt: int = 2000
    recent_messages: int = 10000
    daily_memory: int = 5000
    longterm_memory: int = 8000
    user_profile: int = 2000
    tools: int = 50000
    response: int = 50000
    
    @property
    def total(self) -> int:
        """总预算"""
        return (
            self.system_prompt +
            self.recent_messages +
            self.daily_memory +
            self.longterm_memory +
            self.user_profile +
            self.tools +
            self.response
        )


class ContextBudget:
    """
    Token 预算管理器
    
    职责：
    - 智能分配 128K Token
    - 上下文裁剪
    - 预算使用统计
    """
    
    # 默认预算分配（GLM-4: 128K context）
    DEFAULT_MAX_TOKENS = 128000
    
    def __init__(
        self,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        budget: Optional[TokenBudget] = None,
    ):
        """
        初始化预算管理器
        
        参数:
            max_tokens: 最大 Token 数（默认 128K）
            budget: 预算分配（默认使用 DEFAULT_BUDGET）
        """
        self.max_tokens = max_tokens
        
        # 预算分配
        if budget is None:
            budget = TokenBudget()
        
        self.budget = budget
        
        # 使用统计
        self.usage_stats = {
            "system_prompt": 0,
            "recent_messages": 0,
            "daily_memory": 0,
            "longterm_memory": 0,
            "user_profile": 0,
            "tools": 0,
            "total_used": 0,
        }
    
    def allocate(
        self,
        system_prompt: str,
        recent_messages: list[str],
        daily_memory: str = "",
        longterm_memory: str = "",
        user_profile: str = "",
        tools: str = "",
    ) -> dict[str, str]:
        """
        按预算分配上下文
        
        参数:
            system_prompt: 系统提示
            recent_messages: 最近消息列表
            daily_memory: 日常记忆
            longterm_memory: 长期记忆
            user_profile: 用户画像
            tools: 工具定义
        
        返回:
            分配后的上下文字典
        """
        result = {}
        total_used = 0
        
        # 1. 系统提示（不可压缩）
        tokens = count_tokens(system_prompt)
        if tokens <= self.budget.system_prompt:
            result["system_prompt"] = system_prompt
            self.usage_stats["system_prompt"] = tokens
            total_used += tokens
        else:
            # 超限，截断
            result["system_prompt"] = self._truncate(system_prompt, self.budget.system_prompt)
            self.usage_stats["system_prompt"] = self.budget.system_prompt
            total_used += self.budget.system_prompt
        
        # 2. 最近消息（优先保留最新的）
        messages_text = "\n".join(recent_messages)
        tokens = count_tokens(messages_text)
        if tokens <= self.budget.recent_messages:
            result["recent_messages"] = messages_text
            self.usage_stats["recent_messages"] = tokens
            total_used += tokens
        else:
            # 从后往前保留消息
            truncated = self._truncate_messages(recent_messages, self.budget.recent_messages)
            result["recent_messages"] = truncated
            self.usage_stats["recent_messages"] = self.budget.recent_messages
            total_used += self.budget.recent_messages
        
        # 3. 日常记忆
        tokens = count_tokens(daily_memory)
        if tokens <= self.budget.daily_memory:
            result["daily_memory"] = daily_memory
            self.usage_stats["daily_memory"] = tokens
            total_used += tokens
        else:
            # 压缩
            compressed = self._compress(daily_memory, self.budget.daily_memory)
            result["daily_memory"] = compressed
            self.usage_stats["daily_memory"] = self.budget.daily_memory
            total_used += self.budget.daily_memory
        
        # 4. 长期记忆
        tokens = count_tokens(longterm_memory)
        if tokens <= self.budget.longterm_memory:
            result["longterm_memory"] = longterm_memory
            self.usage_stats["longterm_memory"] = tokens
            total_used += tokens
        else:
            # 压缩
            compressed = self._compress(longterm_memory, self.budget.longterm_memory)
            result["longterm_memory"] = compressed
            self.usage_stats["longterm_memory"] = self.budget.longterm_memory
            total_used += self.budget.longterm_memory
        
        # 5. 用户画像
        tokens = count_tokens(user_profile)
        if tokens <= self.budget.user_profile:
            result["user_profile"] = user_profile
            self.usage_stats["user_profile"] = tokens
            total_used += tokens
        else:
            # 截断
            result["user_profile"] = self._truncate(user_profile, self.budget.user_profile)
            self.usage_stats["user_profile"] = self.budget.user_profile
            total_used += self.budget.user_profile
        
        # 6. 工具定义
        tokens = count_tokens(tools)
        if tokens <= self.budget.tools:
            result["tools"] = tools
            self.usage_stats["tools"] = tokens
            total_used += tokens
        else:
            # 压缩（移除工具描述）
            compressed = self._compress_tools(tools, self.budget.tools)
            result["tools"] = compressed
            self.usage_stats["tools"] = self.budget.tools
            total_used += self.budget.tools
        
        # 更新总使用量
        self.usage_stats["total_used"] = total_used
        
        return result
    
    def get_usage_report(self) -> dict[str, Any]:
        """
        获取使用报告
        
        返回:
            使用统计字典
        """
        report = {
            "max_tokens": self.max_tokens,
            "budget": {
                "system_prompt": self.budget.system_prompt,
                "recent_messages": self.budget.recent_messages,
                "daily_memory": self.budget.daily_memory,
                "longterm_memory": self.budget.longterm_memory,
                "user_profile": self.budget.user_profile,
                "tools": self.budget.tools,
                "response": self.budget.response,
            },
            "usage": self.usage_stats.copy(),
            "remaining": self.max_tokens - self.usage_stats["total_used"],
            "usage_percentage": (self.usage_stats["total_used"] / self.max_tokens) * 100,
        }
        
        return report
    
    def check_budget(self) -> bool:
        """
        检查预算是否合理
        
        返回:
            是否合理
        """
        total_budget = self.budget.total
        return total_budget <= self.max_tokens
    
    def _truncate(self, text: str, max_tokens: int) -> str:
        """
        截断文本到指定 Token 数
        
        参数:
            text: 原始文本
            max_tokens: 最大 Token 数
        
        返回:
            截断后的文本
        """
        # 按字符比例截断
        current_tokens = count_tokens(text)
        if current_tokens <= max_tokens:
            return text
        
        # 计算需要保留的字符比例
        ratio = max_tokens / current_tokens
        char_limit = int(len(text) * ratio)
        
        # 截断
        return text[:char_limit] + "\n...[已截断]"
    
    def _truncate_messages(self, messages: list[str], max_tokens: int) -> str:
        """
        从后往前截断消息列表
        
        参数:
            messages: 消息列表
            max_tokens: 最大 Token 数
        
        返回:
            截断后的文本
        """
        selected_messages = []
        current_tokens = 0
        
        # 从后往前添加消息
        for message in reversed(messages):
            msg_tokens = count_tokens(message)
            
            if current_tokens + msg_tokens <= max_tokens:
                selected_messages.insert(0, message)
                current_tokens += msg_tokens
            else:
                # 超限，停止
                break
        
        return "\n".join(selected_messages)
    
    def _compress(self, text: str, max_tokens: int) -> str:
        """
        压缩文本（简化版，实际应使用 LLM）
        
        参数:
            text: 原始文本
            max_tokens: 最大 Token 数
        
        返回:
            压缩后的文本
        """
        # 简化实现：提取关键行
        lines = text.split("\n")
        compressed_lines = []
        current_tokens = 0
        
        for line in lines:
            # 优先保留标题和重要行
            if line.startswith("#") or line.startswith("- ") or line.startswith("* "):
                line_tokens = count_tokens(line)
                
                if current_tokens + line_tokens <= max_tokens:
                    compressed_lines.append(line)
                    current_tokens += line_tokens
        
        return "\n".join(compressed_lines)
    
    def _compress_tools(self, tools: str, max_tokens: int) -> str:
        """
        压缩工具定义（移除描述）
        
        参数:
            tools: 工具定义
            max_tokens: 最大 Token 数
        
        返回:
            压缩后的工具定义
        """
        # 简化实现：只保留工具名
        lines = tools.split("\n")
        compressed_lines = []
        current_tokens = 0
        
        for line in lines:
            # 只保留工具名和参数
            if '"name"' in line or '"parameters"' in line:
                line_tokens = count_tokens(line)
                
                if current_tokens + line_tokens <= max_tokens:
                    compressed_lines.append(line)
                    current_tokens += line_tokens
        
        return "\n".join(compressed_lines)
