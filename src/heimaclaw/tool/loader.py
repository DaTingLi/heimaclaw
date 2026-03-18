"""
工具加载器

负责从已安装的工具包中加载函数到 ToolRegistry。
"""

import importlib.util
import sys
from typing import Optional

from heimaclaw.agent.tools import ToolRegistry, get_tool_registry
from heimaclaw.console import info, warning
from heimaclaw.tool.manager import ToolInfo, ToolManager, get_tool_manager


class ToolLoader:
    """
    工具加载器

    从已安装的工具包加载函数到 ToolRegistry。
    """

    def __init__(
        self,
        tool_manager: Optional[ToolManager] = None,
        registry: Optional[ToolRegistry] = None,
    ):
        """
        初始化工具加载器

        参数:
            tool_manager: 工具管理器
            registry: 工具注册表
        """
        self.tool_manager = tool_manager or get_tool_manager()
        self.registry = registry or get_tool_registry()

    def load_all(self) -> int:
        """
        加载所有已启用的工具

        返回:
            成功加载的工具数量
        """
        loaded_count = 0

        for tool_info in self.tool_manager.list():
            if not tool_info.enabled:
                continue

            try:
                self.load_tool(tool_info)
                loaded_count += 1
            except Exception as e:
                warning(f"加载工具失败: {tool_info.name} - {e}")

        info(f"已加载 {loaded_count} 个工具")
        return loaded_count

    def load_tool(self, tool_info: ToolInfo) -> None:
        """
        加载单个工具

        参数:
            tool_info: 工具信息
        """
        import json

        # 获取入口文件
        entry_file = tool_info.path / "tool.json"

        with open(entry_file, encoding="utf-8") as f:
            data = json.load(f)

        entry_module = data.get("entry", "main.py")
        module_path = tool_info.path / entry_module

        if not module_path.exists():
            raise FileNotFoundError(f"入口文件不存在: {module_path}")

        # 动态导入模块
        module_name = f"heimaclaw_tool_{tool_info.name}"
        spec = importlib.util.spec_from_file_location(module_name, module_path)

        if spec is None or spec.loader is None:
            raise ImportError(f"无法加载模块: {module_path}")

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

        # 注册函数
        functions = data.get("functions", [])

        for func_def in functions:
            func_name = func_def.get("name")

            if not func_name:
                warning("函数定义缺少 name 字段")
                continue

            # 从模块获取函数
            handler = getattr(module, func_name, None)

            if handler is None:
                warning(f"函数不存在: {func_name}")
                continue

            if not callable(handler):
                warning(f"不是可调用对象: {func_name}")
                continue

            # 注册到 ToolRegistry
            self.registry.register_function(
                name=func_name,
                description=func_def.get("description", ""),
                handler=handler,
                parameters=func_def.get("parameters"),
                timeout_ms=func_def.get("timeout_ms", 30000),
            )

        info(f"加载工具: {tool_info.name} ({len(functions)} 个函数)")
