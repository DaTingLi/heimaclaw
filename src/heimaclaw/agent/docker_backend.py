"""
Docker Backend - Docker 执行后端

实现 BaseBackend 接口，提供 Docker 容器化执行能力。
"""

import asyncio
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from heimaclaw.agent.base_backend import BaseBackend


@dataclass
class ExecuteResponse:
    """执行结果"""
    output: str
    exit_code: int
    error: str = None


class DockerBackend(BaseBackend):
    """
    Docker 沙箱后端
    
    为每个项目创建独立的 Docker 容器，
    容器内有完整的 Python 环境和依赖。
    """
    
    def __init__(
        self,
        workspace: str = "/root/heimaclaw_workspace",
        max_containers: int = 4,
    ):
        self.workspace = Path(workspace)
        
        # 延迟初始化容器池
        self._container_pool = None
        self._max_containers = max_containers
    
    @property
    def container_pool(self):
        """延迟加载容器池"""
        if self._container_pool is None:
            from heimaclaw.core.dockerimpl import get_container_pool
            self._container_pool = get_container_pool()
        return self._container_pool
    
    async def execute(
        self,
        command: str,
        project_name: str = None,
        timeout: int = None,
        is_background: bool = False,
    ) -> ExecuteResponse:
        """
        在项目的 Docker 容器中执行命令
        
        Args:
            command: 要执行的命令
            project_name: 项目名称（从命令中提取）
            timeout: 超时时间（秒）
            is_background: 是否后台执行
            
        Returns:
            ExecuteResponse
        """
        # 提取项目名
        if not project_name:
            project_name = self._extract_project_name(command)
        
        if not project_name:
            return ExecuteResponse(
                output="",
                exit_code=1,
                error="无法提取项目名称",
            )
        
        try:
            # 获取容器
            container = await self.container_pool.get_container(project_name)
            
            # 执行命令
            result = await container.execute(
                command=command,
                timeout=timeout,
                is_background=is_background,
            )
            
            return ExecuteResponse(
                output=result.get("output", ""),
                exit_code=result.get("exit_code", 0),
            )
        
        except Exception as e:
            return ExecuteResponse(
                output="",
                exit_code=1,
                error=str(e),
            )
    
    async def start_service(
        self,
        project_name: str,
        command: str,
        port: int = 5000,
    ) -> dict:
        """
        启动项目服务
        
        Args:
            project_name: 项目名称
            command: 启动命令
            port: 容器端口
            
        Returns:
            {"success": bool, "host_port": int, "access_url": str}
        """
        try:
            # 获取容器
            container = await self.container_pool.get_container(project_name)
            
            # 在后台启动服务
            await container.execute(
                command=command,
                is_background=True,
            )
            
            # 获取主机端口
            host_port = container.host_ports.get(port, port)
            
            return {
                "success": True,
                "host_port": host_port,
                "access_url": f"http://localhost:{host_port}",
            }
        
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }
    
    async def stop_service(self, project_name: str) -> bool:
        """
        停止项目服务
        
        Args:
            project_name: 项目名称
            
        Returns:
            是否成功
        """
        try:
            await self.container_pool.destroy_container(project_name)
            return True
        except Exception:
            return False
    
    async def get_service_status(self, project_name: str) -> dict:
        """
        获取服务状态
        
        Args:
            project_name: 项目名称
            
        Returns:
            状态信息
        """
        try:
            meta_path = self.workspace / ".projects" / project_name / ".project_meta.json"
            
            if not meta_path.exists():
                return {"status": "NOT_FOUND"}
            
            import json
            meta = json.loads(meta_path.read_text())
            
            return {
                "status": meta.get("container", {}).get("status", "UNKNOWN"),
                "ports": meta.get("container", {}).get("hostPorts", {}),
                "image": meta.get("container", {}).get("image"),
                "last_accessed": meta.get("lastAccessed"),
            }
        
        except Exception as e:
            return {"status": "ERROR", "error": str(e)}
    
    def _extract_project_name(self, command: str) -> Optional[str]:
        """
        从命令中提取项目名称
        
        Args:
            command: 命令字符串
            
        Returns:
            项目名称
        """
        # 常见的项目路径模式
        patterns = [
            r"cd\s+(?:/root/heimaclaw_workspace/)?(\S+)",  # cd project
            r"/root/heimaclaw_workspace/(\S+)",  # /root/heimaclaw_workspace/project
            r"nohup\s+.*?(\S+?)[\s/]",  # nohup python server.py
            r"python\s+(\S+?)\.",  # python server.py
            r"python3\s+(\S+?)\.",  # python3 server.py
        ]
        
        for pattern in patterns:
            match = re.search(pattern, command)
            if match:
                project_name = match.group(1)
                
                # 清理路径
                project_name = project_name.strip("/")
                
                # 常见脚本名，不是项目名
                if project_name in ["server", "app", "main", "run"]:
                    continue
                
                return project_name
        
        return None
    
    def get_stats(self) -> dict:
        """获取后端统计"""
        return {
            "backend": "docker",
            "workspace": str(self.workspace),
            "container_pool": self.container_pool.get_stats(),
        }


# 全局实例
_docker_backend: Optional[DockerBackend] = None


def get_docker_backend() -> DockerBackend:
    """获取全局 Docker 后端实例"""
    global _docker_backend
    if _docker_backend is None:
        _docker_backend = DockerBackend()
    return _docker_backend
