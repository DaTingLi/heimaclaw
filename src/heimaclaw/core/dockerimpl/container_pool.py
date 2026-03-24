"""
Container Pool - 容器池管理器

管理所有项目容器，控制资源使用。
"""

import asyncio
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional


class ContainerStatus(Enum):
    """容器状态"""
    NONE = "NONE"
    CREATING = "CREATING"
    RUNNING = "RUNNING"
    IDLE = "IDLE"
    STOPPED = "STOPPED"
    GRACEFUL = "GRACEFUL"
    DESTROYED = "DESTROYED"
    ERROR = "ERROR"


@dataclass
class ContainerConfig:
    """容器配置"""
    project_name: str
    image: str = "python:3.10-slim"
    cpu_limit: float = 1.0
    memory_limit: str = "1g"
    workspace_path: Path = None
    exposed_ports: list[int] = None
    environment: dict = None


@dataclass
class ContainerInfo:
    """容器信息"""
    container_id: str
    project_name: str
    status: ContainerStatus
    image: str
    host_ports: dict[int, int]  # container_port -> host_port
    created_at: str
    last_started: str = None
    idle_since: str = None


class ProjectContainer:
    """
    项目容器管理器
    
    负责单个项目的容器生命周期管理。
    """
    
    def __init__(
        self,
        config: ContainerConfig,
        port_pool,
        dependency_analyzer,
        snapshot_manager,
    ):
        self.config = config
        self.port_pool = port_pool
        self.dependency_analyzer = dependency_analyzer
        self.snapshot_manager = snapshot_manager
        
        self.container_id: Optional[str] = None
        self.status = ContainerStatus.NONE
        self.host_ports: dict[int, int] = {}
        self.idle_since: Optional[str] = None
        
        self._idle_timer: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()
    
    async def ensure(self) -> str:
        """
        确保容器存在并运行
        
        Returns:
            容器 ID
        """
        async with self._lock:
            if self.status == ContainerStatus.NONE:
                await self._create()
            
            elif self.status == ContainerStatus.STOPPED:
                await self._start()
            
            elif self.status == ContainerStatus.IDLE:
                await self._start()
            
            elif self.status == ContainerStatus.ERROR:
                # 尝试重建
                await self._destroy()
                await self._create()
                await self._start()
            
            return self.container_id
    
    async def execute(
        self,
        command: str,
        timeout: int = None,
        is_background: bool = False,
    ) -> dict:
        """
        在容器中执行命令
        
        Args:
            command: 要执行的命令
            timeout: 超时时间（秒）
            is_background: 是否后台执行
            
        Returns:
            {"output": str, "exit_code": int}
        """
        # 确保容器运行
        await self.ensure()
        
        # 重置空闲计时器
        self._reset_idle_timer()
        
        # 执行命令
        result = await self._exec_in_container(command, timeout, is_background)
        
        # 更新状态
        self.status = ContainerStatus.IDLE
        self.idle_since = datetime.now().isoformat()
        
        return result
    
    async def _create(self):
        """创建容器"""
        self.status = ContainerStatus.CREATING
        
        try:
            # 1. 构建镜像（如果需要）
            image = await self._build_image()
            
            # 2. 分配端口
            for container_port in (self.config.exposed_ports or [5000]):
                host_port = self.port_pool.allocate(self.config.project_name, container_port)
                self.host_ports[container_port] = host_port
            
            # 3. 创建容器
            self.container_id = await self._do_create(image)
            
            # 4. 更新状态
            self.status = ContainerStatus.STOPPED
            
            # 5. 保存元数据
            self._save_meta()
        
        except Exception as e:
            self.status = ContainerStatus.ERROR
            raise RuntimeError(f"创建容器失败: {e}") from e
    
    async def _build_image(self) -> str:
        """构建项目专用镜像"""
        deps = self.dependency_analyzer.analyze(self.config.workspace_path)
        
        if not deps.pip_packages and not deps.system_deps:
            # 无特殊依赖，使用基础镜像
            return self.config.image
        
        # 生成 Dockerfile
        dockerfile_content = self.dependency_analyzer.generate_dockerfile(
            self.config.workspace_path,
            self.config.image,
        )
        
        # 写入临时 Dockerfile
        dockerfile_dir = Path(f"/tmp/heimaclaw/{self.config.project_name}")
        dockerfile_dir.mkdir(parents=True, exist_ok=True)
        dockerfile_path = dockerfile_dir / "Dockerfile"
        dockerfile_path.write_text(dockerfile_content)
        
        # 构建镜像
        image_name = f"heimaclaw/{self.config.project_name}:latest"
        
        result = subprocess.run(
            [
                "docker", "build",
                "-t", image_name,
                "-f", str(dockerfile_path),
                str(self.config.workspace_path),
            ],
            capture_output=True,
            text=True,
        )
        
        if result.returncode != 0:
            # 构建失败，使用基础镜像
            return self.config.image
        
        return image_name
    
    async def _do_create(self, image: str) -> str:
        """实际创建容器"""
        workspace = self.config.workspace_path or Path(f"/root/heimaclaw_workspace/{self.config.project_name}")
        
        # 端口映射
        port_bindings = {}
        for container_port, host_port in self.host_ports.items():
            port_bindings[f"{container_port}/tcp"] = [{"HostPort": str(host_port)}]
        
        # 环境变量
        env = self.config.environment or {}
        env.update({
            "PROJECT_NAME": self.config.project_name,
            "PYTHONUNBUFFERED": "1",
        })
        
        # 构建 docker run 命令
        cmd = [
            "docker", "run", "-d",
            "--name", f"heimaclaw-{self.config.project_name}",
            "--hostname", self.config.project_name,
            "-v", f"{workspace}:/root/workspace:rw",
            "-w", "/root/workspace",
            "--memory", self.config.memory_limit,
            "--cpus", str(self.config.cpu_limit),
            "--restart", "unless-stopped",
        ]
        
        # 添加端口映射
        for container_port, host_port in self.host_ports.items():
            cmd.extend(["-p", f"{host_port}:{container_port}"])
        
        # 添加环境变量
        for key, value in env.items():
            cmd.extend(["-e", f"{key}={value}"])
        
        cmd.append(image)
        cmd.extend(["sleep", "infinity"])
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            # 如果容器已存在，尝试获取 ID
            result = subprocess.run(
                ["docker", "ps", "-a", "-q", "-f", f"name=heimaclaw-{self.config.project_name}"],
                capture_output=True,
                text=True,
            )
            
            if result.stdout.strip():
                # 删除旧容器
                subprocess.run(["docker", "rm", "-f", f"heimaclaw-{self.config.project_name}"], capture_output=True)
                # 重新创建
                result = subprocess.run(cmd, capture_output=True, text=True)
            else:
                raise RuntimeError(f"创建容器失败: {result.stderr}")
        
        container_id = result.stdout.strip()
        
        return container_id
    
    async def _start(self):
        """启动容器"""
        if not self.container_id:
            raise RuntimeError("容器不存在")
        
        result = subprocess.run(
            ["docker", "start", self.container_id],
            capture_output=True,
            text=True,
        )
        
        if result.returncode != 0:
            raise RuntimeError(f"启动容器失败: {result.stderr}")
        
        self.status = ContainerStatus.RUNNING
        self.idle_since = None
        
        # 更新元数据
        self._save_meta()
    
    async def _stop(self):
        """停止容器"""
        if not self.container_id:
            return
        
        result = subprocess.run(
            ["docker", "stop", self.container_id],
            capture_output=True,
            text=True,
        )
        
        if result.returncode != 0:
            # 忽略停止失败
            pass
        
        self.status = ContainerStatus.STOPPED
        
        # 更新元数据
        self._save_meta()
    
    async def _destroy(self):
        """销毁容器"""
        if self.container_id:
            # 停止并删除容器
            subprocess.run(["docker", "stop", self.container_id], capture_output=True)
            subprocess.run(["docker", "rm", "-v", self.container_id], capture_output=True)
        
        # 释放端口
        self.port_pool.release(self.config.project_name)
        
        self.container_id = None
        self.status = ContainerStatus.DESTROYED
    
    async def _exec_in_container(
        self,
        command: str,
        timeout: int = None,
        is_background: bool = False,
    ) -> dict:
        """在容器中执行命令"""
        if not self.container_id:
            raise RuntimeError("容器不存在")
        
        if is_background:
            # 后台执行
            cmd = [
                "docker", "exec", "-d",
                self.container_id,
                "bash", "-c", command,
            ]
            subprocess.run(cmd, capture_output=True)
            return {"output": "", "exit_code": 0}
        
        # 同步执行
        cmd = [
            "docker", "exec",
            self.container_id,
            "bash", "-c", command,
        ]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            
            return {
                "output": result.stdout + result.stderr,
                "exit_code": result.returncode,
            }
        except subprocess.TimeoutExpired:
            return {"output": "Command timed out", "exit_code": -1}
    
    def _reset_idle_timer(self):
        """重置空闲计时器"""
        if self._idle_timer:
            self._idle_timer.cancel()
        
        self.idle_since = None
        self.status = ContainerStatus.RUNNING
    
    def _save_meta(self):
        """保存容器元数据"""
        meta_dir = Path(f"/root/heimaclaw_workspace/.projects/{self.config.project_name}")
        meta_dir.mkdir(parents=True, exist_ok=True)
        
        meta = {
            "name": self.config.project_name,
            "container": {
                "containerId": self.container_id,
                "image": self.config.image,
                "status": self.status.value,
                "hostPorts": {str(cp): hp for cp, hp in self.host_ports.items()},
                "createdAt": datetime.now().isoformat(),
                "lastStarted": datetime.now().isoformat(),
            },
        }
        
        import json
        meta_path = meta_dir / ".project_meta.json"
        meta_path.write_text(json.dumps(meta, indent=2))
    
    def get_info(self) -> ContainerInfo:
        """获取容器信息"""
        return ContainerInfo(
            container_id=self.container_id or "",
            project_name=self.config.project_name,
            status=self.status,
            image=self.config.image,
            host_ports=self.host_ports.copy(),
            created_at=datetime.now().isoformat(),
            last_started=self.idle_since,
        )


class ContainerPool:
    """
    容器池管理器
    
    管理所有项目容器，控制资源使用。
    """
    
    def __init__(
        self,
        max_containers: int = 4,
        idle_timeout: int = 1800,  # 30 分钟
        workspace: str = "/root/heimaclaw_workspace",
    ):
        self.max_containers = max_containers
        self.idle_timeout = idle_timeout
        self.workspace = Path(workspace)
        
        self._containers: dict[str, ProjectContainer] = {}
        self._lock = asyncio.Lock()
        
        # 初始化依赖组件
        from .port_pool import get_port_pool
        from .dependency_analyzer import get_dependency_analyzer
        from .snapshot_manager import get_snapshot_manager
        
        self._port_pool = get_port_pool()
        self._dependency_analyzer = get_dependency_analyzer()
        self._snapshot_manager = get_snapshot_manager()
    
    async def get_container(self, project_name: str) -> ProjectContainer:
        """获取或创建项目容器"""
        async with self._lock:
            if project_name not in self._containers:
                # 检查是否达到上限
                if len(self._containers) >= self.max_containers:
                    # 尝试清理空闲容器
                    await self._cleanup_idle_containers()
                
                # 再次检查
                if len(self._containers) >= self.max_containers:
                    raise RuntimeError(
                        f"容器数量已达上限 ({self.max_containers})，"
                        "请等待其他项目完成"
                    )
                
                # 创建新容器
                config = ContainerConfig(
                    project_name=project_name,
                    workspace_path=self.workspace / project_name,
                )
                
                self._containers[project_name] = ProjectContainer(
                    config=config,
                    port_pool=self._port_pool,
                    dependency_analyzer=self._dependency_analyzer,
                    snapshot_manager=self._snapshot_manager,
                )
            
            return self._containers[project_name]
    
    async def _cleanup_idle_containers(self):
        """清理空闲容器"""
        idle_containers = [
            (name, container)
            for name, container in self._containers.items()
            if container.status == ContainerStatus.IDLE
        ]
        
        if not idle_containers:
            return
        
        # 清理 1 个容器
        name, container = idle_containers[0]
        
        # 创建快照（备份）
        try:
            self._snapshot_manager.create_snapshot(
                name,
                description=f"自动清理快照 (idle)",
            )
        except Exception:
            pass
        
        # 停止容器
        await container._stop()
        
        # 从池中移除
        del self._containers[name]
    
    async def destroy_container(self, project_name: str):
        """销毁指定项目容器"""
        async with self._lock:
            if project_name in self._containers:
                await self._containers[project_name]._destroy()
                del self._containers[project_name]
    
    def get_stats(self) -> dict:
        """获取容器池统计"""
        status_counts = {}
        for container in self._containers.values():
            status = container.status.value
            status_counts[status] = status_counts.get(status, 0) + 1
        
        return {
            "total": len(self._containers),
            "max": self.max_containers,
            "idle_timeout_seconds": self.idle_timeout,
            "by_status": status_counts,
            "containers": {
                name: {
                    "status": c.status.value,
                    "ports": {str(cp): hp for cp, hp in c.host_ports.items()},
                }
                for name, c in self._containers.items()
            },
        }


# 全局实例
_container_pool: Optional[ContainerPool] = None


def get_container_pool() -> ContainerPool:
    """获取全局容器池实例"""
    global _container_pool
    if _container_pool is None:
        _container_pool = ContainerPool()
    return _container_pool
