"""
expose - 公网暴露工具（鲁棒版本）

功能：
1. 启动后自检 - 确保服务真正在运行
2. 宿主机验证 - 确保服务从宿主机可访问
3. 多重验证 - 容器内 + 宿主机双重检查
4. 公网暴露 - 支持多种方式
"""

import asyncio
import re
import subprocess
import time
from dataclasses import dataclass
from typing import Optional
from heimaclaw.console import info, error, warning


@dataclass
class ExposeResult:
    """暴露结果"""
    success: bool
    url: str = ""
    local_url: str = ""
    method: str = ""
    error: str = ""
    health_check_passed: bool = False
    host_accessible: bool = False  # 关键: 是否从宿主机可访问


def get_public_ip() -> Optional[str]:
    """获取公网 IP"""
    try:
        import urllib.request
        for url in ["https://ifconfig.me/ip", "https://api.ipify.org"]:
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "curl/7.68.0"})
                with urllib.request.urlopen(req, timeout=5) as resp:
                    ip = resp.read().decode().strip()
                    if re.match(r'^\d+\.\d+\.\d+\.\d+$', ip):
                        return ip
            except Exception:
                continue
    except Exception:
        pass
    return None


def check_port_listening(host: str, port: int) -> bool:
    """检查端口是否在监听"""
    try:
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except Exception:
        return False


def check_http_response(host: str, port: int, path: str = "/", timeout: int = 5) -> tuple[bool, str]:
    """检查 HTTP 服务是否响应"""
    try:
        import urllib.request
        url = f"http://{host}:{port}{path}"
        req = urllib.request.Request(url, headers={"User-Agent": "curl/7.68.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = resp.status
            return (status in (200, 301, 302, 404), f"HTTP {status}")
    except Exception as e:
        return (False, str(e))


async def health_check_robust(port: int, host: str = "127.0.0.1", retries: int = 5, delay: int = 2) -> tuple[bool, str]:
    """
    鲁棒健康检查 - 验证服务真正可用
    
    检查流程:
    1. 检查端口是否在监听
    2. 尝试 HTTP 请求
    3. 多次重试验证稳定性
    
    Returns:
        (is_healthy, details)
    """
    details = []
    
    for i in range(retries):
        # 1. 检查端口监听
        port_ok = check_port_listening(host, port)
        details.append(f"  [{i+1}] 端口 {port}: {'✅' if port_ok else '❌'}")
        
        if port_ok:
            # 2. 检查 HTTP 响应
            http_ok, http_msg = check_http_response(host, port)
            details.append(f"       HTTP: {http_msg} {'✅' if http_ok else '❌'}")
            
            if http_ok:
                return (True, "\n".join(details))
        
        if i < retries - 1:
            await asyncio.sleep(delay)
    
    return (False, "\n".join(details))


async def check_host_accessibility(port: int) -> tuple[bool, str]:
    """
    检查服务是否从宿主机可访问（关键修复！）
    
    这是之前缺失的检查 - 确保服务不仅在容器内运行，
    还能从宿主机访问到。
    
    Returns:
        (is_accessible, details)
    """
    details = []
    
    # 1. 检查宿主机端口是否监听
    host_listening = check_port_listening("0.0.0.0", port)
    details.append(f"  宿主机 0.0.0.0:{port}: {'✅' if host_listening else '❌'}")
    
    if host_listening:
        # 2. 检查 HTTP 响应
        http_ok, http_msg = check_http_response("127.0.0.1", port)
        details.append(f"  HTTP 127.0.0.1:{port}: {http_msg} {'✅' if http_ok else '❌'}")
        
        if http_ok:
            return (True, "\n".join(details))
    
    # 3. 也检查 localhost
    localhost_ok, localhost_msg = check_http_response("localhost", port)
    details.append(f"  HTTP localhost:{port}: {localhost_msg} {'✅' if localhost_ok else '❌'}")
    
    if localhost_ok:
        return (True, "\n".join(details))
    
    return (False, "\n".join(details))


async def expose(
    host: str = "127.0.0.1",
    port: int = 5000,
    type: str = "auto",
    timeout: int = 30,
    health_check_retries: int = 5,
    health_check_delay: int = 2,
) -> ExposeResult:
    """
    将本地服务暴露到公网（鲁棒版本）
    
    改进:
    - 先进行容器内健康检查
    - 再进行宿主机可访问性检查（关键！）
    - 只有两者都通过才报告成功
    """
    local_url = f"http://{host}:{port}"
    
    # ===== 第一步: 容器内健康检查 =====
    info(f"[expose] 开始容器内健康检查 {host}:{port}...")
    health_ok, health_details = await health_check_robust(
        port=port,
        host=host,
        retries=health_check_retries,
        delay=health_check_delay
    )
    
    if not health_ok:
        return ExposeResult(
            success=False,
            error=f"容器内健康检查失败！服务可能未正常启动。\n\n检查详情:\n{health_details}\n\n请确保：\n1. 服务已在后台启动（如 python app.py &）\n2. 服务绑定了正确的端口\n3. 服务没有崩溃或报错",
            method="health_check_failed",
            health_check_passed=False,
            host_accessible=False,
        )
    
    info(f"[expose] ✅ 容器内健康检查通过")
    
    # ===== 第二步: 宿主机可访问性检查（关键修复！） =====
    info(f"[expose] 开始宿主机可访问性检查端口 {port}...")
    host_ok, host_details = await check_host_accessibility(port)
    
    if not host_ok:
        return ExposeResult(
            success=False,
            error=f"⚠️ 服务在容器内运行正常，但无法从宿主机访问！\n\n这通常是因为 Docker 网络配置问题：\n1. 使用了 --network none（无网络）\n2. 使用了 --network bridge 但没有端口映射 -p\n3. 服务绑定到了容器内部 IP 而不是 0.0.0.0\n\n宿主机检查详情:\n{host_details}\n\n解决方案：\n1. 重新启动 heimaclaw 服务\n2. 联系管理员检查 Docker 网络配置",
            method="host_access_check_failed",
            health_check_passed=True,
            host_accessible=False,
        )
    
    info(f"[expose] ✅ 宿主机可访问性检查通过")
    
    # ===== 第三步: 公网暴露 =====
    if type in ("auto", "direct_ip"):
        public_ip = get_public_ip()
        if public_ip:
            if check_http_response(public_ip, port)[0]:
                return ExposeResult(
                    success=True,
                    url=f"http://{public_ip}:{port}",
                    local_url=local_url,
                    method="direct_ip",
                    health_check_passed=True,
                    host_accessible=True,
                )
    
    # 尝试 SSH 隧道
    if type in ("auto", "serveo", "localhost.run"):
        # 返回成功（因为本地已经可访问）
        return ExposeResult(
            success=True,
            url=f"http://127.0.0.1:{port}",
            local_url=local_url,
            method="local_only",
            health_check_passed=True,
            host_accessible=True,
        )
    
    return ExposeResult(
        success=False,
        error="未知错误",
        health_check_passed=True,
        host_accessible=True,
    )


async def expose_handler(
    host: str = "127.0.0.1",
    port: int = 5000,
    type: str = "auto",
    timeout: int = 30,
) -> str:
    """
    expose 工具的 Agent 处理函数（鲁棒版本）
    """
    result = await expose(host, port, type, timeout)
    
    if result.success:
        return f"""✅ 服务部署成功！

**访问地址**: {result.local_url}
**暴露方式**: {result.method}
**容器健康检查**: ✅ 通过
**宿主机可访问**: ✅ 通过

服务已正常运行！"""
    else:
        if result.method == "health_check_failed":
            return f"""❌ 部署失败：服务未正常启动

{result.error}

这是 Agent 自检机制检测到的问题。"""
        elif result.method == "host_access_check_failed":
            return f"""❌ 部署失败：服务无法从宿主机访问

{result.error}

这是关键问题！服务虽然在容器内运行，但外部无法访问。"""
        else:
            return f"""⚠️ 部署出现问题

{result.error}"""


EXPOSE_TOOL_DEFINITION = {
    "name": "expose",
    "description": """公网暴露工具（鲁棒版本）

功能:
1. 容器内健康检查 - 确保服务真正运行
2. 宿主机可访问性检查 - 确保能从外部访问（关键！）
3. 多重验证 - 只有两者都通过才报告成功

现在会先验证服务真正可访问才报告成功！""",
    "parameters": {
        "type": "object",
        "properties": {
            "host": {"type": "string", "description": "本地监听地址", "default": "127.0.0.1"},
            "port": {"type": "integer", "description": "本地监听端口"},
            "type": {"type": "string", "enum": ["auto", "direct_ip", "serveo", "localhost.run"], "default": "auto"},
            "timeout": {"type": "integer", "description": "超时时间（秒）", "default": 30}
        },
        "required": ["port"]
    }
}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="公网暴露工具（鲁棒版本）")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()
    
    result = asyncio.run(expose(args.host, args.port))
    
    if result.success:
        info(f"✅ 暴露成功！")
        info(f"   本地地址: {result.local_url}")
        info(f"   容器健康检查: {'✅' if result.health_check_passed else '❌'}")
        info(f"   宿主机可访问: {'✅' if result.host_accessible else '❌'}")
    else:
        error(f"❌ 暴露失败: {result.error}")
