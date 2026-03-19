"""
文件读取工具

允许 Agent 读取文件内容。
"""

from pathlib import Path
from typing import Any


class ReadTool:
    """文件读取工具"""

    def __init__(self):
        self.name = "read_file"
        self.description = "读取文件内容"
        self.parameters = {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件路径"},
                "limit": {
                    "type": "integer",
                    "description": "最多读取的行数，默认全部",
                    "default": 0,
                },
            },
            "required": ["path"],
        }

    async def execute(self, path: str, limit: int = 0) -> dict[str, Any]:
        """读取文件"""
        try:
            file_path = Path(path).resolve()

            if not file_path.exists():
                return {"success": False, "error": f"文件不存在: {path}", "content": ""}

            if not file_path.is_file():
                return {"success": False, "error": f"不是文件: {path}", "content": ""}

            # 安全限制：只允许读取 /tmp 和 /root
            allowed = str(file_path).startswith("/tmp") or str(file_path).startswith(
                "/root"
            )
            if not allowed:
                return {"success": False, "error": "路径访问被拒绝", "content": ""}

            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                content = (
                    f.read()
                    if limit <= 0
                    else "".join(f.readline() for _ in range(limit))
                )

            max_chars = 100000
            if len(content) > max_chars:
                content = content[:max_chars] + "\n... (内容过长，已截断)"

            return {
                "success": True,
                "content": content,
                "path": str(file_path),
                "size": file_path.stat().st_size,
            }

        except Exception as e:
            return {"success": False, "error": str(e), "content": ""}


async def read_handler(path: str, limit: int = 0) -> str:
    """read_file 工具的处理函数"""
    tool = ReadTool()
    result = await tool.execute(path, limit)
    if result["success"]:
        return result["content"]
    else:
        return f"错误: {result['error']}"
