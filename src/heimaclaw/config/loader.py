"""
配置加载器模块

负责从文件系统加载配置并进行验证。
"""

from pathlib import Path
from typing import Any, Optional

import tomli
from pydantic import BaseModel, Field

from heimaclaw.console import warning


class ServerConfig(BaseModel):
    """服务器配置"""

    host: str = Field(default="0.0.0.0", description="监听地址")
    port: int = Field(default=8000, description="监听端口")
    workers: int = Field(default=1, description="工作进程数")


class SandboxConfig(BaseModel):
    """沙箱配置"""

    enabled: bool = Field(default=True, description="是否启用沙箱")
    backend: str = Field(default="firecracker", description="沙箱后端")
    warm_pool_size: int = Field(default=5, description="预热池大小")
    max_instances: int = Field(default=100, description="最大实例数")
    memory_mb: int = Field(default=128, description="单个实例内存")
    cpu_count: int = Field(default=1, description="单个实例 CPU 核心数")


class FeishuChannelConfig(BaseModel):
    """飞书渠道配置"""

    enabled: bool = Field(default=False, description="是否启用")
    app_id: str = Field(default="", description="App ID")
    app_secret: str = Field(default="", description="App Secret")
    encrypt_key: str = Field(default="", description="加密 Key")
    verification_token: str = Field(default="", description="验证 Token")


class WecomChannelConfig(BaseModel):
    """企业微信渠道配置"""

    enabled: bool = Field(default=False, description="是否启用")
    corp_id: str = Field(default="", description="企业 ID")
    agent_id: str = Field(default="", description="应用 Agent ID")
    secret: str = Field(default="", description="应用 Secret")
    token: str = Field(default="", description="Token")
    encoding_aes_key: str = Field(default="", description="EncodingAESKey")


class ChannelsConfig(BaseModel):
    """渠道配置"""

    feishu: FeishuChannelConfig = Field(default_factory=FeishuChannelConfig)
    wecom: WecomChannelConfig = Field(default_factory=WecomChannelConfig)


class LoggingConfig(BaseModel):
    """日志配置"""

    level: str = Field(default="INFO", description="日志级别")
    file_enabled: bool = Field(default=True, description="是否启用文件日志")
    file_path: str = Field(default="logs/heimaclaw.log", description="日志文件路径")
    console_enabled: bool = Field(default=True, description="是否启用控制台日志")


class AppConfig(BaseModel):
    """应用配置"""

    name: str = Field(default="HeiMaClaw", description="应用名称")
    version: str = Field(default="0.1.0", description="版本号")
    environment: str = Field(default="development", description="运行环境")


class Config(BaseModel):
    """完整配置模型"""

    heimaclaw: AppConfig = Field(default_factory=AppConfig)
    server: ServerConfig = Field(default_factory=ServerConfig)
    sandbox: SandboxConfig = Field(default_factory=SandboxConfig)
    channels: ChannelsConfig = Field(default_factory=ChannelsConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)


# 全局配置实例
_config: Optional[Config] = None


class ConfigLoader:
    """
    配置加载器

    负责从文件系统加载配置，支持多路径查找。
    """

    DEFAULT_PATHS = [
        Path("/opt/heimaclaw/config/config.toml"),
        Path.home() / ".heimaclaw" / "config.toml",
        Path.cwd() / "config.toml",
    ]

    def __init__(self, config_path: Optional[Path] = None):
        """
        初始化配置加载器

        参数:
            config_path: 指定配置文件路径，为 None 则自动查找
        """
        self.config_path = config_path
        self._config: Optional[Config] = None

    def load(self) -> Config:
        """
        加载配置

        返回:
            配置对象
        """
        if self._config is not None:
            return self._config

        # 确定配置文件路径
        path = self._find_config_path()

        if path is None:
            warning("未找到配置文件，使用默认配置")
            self._config = Config()
            return self._config

        # 读取并解析配置
        with open(path, "rb") as f:
            data = tomli.load(f)

        self._config = Config(**data)
        return self._config

    def _find_config_path(self) -> Optional[Path]:
        """查找配置文件路径"""
        if self.config_path is not None:
            if self.config_path.exists():
                return self.config_path
            return None

        for path in self.DEFAULT_PATHS:
            if path.exists():
                return path

        return None

    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置项

        参数:
            key: 配置键，支持点分隔，如 "server.port"
            default: 默认值

        返回:
            配置值
        """
        config = self.load()

        keys = key.split(".")
        value: Any = config.model_dump()

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value


def get_config() -> Config:
    """
    获取全局配置实例

    返回:
        配置对象
    """
    global _config

    if _config is None:
        loader = ConfigLoader()
        _config = loader.load()

    return _config


def reload_config() -> Config:
    """
    重新加载配置

    返回:
        新的配置对象
    """
    global _config
    _config = None
    return get_config()
