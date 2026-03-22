"""
HeiMaClaw 统一路径常量

所有路径通过此模块获取，确保跨平台兼容。
优先级：环境变量 > 默认路径
"""
import os
import sys
from pathlib import Path

# ==================== 根目录 ====================

def _get_install_root() -> Path:
    """
    获取 HeiMaClaw 安装根目录
    
    优先级：
    1. 环境变量 HEIMACLAW_HOME
    2. Linux: /opt/heimaclaw
    3. macOS: ~/Library/Application Support/heimaclaw
    4. Windows: %APPDATA%/heimaclaw
    5. Fallback: ~/.heimaclaw
    """
    env = os.environ.get("HEIMACLAW_HOME")
    if env:
        return Path(env)
    
    if sys.platform == "linux":
        return Path("/opt/heimaclaw")
    elif sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "heimaclaw"
    elif sys.platform == "win32":
        appdata = os.environ.get("APPDATA", str(Path.home()))
        return Path(appdata) / "heimaclaw"
    else:
        return Path.home() / ".heimaclaw"


def _get_user_home() -> Path:
    """获取用户配置根目录 (~/.heimaclaw)"""
    return Path.home() / ".heimaclaw"


# ==================== 公开常量 ====================

# 安装根目录
INSTALL_ROOT = _get_install_root()

# 用户配置根目录
USER_HOME = _get_user_home()

# --- 配置 ---
CONFIG_DIR = INSTALL_ROOT / "config"
CONFIG_FILE = CONFIG_DIR / "config.toml"
USER_CONFIG_FILE = USER_HOME / "config.toml"

# --- Agent ---
AGENTS_DIR = INSTALL_ROOT / "data" / "agents"
USER_AGENTS_DIR = USER_HOME / "agents"

# --- 沙箱 ---
SANDBOX_DIR = INSTALL_ROOT / "sandboxes"
IMAGES_DIR = INSTALL_ROOT / "images"
ROOTFS_PATH = IMAGES_DIR / "rootfs.ext4"
KERNEL_PATH = IMAGES_DIR / "vmlinux"

# --- 运行时 ---
RUN_DIR = INSTALL_ROOT / "run"
PID_FILE = RUN_DIR / "heimaclaw.pid"
USER_RUN_DIR = USER_HOME / "run"

# --- 日志 ---
LOG_DIR = INSTALL_ROOT / "logs"
LOG_FILE = LOG_DIR / "heimaclaw.log"
USER_LOG_DIR = USER_HOME / "logs"

# --- 会话 ---
SESSION_DIR = Path("/tmp/heimaclaw/sessions")

# --- 临时 ---
TEMP_DIR = Path("/tmp/heimaclaw")


def get_config_paths() -> list[Path]:
    """获取配置文件搜索路径（按优先级排序）"""
    return [
        CONFIG_FILE,           # 安装目录（优先）
        USER_CONFIG_FILE,      # 用户目录
    ]


def get_agents_dirs() -> list[Path]:
    """获取 Agent 配置目录列表"""
    return [
        AGENTS_DIR,            # 安装目录
        USER_AGENTS_DIR,       # 用户目录
    ]


def get_run_dir() -> Path:
    """获取运行时目录（PID 文件等）"""
    if os.access(str(RUN_DIR.parent), os.W_OK):
        return RUN_DIR
    return USER_RUN_DIR


def get_log_dir() -> Path:
    """获取日志目录"""
    if os.access(str(LOG_DIR.parent), os.W_OK):
        return LOG_DIR
    return USER_LOG_DIR
