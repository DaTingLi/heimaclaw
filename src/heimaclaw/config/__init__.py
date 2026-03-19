"""
配置模块

提供配置加载、解析、编译、热重载功能
"""

from heimaclaw.config.compiler import ConfigCompiler, create_incremental_compiler
from heimaclaw.config.loader import (
    ConfigLoader,
    get_config,
    reload_config,
    start_config_watcher,
    stop_config_watcher,
)
from heimaclaw.config.markdown_parser import (
    IdentityConfig,
    MarkdownParser,
    MemoryConfig,
    SoulConfig,
    ToolsConfig,
    UserConfig,
)
from heimaclaw.config.watcher import ConfigFileHandler, ConfigWatcher

__all__ = [
    # 配置加载
    "ConfigLoader",
    "get_config",
    "reload_config",
    # Markdown 解析
    "MarkdownParser",
    "SoulConfig",
    "ToolsConfig",
    "IdentityConfig",
    "UserConfig",
    "MemoryConfig",
    # 配置编译
    "ConfigCompiler",
    "create_incremental_compiler",
    # 热重载
    "ConfigWatcher",
    "ConfigFileHandler",
    "start_config_watcher",
    "stop_config_watcher",
]
