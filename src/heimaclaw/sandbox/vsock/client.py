"""
vsock 客户端

在宿主机上运行，与 microVM 内的 vsock 服务端通信。
"""

import json
import socket
import struct
from typing import Any, Optional


class VsockClient:
    """
    vsock 客户端

    连接到 microVM 内的 vsock 服务端，发送命令并接收响应。
    """

    # vsock 地址族
    AF_VSOCK = 40

    # 宿主机 CID
    VMADDR_CID_HOST = 2

    # 默认超时（秒）
    DEFAULT_TIMEOUT = 30

    def __init__(
        self,
        cid: int,
        port: int,
        timeout: int = DEFAULT_TIMEOUT,
    ):
        """
        初始化 vsock 客户端

        参数:
            cid: microVM 的 Context ID
            port: vsock 端口号
            timeout: 超时时间（秒）
        """
        self.cid = cid
        self.port = port
        self.timeout = timeout
        self._socket: Optional[socket.socket] = None

    def connect(self) -> None:
        """建立 vsock 连接"""
        if self._socket is not None:
            return

        try:
            self._socket = socket.socket(self.AF_VSOCK, socket.SOCK_STREAM)
            self._socket.settimeout(self.timeout)
            self._socket.connect((self.cid, self.port))
        except Exception as e:
            self._socket = None
            raise ConnectionError(
                f"vsock 连接失败: cid={self.cid}, port={self.port}, error={e}"
            )

    def disconnect(self) -> None:
        """断开 vsock 连接"""
        if self._socket:
            try:
                self._socket.close()
            except Exception:
                pass
            self._socket = None

    def send_command(
        self,
        command: str,
        parameters: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """
        发送命令到 microVM

        参数:
            command: 命令名称
            parameters: 命令参数

        返回:
            响应数据
        """
        if self._socket is None:
            self.connect()

        # 构建请求
        request = {
            "command": command,
            "parameters": parameters or {},
        }

        # 序列化
        data = json.dumps(request).encode("utf-8")

        # 发送长度前缀
        length = len(data)
        self._socket.sendall(struct.pack(">I", length))

        # 发送数据
        self._socket.sendall(data)

        # 接收响应长度
        length_data = self._recv_exact(4)
        response_length = struct.unpack(">I", length_data)[0]

        # 接收响应数据
        response_data = self._recv_exact(response_length)

        # 解析响应
        response = json.loads(response_data.decode("utf-8"))

        return response

    def _recv_exact(self, length: int) -> bytes:
        """精确接收指定长度的数据"""
        data = b""
        while len(data) < length:
            chunk = self._socket.recv(length - len(data))
            if not chunk:
                raise ConnectionError("vsock 连接已关闭")
            data += chunk
        return data

    def __enter__(self):
        """上下文管理器入口"""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器退出"""
        self.disconnect()
        return False


class VsockCommand:
    """
    vsock 命令构建器

    提供常用的命令构建方法。
    """

    @staticmethod
    def execute(
        command: str,
        cwd: Optional[str] = None,
        env: Optional[dict[str, str]] = None,
        timeout_ms: int = 30000,
    ) -> dict[str, Any]:
        """
        构建命令执行请求

        参数:
            command: Shell 命令
            cwd: 工作目录
            env: 环境变量
            timeout_ms: 超时时间（毫秒）

        返回:
            命令请求字典
        """
        return {
            "type": "execute",
            "command": command,
            "cwd": cwd,
            "env": env,
            "timeout_ms": timeout_ms,
        }

    @staticmethod
    def call_tool(
        tool_name: str,
        parameters: dict[str, Any],
    ) -> dict[str, Any]:
        """
        构建工具调用请求

        参数:
            tool_name: 工具名称
            parameters: 工具参数

        返回:
            工具调用请求字典
        """
        return {
            "type": "call_tool",
            "tool_name": tool_name,
            "parameters": parameters,
        }

    @staticmethod
    def health_check() -> dict[str, Any]:
        """
        构建健康检查请求

        返回:
            健康检查请求字典
        """
        return {
            "type": "health_check",
        }

    @staticmethod
    def get_info() -> dict[str, Any]:
        """
        构建信息查询请求

        返回:
            信息查询请求字典
        """
        return {
            "type": "get_info",
        }
