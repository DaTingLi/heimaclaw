"""
工具注册表模块

管理 Agent 可用的工具，提供工具定义和执行接口。
"""

import asyncio
import inspect
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from heimaclaw.console import info, warning
from heimaclaw.interfaces import ToolDefinition, ToolResult


@dataclass
class RegisteredTool:
    """已注册的工具"""
    definition: ToolDefinition
    handler: Callable
    is_async: bool = False
    timeout_ms: int = 30000


class ToolRegistry:
    """
    工具注册表
    
    管理工具的注册、查找、执行。
    """
    
    def __init__(self):
        """初始化工具注册表"""
        self._tools: dict[str, RegisteredTool] = {}
    
    def register(
        self,
        name: str,
        description: str,
        parameters: Optional[dict[str, Any]] = None,
        timeout_ms: int = 30000,
    ) -> Callable:
        """
        注册工具（装饰器方式）
        
        参数:
            name: 工具名称
            description: 工具描述
            parameters: 参数定义（JSON Schema）
            timeout_ms: 执行超时时间
            
        返回:
            装饰器函数
        """
        def decorator(func: Callable) -> Callable:
            definition = ToolDefinition(
                name=name,
                description=description,
                parameters=parameters or {},
            )
            
            is_async = inspect.iscoroutinefunction(func)
            
            self._tools[name] = RegisteredTool(
                definition=definition,
                handler=func,
                is_async=is_async,
                timeout_ms=timeout_ms,
            )
            
            info(f"注册工具: {name} (async={is_async})")
            
            return func
        
        return decorator
    
    def register_function(
        self,
        name: str,
        description: str,
        handler: Callable,
        parameters: Optional[dict[str, Any]] = None,
        timeout_ms: int = 30000,
    ) -> None:
        """
        直接注册工具函数
        
        参数:
            name: 工具名称
            description: 工具描述
            handler: 处理函数
            parameters: 参数定义
            timeout_ms: 执行超时时间
        """
        definition = ToolDefinition(
            name=name,
            description=description,
            parameters=parameters or {},
        )
        
        is_async = inspect.iscoroutinefunction(handler)
        
        self._tools[name] = RegisteredTool(
            definition=definition,
            handler=handler,
            is_async=is_async,
            timeout_ms=timeout_ms,
        )
        
        info(f"注册工具: {name} (async={is_async})")
    
    def unregister(self, name: str) -> None:
        """
        注销工具
        
        参数:
            name: 工具名称
        """
        if name in self._tools:
            del self._tools[name]
            info(f"注销工具: {name}")
    
    def get(self, name: str) -> Optional[RegisteredTool]:
        """
        获取工具
        
        参数:
            name: 工具名称
            
        返回:
            工具对象，不存在则返回 None
        """
        return self._tools.get(name)
    
    def list_all(self) -> list[ToolDefinition]:
        """
        列出所有工具定义
        
        返回:
            工具定义列表
        """
        return [t.definition for t in self._tools.values()]
    
    async def execute(
        self,
        name: str,
        parameters: dict[str, Any],
    ) -> ToolResult:
        """
        执行工具
        
        参数:
            name: 工具名称
            parameters: 工具参数
            
        返回:
            执行结果
        """
        tool = self.get(name)
        
        if not tool:
            return ToolResult(
                tool_name=name,
                success=False,
                result=None,
                error=f"工具不存在: {name}",
            )
        
        try:
            if tool.is_async:
                result = await asyncio.wait_for(
                    tool.handler(**parameters),
                    timeout=tool.timeout_ms / 1000,
                )
            else:
                result = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: tool.handler(**parameters),
                )
            
            return ToolResult(
                tool_name=name,
                success=True,
                result=result,
            )
            
        except asyncio.TimeoutError:
            return ToolResult(
                tool_name=name,
                success=False,
                result=None,
                error=f"工具执行超时: {name}",
            )
        except Exception as e:
            return ToolResult(
                tool_name=name,
                success=False,
                result=None,
                error=f"工具执行错误: {e}",
            )
    
    def get_openai_tools(self) -> list[dict[str, Any]]:
        """
        获取 OpenAI 格式的工具定义
        
        返回:
            OpenAI 格式的工具列表
        """
        tools = []
        
        for tool in self._tools.values():
            tools.append({
                "type": "function",
                "function": {
                    "name": tool.definition.name,
                    "description": tool.definition.description,
                    "parameters": tool.definition.parameters,
                }
            })
        
        return tools


# 全局工具注册表
_global_registry: Optional[ToolRegistry] = None


def get_tool_registry() -> ToolRegistry:
    """获取全局工具注册表"""
    global _global_registry
    
    if _global_registry is None:
        _global_registry = ToolRegistry()
    
    return _global_registry
