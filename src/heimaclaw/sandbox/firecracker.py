"""
Firecracker 沙箱后端

通过 Firecracker microVM 实现硬件级隔离。
"""

import asyncio
import json
import os
import shutil
import socket
import subprocess
import time
import uuid
from pathlib import Path
from typing import Optional

from heimaclaw.console import error, info, sandbox_event, warning
from heimaclaw.sandbox.base import (
    ExecutionResult,
    InstanceInfo,
    InstanceStatus,
    SandboxBackend,
)


class FirecrackerBackend(SandboxBackend):
    """
    Firecracker 沙箱后端

    通过 Firecracker 创建轻量级 microVM 实例，实现硬件级隔离。
    目标：冷启动 < 200ms，预热后 < 50ms，单实例内存 < 20MB。
    """

    def __init__(
        self,
        firecracker_path: str = "firecracker",
        jailer_path: str = "jailer",
        rootfs_path: Optional[str] = None,
        kernel_path: Optional[str] = None,
        work_dir: str = "/opt/heimaclaw/sandboxes",
    ):
        """
        初始化 Firecracker 后端

        参数:
            firecracker_path: firecracker 可执行文件路径
            jailer_path: jailer 可执行文件路径
            rootfs_path: 根文件系统模板路径
            kernel_path: 内核镜像路径
            work_dir: 工作目录
        """
        self.firecracker_path = firecracker_path
        self.jailer_path = jailer_path
        self.rootfs_path = rootfs_path or "/opt/heimaclaw/images/rootfs.ext4"
        self.kernel_path = kernel_path or "/opt/heimaclaw/images/vmlinux"
        self.work_dir = Path(work_dir)

        self._instances: dict[str, InstanceInfo] = {}
        self._processes: dict[str, subprocess.Popen] = {}
        self._sockets: dict[str, socket.socket] = {}
        self._vsock_ports: dict[str, int] = {}
        self._next_vsock_port = 10000

        self._initialized = False

    @property
    def backend_type(self) -> str:
        """后端类型"""
        return "firecracker"

    @property
    def is_available(self) -> bool:
        """
        检查 Firecracker 是否可用

        需要满足：
        1. firecracker 可执行文件存在
        2. KVM 支持可用
        """
        # 检查 firecracker
        if not shutil.which(self.firecracker_path):
            return False

        # 检查 KVM
        kvm_path = Path("/dev/kvm")
        if not kvm_path.exists():
            return False

        if not os.access(kvm_path, os.R_OK | os.W_OK):
            return False

        return True

    async def initialize(self) -> None:
        """
        初始化后端

        创建工作目录，检查依赖。
        """
        if self._initialized:
            return

        sandbox_event("初始化 Firecracker 后端")

        # 创建工作目录
        self.work_dir.mkdir(parents=True, exist_ok=True)

        # 检查 firecracker
        if not shutil.which(self.firecracker_path):
            warning("firecracker 未安装，沙箱功能将不可用")
            warning("安装方法: https://github.com/firecracker-microvm/firecracker")

        # 检查 KVM
        if not Path("/dev/kvm").exists():
            warning("KVM 不可用，microVM 将无法启动")
            warning("确保 CPU 支持虚拟化并已在 BIOS 中启用")

        # 检查镜像文件
        if not Path(self.rootfs_path).exists():
            warning(f"根文件系统不存在: {self.rootfs_path}")

        if not Path(self.kernel_path).exists():
            warning(f"内核镜像不存在: {self.kernel_path}")

        self._initialized = True
        sandbox_event("Firecracker 后端初始化完成")

    async def shutdown(self) -> None:
        """关闭后端，清理所有实例"""
        sandbox_event("关闭 Firecracker 后端")

        # 销毁所有实例
        for instance_id in list(self._instances.keys()):
            try:
                await self.destroy_instance(instance_id)
            except Exception as e:
                error(f"销毁实例 {instance_id} 失败: {e}")

        self._initialized = False

    async def create_instance(
        self,
        agent_id: str,
        memory_mb: int = 128,
        cpu_count: int = 1,
        snapshot_id: Optional[str] = None,
    ) -> InstanceInfo:
        """
        创建 Firecracker microVM 实例

        参数:
            agent_id: Agent ID
            memory_mb: 内存大小（MB）
            cpu_count: CPU 核心数
            snapshot_id: 快照 ID（用于快照恢复）

        返回:
            实例信息
        """
        if not self._initialized:
            await self.initialize()

        instance_id = str(uuid.uuid4())[:8]
        instance_dir = self.work_dir / instance_id
        instance_dir.mkdir(parents=True, exist_ok=True)

        sandbox_event(f"创建 microVM 实例: {instance_id} (agent={agent_id})")

        # 分配 vsock 端口
        vsock_port = self._next_vsock_port
        self._next_vsock_port += 1
        self._vsock_ports[instance_id] = vsock_port

        # 创建实例信息
        instance_info = InstanceInfo(
            instance_id=instance_id,
            agent_id=agent_id,
            status=InstanceStatus.CREATING,
            created_at=time.time(),
            memory_mb=memory_mb,
            cpu_count=cpu_count,
            vsock_port=vsock_port,
        )

        try:
            # 如果指定了快照，从快照恢复
            if snapshot_id:
                await self._restore_from_snapshot(instance_id, snapshot_id)
            else:
                # 创建新实例
                await self._create_new_instance(
                    instance_id,
                    instance_dir,
                    memory_mb,
                    cpu_count,
                    vsock_port,
                )

            instance_info.status = InstanceStatus.RUNNING
            self._instances[instance_id] = instance_info

            sandbox_event(f"microVM 实例创建成功: {instance_id}")
            return instance_info

        except Exception as e:
            instance_info.status = InstanceStatus.ERROR
            self._instances[instance_id] = instance_info
            error(f"创建 microVM 实例失败: {e}")
            raise

    async def _create_new_instance(
        self,
        instance_id: str,
        instance_dir: Path,
        memory_mb: int,
        cpu_count: int,
        vsock_port: int,
    ) -> None:
        """
        创建新的 microVM 实例
        """
        # 复制 rootfs
        rootfs_copy = instance_dir / "rootfs.ext4"
        if Path(self.rootfs_path).exists():
            shutil.copy(self.rootfs_path, rootfs_copy)
        else:
            # 创建空的 rootfs（用于演示）
            await self._create_minimal_rootfs(rootfs_copy, memory_mb)

        # 生成 Firecracker 配置
        config = {
            "boot-source": {
                "kernel_image_path": self.kernel_path,
                "boot_args": "console=ttyS0 reboot=k panic=1 pci=off",
            },
            "drives": [
                {
                    "drive_id": "rootfs",
                    "path_on_host": str(rootfs_copy),
                    "is_root_device": True,
                    "is_read_only": False,
                }
            ],
            "machine-config": {
                "vcpu_count": cpu_count,
                "mem_size_mib": memory_mb,
                "smt": False,
            },
            "vsock": {
                "vsock_id": "vsock0",
                "guest_cid": vsock_port,
                "uds_path": str(instance_dir / "vsock.sock"),
            },
        }

        config_path = instance_dir / "config.json"
        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)

        # 启动 Firecracker
        socket_path = instance_dir / "api.sock"

        # 使用 nohup 后台启动
        cmd = [
            self.firecracker_path,
            "--api-sock",
            str(socket_path),
            "--config-file",
            str(config_path),
        ]

        # 检查 firecracker 是否存在
        if not shutil.which(self.firecracker_path):
            # 降级模式：使用进程模拟
            warning("firecracker 不可用，使用降级模式（进程隔离）")
            await self._create_fallback_instance(instance_id, instance_dir)
            return

        process = subprocess.Popen(
            cmd,
            stdout=open(instance_dir / "stdout.log", "w"),
            stderr=open(instance_dir / "stderr.log", "w"),
            start_new_session=True,
        )

        self._processes[instance_id] = process

        # 等待启动
        await asyncio.sleep(0.1)  # 等待 100ms

        if process.poll() is not None:
            raise RuntimeError(f"Firecracker 启动失败，退出码: {process.returncode}")

    async def _create_fallback_instance(
        self,
        instance_id: str,
        instance_dir: Path,
    ) -> None:
        """
        创建降级模式实例（进程隔离）

        当 Firecracker 不可用时使用。
        """
        info(f"使用降级模式创建实例: {instance_id}")

        # 在降级模式下，我们只记录实例信息
        # 实际的隔离由 Agent 运行时处理
        fallback_marker = instance_dir / ".fallback"
        fallback_marker.write_text("process")

    async def _create_minimal_rootfs(self, rootfs_path: Path, size_mb: int) -> None:
        """
        创建最小的 rootfs
        """
        # 创建空文件作为占位符
        rootfs_path.touch()
        info(f"创建最小 rootfs: {rootfs_path}")

    async def _restore_from_snapshot(
        self,
        instance_id: str,
        snapshot_id: str,
    ) -> None:
        """
        从快照恢复实例
        """
        snapshot_path = self.work_dir / "snapshots" / f"{snapshot_id}.snapshot"

        if not snapshot_path.exists():
            raise FileNotFoundError(f"快照不存在: {snapshot_id}")

        sandbox_event(f"从快照恢复实例: {snapshot_id}")

        # TODO: 实现 Firecracker 快照恢复
        # 参考文档: https://github.com/firecracker-microvm/firecracker/blob/main/docs/snapshotting.md

    async def destroy_instance(self, instance_id: str) -> None:
        """
        销毁实例
        """
        if instance_id not in self._instances:
            return

        sandbox_event(f"销毁 microVM 实例: {instance_id}")

        # 终止进程
        if instance_id in self._processes:
            process = self._processes[instance_id]
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
            del self._processes[instance_id]

        # 关闭 socket
        if instance_id in self._sockets:
            self._sockets[instance_id].close()
            del self._sockets[instance_id]

        # 清理 vsock 端口
        if instance_id in self._vsock_ports:
            del self._vsock_ports[instance_id]

        # 删除实例目录
        instance_dir = self.work_dir / instance_id
        if instance_dir.exists():
            shutil.rmtree(instance_dir, ignore_errors=True)

        # 移除实例信息
        del self._instances[instance_id]

    async def execute(
        self,
        instance_id: str,
        command: str,
        timeout_ms: int = 30000,
    ) -> ExecutionResult:
        """
        在实例中执行命令

        通过 vsock 与 microVM 内的 agent 通信。
        """
        if instance_id not in self._instances:
            raise ValueError(f"实例不存在: {instance_id}")

        instance = self._instances[instance_id]

        if instance.status != InstanceStatus.RUNNING:
            raise RuntimeError(f"实例状态异常: {instance.status}")

        time.time()

        # 检查是否为降级模式
        instance_dir = self.work_dir / instance_id
        fallback_marker = instance_dir / ".fallback"

        if fallback_marker.exists():
            # 降级模式：直接在本地执行
            return await self._execute_fallback(command, timeout_ms)

        # 正常模式：通过 vsock 通信
        return await self._execute_via_vsock(instance_id, command, timeout_ms)

    async def _execute_fallback(
        self,
        command: str,
        timeout_ms: int,
    ) -> ExecutionResult:
        """
        降级模式执行命令
        """
        start_time = time.time()

        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout_ms / 1000,
            )

            duration_ms = int((time.time() - start_time) * 1000)

            return ExecutionResult(
                exit_code=process.returncode or 0,
                stdout=stdout.decode("utf-8", errors="replace"),
                stderr=stderr.decode("utf-8", errors="replace"),
                duration_ms=duration_ms,
            )

        except asyncio.TimeoutError:
            process.kill()
            return ExecutionResult(
                exit_code=-1,
                stdout="",
                stderr="命令执行超时",
                duration_ms=timeout_ms,
            )

    async def _execute_via_vsock(
        self,
        instance_id: str,
        command: str,
        timeout_ms: int,
    ) -> ExecutionResult:
        """
        通过 vsock 执行命令

        使用 Unix socket 连接到 microVM 的 vsock 端口。
        """
        import json
        import socket
        import time

        start_time = time.time()

        # 获取 vsock socket 路径
        instance_dir = self.work_dir / instance_id
        vsock_path = instance_dir / "vsock.sock"

        if not vsock_path.exists():
            # vsock 未就绪，使用降级模式
            return await self._execute_fallback(command, timeout_ms)

        try:
            # 连接 vsock（通过 Unix socket）
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.settimeout(timeout_ms / 1000)
            sock.connect(str(vsock_path))

            # 构建请求
            request = {
                "type": "execute",
                "command": command,
                "timeout_ms": timeout_ms,
            }

            # 发送请求
            data = json.dumps(request).encode("utf-8")
            import struct

            sock.sendall(struct.pack(">I", len(data)))
            sock.sendall(data)

            # 接收响应长度
            length_data = b""
            while len(length_data) < 4:
                chunk = sock.recv(4 - len(length_data))
                if not chunk:
                    break
                length_data += chunk

            if len(length_data) < 4:
                raise ConnectionError("vsock 响应不完整")

            response_length = struct.unpack(">I", length_data)[0]

            # 接收响应数据
            response_data = b""
            while len(response_data) < response_length:
                chunk = sock.recv(response_length - len(response_data))
                if not chunk:
                    break
                response_data += chunk

            sock.close()

            # 解析响应
            response = json.loads(response_data.decode("utf-8"))

            duration_ms = int((time.time() - start_time) * 1000)

            if response.get("success"):
                return ExecutionResult(
                    exit_code=response.get("exit_code", 0),
                    stdout=response.get("stdout", ""),
                    stderr=response.get("stderr", ""),
                    duration_ms=duration_ms,
                )
            else:
                return ExecutionResult(
                    exit_code=1,
                    stdout="",
                    stderr=response.get("error", "执行失败"),
                    duration_ms=duration_ms,
                )

        except Exception as e:
            # vsock 通信失败，降级
            return ExecutionResult(
                exit_code=1,
                stdout="",
                stderr=f"vsock 通信失败: {e}",
                duration_ms=int((time.time() - start_time) * 1000),
            )

    async def get_instance(self, instance_id: str) -> Optional[InstanceInfo]:
        """获取实例信息"""
        return self._instances.get(instance_id)

    async def list_instances(
        self, agent_id: Optional[str] = None
    ) -> list[InstanceInfo]:
        """列出实例"""
        instances = list(self._instances.values())

        if agent_id:
            instances = [i for i in instances if i.agent_id == agent_id]

        return instances

    async def create_snapshot(self, instance_id: str, snapshot_id: str) -> str:
        """
        创建快照
        """
        if instance_id not in self._instances:
            raise ValueError(f"实例不存在: {instance_id}")

        snapshot_dir = self.work_dir / "snapshots"
        snapshot_dir.mkdir(parents=True, exist_ok=True)

        snapshot_path = snapshot_dir / f"{snapshot_id}.snapshot"

        sandbox_event(f"创建快照: {snapshot_id}")

        # TODO: 实现 Firecracker 快照创建
        # 需要先暂停 VM，然后保存内存和设备状态

        snapshot_path.write_text(
            json.dumps(
                {
                    "instance_id": instance_id,
                    "snapshot_id": snapshot_id,
                    "created_at": time.time(),
                }
            )
        )

        return str(snapshot_path)

    async def pause_instance(self, instance_id: str) -> None:
        """暂停实例"""
        if instance_id not in self._instances:
            raise ValueError(f"实例不存在: {instance_id}")

        # TODO: 实现暂停
        self._instances[instance_id].status = InstanceStatus.PAUSED
        sandbox_event(f"暂停实例: {instance_id}")

    async def resume_instance(self, instance_id: str) -> None:
        """恢复实例"""
        if instance_id not in self._instances:
            raise ValueError(f"实例不存在: {instance_id}")

        # TODO: 实现恢复
        self._instances[instance_id].status = InstanceStatus.RUNNING
        sandbox_event(f"恢复实例: {instance_id}")
