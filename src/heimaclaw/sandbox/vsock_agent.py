"""
microVM 内的 vsock Agent

运行在 microVM 内部，作为 vsock 服务端，接收宿主机命令。
"""

import sys

# 添加路径
sys.path.insert(0, "/opt/heimaclaw/lib/python")

from heimaclaw.sandbox.vsock.server import main

if __name__ == "__main__":
    main()
