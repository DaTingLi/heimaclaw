"""
write_todos 工具处理器 - 增强版

参考 LangChain write_todos 设计：
1. Todo 状态：pending, in_progress, completed
2. 与 ServiceRegistry 集成
3. 与 SubAgent 派生集成
4. 自动追踪任务进度
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


def get_todos_definition() -> dict:
    """获取 write_todos 工具定义"""
    return {
        "name": "write_todos",
        "description": """创建和管理任务列表，用于跟踪当前工作进度。

## 使用场景
- 复杂多步骤任务（3步以上）
- 需要并行派生多个 subagent 的任务
- 需要跟踪进度的长任务
- 需要注册到 ServiceRegistry 的服务

## 任务状态
- pending: 未开始
- in_progress: 进行中
- completed: 已完成

## 使用规则
1. 开始工作时：标记 in_progress
2. 完成后：立即标记 completed
3. 遇到错误：保持 in_progress，创建新任务描述问题
4. 派生 subagent 时：注册到 ServiceRegistry
5. 不要并行调用 write_todos

## 返回格式
todos: [
  {
    "id": "step_1",  // 可选，用于追踪
    "content": "安装依赖",
    "status": "in_progress",
    "agent_id": "subagent_1",  // 如果是派生agent
    "service_name": "my_app",   // 如果是服务
    "port": 8501               // 如果启动了服务
  }
]

## 与 ServiceRegistry 集成
当任务涉及启动服务时，自动注册：
- service_name: 服务名称
- port: 端口号
- url: 访问 URL

## 与 SubAgent 集成
当派生 subagent 时：
- agent_id: subagent 标识
- task: 具体任务描述

参数：
- todos: 任务列表""",
        "parameters": {
            "type": "object",
            "properties": {
                "todos": {
                    "type": "array",
                    "description": "任务列表",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string", "description": "任务ID"},
                            "content": {"type": "string", "description": "任务描述"},
                            "status": {
                                "type": "string",
                                "enum": ["pending", "in_progress", "completed"],
                                "description": "任务状态"
                            },
                            "agent_id": {"type": "string", "description": "派生的agent ID"},
                            "service_name": {"type": "string", "description": "服务名称"},
                            "port": {"type": "integer", "description": "服务端口"},
                            "url": {"type": "string", "description": "服务URL"},
                            "error": {"type": "string", "description": "错误信息"},
                        },
                        "required": ["content", "status"]
                    }
                }
            },
            "required": ["todos"]
        }
    }


async def write_todos_handler(todos: list[dict[str, Any]]) -> str:
    """
    write_todos 工具的处理函数 - 增强版
    
    与 ServiceRegistry 和 SubAgent 集成
    """
    manager = get_todo_manager()
    
    # 验证格式
    valid, error = manager.validate_todos(todos)
    if not valid:
        return f"错误: {error}"
    
    # 更新状态
    updated_todos = manager.update_todos(todos)
    
    # 处理服务注册
    services_registered = []
    for todo in updated_todos:
        if todo.get("status") == "completed" and todo.get("service_name"):
            # 服务完成时注册到 ServiceRegistry
            try:
                from heimaclaw.core.service_registry import get_service_registry
                registry = get_service_registry()
                registry.register(
                    service_name=todo["service_name"],
                    port=todo.get("port", 0),
                    url=todo.get("url", f"http://localhost:{todo.get('port', 0)}"),
                    extra={"task_id": todo.get("id", ""), "content": todo.get("content", "")}
                )
                services_registered.append(todo["service_name"])
            except Exception as e:
                print(f"[write_todos] 服务注册失败: {e}")
    
    # 统计
    completed = len([t for t in updated_todos if t.get("status") == "completed"])
    in_progress = len([t for t in updated_todos if t.get("status") == "in_progress"])
    total = len(updated_todos)
    
    if total == 0:
        return "✅ 已清空待办列表"
    
    # 构建回复
    result_parts = []
    
    # 进度摘要
    if completed == total:
        result_parts.append(f"🎉 全部完成 ({completed}/{total})")
    else:
        result_parts.append(f"📋 进度: {completed}/{total} 完成，{in_progress} 进行中")
    
    # 进行中的任务
    in_progress_tasks = [t for t in updated_todos if t.get("status") == "in_progress"]
    if in_progress_tasks:
        result_parts.append("\n🔄 进行中:")
        for t in in_progress_tasks:
            agent_info = f" (Agent: {t.get('agent_id')})" if t.get("agent_id") else ""
            service_info = f" @ 端口{t.get('port')}" if t.get("port") else ""
            result_parts.append(f"   • {t.get('content')}{service_info}{agent_info}")
    
    # 待处理的任务
    pending_tasks = [t for t in updated_todos if t.get("status") == "pending"]
    if pending_tasks:
        result_parts.append("\n⬜ 待处理:")
        for t in pending_tasks:
            result_parts.append(f"   • {t.get('content')}")
    
    # 已完成的任务
    completed_tasks = [t for t in updated_todos if t.get("status") == "completed"]
    if completed_tasks:
        result_parts.append("\n✅ 已完成:")
        for t in completed_tasks:
            service_info = f" → http://localhost:{t.get('port')}" if t.get("port") else ""
            result_parts.append(f"   ✓ {t.get('content')}{service_info}")
    
    # 服务注册信息
    if services_registered:
        result_parts.append(f"\n🔗 已注册服务: {', '.join(services_registered)}")
    
    return "\n".join(result_parts)
