"""
沙箱模块

提供 microVM 沙箱隔离能力，支持 Firecracker 后端。
"""

from heimaclaw.sandbox.base import SandboxBackend
from heimaclaw.sandbox.firecracker import FirecrackerBackend
from heimaclaw.sandbox.pool import WarmPool

__all__ = ["SandboxBackend", "FirecrackerBackend", "WarmPool"]
