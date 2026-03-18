"""
控制台输出模块

提供统一的日志输出，支持颜色区分、NO_COLOR 环境变量适配。
"""

import os
import sys
from typing import Any

from rich.console import Console
from rich.theme import Theme

# 定义主题颜色
THEME = Theme({
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
})

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


def debug(message: str, **kwargs: Any) -> None:
    """输出调试级别日志"""
    console.print(f"[debug]{message}[/debug]", **kwargs)


def info(message: str, **kwargs: Any) -> None:
    """输出信息级别日志"""
    console.print(f"[info]{message}[/info]", **kwargs)


def success(message: str, **kwargs: Any) -> None:
    """输出成功级别日志"""
    console.print(f"[success]{message}[/success]", **kwargs)


def warning(message: str, **kwargs: Any) -> None:
    """输出警告级别日志"""
    console.print(f"[warning]{message}[/warning]", **kwargs)


def error(message: str, **kwargs: Any) -> None:
    """输出错误级别日志"""
    console.print(f"[error]{message}[/error]", **kwargs)


def critical(message: str, **kwargs: Any) -> None:
    """输出严重错误级别日志"""
    console.print(f"[critical]{message}[/critical]", **kwargs)


def agent_event(message: str, **kwargs: Any) -> None:
    """输出 Agent 相关事件日志"""
    console.print(f"[agent]{message}[/agent]", **kwargs)


def sandbox_event(message: str, **kwargs: Any) -> None:
    """输出沙箱相关事件日志"""
    console.print(f"[sandbox]{message}[/sandbox]", **kwargs)


def highlight(message: str, **kwargs: Any) -> None:
    """输出高亮信息"""
    console.print(f"[highlight]{message}[/highlight]", **kwargs)


def title(message: str, **kwargs: Any) -> None:
    """输出标题"""
    console.print(f"[title]{message}[/title]", **kwargs)


def dim(message: str, **kwargs: Any) -> None:
    """输出暗淡信息"""
    console.print(f"[dim]{message}[/dim]", **kwargs)


def print_table(title_str: str, rows: list[list[str]], headers: list[str]) -> None:
    """
    打印表格

    参数:
        title_str: 表格标题
        rows: 数据行列表
        headers: 表头列表
    """
    from rich.table import Table
    
    table = Table(title=title_str, show_header=True, header_style="cyan bold")
    
    for header in headers:
        table.add_column(header)
    
    for row in rows:
        table.add_row(*row)
    
    console.print(table)


def print_panel(content: str, title_str: str = "", style: str = "cyan") -> None:
    """
    打印面板

    参数:
        content: 面板内容
        title_str: 面板标题
        style: 面板样式
    """
    from rich.panel import Panel
    
    panel = Panel(content, title=title_str if title_str else None, style=style)
    console.print(panel)
