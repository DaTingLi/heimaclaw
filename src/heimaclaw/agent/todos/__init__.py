"""
待办事项模块 - 参考 LangChain agents/middleware/todo.py

提供完整的任务规划功能：
- Todo 类型定义
- write_todos 工具
- TodoManager 状态管理
"""

from .types import (
    Todo,
    PlanningState,
    WRITE_TODOS_TOOL_DESCRIPTION,
    get_write_todos_definition,
)
from .manager import TodoManager
from .tool_handler import (
    write_todos_handler,
    get_todo_manager,
    reset_todo_manager,
)

__all__ = [
    "Todo",
    "PlanningState",
    "WRITE_TODOS_TOOL_DESCRIPTION",
    "get_write_todos_definition",
    "TodoManager",
    "write_todos_handler",
    "get_todo_manager",
    "reset_todo_manager",
]
