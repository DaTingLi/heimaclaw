"""
Planner Executor - Planner 模块的别名

为了保持向后兼容，从 planner 模块导入并导出所有内容。
"""

from heimaclaw.agent.planner import (
    Planner,
    ExecutionStep,
    ExecutionMode,
    ExecutionPlan,
)


class SimpleExecutor:
    """
    简单的执行器（占位实现）
    
    用于向后兼容。
    """
    
    def __init__(self, *args, **kwargs):
        pass
    
    async def execute(self, *args, **kwargs):
        return {"status": "ok"}
    
    def execute_sync(self, *args, **kwargs):
        return {"status": "ok"}


__all__ = [
    "Planner",
    "ExecutionStep",
    "ExecutionMode",
    "ExecutionPlan",
    "SimpleExecutor",
]
