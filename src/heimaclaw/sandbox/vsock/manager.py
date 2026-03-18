"""
vsock 管理器

管理 vsock 端口分配和连接管理。
"""

from pathlib import Path
from typing import Any

from heimaclaw.console import info


class VsockManager:
    """
    vsock 管理器

    管理 vsock CID 分配和连接。
    """

    # vsock CID 范围
    CID_MIN = 3
    CID_MAX = 65535

    # 默认端口
    DEFAULT_PORT = 1234

    def __init__(self) -> None:
        """初始化 vsock 管理器"""
        self._next_cid = self.CID_MIN
        self._allocated_cids: set[int] = set()

    def allocate_cid(self) -> int:
        """
        分配一个未使用的 CID

        返回:
            CID 值
        """
        while self._next_cid in self._allocated_cids:
            self._next_cid += 1
            if self._next_cid > self.CID_MAX:
                raise RuntimeError("vsock CID 耗尽")

        cid = self._next_cid
        self._allocated_cids.add(cid)
        self._next_cid += 1

        info(f"分配 vsock CID: {cid}")

        return cid

    def release_cid(self, cid: int) -> None:
        """
        释放 CID

        参数:
            cid: 要释放的 CID
        """
        self._allocated_cids.discard(cid)

    @staticmethod
    def check_vsock_support() -> bool:
        """
        检查系统是否支持 vsock

        返回:
            是否支持 vsock
        """
        # 检查 /dev/vhost-vsock
        if Path("/dev/vhost-vsock").exists():
            return True

        # 检查内核模块
        if Path("/sys/module/vhost_vsock").exists():
            return True

        return False

    @staticmethod
    def generate_firecracker_vsock_config(
        cid: int,
        port: int = DEFAULT_PORT,
        uds_path: str = "/tmp/vsock.sock",
    ) -> dict[str, Any]:
        """
        生成 Firecracker vsock 配置

        参数:
            cid: Context ID
            port: 端口号（guest_cid）
            uds_path: Unix socket 路径

        返回:
            vsock 配置字典
        """
        return {
            "vsock_id": "vsock0",
            "guest_cid": cid,
            "uds_path": uds_path,
        }
