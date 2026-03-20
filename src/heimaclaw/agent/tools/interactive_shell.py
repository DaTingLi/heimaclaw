"""
交互式 Shell 工具 - 支持 PTY 和交互式命令

使用 pexpect 处理交互式命令（如 Claude CLI、Gemini CLI），
当命令需要用户输入（如 [y/N] 确认）时，自动向 LLM 请求决策。
"""

import asyncio
import os
import re
from typing import Any, Optional, Callable

import pexpect

# 交互式命令模式（需要 PTY）
INTERACTIVE_PATTERNS = [
    "claude",
    "gemini",
    "python",
    "bash",
    "ssh",
    "ftp",
    "vim",
    "nano",
    "emacs",
    "top",
    "htop",
    "交互",
    "confirm",
    "Proceed?",
    "[y/N]",
    "[Y/n]",
    "yes/no",
]

# 危险命令（安全加固）
DANGEROUS_PATTERNS = [
    r"\brm\s+-[rf]{1,2}\s+/",  # rm -rf /
    r"\bdd\s+if=",  # dd 命令
    r"\bmkfs\b",  # 格式化
    r"\bshutdown\b",  # 关机
    r"\breboot\b",  # 重启
    r":\(\)\s*\{.*\};:",  # fork bomb
    r">\s*/dev/sd[a-z]",  # 直接写设备
    r"chmod\s+777\s+/etc",  # 危险权限
]


class InteractiveShell:
    """
    交互式 Shell 工具
    
    使用 PTY 处理交互式命令，支持：
    - 实时输出流
    - 自动确认（如 [y/N]）
    - 超时管理
    - 安全检查
    """
    
    def __init__(
        self,
        on_output: Optional[Callable[[str], None]] = None,
        on_confirm: Optional[Callable[[str], str]] = None,
    ):
        """
        Args:
            on_output: 输出回调（实时）
            on_confirm: 确认请求回调，返回 'y' 或 'n'
        """
        self.on_output = on_output
        self.on_confirm = on_confirm or (lambda prompt: "y")
        self._running = False
    
    def _is_dangerous(self, command: str) -> bool:
        """检查危险命令"""
        for pattern in DANGEROUS_PATTERNS:
            if re.search(pattern, command, re.IGNORECASE):
                return True
        return False
    
    def _is_interactive(self, command: str) -> bool:
        """检查是否交互式命令"""
        cmd_lower = command.lower().split()[0] if command else ""
        for pattern in INTERACTIVE_PATTERNS:
            if pattern.lower() in cmd_lower:
                return True
        return False
    
    async def execute(
        self,
        command: str,
        timeout: int = 120,
        cwd: str = "/tmp",
        auto_confirm: bool = True,
    ) -> dict[str, Any]:
        """
        执行命令
        
        Args:
            command: 命令
            timeout: 超时（秒）
            cwd: 工作目录
            auto_confirm: 是否自动确认
        """
        # 安全检查
        if self._is_dangerous(command):
            return {
                "success": False,
                "error": f"危险命令被拒绝: {command[:50]}...",
                "output": "",
                "exit_code": -1,
            }
        
        # 非交互式命令，使用简单方式
        if not self._is_interactive(command):
            return await self._execute_simple(command, timeout, cwd)
        
        # 交互式命令，使用 PTY
        return await self._execute_pty(command, timeout, cwd, auto_confirm)
    
    async def _execute_simple(
        self, command: str, timeout: int, cwd: str
    ) -> dict[str, Any]:
        """简单执行（非交互式）"""
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )
            
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
            
            output = stdout.decode("utf-8", errors="replace")
            error = stderr.decode("utf-8", errors="replace")
            
            return {
                "success": proc.returncode == 0,
                "output": output,
                "error": error,
                "exit_code": proc.returncode,
            }
        except asyncio.TimeoutError:
            return {
                "success": False,
                "error": f"命令执行超时 ({timeout}秒)",
                "output": "",
                "exit_code": -1,
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "output": "",
                "exit_code": -1,
            }
    
    async def _execute_pty(
        self,
        command: str,
        timeout: int,
        cwd: str,
        auto_confirm: bool,
    ) -> dict[str, Any]:
        """使用 PTY 执行交互式命令"""
        output_parts = []
        
        def output_callback(data: str):
            """实时输出回调"""
            output_parts.append(data)
            if self.on_output:
                self.on_output(data)
        
        try:
            # 在线程池中执行 pexpect（避免阻塞事件循环）
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                self._pty_worker,
                command,
                timeout,
                cwd,
                auto_confirm,
                output_callback,
            )
            return result
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "output": "".join(output_parts),
                "exit_code": -1,
            }
    
    def _pty_worker(
        self,
        command: str,
        timeout: int,
        cwd: str,
        auto_confirm: bool,
        output_callback,
    ) -> dict[str, Any]:
        """PTY 工作线程（同步执行）"""
        output_parts = []
        
        try:
            # 启动 pexpect
            child = pexpect.spawn(
                "/bin/bash",
                ["-c", command],
                cwd=cwd,
                timeout=timeout,
                encoding="utf-8",
                echo=True,
            )
            
            # 设置 PTY
            import pty
            import os
            master_fd, slave_fd = pty.openpty()
            child.setwinsize(24, 80)
            
            self._running = True
            output = ""
            
            # 读取输出
            while self._running:
                try:
                    # 使用超时读取
                    child.expect("\n", timeout=2)
                    line = child.before or ""
                    output += line + "\n"
                    output_callback(line)
                except pexpect.TIMEOUT:
                    # 检查是否需要确认
                    if auto_confirm and any(p in output for p in ["[y/N]", "[Y/n]", "Proceed?", "yes/no"]):
                        child.sendline("y")
                        output_callback("\n[自动确认: y]\n")
                    else:
                        # 超时，发送空行
                        child.sendline("")
                except pexpect.EOF:
                    break
            
            output += child.before or ""
            output_callback(child.before or "")
            
            child.close()
            return {
                "success": child.exitstatus == 0,
                "output": output,
                "error": "",
                "exit_code": child.exitstatus or 0,
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "output": "".join(output_parts),
                "exit_code": -1,
            }
    
    def stop(self):
        """停止执行"""
        self._running = False
