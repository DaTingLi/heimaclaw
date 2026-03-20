"""
Todo 类型定义 - 参考 LangChain agents/middleware/todo.py

完整保留所有类型定义和规则。
"""

from typing import Annotated, Literal, TypedDict

try:
    from typing import NotRequired
except ImportError:
    from typing_extensions import NotRequired


class Todo(TypedDict):
    """
    单个待办事项
    
    Attributes:
        content: 任务内容/描述
        status: 当前状态
    """
    content: str
    status: Literal["pending", "in_progress", "completed"]


class PlanningState(TypedDict):
    """
    任务规划状态 - 用于跟踪任务进度
    
    Attributes:
        todos: 待办事项列表
        messages: 消息历史（用于 Agent 通信）
    """
    todos: NotRequired[list[Todo]]
    messages: NotRequired[list[dict]]


WRITE_TODOS_TOOL_DESCRIPTION = """使用此工具创建和管理当前工作会话的结构化任务列表。
这有助于跟踪进度、组织复杂任务，并向用户展示工作的完整性。

仅在以下情况使用此工具：
1. 复杂的多步骤任务 - 需要3个或更多独立步骤
2. 非平凡的复杂任务 - 需要仔细计划或多个操作
3. 用户明确要求使用待办列表
4. 用户提供多个任务列表
5. 计划可能需要根据前几步的结果进行修订

## 任务状态
- pending: 任务尚未开始
- in_progress: 正在进行中
- completed: 已完成

## 重要规则
1. 开始任务前 - 立即标记为 in_progress
2. 完成任务后 - 立即标记为 completed，不要批量完成
3. 遇到错误 - 保持 in_progress，创建新任务描述需要解决的问题
4. 绝不能并行调用此工具 - 每个模型轮次只能调用一次
5. 除非所有任务完成，否则必须保持至少一个 in_progress 任务

## 完成要求
只有满足以下条件才能标记为 completed：
- 完全完成任务
- 没有未解决的问题或错误
- 工作完整，不是部分的
- 遇到阻塞时要创建新任务描述需要解决的内容"""


def get_write_todos_definition() -> dict:
    """
    获取 write_todos 工具定义
    
    Returns:
        OpenAI 格式的工具定义
    """
    return {
        "name": "write_todos",
        "description": WRITE_TODOS_TOOL_DESCRIPTION,
        "parameters": {
            "type": "object",
            "properties": {
                "todos": {
                    "type": "array",
                    "description": "待办事项列表",
                    "items": {
                        "type": "object",
                        "properties": {
                            "content": {
                                "type": "string",
                                "description": "任务内容/描述"
                            },
                            "status": {
                                "type": "string",
                                "enum": ["pending", "in_progress", "completed"],
                                "description": "任务状态"
                            }
                        },
                        "required": ["content", "status"]
                    }
                }
            },
            "required": ["todos"]
        }
    }
