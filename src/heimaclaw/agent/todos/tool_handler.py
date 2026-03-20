"""
write_todos 工具处理器

参考 LangChain write_todos 实现
"""

from typing import Any

from heimaclaw.agent.todos.manager import TodoManager


# 全局 TodoManager 实例
_todo_manager: TodoManager = None


def get_todo_manager() -> TodoManager:
    """获取全局 TodoManager 实例"""
    global _todo_manager
    if _todo_manager is None:
        _todo_manager = TodoManager()
    return _todo_manager


def reset_todo_manager():
    """重置 TodoManager（新会话）"""
    global _todo_manager
    _todo_manager = TodoManager()


async def write_todos_handler(todos: list[dict[str, Any]]) -> str:
    """
    write_todos 工具的处理函数
    """
    manager = get_todo_manager()
    
    # 验证格式
    valid, error = manager.validate_todos(todos)
    if not valid:
        return f"错误: {error}"
    
    # 更新状态
    updated_todos = manager.update_todos(todos)
    
    # 生成反馈
    completed = len(manager.get_completed())
    total = len(updated_todos)
    
    if total == 0:
        return "已清空待办列表"
    
    result_parts = [
        f"待办列表已更新 ({completed}/{total} 完成)",
    ]
    
    # 列出进行中的任务
    in_progress = manager.get_in_progress()
    if in_progress:
        result_parts.append("\n🔄 进行中:")
        for t in in_progress:
            result_parts.append(f"   - {t['content']}")
    
    # 列出待处理任务
    pending = manager.get_pending()
    if pending:
        result_parts.append("\n⬜ 待处理:")
        for t in pending:
            result_parts.append(f"   - {t['content']}")
    
    # 列出已完成任务
    completed_tasks = manager.get_completed()
    if completed_tasks:
        result_parts.append("\n✅ 已完成:")
        for t in completed_tasks:
            result_parts.append(f"   - {t['content']}")
    
    return "\n".join(result_parts)
