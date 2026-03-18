"""
工具管理器

负责工具的安装、卸载、列表、加载等功能。
"""

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from heimaclaw.console import error, info, success, warning


@dataclass
class ToolInfo:
    """工具信息"""

    name: str
    version: str
    description: str
    path: Path
    functions: list[dict[str, Any]]
    enabled: bool = True


class ToolManager:
    """
    工具管理器

    管理工具的安装、卸载、列表、加载。
    """

    def __init__(self, tools_dir: Optional[Path] = None):
        """
        初始化工具管理器

        参数:
            tools_dir: 工具目录，默认 ~/.heimaclaw/tools
        """
        self.tools_dir = tools_dir or Path.home() / ".heimaclaw" / "tools"
        self.tools_dir.mkdir(parents=True, exist_ok=True)
        self._tools: dict[str, ToolInfo] = {}
        self._load_tools()

    def _load_tools(self) -> None:
        """加载所有已安装的工具"""
        for tool_dir in self.tools_dir.iterdir():
            if not tool_dir.is_dir():
                continue

            tool_json = tool_dir / "tool.json"
            if not tool_json.exists():
                continue

            try:
                with open(tool_json, encoding="utf-8") as f:
                    data = json.load(f)

                tool_info = ToolInfo(
                    name=data.get("name", tool_dir.name),
                    version=data.get("version", "0.0.0"),
                    description=data.get("description", ""),
                    path=tool_dir,
                    functions=data.get("functions", []),
                    enabled=data.get("enabled", True),
                )

                self._tools[tool_info.name] = tool_info

            except Exception as e:
                warning(f"加载工具失败: {tool_dir.name} - {e}")

    def install(self, source: str) -> bool:
        """
        安装工具

        参数:
            source: 工具源（本地路径、Git URL、PyPI 包名）

        返回:
            是否安装成功
        """
        info(f"安装工具: {source}")

        # 判断源类型
        if source.startswith(("http://", "https://", "git@")):
            return self._install_from_git(source)
        elif Path(source).exists():
            return self._install_from_local(Path(source))
        else:
            return self._install_from_pypi(source)

    def _install_from_git(self, url: str) -> bool:
        """从 Git 安装工具"""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            # 克隆仓库
            result = subprocess.run(
                ["git", "clone", "--depth", "1", url, tmpdir],
                capture_output=True,
                text=True,
            )

            if result.returncode != 0:
                error(f"Git 克隆失败: {result.stderr}")
                return False

            # 检查是否有 tool.json
            tool_json = Path(tmpdir) / "tool.json"
            if not tool_json.exists():
                error("工具包缺少 tool.json 文件")
                return False

            # 读取工具信息
            with open(tool_json, encoding="utf-8") as f:
                data = json.load(f)

            tool_name = data.get("name")
            if not tool_name:
                error("tool.json 缺少 name 字段")
                return False

            # 复制到工具目录
            dest_dir = self.tools_dir / tool_name
            if dest_dir.exists():
                shutil.rmtree(dest_dir)

            shutil.copytree(tmpdir, dest_dir)

            # 重新加载工具
            self._load_tools()

            success(f"工具安装成功: {tool_name}")
            return True

    def _install_from_local(self, path: Path) -> bool:
        """从本地目录安装工具"""
        tool_json = path / "tool.json"

        if not tool_json.exists():
            error(f"工具包缺少 tool.json: {path}")
            return False

        with open(tool_json, encoding="utf-8") as f:
            data = json.load(f)

        tool_name = data.get("name")
        if not tool_name:
            error("tool.json 缺少 name 字段")
            return False

        # 复制到工具目录
        dest_dir = self.tools_dir / tool_name
        if dest_dir.exists():
            shutil.rmtree(dest_dir)

        shutil.copytree(path, dest_dir)

        # 重新加载工具
        self._load_tools()

        success(f"工具安装成功: {tool_name}")
        return True

    def _install_from_pypi(self, package: str) -> bool:
        """从 PyPI 安装工具包"""
        result = subprocess.run(
            ["pip", "install", package],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            error(f"PyPI 安装失败: {result.stderr}")
            return False

        # 安装后尝试从包中查找工具定义
        # TODO: 实现包内工具发现

        success(f"包安装成功: {package}")
        return True

    def uninstall(self, name: str) -> bool:
        """
        卸载工具

        参数:
            name: 工具名称

        返回:
            是否卸载成功
        """
        if name not in self._tools:
            error(f"工具不存在: {name}")
            return False

        tool_dir = self._tools[name].path
        shutil.rmtree(tool_dir)
        del self._tools[name]

        success(f"工具已卸载: {name}")
        return True

    def list(self) -> list[ToolInfo]:
        """
        列出所有已安装的工具

        返回:
            工具信息列表
        """
        return list(self._tools.values())

    def get(self, name: str) -> Optional[ToolInfo]:
        """
        获取工具信息

        参数:
            name: 工具名称

        返回:
            工具信息，不存在则返回 None
        """
        return self._tools.get(name)

    def enable(self, name: str) -> bool:
        """启用工具"""
        if name not in self._tools:
            return False

        tool = self._tools[name]
        tool.enabled = True
        self._save_tool_config(tool)
        return True

    def disable(self, name: str) -> bool:
        """禁用工具"""
        if name not in self._tools:
            return False

        tool = self._tools[name]
        tool.enabled = False
        self._save_tool_config(tool)
        return True

    def _save_tool_config(self, tool: ToolInfo) -> None:
        """保存工具配置"""
        tool_json = tool.path / "tool.json"

        with open(tool_json, encoding="utf-8") as f:
            data = json.load(f)

        data["enabled"] = tool.enabled

        with open(tool_json, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)


# 全局工具管理器
_global_manager: Optional[ToolManager] = None


def get_tool_manager() -> ToolManager:
    """获取全局工具管理器"""
    global _global_manager

    if _global_manager is None:
        _global_manager = ToolManager()

    return _global_manager
