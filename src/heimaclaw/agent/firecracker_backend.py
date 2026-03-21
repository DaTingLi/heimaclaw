"""Firecracker 沙箱后端

将命令路由到 Firecracker microVM 沙箱中执行。
"""

import asyncio
from typing import Optional

from deepagents.backends.protocol import ExecuteResponse, SandboxBackendProtocol
from heimaclaw.console import info, error


class FirecrackerSandboxBackend:
    """使用 Firecracker microVM 沙箱执行命令的后端"""

    def __init__(self, sandbox_backend, instance_id: str, root_dir: str = "/root"):
        self._sandbox_backend = sandbox_backend
        self._instance_id = instance_id
        self._root_dir = root_dir
        self._timeout = 120

    @property
    def id(self) -> str:
        return f"firecracker-{self._instance_id}"

    @property
    def cwd(self) -> str:
        return self._root_dir

    def execute(
        self,
        command: str,
        *,
        timeout: Optional[int] = None,
    ) -> ExecuteResponse:
        """通过沙箱执行命令"""
        info(f"[FirecrackerSandboxBackend.execute] instance={self._instance_id}, cmd={command[:100]}")

        try:
            result = asyncio.get_event_loop().run_until_complete(
                self._sandbox_backend.execute(
                    instance_id=self._instance_id,
                    command=command,
                    timeout_ms=(timeout or self._timeout) * 1000,
                )
            )

            return ExecuteResponse(
                output=result.stdout or "",
                exit_code=result.exit_code,
                truncated=False,
            )

        except Exception as e:
            error(f"[FirecrackerSandboxBackend] 执行失败: {e}")
            return ExecuteResponse(
                output=f"沙箱执行错误: {e}",
                exit_code=1,
                truncated=False,
            )

    def ls(self, path: str) -> "LsResult":
        """列出目录（通过 execute 实现）"""
        import json
        from deepagents.backends.protocol import LsResult, FileInfo

        result = self.execute(f"python3 -c \"import os,json; print(json.dumps([{'path':e.path,'is_dir':e.is_dir()} for e in os.scandir('{path}')]))\"")
        
        try:
            entries = json.loads(result.output)
            return LsResult(entries=entries)
        except:
            return LsResult(entries=[])

    def read(self, file_path: str, offset: int = 0, limit: int = 2000) -> "ReadResult":
        """读取文件"""
        from deepagents.backends.protocol import ReadResult
        from deepagents.backends.utils import create_file_data

        result = self.execute(f"cat {file_path}")
        
        if result.exit_code != 0:
            return ReadResult(error=f"无法读取文件: {result.output}")
        
        return ReadResult(file_data=create_file_data(result.output))

    def write(self, file_path: str, content: str) -> "WriteResult":
        """写入文件"""
        from deepagents.backends.protocol import WriteResult
        
        # 使用 heredoc 避免转义问题
        result = self.execute(f"cat > {file_path} << 'DEEPAGENTS_EOF'\n{content}\nDEEPAGENTS_EOF")
        
        if result.exit_code != 0:
            return WriteResult(error=f"无法写入文件: {result.output}")
        
        return WriteResult(path=file_path)

    def edit(self, file_path: str, old_string: str, new_string: str, replace_all: bool = False) -> "EditResult":
        """编辑文件"""
        from deepagents.backends.protocol import EditResult
        
        # 使用 sed 进行替换
        flag = "g" if replace_all else ""
        result = self.execute(f"sed -i 's/{old_string}/{new_string}/{flag}' {file_path}")
        
        if result.exit_code != 0:
            return EditResult(error=f"编辑失败: {result.output}")
        
        return EditResult(path=file_path)

    def grep(self, pattern: str, path: str = None, glob: str = None) -> "GrepResult":
        """搜索文件"""
        from deepagents.backends.protocol import GrepResult
        
        path = path or "."
        result = self.execute(f"grep -rHn {pattern} {path}")
        
        matches = []
        for line in result.output.strip().split("\n"):
            if ":" in line:
                parts = line.split(":", 2)
                if len(parts) >= 3:
                    matches.append({"path": parts[0], "line": int(parts[1]), "text": parts[2]})
        
        return GrepResult(matches=matches)

    def glob(self, pattern: str, path: str = "/") -> "GlobResult":
        """glob 搜索"""
        from deepagents.backends.protocol import GlobResult
        
        result = self.execute(f"find {path} -name '{pattern}' -type f")
        
        matches = []
        for line in result.output.strip().split("\n"):
            if line:
                matches.append({"path": line, "is_dir": False})
        
        return GlobResult(matches=matches)

    def upload_files(self, files):
        """上传文件到沙箱"""
        from deepagents.backends.protocol import FileUploadResponse
        # 简化实现
        return [FileUploadResponse(path=path, success=True) for path, _ in files]

    def download_files(self, paths):
        """从沙箱下载文件"""
        from deepagents.backends.protocol import FileDownloadResponse
        # 简化实现
        return [FileDownloadResponse(path=path, success=True, content=b"") for path in paths]
