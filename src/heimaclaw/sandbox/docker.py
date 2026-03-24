"""
Docker 沙箱后端

实现 SandboxBackend 接口，提供 Docker 容器化执行能力。
"""

import asyncio
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from heimaclaw.sandbox.base import (
    SandboxBackend,
    InstanceInfo,
    InstanceStatus,
    ExecutionResult,
)
from heimaclaw.console import info, error, warning


@dataclass
class DockerInstanceInfo:
    """Docker 容器实例信息"""
    instance_id: str
    container_id: str
    project_name: str
    status: InstanceStatus
    created_at: float
    host_port: int
    container_port: int = 5000


class DockerSandboxBackend(SandboxBackend):
    """
    Docker 沙箱后端
    
    使用 Docker 容器作为隔离执行环境。
    每个项目对应一个独立的容器。
    """
    
    def __init__(
        self,
        workspace: str = "/root/heimaclaw_workspace",
        base_image: str = "python:3.10-slim",
        max_containers: int = 4,
    ):
        self.workspace = Path(workspace)
        self.base_image = base_image
        self.max_containers = max_containers
        
        # 容器实例记录: instance_id -> DockerInstanceInfo
        self._instances: dict[str, DockerInstanceInfo] = {}
        
        # 实例计数器
        self._instance_counter = 0
    
    @property
    def backend_type(self) -> str:
        return "docker"
    
    @property
    def is_available(self) -> bool:
        """检查 Docker 是否可用"""
        try:
            result = subprocess.run(
                ["docker", "--version"],
                capture_output=True,
                text=True,
            )
            return result.returncode == 0
        except FileNotFoundError:
            return False
    
    async def initialize(self) -> None:
        """初始化后端"""
        if not self.is_available:
            raise RuntimeError("Docker 不可用，请安装 Docker")
        
        info("[DockerSandboxBackend] 初始化完成")
    
    async def shutdown(self) -> None:
        """关闭后端"""
        # 销毁所有实例
        for instance_id in list(self._instances.keys()):
            await self.destroy_instance(instance_id)
        
        info("[DockerSandboxBackend] 关闭完成")
    
    async def create_instance(
        self,
        agent_id: str,
        memory_mb: int = 128,
        cpu_count: int = 1,
        snapshot_id: Optional[str] = None,
        preferred_port: int = None,
    ) -> InstanceInfo:
        """
        创建沙箱实例
        
        Args:
            agent_id: Agent ID (用作项目名)
            memory_mb: 内存大小
            cpu_count: CPU 核心数
            snapshot_id: 快照 ID (未实现)
            preferred_port: 优先使用的宿主机端口（用户指定）
            
        Returns:
            InstanceInfo
        """
        self._instance_counter += 1
        instance_id = f"docker-{agent_id}-{self._instance_counter}"
        project_name = agent_id
        
        try:
            # 导入 dockerimpl 组件
            from heimaclaw.core.dockerimpl import (
                get_container_pool,
                get_port_pool,
                get_dependency_analyzer,
            )
            
            container_pool = get_container_pool()
            port_pool = get_port_pool()
            analyzer = get_dependency_analyzer()
            
            # 分析项目依赖
            project_dir = self.workspace / project_name
            deps = analyzer.analyze(project_dir)
            
            # 分配端口
            host_port = port_pool.allocate(project_name, 5000, preferred_port)
            
            # 构建镜像（如果需要）
            image_name = self.base_image
            
            if deps.pip_packages or deps.system_deps:
                # 生成项目专用镜像
                dockerfile_content = analyzer.generate_dockerfile(
                    project_dir,
                    self.base_image,
                )
                
                dockerfile_dir = Path(f"/tmp/heimaclaw/{project_name}")
                dockerfile_dir.mkdir(parents=True, exist_ok=True)
                dockerfile_path = dockerfile_dir / "Dockerfile"
                dockerfile_path.write_text(dockerfile_content)
                
                image_name = f"heimaclaw/{project_name}:latest"
                
                # 构建镜像
                build_result = subprocess.run(
                    [
                        "docker", "build",
                        "-t", image_name,
                        "-f", str(dockerfile_path),
                        str(project_dir),
                    ],
                    capture_output=True,
                    text=True,
                    timeout=300,
                )
                
                if build_result.returncode != 0:
                    warning(f"[DockerSandboxBackend] 镜像构建失败，使用基础镜像: {build_result.stderr[:200]}")
                    image_name = self.base_image
            
            # 创建容器
            container_name = f"heimaclaw-{project_name}"
            
            # 检查是否已存在容器
            existing = subprocess.run(
                ["docker", "ps", "-a", "-q", "-f", f"name={container_name}"],
                capture_output=True,
                text=True,
            )
            
            if existing.stdout.strip():
                # 删除旧容器
                subprocess.run(["docker", "rm", "-f", container_name], capture_output=True)
            
            # 构建 docker run 命令
            cmd = [
                "docker", "run", "-d",
                "--name", container_name,
                "--hostname", project_name,
                "-v", f"{project_dir}:/root/workspace:rw",
                "-w", "/root/workspace",
                "-p", f"{host_port}:5000",
            ]
            
            # 添加环境变量
            cmd.extend([
                "-e", f"PROJECT_NAME={project_name}",
                "-e", "PYTHONUNBUFFERED=1",
            ])
            
            cmd.append(image_name)
            cmd.extend(["sleep", "infinity"])
            
            # 创建容器
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                raise RuntimeError(f"创建容器失败: {result.stderr}")
            
            container_id = result.stdout.strip()
            
            # 记录实例
            instance_info = DockerInstanceInfo(
                instance_id=instance_id,
                container_id=container_id,
                project_name=project_name,
                status=InstanceStatus.RUNNING,
                created_at=time.time(),
                host_port=host_port,
                container_port=5000,
            )
            
            self._instances[instance_id] = instance_info
            
            info(f"[DockerSandboxBackend] 创建实例: {instance_id}, 容器: {container_id[:12]}")
            
            return InstanceInfo(
                instance_id=instance_id,
                agent_id=agent_id,
                status=InstanceStatus.RUNNING,
                created_at=time.time(),
                memory_mb=memory_mb,
                cpu_count=cpu_count,
                metadata={
                    "container_id": container_id,
                    "host_port": host_port,
                    "image": image_name,
                },
            )
        
        except Exception as e:
            error(f"[DockerSandboxBackend] 创建实例失败: {e}")
            raise
    
    async def destroy_instance(self, instance_id: str) -> None:
        """
        销毁沙箱实例
        
        Args:
            instance_id: 实例 ID
        """
        if instance_id not in self._instances:
            return
        
        instance = self._instances[instance_id]
        
        try:
            # 停止并删除容器
            subprocess.run(
                ["docker", "stop", instance.container_id],
                capture_output=True,
                timeout=10,
            )
            subprocess.run(
                ["docker", "rm", "-v", instance.container_id],
                capture_output=True,
            )
            
            # 释放端口
            from heimaclaw.core.dockerimpl import get_port_pool
            port_pool = get_port_pool()
            port_pool.release(instance.project_name)
            
            del self._instances[instance_id]
            
            info(f"[DockerSandboxBackend] 销毁实例: {instance_id}")
        
        except Exception as e:
            warning(f"[DockerSandboxBackend] 销毁实例时出错: {e}")
    
    async def execute(
        self,
        instance_id: str,
        command: str,
        timeout_ms: int = 30000,
    ) -> ExecutionResult:
        """
        在实例中执行命令
        
        Args:
            instance_id: 实例 ID
            command: 要执行的命令
            timeout_ms: 超时时间（毫秒）
            
        Returns:
            ExecutionResult
        """
        if instance_id not in self._instances:
            return ExecutionResult(
                exit_code=1,
                stdout="",
                stderr=f"实例不存在: {instance_id}",
                duration_ms=0,
            )
        
        instance = self._instances[instance_id]
        start_time = time.time()
        
        try:
            # 确保容器运行
            subprocess.run(
                ["docker", "start", instance.container_id],
                capture_output=True,
            )
            
            # 执行命令
            result = subprocess.run(
                [
                    "docker", "exec",
                    instance.container_id,
                    "bash", "-c", command,
                ],
                capture_output=True,
                text=True,
                timeout=timeout_ms // 1000,
            )
            
            duration_ms = int((time.time() - start_time) * 1000)
            
            return ExecutionResult(
                exit_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                duration_ms=duration_ms,
            )
        
        except subprocess.TimeoutExpired:
            duration_ms = int((time.time() - start_time) * 1000)
            return ExecutionResult(
                exit_code=-1,
                stdout="",
                stderr="命令执行超时",
                duration_ms=duration_ms,
            )
        
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            return ExecutionResult(
                exit_code=1,
                stdout="",
                stderr=str(e),
                duration_ms=duration_ms,
            )
    
    async def execute_in_background(
        self,
        instance_id: str,
        command: str,
    ) -> bool:
        """
        在实例中后台执行命令
        
        Args:
            instance_id: 实例 ID
            command: 要执行的命令
            
        Returns:
            是否成功
        """
        if instance_id not in self._instances:
            return False
        
        instance = self._instances[instance_id]
        
        try:
            subprocess.run(
                [
                    "docker", "exec", "-d",
                    instance.container_id,
                    "bash", "-c", command,
                ],
                capture_output=True,
            )
            return True
        
        except Exception:
            return False
    
    async def get_instance(self, instance_id: str) -> Optional[InstanceInfo]:
        """获取实例信息"""
        if instance_id not in self._instances:
            return None
        
        instance = self._instances[instance_id]
        
        return InstanceInfo(
            instance_id=instance.instance_id,
            agent_id=instance.project_name,
            status=instance.status,
            created_at=instance.created_at,
            metadata={
                "container_id": instance.container_id,
                "host_port": instance.host_port,
            },
        )
    
    async def list_instances(
        self,
        agent_id: Optional[str] = None,
    ) -> list[InstanceInfo]:
        """列出实例"""
        instances = []
        
        for instance in self._instances.values():
            if agent_id and instance.project_name != agent_id:
                continue
            
            instances.append(InstanceInfo(
                instance_id=instance.instance_id,
                agent_id=instance.project_name,
                status=instance.status,
                created_at=instance.created_at,
                metadata={
                    "container_id": instance.container_id,
                    "host_port": instance.host_port,
                },
            ))
        
        return instances
    
    async def create_snapshot(
        self,
        instance_id: str,
        snapshot_id: str,
    ) -> str:
        """创建快照（委托给 SnapshotManager）"""
        if instance_id not in self._instances:
            raise RuntimeError(f"实例不存在: {instance_id}")
        
        instance = self._instances[instance_id]
        
        from heimaclaw.core.dockerimpl import get_snapshot_manager
        
        snapshot_manager = get_snapshot_manager()
        snapshot = snapshot_manager.create_snapshot(
            instance.project_name,
            description=f"Snapshot {snapshot_id}",
        )
        
        return snapshot.path
    
    async def pause_instance(self, instance_id: str) -> None:
        """暂停实例"""
        if instance_id not in self._instances:
            return
        
        instance = self._instances[instance_id]
        
        subprocess.run(
            ["docker", "pause", instance.container_id],
            capture_output=True,
        )
        
        instance.status = InstanceStatus.PAUSED
    
    async def resume_instance(self, instance_id: str) -> None:
        """恢复实例"""
        if instance_id not in self._instances:
            return
        
        instance = self._instances[instance_id]
        
        subprocess.run(
            ["docker", "unpause", instance.container_id],
            capture_output=True,
        )
        
        instance.status = InstanceStatus.RUNNING
    
    def get_container_logs(
        self,
        instance_id: str,
        lines: int = 100,
    ) -> str:
        """获取容器日志"""
        if instance_id not in self._instances:
            return ""
        
        instance = self._instances[instance_id]
        
        result = subprocess.run(
            ["docker", "logs", "--tail", str(lines), instance.container_id],
            capture_output=True,
            text=True,
        )
        
        return result.stdout + result.stderr


__all__ = ["DockerSandboxBackend"]
