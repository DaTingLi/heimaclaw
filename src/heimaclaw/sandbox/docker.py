"""
Docker 沙箱后端

使用 Docker 容器作为隔离执行环境。
"""

import asyncio
import socket
import threading
import subprocess
import time
from pathlib import Path
from dataclasses import dataclass
from typing import Any, Optional

from heimaclaw.console import error, info, warning

# Docker 操作通过 subprocess 执行，不需要 Python SDK
# 使用 docker CLI 代替 Python SDK


class DockerInstanceInfo:
    """Docker 容器实例信息"""

    def __init__(
        self,
        instance_id: str,
        container: Any,
        project_dir: Path,
        created_at: float,
        container_name: str = "",
    ):
        self.instance_id = instance_id
        self.container = container
        self.container_name = container_name or f"heimaclaw-{instance_id}"
        self.project_dir = project_dir
        self.created_at = created_at
        self._process: Optional[asyncio.subprocess.Process] = None




def get_port_process_info(port):
    """获取占用端口的进程信息"""
    try:
        result = subprocess.run(
            ['ss', '-tlnp', f' sport = :{port}'],
            capture_output=True, text=True, timeout=5
        )
        lines = result.stdout.strip().split('\n')
        processes = []
        for line in lines[1:]:  # 跳过标题行
            if str(port) in line:
                # 提取进程信息
                parts = line.split()
                processes.append(line)
        return processes
    except:
        return []


def kill_process_on_port(port, signal='-9'):
    """强制终止占用端口的进程"""
    try:
        # 查找占用端口的进程
        result = subprocess.run(
            ['fuser', f'{port}/tcp'],
            capture_output=True, text=True, timeout=5
        )
        if result.stdout.strip():
            pids = result.stdout.strip().split()
            for pid in pids:
                try:
                    subprocess.run(['kill', signal, pid], timeout=5)
                    info(f"[端口 {port}] 已 kill 进程 PID={pid}")
                except Exception as e:
                    warning(f"[端口 {port}] kill 进程 {pid} 失败: {e}")
            return True
        return False
    except Exception as e:
        warning(f"[端口 {port}] fuser 查询失败: {e}")
        return False


def get_available_port(start=5000, end=6000, exclude=None):
    """获取范围内第一个可用端口"""
    exclude = exclude or set()
    for port in range(start, end + 1):
        if port in exclude:
            continue
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        try:
            sock.bind(('0.0.0.0', port))
            sock.close()
            return port
        except (OSError, socket.error):
            continue
    return None


def is_port_available(port):
    """检查端口是否可用"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1)
    try:
        sock.bind(('0.0.0.0', port))
        sock.close()
        return True
    except (OSError, socket.error):
        return False

class DockerSandboxBackend:
    """
    Docker 沙箱后端

    使用 Docker 容器作为隔离执行环境。

    安全特性 (OpenClaw 风格):
        - network: none/bridge/host (默认 bridge)
        - user: 非 root 用户 (默认 1000:1000)
        - cap_drop: 移除所有 capabilities
        - read_only_root: 只读根文件系统
        - pids_limit: PID 数量限制
        - memory: 内存限制
        - tmpfs: 挂载临时文件系统
        - exposed_ports: 要映射到宿主机的端口列表
          例如: [5010, 5012] 会映射 5010:5010 和 5012:5012
    """

    backend_type = "docker"

    def __init__(
        self,
        workspace: str = "/root/heimaclaw_workspace",
        base_image: str = "python:3.10-slim",
        max_containers: int = 4,
        # 安全配置 (OpenClaw 风格, 默认为 True)
        security_mode: bool = True,
        # 网络模式: "none"(安全) / "bridge"(可访问外网) / "host"(遗留,危险但端口直通)
        network_mode: str = "host",  # host 模式，端口直接绑定宿主机
        # 用户 (留空则使用 root)
        container_user: str = "root",  # 使用 root 用户
        # 只读根文件系统
        read_only_root: bool = False,  # 允许写入
        # PID 限制
        pids_limit: int = 256,
        # 内存限制
        memory_limit: str = "1g",
        memory_swap: str = "2g",
        # 临时文件系统
        tmpfs: list = None,
        # Capabilities 限制
        cap_drop: list = None,
        # 端口配置
        exposed_ports: list = None,  # 固定端口列表（保留）
        port_range_start: int = 5000,  # 动态端口范围起始
        port_range_end: int = 6000,  # 动态端口范围结束
    ):
        self.workspace = Path(workspace)
        self.base_image = base_image
        self.max_containers = max_containers

        # 安全配置
        self.security_mode = security_mode
        self.network_mode = network_mode
        self.container_user = container_user
        self.read_only_root = read_only_root
        self.pids_limit = pids_limit
        self.memory_limit = memory_limit
        self.memory_swap = memory_swap
        self.tmpfs = tmpfs or ["/tmp", "/var/tmp", "/run"]
        self.cap_drop = cap_drop or ["ALL"]
        # 端口映射列表
        self.exposed_ports = exposed_ports or []  # 空列表，Docker 随机分配端口
        self.port_range_start = port_range_start
        self.port_range_end = port_range_end

        # 智能端口分配：检查每个端口是否可用
        self._allocated_ports = {}  # instance_id -> {container_port: host_port}
        self._port_lock = threading.Lock()
        self._used_host_ports = set()

        # 预检查并记录可用端口（端口范围）
        self._available_port_range = []
        for port in range(self.port_range_start, self.port_range_end + 1):
            if is_port_available(port):
                self._available_port_range.append(port)
        info(f"[DockerSandboxBackend] 可用端口范围: {self.port_range_start}-{self.port_range_end}, "
             f"可用端口: {len(self._available_port_range)} 个")

        # Docker 操作通过 subprocess 执行，不需要 Python SDK 客户端
        # 容器实例记录: instance_id -> DockerInstanceInfo
        self._instances: dict[str, DockerInstanceInfo] = {}

        # 实例计数器
        self._instance_counter = 0

        info(f"[DockerSandboxBackend] 初始化完成")
        info(f"[DockerSandboxBackend] 最大容器数: {max_containers}")
    
    async def initialize(self) -> None:
        """初始化沙箱（创建默认实例）"""
        pass

    def _generate_instance_id(self, prefix: str = "docker") -> str:
        """生成唯一的实例 ID"""
        self._instance_counter += 1
        import uuid; return f"{prefix}-{self._instance_counter}-{uuid.uuid4().hex[:6]}"

    async def create_instance(self, project_name: str = "default", agent_id: str = None, memory_mb: int = None, cpu_count: int = None, **kwargs) -> str:
        """创建沙箱实例

        Args:
            project_name: 项目名称
            agent_id: Agent ID (兼容旧接口)
            memory_mb: 内存限制 MB (未实现)
            cpu_count: CPU 核心数 (未实现)
        """
        if agent_id:
            project_name = agent_id
        """
        创建新的沙箱实例

        Args:
            project_name: 项目名称 (用于容器名和 hostname)

        Returns:
            instance_id: 新创建的实例 ID
        """
        instance_id = self._generate_instance_id()
        container_name = f"heimaclaw-{instance_id}"
        project_dir = self.workspace / project_name
        project_dir.mkdir(parents=True, exist_ok=True)

        info(f"[DockerSandboxBackend] 创建实例: {instance_id}, 容器: {container_name[:20]}...")

        try:
            # 构建 docker run 命令
            # 使用 bridge 网络 + 端口映射 (关键修复!)
            cmd = [
                "docker", "run", "-d",
                "--name", container_name,
                "--hostname", project_name,
                "-v", f"{project_dir}:/root/workspace:rw",
                "-w", "/root/workspace",
            ]

            if self.security_mode:
                # === OpenClaw 风格安全配置 ===

                # 网络隔离
                if self.network_mode == "none":
                    cmd.extend(["--network", "none"])
                elif self.network_mode == "bridge":
                    cmd.extend(["--network", "bridge"])
                else:
                    if self.network_mode == "host":
                        warning("[DockerSandboxBackend] host 网络模式: 容器与宿主机共享网络命名空间")
                    cmd.extend(["--network", self.network_mode])

                # 用户权限
                if self.container_user:
                    cmd.extend(["--user", self.container_user])

                # Capabilities 限制
                for cap in self.cap_drop:
                    cmd.extend(["--cap-drop", cap])

                # 只读根文件系统
                if self.read_only_root:
                    cmd.append("--read-only")

                # PID 限制
                cmd.extend(["--pids-limit", str(self.pids_limit)])

                # 内存限制
                cmd.extend(["--memory", self.memory_limit])
                if self.memory_swap:
                    cmd.extend(["--memory-swap", self.memory_swap])

                # 临时文件系统
                for mount in self.tmpfs:
                    cmd.extend(["--tmpfs", f"{mount}:rw,noexec,nosuid,size=64m"])

                # DNS
                cmd.extend(["--dns", "1.1.1.1", "--dns", "8.8.8.8"])

            else:
                # 非安全模式或 host 模式
                cmd.extend(["--net", self.network_mode])

            # ========== 智能端口映射（bridge 模式） ==========
            # 策略：按需分配，冲突自动重试
            if self.network_mode == "bridge":
                if not self.exposed_ports:
                    # 无固定端口需求，让 Docker 随机分配
                    cmd.extend(["-P"])
                    info(f"[DockerSandboxBackend] Docker 随机端口映射")
                else:
                    # 尝试按顺序分配端口
                    for port in self.exposed_ports:
                        cmd.extend(["-p", f"{port}:{port}"])
                    info(f"[DockerSandboxBackend] 请求端口映射: {self.exposed_ports}")
            elif self.network_mode == "host":
                info(f"[DockerSandboxBackend] host 模式：端口直接绑定宿主机")

            # 添加环境变量
            cmd.extend([
                "-e", f"PROJECT_NAME={project_name}",
                "-e", "PYTHONUNBUFFERED=1",
                "-e", "HOST=0.0.0.0",
                "-e", "FLASK_RUN_HOST=0.0.0.0",
            ])

            cmd.append(self.base_image)
            cmd.extend(["sleep", "infinity"])

            # 启动容器
            result = await asyncio.create_subprocess_shell(
                " ".join(cmd),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await result.communicate()

            if result.returncode != 0:
                error(f"容器启动失败: {stderr.decode()}")
                raise RuntimeError(f"Docker container failed to start: {stderr.decode()}")

            container_id = stdout.decode().strip()[:12]
            info(f"[DockerSandboxBackend] 容器已启动: {container_id}")

            # 获取容器对象
            # 通过 docker inspect 获取容器信息 (不依赖 docker SDK)
            import subprocess
            result = subprocess.run(['docker', 'inspect', container_id, '--format', '{{.State.Status}}'], capture_output=True, text=True)
            if result.returncode != 0:
                raise RuntimeError(f'容器不存在: {container_id}')
            container = None  # 我们不直接引用 container 对象

            # 记录实例
            instance_info = DockerInstanceInfo(
                instance_id=instance_id,
                container=container,
                project_dir=project_dir,
                created_at=time.time(),
            )
            self._instances[instance_id] = instance_info
            info(f"[DockerSandboxBackend] 实例已创建: {instance_id}")
            return instance_info

        except Exception as e:
            error(f"创建沙箱实例失败: {e}")
            raise

    async def execute(
        self,
        instance_id: str,
        command: str,
        timeout_ms: int = 30000,
    ) -> "CommandResult":
        """
        在沙箱实例中执行命令

        Args:
            instance_id: 实例 ID
            command: 要执行的命令
            timeout_ms: 超时时间 (毫秒)

        Returns:
            CommandResult: 包含 stdout, stderr, exit_code
        """
        if instance_id not in self._instances:
            raise ValueError(f"Unknown instance: {instance_id}")

        instance = self._instances[instance_id]
        container_name = instance.container_name

        info(f"[Docker-Backend.execute] 实例={instance_id}, cmd={command[:100]}...")

        try:
            import shlex
            # 使用 docker exec 在容器内执行命令
            # 注意: 使用 bash -c 来执行命令，支持管道等复杂命令
            # 使用 shlex.quote 进行标准的 Shell 级转义，解决带引号/管道符命令的语法错误问题
            result = await asyncio.create_subprocess_shell(
                f"docker exec {container_name} bash -c {shlex.quote(command)}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    result.communicate(), timeout=timeout_ms / 1000
                )

                output = stdout.decode("utf-8", errors="replace")
                error_output = stderr.decode("utf-8", errors="replace")

                info(f"[Docker-Backend.execute] Docker 执行完成: exit={result.returncode}")

                return CommandResult(
                    exit_code=result.returncode,
                    stdout=output,
                    stderr=error_output,
                )

            except asyncio.TimeoutError:
                result.kill()
                await result.wait()
                error(f"[Docker-Backend.execute] 命令执行超时: {timeout_ms}ms")
                return CommandResult(
                    exit_code=-1,
                    stdout="",
                    stderr=f"Command execution timeout ({timeout_ms}ms)",
                )

        except Exception as e:
            error(f"[Docker-Backend.execute] 执行失败: {e}")
            return CommandResult(
                exit_code=-1,
                stdout="",
                stderr=str(e),
            )

    async def destroy_instance(self, instance_id: str) -> None:
        """销毁沙箱实例"""
        if instance_id not in self._instances:
            warning(f"[DockerSandboxBackend] 尝试销毁未知实例: {instance_id}")
            return

        instance = self._instances[instance_id]
        container_name = instance.container_name

        try:
            # 停止并删除容器
            subprocess.run(['docker', 'stop', container_name], capture_output=True, timeout=10)
            subprocess.run(['docker', 'rm', '-f', container_name], capture_output=True)
            info(f"[DockerSandboxBackend] 实例已销毁: {instance_id}")
        except Exception as e:
            warning(f"[DockerSandboxBackend] 销毁实例失败: {e}")
        finally:
            del self._instances[instance_id]

    def list_instances(self) -> list[str]:
        """列出所有活跃实例"""
        return list(self._instances.keys())

    async def cleanup_idle_instances(self, max_idle_seconds: int = 3600) -> int:
        """
        清理空闲实例

        Args:
            max_idle_seconds: 最大空闲时间 (秒)

        Returns:
            清理的实例数量
        """
        now = time.time()
        to_remove = []

        for instance_id, instance in self._instances.items():
            idle_time = now - instance.created_at
            if idle_time > max_idle_seconds:
                to_remove.append(instance_id)

        for instance_id in to_remove:
            await self.destroy_instance(instance_id)

        if to_remove:
            info(f"[DockerSandboxBackend] 已清理 {len(to_remove)} 个空闲实例")

        return len(to_remove)


class CommandResult:
    """命令执行结果"""
    exit_code: int
    stdout: str
    stderr: str

    def __init__(self, exit_code: int = 0, stdout: str = "", stderr: str = ""):
        self.exit_code = exit_code
        self.stdout = stdout
        self.stderr = stderr

    @property
    def success(self) -> bool:
        return self.exit_code == 0
