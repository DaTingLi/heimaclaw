"""
Shell 执行工具

允许 Agent 执行系统命令。
"""

import asyncio
import os
import re
from pathlib import Path
from typing import Any

# 危险命令模式（黑名单）
DANGEROUS_PATTERNS = [
    r"\brm\s+-[rf]{1,2}\s+/",  # rm -rf / 或类似
    r"\bdd\s+if=",  # dd 命令
    r"\bmkfs\b",  # 格式化
    r"\bshutdown\b",  # 关机
    r"\breboot\b",  # 重启
    r":\(\)\s*\{.*\};:",  # fork bomb
]


class ExecTool:
    """Shell 执行工具"""

    def __init__(self):
        self.name = "exec"
        self.description = "执行 Shell 命令并返回输出结果"
        self.parameters = {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "要执行的 Shell 命令"},
                "timeout": {
                    "type": "integer",
                    "description": "超时时间（秒），默认 30",
                    "default": 30,
                },
                "cwd": {"type": "string", "description": "工作目录，默认 /tmp"},
            },
            "required": ["command"],
        }

    def _is_dangerous(self, command: str) -> bool:
        """检查是否是危险命令"""
        for pattern in DANGEROUS_PATTERNS:
            if re.search(pattern, command, re.IGNORECASE):
                return True
        return False

    async def execute(
        self, command: str, timeout: int = 30, cwd: str = "/tmp"
    ) -> dict[str, Any]:
        """执行 Shell 命令"""
        # 安全检查
        if self._is_dangerous(command):
            return {
                "success": False,
                "error": f"危险命令被拒绝: {command[:50]}...",
                "output": "",
                "exit_code": -1,
            }
        
        # 拦截 claude/gemini 等交互式命令，自动后台执行
        cmd_lower = command.lower().strip()
        block_patterns = [r"^claude", r"^gemini"]
        if any(re.search(p, cmd_lower) for p in block_patterns):
            if not command.strip().endswith("--yes") and not command.strip().endswith("&"):
                safe_cmd = f"{command.rstrip()} --yes"
            else:
                safe_cmd = command
            log_file = "./heimaclaw_workspace/cli_agent.log"
            safe_cmd = f"nohup {safe_cmd} > {log_file} 2>&1 &"
            command = safe_cmd

        try:
            work_dir = Path(cwd)
            work_dir.mkdir(parents=True, exist_ok=True)

            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr= asyncio.subprocess.PIPE,
                cwd=str(work_dir),
                env={
                    **os.environ,
                    "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
                },
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=timeout
                )

                output = stdout.decode("utf-8", errors="replace")
                error = stderr.decode("utf-8", errors="replace")

                return {
                    "success": proc.returncode == 0,
                    "output": output,
                    "error": error if proc.returncode != 0 else "",
                    "exit_code": proc.returncode,
                }

            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                return {
                    "success": False,
                    "error": f"命令执行超时 ({timeout}秒)",
                    "output": "",
                    "exit_code": -1,
                }

        except Exception as e:
            return {"success": False, "error": str(e), "output": "", "exit_code": -1}


async def exec_handler(command: str, timeout: int = 30, cwd: str = "/tmp") -> str:
    """exec 工具的处理函数"""
    from heimaclaw.agent.tools import get_tool_registry
    
    registry = get_tool_registry()
    
    # 优先使用沙箱执行
    if registry.sandbox_backend and registry.sandbox_instance_id:
        try:
            # 准备环境变量
            auth_env = {
                k: os.environ[k] 
                for k in ["ANTHROPIC_API_KEY", "GEMINI_API_KEY", "OPENAI_API_KEY"] 
                if k in os.environ
            }
            
            # 通过沙箱执行
            result = await registry.sandbox_backend.execute(
                instance_id=registry.sandbox_instance_id,
                command=command,
                timeout_ms=timeout * 1000,
            )
            
            print(f"[EXEC-SANDBOX] 在沙箱 {registry.sandbox_instance_id} 执行: {command[:100]}...")
            
            if result.exit_code == 0:
                return result.stdout
            else:
                return f"[沙箱错误 {result.exit_code}]\n{result.stderr}\n{result.stdout}"
                
        except Exception as e:
            print(f"[EXEC-SANDBOX] 沙箱执行失败，回退到本地: {e}")
            # Fallback 到本地执行
    
    # 本地执行 (Fallback)
    print(f"[EXEC-LOCAL] 执行命令: {command[:200]}")
    
    tool = ExecTool()
    result = await tool.execute(command, timeout, cwd)
    if result["success"]:
        return result["output"]
    else:
        return f"错误: {result['error']}\n{result['output']}"
