"""
TodoManager - 待办事项管理器

参考 LangChain TodoListMiddleware 实现完整功能：
1. 维护全局待办事项状态
2. 提供任务创建、更新、完成接口
3. 防止并行调用 write_todos
"""

from typing import Any, Optional

from .types import Todo, PlanningState


class TodoManager:
    """
    待办事项管理器
    
    负责：
    - 维护待办事项列表
    - 更新任务状态
    - 验证任务操作
    """
    
    def __init__(self):
        self._todos: list[Todo] = []
        self._call_count: int = 0  # 当前轮次调用计数
    
    @property
    def todos(self) -> list[Todo]:
        """获取当前待办事项"""
        return self._todos.copy()
    
    def update_todos(self, todos: list[Todo]) -> list[Todo]:
        """
        更新待办事项列表
        
        Args:
            todos: 新的待办事项列表
        
        Returns:
            更新后的列表
        """
        self._todos = todos
        self._call_count += 1
        return self._todos
    
    def get_pending(self) -> list[Todo]:
        """获取所有待处理任务"""
        return [t for t in self._todos if t["status"] == "pending"]
    
    def get_in_progress(self) -> list[Todo]:
        """获取所有进行中的任务"""
        return [t for t in self._todos if t["status"] == "in_progress"]
    
    def get_completed(self) -> list[Todo]:
        """获取所有已完成的任务"""
        return [t for t in self._todos if t["status"] == "completed"]
    
    def has_in_progress(self) -> bool:
        """检查是否有进行中的任务"""
        return any(t["status"] == "in_progress" for t in self._todos)
    
    def all_completed(self) -> bool:
        """检查是否所有任务都已完成"""
        if not self._todos:
            return True
        return all(t["status"] == "completed" for t in self._todos)
    
    def reset_call_count(self):
        """重置调用计数（新的一轮）"""
        self._call_count = 0
    
    def get_progress_summary(self) -> str:
        """
        获取进度摘要
        
        Returns:
            格式化的进度字符串
        """
        total = len(self._todos)
        completed = len(self.get_completed())
        in_progress = len(self.get_in_progress())
        pending = len(self.get_pending())
        
        if total == 0:
            return "暂无任务"
        
        pct = (completed / total * 100) if total > 0 else 0
        return f"进度: {completed}/{total} ({pct:.0f}%) | 进行中: {in_progress} | 待处理: {pending}"
    
    def format_todos_for_display(self) -> str:
        """
        格式化待办事项用于显示
        
        Returns:
            格式化的待办列表字符串
        """
        if not self._todos:
            return "📋 待办列表为空"
        
        lines = ["📋 **待办事项**\n"]
        
        # 按状态分组
        for i, todo in enumerate(self._todos, 1):
            status = todo["status"]
            content = todo["content"]
            
            if status == "completed":
                icon = "✅"
            elif status == "in_progress":
                icon = "🔄"
            else:
                icon = "⬜"
            
            lines.append(f"{icon} {i}. {content}")
        
        lines.append(f"\n{self.get_progress_summary()}")
        
        return "\n".join(lines)
    
    def validate_todos(self, todos: list[Todo]) -> tuple[bool, str]:
        """
        验证待办事项列表
        
        Args:
            todos: 待验证的列表
        
        Returns:
            (是否有效, 错误消息)
        """
        if not isinstance(todos, list):
            return False, "todos 必须是列表"
        
        valid_statuses = {"pending", "in_progress", "completed"}
        
        for i, todo in enumerate(todos):
            if not isinstance(todo, dict):
                return False, f"todo[{i}] 必须是字典"
            
            if "content" not in todo:
                return False, f"todo[{i}] 缺少 content 字段"
            
            if "status" not in todo:
                return False, f"todo[{i}] 缺少 status 字段"
            
            if todo["status"] not in valid_statuses:
                return False, f"todo[{i}] status 必须是 {valid_statuses} 之一"
        
        return True, ""
