#!/usr/bin/env python3
"""
vsock 通信测试脚本

测试宿主机与 microVM 的 vsock 通信。
"""

import asyncio
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.heimaclaw.sandbox.vsock import VsockClient, VsockCommand


async def test_vsock_connection(cid: int, port: int = 1234):
    """
    测试 vsock 连接
    
    参数:
        cid: microVM 的 Context ID
        port: vsock 端口
    """
    print(f"测试 vsock 连接: CID={cid}, Port={port}")
    
    try:
        client = VsockClient(cid=cid, port=port)
        client.connect()
        
        print("✓ 连接成功")
        
        # 测试健康检查
        print("\n1. 健康检查...")
        response = client.send_command("health_check", {})
        print(f"   响应: {response}")
        
        # 测试信息查询
        print("\n2. 查询系统信息...")
        response = client.send_command("get_info", {})
        print(f"   响应: {response}")
        
        # 测试命令执行
        print("\n3. 执行命令 'uname -a'...")
        response = client.send_command("execute", {
            "command": "uname -a",
            "timeout_ms": 5000
        })
        print(f"   退出码: {response.get('exit_code')}")
        print(f"   输出: {response.get('stdout')}")
        print(f"   错误: {response.get('stderr')}")
        
        client.disconnect()
        print("\n✓ 测试完成")
        return True
        
    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        return False


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="vsock 通信测试")
    parser.add_argument("--cid", type=int, required=True, help="microVM CID")
    parser.add_argument("--port", type=int, default=1234, help="vsock 端口")
    
    args = parser.parse_args()
    
    success = asyncio.run(test_vsock_connection(args.cid, args.port))
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
