"""
vsock 服务端

在 microVM 内运行，接收宿主机的命令请求并执行。

这个服务端需要被打包到 rootfs 中，随 microVM 启动时运行。
"""

import json
import socket
import struct
import subprocess
import threading
from typing import Callable, Optional

from heimaclaw.console import error, info


class VsockServer:
    """
    vsock 服务端

    在 microVM 内运行，监听来自宿主机的连接，执行命令并返回结果。
    """

    # vsock 地址族
    AF_VSOCK = 40

    # microVM CID（任意地址）
    VMADDR_CID_ANY = -1

    # 默认端口
    DEFAULT_PORT = 1234

    # 最大连接数
    MAX_CONNECTIONS = 10

    def __init__(
        self,
        port: int = DEFAULT_PORT,
        handler: Optional[Callable[[dict], dict]] = None,
    ):
        """
        初始化 vsock 服务端

        参数:
            port: 监听端口
            handler: 命令处理函数
        """
        self.port = port
        self.handler = handler or self._default_handler
        self._socket: Optional[socket.socket] = None
        self._running = False
        self._threads: list[threading.Thread] = []

    def start(self) -> None:
        """启动 vsock 服务端"""
        if self._running:
            return

        try:
            self._socket = socket.socket(self.AF_VSOCK, socket.SOCK_STREAM)
            self._socket.bind((self.VMADDR_CID_ANY, self.port))
            self._socket.listen(self.MAX_CONNECTIONS)
            self._running = True

            info(f"vsock 服务端启动: port={self.port}")

            while self._running:
                try:
                    conn, addr = self._socket.accept()
                    thread = threading.Thread(
                        target=self._handle_connection, args=(conn, addr)
                    )
                    thread.daemon = True
                    thread.start()
                    self._threads.append(thread)
                except Exception as e:
                    if self._running:
                        error(f"接受连接失败: {e}")

        except Exception as e:
            error(f"vsock 服务端启动失败: {e}")
            raise

    def stop(self) -> None:
        """停止 vsock 服务端"""
        self._running = False

        if self._socket:
            try:
                self._socket.close()
            except Exception:
                pass
            self._socket = None

        info("vsock 服务端已停止")

    def _handle_connection(
        self,
        conn: socket.socket,
        addr: tuple,
    ) -> None:
        """
        处理单个连接

        参数:
            conn: 连接 socket
            addr: 客户端地址
        """
        try:
            while True:
                # 接收请求长度
                length_data = self._recv_exact(conn, 4)
                if not length_data:
                    break

                length = struct.unpack(">I", length_data)[0]

                # 接收请求数据
                data = self._recv_exact(conn, length)
                if not data:
                    break

                # 解析请求
                request = json.loads(data.decode("utf-8"))

                # 处理请求
                response = self.handler(request)

                # 发送响应
                response_data = json.dumps(response).encode("utf-8")
                conn.sendall(struct.pack(">I", len(response_data)))
                conn.sendall(response_data)

        except Exception as e:
            error(f"处理连接失败: {e}")

        finally:
            conn.close()

    def _recv_exact(self, conn: socket.socket, length: int) -> bytes:
        """精确接收指定长度的数据"""
        data = b""
        while len(data) < length:
            chunk = conn.recv(length - len(data))
            if not chunk:
                return b""
            data += chunk
        return data

    def _default_handler(self, request: dict) -> dict:
        """
        默认命令处理函数

        参数:
            request: 请求字典

        返回:
            响应字典
        """
        request_type = request.get("type")

        if request_type == "execute":
            return self._handle_execute(request)
        elif request_type == "health_check":
            return {"status": "healthy"}
        elif request_type == "get_info":
            return self._handle_get_info()
        else:
            return {
                "success": False,
                "error": f"未知命令类型: {request_type}",
            }

    def _handle_execute(self, request: dict) -> dict:
        """
        处理命令执行请求

        参数:
            request: 请求字典

        返回:
            执行结果
        """
        command = request.get("command")
        cwd = request.get("cwd")
        env = request.get("env")
        timeout_ms = request.get("timeout_ms", 30000)

        if not command:
            return {
                "success": False,
                "error": "缺少 command 参数",
            }

        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                cwd=cwd,
                env=env,
                timeout=timeout_ms / 1000,
            )

            return {
                "success": True,
                "exit_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": "命令执行超时",
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    def _handle_get_info(self) -> dict:
        """
        处理信息查询请求

        返回:
            microVM 信息
        """
        import platform

        return {
            "success": True,
            "system": platform.system(),
            "node": platform.node(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
        }


def main():
    """vsock 服务端入口函数"""
    import argparse

    parser = argparse.ArgumentParser(description="HeiMaClaw vsock 服务端")
    parser.add_argument(
        "--port",
        type=int,
        default=VsockServer.DEFAULT_PORT,
        help="vsock 监听端口",
    )

    args = parser.parse_args()

    server = VsockServer(port=args.port)

    try:
        server.start()
    except KeyboardInterrupt:
        server.stop()


if __name__ == "__main__":
    main()
