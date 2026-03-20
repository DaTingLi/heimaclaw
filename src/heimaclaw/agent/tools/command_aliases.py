"""
Command Aliases - 便捷命令注册

为常用命令提供便捷调用和智能补全

使用场景：
- "帮我用 claude 写一个爬虫" → 自动调用 claude
- "帮我 wget 下载这个文件" → 自动调用 wget
- "用 curl 测试这个 API" → 自动调用 curl
"""

import asyncio
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional


@dataclass
class CommandAlias:
    """命令别名"""
    name: str                           # 命令名
    command: str                        # 实际命令
    description: str                    # 描述
    args_template: str = "{args}"      # 参数模板
    requires_shell: bool = True        # 是否需要 shell


# 预定义便捷命令
BUILTIN_ALIASES = [
    CommandAlias(
        name="claude",
        command="claude",
        description="Claude Code 编程助手 - 直接帮你写代码",
        args_template="-p '{args}'" if '{args}' else "",
    ),
    CommandAlias(
        name="python",
        command="python3",
        description="Python 解释器",
        args_template="{args}",
    ),
    CommandAlias(
        name="gemini",
        command="gemini",
        description="Gemini CLI 助手 - Google AI 编程助手",
        args_template="'{args}'" if '{args}' else "",
    ),
    CommandAlias(
        name="wget",
        command="wget",
        description="下载文件",
        args_template="-O /tmp/downloaded_file {url}",
    ),
    CommandAlias(
        name="curl",
        command="curl",
        description="测试 HTTP 请求",
        args_template="-X GET {url} -H 'Accept: application/json'",
    ),
    CommandAlias(
        name="git",
        command="git",
        description="Git 版本控制",
        args_template="{args}",
    ),
    CommandAlias(
        name="docker",
        command="docker",
        description="Docker 容器管理",
        args_template="{args}",
    ),
    CommandAlias(
        name="npm",
        command="npm",
        description="Node.js 包管理",
        args_template="{args}",
    ),
    CommandAlias(
        name="pip",
        command="pip",
        description="Python 包管理",
        args_template="{args}",
    ),
    CommandAlias(
        name="apt",
        command="apt",
        description="Ubuntu 包管理",
        args_template="{args}",
    ),
]


class CommandExecutor:
    """
    命令执行器
    
    支持：
    - 预定义命令别名
    - 自定义命令别名
    - Shell 命令直接执行
    """
    
    def __init__(self):
        self.aliases: dict[str, CommandAlias] = {
            alias.name: alias for alias in BUILTIN_ALIASES
        }
    
    def register_alias(self, alias: CommandAlias) -> bool:
        """注册自定义命令别名"""
        try:
            self.aliases[alias.name] = alias
            return True
        except Exception:
            return False
    
    def get_alias(self, name: str) -> Optional[CommandAlias]:
        """获取命令别名"""
        return self.aliases.get(name)
    
    def list_aliases(self) -> list[dict]:
        """列出所有命令别名"""
        return [
            {"name": a.name, "command": a.command, "description": a.description}
            for a in self.aliases.values()
        ]
    
    async def execute(
        self,
        command: str,
        args: str = "",
        timeout: int = 120,
        cwd: str = None,
    ) -> dict[str, Any]:
        """
        执行命令
        
        Args:
            command: 命令或别名
            args: 参数
            timeout: 超时时间（秒）
            cwd: 工作目录
        
        Returns:
            {"success": bool, "stdout": str, "stderr": str, "returncode": int}
        """
        # 检查是否是别名
        alias = self.get_alias(command)
        if alias:
            if alias.args_template and args:
                actual_command = f"{alias.command} {alias.args_template.format(args=args, url=args)}"
            else:
                actual_command = f"{alias.command} {args}" if args else alias.command
        else:
            actual_command = f"{command} {args}" if args else command
        
        try:
            result = subprocess.run(
                actual_command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=cwd,
            )
            
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
                "command": actual_command,
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"命令执行超时（{timeout}秒）",
                "returncode": -1,
                "command": actual_command,
            }
        except Exception as e:
            return {
                "success": False,
                "stdout": "",
                "stderr": str(e),
                "returncode": -1,
                "command": actual_command,
            }
    
    async def execute_background(
        self,
        command: str,
        args: str = "",
        log_file: str = "/tmp/command.log",
    ) -> dict[str, Any]:
        """
        后台执行命令
        
        Returns:
            {"success": bool, "pid": int, "command": str}
        """
        alias = self.get_alias(command)
        if alias:
            actual_command = f"{alias.command} {alias.args_template.format(args=args)}"
        else:
            actual_command = f"{command} {args}" if args else command
        
        # 使用 nohup 后台执行
        full_command = f"cd /tmp && nohup {actual_command} > {log_file} 2>&1 &"
        
        try:
            result = subprocess.run(
                full_command,
                shell=True,
                capture_output=True,
                text=True,
            )
            
            # 获取 PID
            pid_result = subprocess.run(
                f"pgrep -f '{actual_command}' | head -1",
                shell=True,
                capture_output=True,
                text=True,
            )
            pid = pid_result.stdout.strip() or "unknown"
            
            return {
                "success": True,
                "pid": pid,
                "command": actual_command,
                "log_file": log_file,
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "command": actual_command,
            }


# 全局实例
_executor: Optional[CommandExecutor] = None

def get_command_executor() -> CommandExecutor:
    """获取命令执行器单例"""
    global _executor
    if _executor is None:
        _executor = CommandExecutor()
    return _executor
