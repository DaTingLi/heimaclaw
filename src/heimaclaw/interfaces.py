"""
模块接口契约定义

定义 HeiMaClaw 核心接口，所有模块必须遵循这些接口。
"""

from enum import Enum
from typing import Any, Optional, Protocol

from pydantic import BaseModel, Field

# ==================== 枚举类型 ====================


class ChannelType(str, Enum):
    """渠道类型枚举"""

    FEISHU = "feishu"
    WECOM = "wecom"


class SandboxBackend(str, Enum):
    """沙箱后端类型枚举"""

    FIRECRACKER = "firecracker"
    DOCKER = "docker"
    PROCESS = "process"  # 降级模式，仅用于开发


class AgentStatus(str, Enum):
    """Agent 状态枚举"""

    CREATING = "creating"
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"


class SessionStatus(str, Enum):
    """会话状态枚举"""

    ACTIVE = "active"
    IDLE = "idle"
    CLOSED = "closed"


# ==================== 数据模型 ====================


class AgentConfig(BaseModel):
    """Agent 配置模型"""

    name: str = Field(..., description="Agent 名称")
    description: str = Field(default="", description="Agent 描述")
    channel: ChannelType = Field(..., description="渠道类型")
    enabled: bool = Field(default=True, description="是否启用")
    model_provider: str = Field(default="openai", description="模型提供商")
    model_name: str = Field(default="gpt-4", description="模型名称")
    sandbox_enabled: bool = Field(default=True, description="是否启用沙箱")
    sandbox_memory_mb: int = Field(default=128, description="沙箱内存")
    sandbox_cpu_count: int = Field(default=1, description="沙箱 CPU 核心数")
    context_mode: str = Field(
        default="minimal",
        description="上下文模式: full=完整历史, compact=摘要, minimal=仅当前",
    )


class SessionContext(BaseModel):
    """会话上下文模型"""

    session_id: str = Field(..., description="会话 ID")
    agent_id: str = Field(..., description="Agent ID")
    channel: ChannelType = Field(..., description="渠道类型")
    user_id: str = Field(..., description="用户 ID")
    status: SessionStatus = Field(default=SessionStatus.ACTIVE, description="会话状态")
    metadata: dict[str, Any] = Field(default_factory=dict, description="元数据")


class Message(BaseModel):
    """消息模型"""

    message_id: str = Field(..., description="消息 ID")
    session_id: str = Field(..., description="会话 ID")
    role: str = Field(..., description="角色: user / assistant / system")
    content: str = Field(..., description="消息内容")
    timestamp: float = Field(..., description="时间戳")


class ToolDefinition(BaseModel):
    """工具定义模型"""

    name: str = Field(..., description="工具名称")
    description: str = Field(..., description="工具描述")
    parameters: dict[str, Any] = Field(default_factory=dict, description="参数定义")


class ToolResult(BaseModel):
    """工具执行结果模型"""

    tool_name: str = Field(..., description="工具名称")
    success: bool = Field(..., description="是否成功")
    result: Any = Field(..., description="执行结果")
    error: Optional[str] = Field(default=None, description="错误信息")


# ==================== 接口定义 ====================


class ConfigProvider(Protocol):
    """配置提供者接口"""

    def load(self) -> dict[str, Any]:
        """加载配置"""
        ...

    def get(self, key: str, default: Any = None) -> Any:
        """获取配置项"""
        ...

    def set(self, key: str, value: Any) -> None:
        """设置配置项"""
        ...

    def save(self) -> None:
        """保存配置"""
        ...


class SandboxBackendProtocol(Protocol):
    """沙箱后端接口"""

    async def create_instance(self, agent_id: str, config: AgentConfig) -> str:
        """
        创建沙箱实例

        参数:
            agent_id: Agent ID
            config: Agent 配置

        返回:
            沙箱实例 ID
        """
        ...

    async def destroy_instance(self, instance_id: str) -> None:
        """
        销毁沙箱实例

        参数:
            instance_id: 沙箱实例 ID
        """
        ...

    async def execute(
        self,
        instance_id: str,
        command: str,
        timeout_ms: int = 30000,
    ) -> tuple[int, str, str]:
        """
        在沙箱中执行命令

        参数:
            instance_id: 沙箱实例 ID
            command: 要执行的命令
            timeout_ms: 超时时间（毫秒）

        返回:
            (退出码, 标准输出, 标准错误)
        """
        ...

    async def get_status(self, instance_id: str) -> dict[str, Any]:
        """
        获取沙箱状态

        参数:
            instance_id: 沙箱实例 ID

        返回:
            状态信息字典
        """
        ...


class ChannelAdapter(Protocol):
    """渠道适配器接口"""

    async def verify_webhook(self, request: Any) -> bool:
        """
        验证 Webhook 请求

        参数:
            request: HTTP 请求对象

        返回:
            是否验证通过
        """
        ...

    async def parse_message(self, request: Any) -> Message:
        """
        解析消息

        参数:
            request: HTTP 请求对象

        返回:
            解析后的消息对象
        """
        ...

    async def send_message(
        self,
        session: SessionContext,
        content: str,
    ) -> bool:
        """
        发送消息

        参数:
            session: 会话上下文
            content: 消息内容

        返回:
            是否发送成功
        """
        ...


class SessionStore(Protocol):
    """会话存储接口"""

    async def create(self, session: SessionContext) -> None:
        """创建会话"""
        ...

    async def get(self, session_id: str) -> Optional[SessionContext]:
        """获取会话"""
        ...

    async def update(self, session: SessionContext) -> None:
        """更新会话"""
        ...

    async def delete(self, session_id: str) -> None:
        """删除会话"""
        ...

    async def list_active(self, agent_id: Optional[str] = None) -> list[SessionContext]:
        """列出活跃会话"""
        ...


class ToolRegistry(Protocol):
    """工具注册表接口"""

    def register(self, tool: ToolDefinition, handler: Any) -> None:
        """注册工具"""
        ...

    def unregister(self, name: str) -> None:
        """注销工具"""
        ...

    def get(self, name: str) -> Optional[tuple[ToolDefinition, Any]]:
        """获取工具"""
        ...

    def list_all(self) -> list[ToolDefinition]:
        """列出所有工具"""
        ...


class AgentRunner(Protocol):
    """Agent 运行器接口"""

    async def start(self, agent_id: str) -> None:
        """启动 Agent"""
        ...

    async def stop(self, agent_id: str) -> None:
        """停止 Agent"""
        ...

    async def process_message(
        self,
        agent_id: str,
        message: Message,
    ) -> Message:
        """
        处理消息

        参数:
            agent_id: Agent ID
            message: 输入消息

        返回:
            响应消息
        """
        ...

    async def get_status(self, agent_id: str) -> AgentStatus:
        """获取 Agent 状态"""
        ...
