"""
安全沙箱执行器

使用安全配置创建和管理 Docker 容器，符合 OpenClaw 沙箱标准。
"""

import asyncio
import subprocess
import time
from pathlib import Path
from typing import Optional

from heimaclaw.console import info, warning, error

from .docker_secure import SandboxConfig, SandboxDockerConfig, DEFAULT_SANDBOX_CONFIG


class SecureSandboxExecutor:
    """
    安全沙箱执行器
    
    使用安全的 Docker 配置创建隔离执行环境。
    """
    
    def __init__(
        self,
        workspace: str = "/root/heimaclaw_workspace",
        config: SandboxConfig = None,
    ):
        self.workspace = Path(workspace)
        self.config = config or DEFAULT_SANDBOX_CONFIG
        self._containers: dict[str, dict] = {}  # instance_id -> container_info
    
    def _validate_security(self) -> None:
        """验证配置安全性"""
        errors = self.config.validate()
        if errors:
            raise SecurityError(
                f"沙箱配置安全验证失败:\n" + "\n".join(f"  - {e}" for e in errors)
            )
        
        # 额外的运行时检查
        if self.config.docker.network == "host":
            raise SecurityError("host 网络模式被禁止")
    
    def _get_container_name(self, instance_id: str) -> str:
        """生成安全的容器名称"""
        prefix = self.config.docker.container_prefix
        # 清理 instance_id 中的不安全字符
        safe_id = "".join(c if c.isalnum() or c in "-_" else "-" for c in instance_id)
        return f"{prefix}{safe_id}"
    
    def _build_volumes(self, project_name: str = None) -> dict[str, str]:
        """构建卷挂载"""
        volumes = {}
        
        if self.config.workspace_access == "none":
            # 使用沙箱专用工作区
            sandbox_ws = Path.home() / ".heimaclaw" / "sandboxes" / (project_name or "default")
            sandbox_ws.mkdir(parents=True, exist_ok=True)
            volumes[str(sandbox_ws)] = "/workspace"
        
        elif self.config.workspace_access in ["ro", "rw"]:
            # 挂载宿主机的 heimaclaw_workspace
            if self.config.workspace_access == "ro":
                volumes[f"{self.workspace}:/workspace:ro"] = ""  # 占位
            else:
                volumes[str(self.workspace)] = "/workspace"
        
        return volumes
    
    async def create_container(
        self,
        instance_id: str,
        project_name: str = None,
    ) -> dict:
        """
        创建安全沙箱容器
        
        Args:
            instance_id: 实例 ID
            project_name: 项目名称
            
        Returns:
            容器信息字典
        """
        self._validate_security()
        
        container_name = self._get_container_name(instance_id)
        
        # 检查容器是否已存在
        existing = subprocess.run(
            ["docker", "ps", "-a", "-q", "-f", f"name={container_name}"],
            capture_output=True,
            text=True,
        )
        if existing.stdout.strip():
            # 删除旧容器
            subprocess.run(["docker", "rm", "-f", container_name], capture_output=True)
            info(f"[SecureSandbox] 删除旧容器: {container_name}")
        
        # 构建卷挂载
        volumes = self._build_volumes(project_name)
        
        # 构建 docker run 命令
        cmd = ["docker", "run", "-d"]
        
        # 容器名称
        cmd.extend(["--name", container_name])
        
        docker_cfg = self.config.docker
        
        # 网络模式
        if docker_cfg.network == "none":
            cmd.extend(["--network", "none"])
        elif docker_cfg.network:
            cmd.extend(["--network", docker_cfg.network])
        
        # 用户权限
        if docker_cfg.user:
            cmd.extend(["--user", docker_cfg.user])
        
        # Capabilities drop
        for cap in docker_cfg.cap_drop:
            cmd.extend(["--cap-drop", cap])
        
        # 只读根文件系统
        if docker_cfg.read_only_root:
            cmd.append("--read-only")
        
        # PID 限制
        cmd.extend(["--pids-limit", str(docker_cfg.pids_limit)])
        
        # 内存限制
        cmd.extend(["--memory", docker_cfg.memory])
        if docker_cfg.memory_swap:
            cmd.extend(["--memory-swap", docker_cfg.memory_swap])
        
        # CPU 限制
        cmd.extend(["--cpus", str(docker_cfg.cpus)])
        
        # Ulimits
        for name, limits in docker_cfg.ulimits.items():
            cmd.extend(["--ulimit", f"{name}={limits['soft']}:{limits['hard']}"])
        
        # Tmpfs
        for mount in docker_cfg.tmpfs:
            cmd.extend(["--tmpfs", f"{mount}:rw,noexec,nosuid,size=64m"])
        
        # DNS
        for dns in docker_cfg.dns:
            cmd.extend(["--dns", dns])
        
        # 额外 hosts
        for h in docker_cfg.extra_hosts:
            cmd.extend(["--add-host", h])
        
        # 环境变量
        for k, v in docker_cfg.env.items():
            cmd.extend(["-e", f"{k}={v}"])
        
        # 卷挂载
        for host_path, container_path_mode in volumes.items():
            if ":ro:" in host_path or host_path.endswith(":ro"):
                cmd.extend(["-v", host_path])
            else:
                cmd.extend(["-v", f"{host_path}:/workspace:rw"])
        
        # 工作目录
        cmd.extend(["-w", docker_cfg.workdir])
        
        # 镜像
        cmd.append(docker_cfg.image)
        
        # 命令
        cmd.extend(["sleep", "infinity"])
        
        info(f"[SecureSandbox] 创建容器: {container_name}")
        info(f"[SecureSandbox] 安全配置: network={docker_cfg.network}, user={docker_cfg.user}, cap_drop={docker_cfg.cap_drop}")
        
        # 执行 docker run
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            error(f"[SecureSandbox] 创建容器失败: {result.stderr}")
            raise RuntimeError(f"创建容器失败: {result.stderr}")
        
        container_id = result.stdout.strip()
        
        # 执行 setup 命令（如果配置了）
        if docker_cfg.setup_command:
            info(f"[SecureSandbox] 执行初始化命令...")
            setup_result = subprocess.run(
                ["docker", "exec", container_id, "sh", "-lc", docker_cfg.setup_command],
                capture_output=True,
                text=True,
                timeout=300,  # 5分钟超时
            )
            if setup_result.returncode != 0:
                warning(f"[SecureSandbox] 初始化命令失败: {setup_result.stderr[:200]}")
        
        container_info = {
            "container_id": container_id,
            "container_name": container_name,
            "instance_id": instance_id,
            "created_at": time.time(),
            "config": self.config,
        }
        
        self._containers[instance_id] = container_info
        
        info(f"[SecureSandbox] 容器创建成功: {container_name} ({container_id[:12]})")
        
        return container_info
    
    async def execute(
        self,
        instance_id: str,
        command: str,
        timeout_ms: int = 30000,
    ) -> dict:
        """
        在容器中执行命令
        
        Args:
            instance_id: 实例 ID
            command: 要执行的命令
            timeout_ms: 超时时间（毫秒）
            
        Returns:
            执行结果字典
        """
        if instance_id not in self._containers:
            return {
                "exit_code": 1,
                "stdout": "",
                "stderr": f"容器不存在: {instance_id}",
            }
        
        container_info = self._containers[instance_id]
        container_id = container_info["container_id"]
        
        try:
            # 确保容器运行
            subprocess.run(
                ["docker", "start", container_id],
                capture_output=True,
            )
            
            # 执行命令
            result = subprocess.run(
                ["docker", "exec", container_id, "bash", "-c", command],
                capture_output=True,
                text=True,
                timeout=timeout_ms // 1000,
            )
            
            return {
                "exit_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
        
        except subprocess.TimeoutExpired:
            return {
                "exit_code": -1,
                "stdout": "",
                "stderr": f"命令执行超时 ({timeout_ms}ms)",
            }
        except Exception as e:
            return {
                "exit_code": 1,
                "stdout": "",
                "stderr": str(e),
            }
    
    async def destroy_container(self, instance_id: str) -> None:
        """销毁容器"""
        if instance_id not in self._containers:
            return
        
        container_info = self._containers[instance_id]
        container_id = container_info["container_id"]
        
        try:
            subprocess.run(
                ["docker", "stop", container_id],
                capture_output=True,
                timeout=10,
            )
            subprocess.run(
                ["docker", "rm", "-v", container_id],
                capture_output=True,
            )
            info(f"[SecureSandbox] 容器已销毁: {container_id[:12]}")
        except Exception as e:
            warning(f"[SecureSandbox] 销毁容器出错: {e}")
        
        del self._containers[instance_id]
    
    async def list_containers(self) -> list[dict]:
        """列出所有容器"""
        return list(self._containers.values())


class SecurityError(Exception):
    """安全配置错误异常"""
    pass
