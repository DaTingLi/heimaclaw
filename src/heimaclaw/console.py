"""
控制台输出模块

提供统一的日志输出，支持颜色区分、NO_COLOR 环境变量适配，
同时写入日志文件。
"""

import os
import sys
from datetime import datetime
from typing import Any
from pathlib import Path

from rich.console import Console
from rich.theme import Theme

# 定义主题颜色
THEME = Theme(
    {
        "debug": "grey50 italic",
        "info": "cyan",
        "success": "green bold",
        "warning": "yellow bold",
        "error": "red bold",
        "critical": "magenta bold on white",
        "agent": "blue bold",
        "sandbox": "magenta",
        "highlight": "cyan bold",
        "dim": "grey50",
        "title": "cyan bold",
    }
)


# 检测是否禁用颜色
def _should_use_color() -> bool:
    """检测是否应该使用彩色输出"""
    if os.getenv("NO_COLOR"):
        return False
    if not sys.stdout.isatty():
        return False
    return True


# 创建控制台实例
console = Console(theme=THEME, force_terminal=_should_use_color())


# 日志文件配置
_log_file_path: str | None = None
_log_file_enabled: bool = True


def configure_logging(log_file_path: str | None = None, enabled: bool = True) -> None:
    """配置日志写入文件"""
    global _log_file_path, _log_file_enabled
    _log_file_enabled = enabled
    if log_file_path:
        _log_file_path = log_file_path
        # 确保目录存在
        Path(log_file_path).parent.mkdir(parents=True, exist_ok=True)


def _write_to_file(message: str) -> None:
    """写入日志到文件"""
    if not _log_file_enabled or not _log_file_path:
        return
    try:
        with open(_log_file_path, "a", encoding="utf-8") as f:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"[{timestamp}] {message}\n")
    except Exception:
        pass  # 静默忽略文件写入错误


def _log_with_level(level: str, message: str, **kwargs: Any) -> None:
    """带级别的日志输出"""
    # 输出到控制台
    console.print(f"[{level}]{message}[/{level}]", **kwargs)
    # 写入文件
    _write_to_file(f"[{level.upper()}] {message}")


def debug(message: str, **kwargs: Any) -> None:
    """输出调试级别日志"""
    _log_with_level("debug", message, **kwargs)


def info(message: str, **kwargs: Any) -> None:
    """输出信息级别日志"""
    _log_with_level("info", message, **kwargs)


def success(message: str, **kwargs: Any) -> None:
    """输出成功级别日志"""
    _log_with_level("success", message, **kwargs)


def warning(message: str, **kwargs: Any) -> None:
    """输出警告级别日志"""
    _log_with_level("warning", message, **kwargs)


def error(message: str, **kwargs: Any) -> None:
    """输出错误级别日志"""
    _log_with_level("error", message, **kwargs)


def critical(message: str, **kwargs: Any) -> None:
    """输出严重错误级别日志"""
    _log_with_level("critical", message, **kwargs)


def agent_event(message: str, **kwargs: Any) -> None:
    """输出 Agent 相关事件日志"""
    _log_with_level("agent", message, **kwargs)


def sandbox_event(message: str, **kwargs: Any) -> None:
    """输出沙箱相关事件日志"""
    _log_with_level("sandbox", message, **kwargs)


def highlight(message: str, **kwargs: Any) -> None:
    """输出高亮信息"""
    _log_with_level("highlight", message, **kwargs)


def title(message: str, **kwargs: Any) -> None:
    """输出标题"""
    _log_with_level("title", message, **kwargs)


def dim(message: str, **kwargs: Any) -> None:
    """输出暗淡信息"""
    _log_with_level("dim", message, **kwargs)


def print_table(title_str: str, rows: list[list[str]], headers: list[str]) -> None:
    """打印表格"""
    from rich.table import Table
    table = Table(title=title_str, show_header=True, header_style="cyan bold")
    for header in headers:
        table.add_column(header)
    for row in rows:
        table.add_row(*row)
    console.print(table)


def print_panel(content: str, title_str: str = "", style: str = "cyan") -> None:
    """打印面板"""
    from rich.panel import Panel
    panel = Panel(content, title=title_str if title_str else None, style=style)
    console.print(panel)
