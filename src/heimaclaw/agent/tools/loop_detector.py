"""
LoopDetector - 命令重复执行检测器

检测 Agent 是否陷入重复执行相同命令的循环，
类似 OpenClaw 的三次重复检测机制。

工作原理：
- 记录最近 N 次工具调用的命令签名
- 如果同一命令连续失败 N 次，触发"反思"模式
- 反思模式：让 LLM 分析失败原因，重新制定策略
"""

import hashlib
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ToolCall:
    """工具调用记录"""
    command: str      # 命令内容
    tool_name: str   # 工具名称
    timestamp: float  # 调用时间
    success: bool    # 是否成功
    error: str = ""  # 错误信息


@dataclass
class LoopDetectionResult:
    """循环检测结果"""
    is_loop: bool
    repeated_count: int  # 连续重复次数
    suggested_action: str  # 建议的行动


class LoopDetector:
    """
    命令执行循环检测器
    
    使用滑动窗口记录最近的工具调用历史，
    检测是否存在重复失败的命令模式。
    """
    
    def __init__(
        self,
        max_history: int = 10,        # 最多记录多少次调用
        max_repeat: int = 3,         # 超过这个次数判定为循环
        cooldown_seconds: float = 5.0, # 同一命令的最小时间间隔
    ):
        self.max_history = max_history
        self.max_repeat = max_repeat
        self.cooldown_seconds = cooldown_seconds
        
        # 调用历史（滑动窗口）
        self._history: deque[ToolCall] = deque(maxlen=max_history)
        
        # 上次触发循环警告的时间
        self._last_loop_warning: float = 0
    
    def _get_command_signature(self, command: str) -> str:
        """
        获取命令签名
        
        将命令标准化，移除时间戳、随机数等不可重复的部分
        """
        # 移除常见的时间戳和随机字符串
        import re
        normalized = re.sub(r'\d{10,}', '<TIMESTAMP>', command)
        normalized = re.sub(r'[a-f0-9]{32,}', '<HASH>', normalized)
        normalized = re.sub(r'[a-zA-Z0-9+/]{20,}={0,2}', '<TOKEN>', normalized)
        
        # 移除多余空白
        normalized = ' '.join(normalized.split())
        return hashlib.md5(normalized.encode()).hexdigest()[:16]
    
    def record(
        self,
        command: str,
        tool_name: str,
        success: bool,
        error: str = "",
    ) -> None:
        """记录一次工具调用"""
        call = ToolCall(
            command=command,
            tool_name=tool_name,
            timestamp=time.time(),
            success=success,
            error=error,
        )
        self._history.append(call)
    
    def check(self) -> LoopDetectionResult:
        """
        检查是否存在循环
        
        Returns:
            LoopDetectionResult: 包含是否循环、重复次数、建议行动
        """
        if len(self._history) < 2:
            return LoopDetectionResult(is_loop=False, repeated_count=0, suggested_action="")
        
        # 获取最近连续失败的相同命令
        last_call = self._history[-1]
        if last_call.success:
            return LoopDetectionResult(is_loop=False, repeated_count=0, suggested_action="")
        
        # 查找最近相同命令的连续失败记录
        repeated_count = 1
        cmd_sig = self._get_command_signature(last_call.command)
        
        for i in range(len(self._history) - 2, -1, -1):
            prev_call = self._history[i]
            if prev_call.success:
                break
            if self._get_command_signature(prev_call.command) == cmd_sig:
                repeated_count += 1
            else:
                break
        
        if repeated_count >= self.max_repeat:
            # 生成反思提示
            last_failed = last_call.command
            error_summary = last_call.error[:100] if last_call.error else "未知错误"
            
            suggested_action = (
                f"反思策略：连续 {repeated_count} 次执行相同命令均失败。\n"
                f"最后失败命令: {last_failed[:100]}\n"
                f"错误信息: {error_summary}\n\n"
                f"建议重新分析：\n"
                f"1. 确认文件/目录是否真的存在\n"
                f"2. 如果文件不存在，先创建文件再运行\n"
                f"3. 检查依赖是否已安装\n"
                f"4. 考虑使用不同的命令或参数"
            )
            
            return LoopDetectionResult(
                is_loop=True,
                repeated_count=repeated_count,
                suggested_action=suggested_action,
            )
        
        return LoopDetectionResult(is_loop=False, repeated_count=0, suggested_action="")
    
    def should_trigger_reflection(self) -> bool:
        """是否应该触发反思模式"""
        result = self.check()
        if not result.is_loop:
            return False
        
        # 冷却时间检查（避免反复触发）
        now = time.time()
        if now - self._last_loop_warning < 60:  # 60秒内不重复触发
            return False
        
        self._last_loop_warning = now
        return True
    
    def get_summary(self) -> str:
        """获取当前历史摘要"""
        lines = ["[LoopDetector] 最近调用记录:"]
        for i, call in enumerate(list(self._history)[-5:]):
            status = "✅" if call.success else "❌"
            cmd_preview = call.command[:60].replace('\n', ' ')
            lines.append(f"  {status} [{call.tool_name}] {cmd_preview}...")
        return "\n".join(lines)
