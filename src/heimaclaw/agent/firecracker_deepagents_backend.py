"""
Firecracker 沙箱 DeepAgents 后端

继承 LocalShellBackend，但 execute() 路由到 Firecracker 沙箱。
文件操作依然走 LocalShellBackend（映射了工作区）。
沙箱失败时不允许回退本地，必须返回错误给上层。
"""

import asyncio
import os
import subprocess
from pathlib import Path
from typing import Optional

from deepagents.backends import LocalShellBackend
from deepagents.backends.protocol import ExecuteResponse
from heimaclaw.console import info, error


# 沙箱内路径
SANDBOX_WORKSPACE = "/root/heimaclaw_workspace"
# 宿主机路径
HOST_WORKSPACE = "./heimaclaw_workspace"


class FirecrackerDeepAgentsBackend(LocalShellBackend):
    """
    深度集成 Firecracker 沙箱的 DeepAgents 后端
    
    文件读写依然走 LocalShellBackend（映射了工作区），
    但危险的 Shell 执行 (execute) 强制路由到 Firecracker 沙箱。
    沙箱失败时不允许回退本地。
    """

    def __init__(
        self,
        root_dir: str,
        sandbox_backend,
        instance_id: str,
        env: dict = None,
        **kwargs
    ):
        # 使用沙箱路径初始化（供文件操作使用）
        super().__init__(root_dir=root_dir, env=env, **kwargs)
        self.sandbox_backend = sandbox_backend
        self.instance_id = instance_id
        info(f"[FirecrackerDeepAgentsBackend] 初始化，沙箱实例: {instance_id}")

    async def _do_sandbox_execute(self, command: str, timeout_ms: int):
        """异步执行沙箱命令"""
        return await self.sandbox_backend.execute(
            instance_id=self.instance_id,
            command=command,
            timeout_ms=timeout_ms,
        )

    def execute(self, command: str, *, timeout: int | None = None) -> ExecuteResponse:
        """同步执行 - 强制沙箱，不允许本地回退"""
        info(f"[FC-Backend.execute] 实例={self.instance_id}, cmd={command[:50]}...")

        timeout_ms = (timeout or 120) * 1000

        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(self._do_sandbox_execute(command, timeout_ms))
            finally:
                loop.close()

            info(f"[FC-Backend.execute] 沙箱执行完成: exit={result.exit_code}")
            return ExecuteResponse(
                output=result.stdout + ("\n" + result.stderr if result.stderr else ""),
                exit_code=result.exit_code,
                truncated=False,
            )
        except Exception as e:
            error(f"[FC-Backend.execute] 沙箱执行失败: {e}")
            return ExecuteResponse(
                output="",
                stderr=f"[FC-Backend] 沙箱执行失败: {e}",
                exit_code=1,
                truncated=False,
            )

    async def aexecute(self, command: str, *, timeout: int | None = None) -> ExecuteResponse:
        """异步执行 - 强制沙箱，不允许本地回退"""
        info(f"[FC-Backend.aexecute] 实例={self.instance_id}, cmd={command[:50]}...")

        timeout_ms = (timeout or 120) * 1000

        try:
            result = await self._do_sandbox_execute(command, timeout_ms)
            info(f"[FC-Backend.aexecute] 沙箱执行完成: exit={result.exit_code}")
            return ExecuteResponse(
                output=result.stdout + ("\n" + result.stderr if result.stderr else ""),
                exit_code=result.exit_code,
                truncated=False,
            )
        except Exception as e:
            error(f"[FC-Backend.aexecute] 沙箱执行失败: {e}")
            return ExecuteResponse(
                output="",
                stderr=f"[FC-Backend] 沙箱执行失败: {e}",
                exit_code=1,
                truncated=False,
            )


__all__ = ["FirecrackerDeepAgentsBackend"]
