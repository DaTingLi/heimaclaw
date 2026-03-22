"""
配置加载器模块

支持多账号飞书配置：
[channels.feishu]
enabled = true
default = "pm1"

[channels.feishu.accounts.pm1]
app_id = "xxx"
app_secret = "yyy"
name = "产品经理1号"
enabled = true
"""

import heimaclaw.paths as paths
from pathlib import Path
from typing import Optional

import tomli_w
try:
    import tomllib as tomli
except ImportError:
    import tomli

from pydantic import BaseModel, Field

from heimaclaw.console import warning

# ==================== 飞书多账号配置 ====================


class FeishuAccountConfig(BaseModel):
    """单个飞书账号配置"""

    app_id: str = Field(default="", description="App ID")
    app_secret: str = Field(default="", description="App Secret")
    name: str = Field(default="", description="账号名称")
    enabled: bool = Field(default=False, description="是否启用")
    encrypt_key: str = Field(default="", description="加密 Key")
    verification_token: str = Field(default="", description="验证 Token")


class FeishuChannelConfig(BaseModel):
    """飞书渠道配置（多账号）"""

    enabled: bool = Field(default=False, description="是否启用")
    default: str = Field(default="", description="默认账号名称")
    accounts: dict[str, FeishuAccountConfig] = Field(default_factory=dict)

    class Config:
        arbitrary_types_allowed = True

    def get_default_account(self) -> Optional[FeishuAccountConfig]:
        """获取默认账号"""
        if not self.default and self.accounts:
            self.default = next(iter(self.accounts))
        if self.default and self.default in self.accounts:
            return self.accounts[self.default]
        return None

    def get_account(self, name: str) -> Optional[FeishuAccountConfig]:
        """获取指定账号"""
        return self.accounts.get(name)

    def list_enabled_accounts(self) -> list[str]:
        """列出所有已启用的账号"""
        return [name for name, acc in self.accounts.items() if acc.enabled]


# ==================== 其他配置类 ====================


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

    class Config:
        arbitrary_types_allowed = True


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
    memory_mb: int = Field(default=128, description="内存 MB")
    cpu_count: int = Field(default=1, description="CPU 核数")


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


class VisionConfig(BaseModel):
    """全局视觉理解配置"""
    enabled: bool = Field(default=False, description="是否启用全局视觉理解")
    model: str = Field(default="glm-4v", description="视觉模型名称")
    api_key: str = Field(default="", description="API Key")
    base_url: str = Field(
        default="https://open.bigmodel.cn/api/coding/paas/v4",
        description="API Base URL"
    )
    timeout: int = Field(default=60, description="超时时间（秒）")
    max_retries: int = Field(default=3, description="最大重试次数")


class Config(BaseModel):
    """完整配置模型"""

    heimaclaw: AppConfig = Field(default_factory=AppConfig)
    server: ServerConfig = Field(default_factory=ServerConfig)
    sandbox: SandboxConfig = Field(default_factory=SandboxConfig)
    channels: ChannelsConfig = Field(default_factory=ChannelsConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    vision: VisionConfig = Field(default_factory=VisionConfig)

    class Config:
        arbitrary_types_allowed = True


# ==================== 配置加载器 ====================


class ConfigLoader:
    """配置加载器"""

    # 配置路径优先级（安装目录优先，用户覆盖）
    DEFAULT_PATHS = [
        paths.CONFIG_FILE,  # 安装目录（优先）
        Path.home() / ".heimaclaw" / "config.toml",  # 用户目录
        Path(__file__).parent.parent.parent.parent / "config" / "config.toml",  # 项目源码 config/
        Path.cwd() / "config.toml",  # 当前目录
    ]

    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path

    def load(self) -> Config:
        """加载配置"""
        # 查找配置文件
        config_file = self._find_config_file()

        if not config_file or not config_file.exists():
            warning("配置文件不存在，使用默认配置")
            return Config()

        # 解析配置
        try:
            with open(config_file, "rb") as f:
                raw_config = tomli.load(f)
        except Exception as e:
            warning(f"配置文件解析失败: {e}，使用默认配置")
            return Config()

        # 转换为嵌套对象
        return self._parse_config(raw_config)

    def _find_config_file(self) -> Optional[Path]:
        """查找配置文件"""
        if self.config_path:
            return self.config_path

        for path in self.DEFAULT_PATHS:
            if path.exists():
                return path

        return None

    def _parse_config(self, raw: dict) -> Config:
        """解析配置字典"""
        # 解析飞书多账号配置
        feishu_raw = raw.get("channels", {}).get("feishu", {})
        accounts_raw = feishu_raw.get("accounts", {})

        feishu_accounts = {}
        for name, acc_data in accounts_raw.items():
            if isinstance(acc_data, dict):
                feishu_accounts[name] = FeishuAccountConfig(**acc_data)

        feishu_config = FeishuChannelConfig(
            enabled=feishu_raw.get("enabled", False),
            default=feishu_raw.get("default", ""),
            accounts=feishu_accounts,
        )

        # 解析其他渠道
        wecom_raw = raw.get("channels", {}).get("wecom", {})
        wecom_config = WecomChannelConfig(**wecom_raw)

        channels_config = ChannelsConfig(
            feishu=feishu_config,
            wecom=wecom_config,
        )

        # 构建完整配置
        return Config(
            heimaclaw=AppConfig(**raw.get("heimaclaw", {})),
            server=ServerConfig(**raw.get("server", {})),
            sandbox=SandboxConfig(**raw.get("sandbox", {})),
            channels=channels_config,
            logging=LoggingConfig(**raw.get("logging", {})),
            vision=VisionConfig(**raw.get("vision", {})),
        )

    def save(self, config: Config, path: Optional[Path] = None) -> None:
        """保存配置"""
        config_file = path or self.config_path or self.DEFAULT_PATHS[0]
        config_file.parent.mkdir(parents=True, exist_ok=True)

        raw = self._serialize_config(config)

        with open(config_file, "wb") as f:
            tomli_w.dump(raw, f)

    def _serialize_config(self, config: Config) -> dict:
        """序列化配置为字典"""
        result = {
            "heimaclaw": config.heimaclaw.model_dump(),
            "server": config.server.model_dump(),
            "sandbox": config.sandbox.model_dump(),
            "logging": config.logging.model_dump(),
            "channels": {
                "feishu": {
                    "enabled": config.channels.feishu.enabled,
                    "default": config.channels.feishu.default,
                    "accounts": {},
                },
                "wecom": config.channels.wecom.model_dump(),
            },
        }

        # 序列化飞书账号
        for name, acc in config.channels.feishu.accounts.items():
            result["channels"]["feishu"]["accounts"][name] = acc.model_dump()

        return result


# ==================== 全局配置 ====================


_config: Optional[Config] = None


def get_config() -> Config:
    """获取全局配置实例"""
    global _config

    if _config is None:
        loader = ConfigLoader()
        _config = loader.load()

    return _config


def reload_config() -> Config:
    """重新加载配置"""
    global _config
    _config = None
    return get_config()


# ==================== 热重载集成 ====================


_watcher_started = False


def _on_config_file_changed(path: "Path"):
    """配置文件变化时的回调"""
    from heimaclaw.console import info

    global _config
    info(f"配置文件已变更: {path}，重新加载配置...")
    _config = None

    # 重新加载
    loader = ConfigLoader()
    _config = loader.load()
    info("配置已重新加载")


def start_config_watcher():
    """
    启动配置热重载监听器

    自动监听默认配置路径，支持配置文件变更时自动重载。
    """
    global _watcher_started

    if _watcher_started:
        return

    

    from heimaclaw.config.watcher import start_watcher
    from heimaclaw.console import info

    # 监听所有默认配置路径
    watch_paths = [
        paths.CONFIG_DIR,
        Path.home() / ".heimaclaw",
    ]

    # 只监听存在的路径
    existing_paths = [p for p in watch_paths if p.exists()]

    if existing_paths:
        start_watcher(
            watch_paths=existing_paths,
            extensions={".toml", ".yaml", ".yml", ".json"},
            callback=_on_config_file_changed,
        )
        _watcher_started = True
        info(f"配置热重载监听已启动，监听 {len(existing_paths)} 个路径")


def stop_config_watcher():
    """停止配置热重载监听器"""
    global _watcher_started

    if _watcher_started:
        from heimaclaw.config.watcher import stop_watcher
        from heimaclaw.console import info

        stop_watcher()
        _watcher_started = False
        info("配置热重载监听已停止")
