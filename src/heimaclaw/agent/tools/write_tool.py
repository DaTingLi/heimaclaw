"""
文件写入工具

允许 Agent 创建或覆盖文件。
"""

from pathlib import Path
from typing import Any


class WriteTool:
    """文件写入工具"""

    def __init__(self):
        self.name = "write_file"
        self.description = "写入内容到文件（会覆盖原有内容）"
        self.parameters = {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件路径"},
                "content": {"type": "string", "description": "要写入的内容"},
            },
            "required": ["path", "content"],
        }

    async def execute(self, path: str, content: str) -> dict[str, Any]:
        """写入文件"""
        try:
            file_path = Path(path).resolve()

            # 安全限制：只允许写入 /tmp 和 /root
            allowed_dirs = ["/tmp", "/root"]
            is_allowed = any(str(file_path).startswith(d) for d in allowed_dirs)
            if not is_allowed:
                return {
                    "success": False,
                    "error": "路径访问被拒绝，只允许写入 /tmp 或 /root",
                    "path": str(file_path),
                }

            file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)

            return {"success": True, "path": str(file_path), "size": len(content)}

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "path": str(file_path) if "file_path" in dir() else path,
            }


async def write_handler(path: str, content: str) -> str:
    """write_file 工具的处理函数"""
    tool = WriteTool()
    result = await tool.execute(path, content)
    if result["success"]:
        return f"文件已写入: {result['path']} ({result['size']} bytes)"
    else:
        return f"错误: {result['error']}"
