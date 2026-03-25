"""
Docker DeepAgents 后端

继承 LocalShellBackend，但 execute() 路由到 Docker 容器。
文件操作依然走 LocalShellBackend（映射了工作区）。
"""

import asyncio
import subprocess
from pathlib import Path
from typing import Optional

from deepagents.backends import LocalShellBackend
from deepagents.backends.protocol import ExecuteResponse
from heimaclaw.console import info, error


# 沙箱内路径
SANDBOX_WORKSPACE = "/root/heimaclaw_workspace"
# 宿主机路径
HOST_WORKSPACE = "/root/heimaclaw_workspace"


class DockerDeepAgentsBackend(LocalShellBackend):
    """
    深度集成 Docker 沙箱的 DeepAgents 后端
    
    文件读写依然走 LocalShellBackend（映射了工作区），
    但危险的 Shell 执行 (execute) 强制路由到 Docker 容器。
    """

    def __init__(
        self,
        root_dir: str,
        docker_backend,
        instance_id: str,
        env: dict = None,
        **kwargs
    ):
        # 使用宿主机路径初始化（供文件操作使用）
        super().__init__(root_dir=root_dir, env=env, **kwargs)
        self.docker_backend = docker_backend
        self.instance_id = instance_id
        self.container_id = None
        
        # 从 instance_id 获取 container_id
        if instance_id in docker_backend._instances:
            self.container_id = docker_backend._instances[instance_id].container_name
        
        info(f"[DockerDeepAgentsBackend] 初始化，实例: {instance_id}, 容器: {self.container_id[:12] if self.container_id else 'N/A'}")

    async def _do_docker_execute(self, command: str, timeout_ms: int):
        """异步执行 Docker 命令"""
        return await self.docker_backend.execute(
            instance_id=self.instance_id,
            command=command,
            timeout_ms=timeout_ms,
        )

    def execute(self, command: str, *, timeout: int | None = None) -> ExecuteResponse:
        """同步执行 - 强制 Docker 容器，不允许本地回退"""
        info(f"[Docker-Backend.execute] 实例={self.instance_id}, cmd={command[:50]}...")

        timeout_ms = (timeout or 120) * 1000

        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(self._do_docker_execute(command, timeout_ms))
            finally:
                loop.close()

            info(f"[Docker-Backend.execute] Docker 执行完成: exit={result.exit_code}")
            return ExecuteResponse(
                output=result.stdout + ("\n" + result.stderr if result.stderr else ""),
                exit_code=result.exit_code,
                truncated=False,
            )
        except Exception as e:
            error(f"[Docker-Backend.execute] Docker 执行失败: {e}")
            return ExecuteResponse(
                output="",
                stderr=f"[Docker-Backend] Docker 执行失败: {e}",
                exit_code=1,
                truncated=False,
            )

    async def aexecute(self, command: str, *, timeout: int | None = None) -> ExecuteResponse:
        """异步执行 - 强制 Docker 容器，不允许本地回退"""
        info(f"[Docker-Backend.aexecute] 实例={self.instance_id}, cmd={command[:50]}...")

        timeout_ms = (timeout or 120) * 1000

        try:
            result = await self._do_docker_execute(command, timeout_ms)
            info(f"[Docker-Backend.aexecute] Docker 执行完成: exit={result.exit_code}")
            return ExecuteResponse(
                output=result.stdout + ("\n" + result.stderr if result.stderr else ""),
                exit_code=result.exit_code,
                truncated=False,
            )
        except Exception as e:
            error(f"[Docker-Backend.aexecute] Docker 执行失败: {e}")
            return ExecuteResponse(
                output="",
                stderr=f"[Docker-Backend] Docker 执行失败: {e}",
                exit_code=1,
                truncated=False,
            )

    def get_container_logs(self, lines: int = 100) -> str:
        """获取容器日志"""
        if not self.container_id:
            return "容器不存在"
        
        result = subprocess.run(
            ["docker", "logs", "--tail", str(lines), self.container_id],
            capture_output=True,
            text=True,
        )
        
        return result.stdout + result.stderr


__all__ = ["DockerDeepAgentsBackend"]
