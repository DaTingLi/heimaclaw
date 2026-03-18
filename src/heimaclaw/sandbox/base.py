"""
沙箱后端基类

定义沙箱后端的通用接口和抽象实现。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class InstanceStatus(str, Enum):
    """沙箱实例状态"""

    CREATING = "creating"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class InstanceInfo:
    """沙箱实例信息"""

    instance_id: str
    agent_id: str
    status: InstanceStatus
    created_at: float
    memory_mb: int = 128
    cpu_count: int = 1
    vsock_port: int = 0
    metadata: dict[str, Any] = field(default_factory=dict[str, Any])


@dataclass
class ExecutionResult:
    """命令执行结果"""

    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int


class SandboxBackend(ABC):
    """
    沙箱后端抽象基类

    所有沙箱后端（Firecracker、Docker、Process）必须实现此接口。
    """

    @abstractmethod
    async def initialize(self) -> None:
        """
        初始化后端

        检查依赖、准备资源等。
        """
        pass

    @abstractmethod
    async def shutdown(self) -> None:
        """
        关闭后端

        清理所有实例和资源。
        """
        pass

    @abstractmethod
    async def create_instance(
        self,
        agent_id: str,
        memory_mb: int = 128,
        cpu_count: int = 1,
        snapshot_id: Optional[str] = None,
    ) -> InstanceInfo:
        """
        创建沙箱实例

        参数:
            agent_id: Agent ID
            memory_mb: 内存大小（MB）
            cpu_count: CPU 核心数
            snapshot_id: 快照 ID（用于快照恢复）

        返回:
            实例信息
        """
        pass

    @abstractmethod
    async def destroy_instance(self, instance_id: str) -> None:
        """
        销毁沙箱实例

        参数:
            instance_id: 实例 ID
        """
        pass

    @abstractmethod
    async def execute(
        self,
        instance_id: str,
        command: str,
        timeout_ms: int = 30000,
    ) -> ExecutionResult:
        """
        在实例中执行命令

        参数:
            instance_id: 实例 ID
            command: 要执行的命令
            timeout_ms: 超时时间（毫秒）

        返回:
            执行结果
        """
        pass

    @abstractmethod
    async def get_instance(self, instance_id: str) -> Optional[InstanceInfo]:
        """
        获取实例信息

        参数:
            instance_id: 实例 ID

        返回:
            实例信息，不存在则返回 None
        """
        pass

    @abstractmethod
    async def list_instances(
        self, agent_id: Optional[str] = None
    ) -> list[InstanceInfo]:
        """
        列出实例

        参数:
            agent_id: 可选的 Agent ID 过滤

        返回:
            实例列表
        """
        pass

    @abstractmethod
    async def create_snapshot(self, instance_id: str, snapshot_id: str) -> str:
        """
        创建快照

        参数:
            instance_id: 实例 ID
            snapshot_id: 快照 ID

        返回:
            快照路径或标识
        """
        pass

    @abstractmethod
    async def pause_instance(self, instance_id: str) -> None:
        """
        暂停实例

        参数:
            instance_id: 实例 ID
        """
        pass

    @abstractmethod
    async def resume_instance(self, instance_id: str) -> None:
        """
        恢复实例

        参数:
            instance_id: 实例 ID
        """
        pass

    @property
    @abstractmethod
    def backend_type(self) -> str:
        """
        后端类型标识

        返回:
            后端类型字符串（如 "firecracker"、"docker"、"process"）
        """
        pass

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """
        后端是否可用

        返回:
            后端是否可用
        """
        pass
