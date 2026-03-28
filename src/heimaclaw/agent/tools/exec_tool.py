"""
Shell 执行工具

允许 Agent 执行系统命令。

集成 Tool Policy:
    - 是什么: 三层执行控制机制
    - 为什么: 安全隔离 + 最小权限 + 可控执行
    - 何时触发: Agent 执行任意命令时自动检查
"""

import asyncio
import os
import re
from pathlib import Path
from typing import Any

# 导入工具策略
from heimaclaw.tools.policy import check_command, PolicyAction, ExecutionLayer


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

    async def execute(
        self, command: str, timeout: int = 30, cwd: str = "/tmp"
    ) -> dict[str, Any]:
        """执行 Shell 命令"""
        
        # ========== Step 1: Tool Policy 检查 ==========
        policy_result = check_command(command)
        
        if policy_result.action == PolicyAction.DENY:
            return {
                "success": False,
                "error": f"[策略拒绝] {policy_result.reason}\n命令: {command[:100]}",
                "output": "",
                "exit_code": -1,
                "policy": str(policy_result),
            }
        
        if policy_result.action == PolicyAction.ELEVATED:
            return {
                "success": False,
                "error": f"[需要 Elevated 权限] {policy_result.reason}\n命令: {command[:100]}\n\n如需执行，请联系管理员配置 Elevated 权限。",
                "output": "",
                "exit_code": -1,
                "policy": str(policy_result),
                "requires_elevated": True,
            }
        
        if policy_result.action == PolicyAction.ASK:
            # 未知工具，打印警告但仍然执行（向后兼容）
            warning(f"[Tool Policy] ⚠️ {policy_result.reason} - 仍尝试执行")
        
        # ========== Step 2: 文件存在性预检 ==========
        pre_check_match = re.match(r'(?:python3?\s+)(.+?\.py)(?:\s|$)', command.strip())
        if pre_check_match:
            script_path = pre_check_match.group(1).strip()
            if not os.path.isabs(script_path):
                script_abs = os.path.join(os.getcwd(), script_path)
            else:
                script_abs = script_path
            
            if not os.path.exists(script_abs):
                err_msg = (
                    "错误：文件不存在 \"" + script_abs + "\"\n\n"
                    "建议：先使用 write_file 工具创建文件，再运行。"
                )
                return {
                    "success": False,
                    "output": err_msg,
                    "exit_code": 127,
                    "error": "FILE_NOT_FOUND",
                }

        # ========== Step 3: 命令执行 ==========
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
                    "policy": str(policy_result),
                }

            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                return {
                    "success": False,
                    "error": f"命令执行超时 ({timeout}秒)",
                    "output": "",
                    "exit_code": -1,
                    "policy": str(policy_result),
                }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "output": "",
                "exit_code": -1,
                "policy": str(policy_result),
            }


async def exec_handler(command: str, timeout: int = 30, cwd: str = "/tmp") -> str:
    """exec 工具的处理函数"""
    from heimaclaw.agent.tools import get_tool_registry
    
    registry = get_tool_registry()
    
    # 优先使用沙箱执行
    if registry.sandbox_backend and registry.sandbox_instance_id:
        try:
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
            
            info(f"[EXEC-SANDBOX] 在沙箱 {registry.sandbox_instance_id} 执行: {command[:100]}...")
            
            if result.exit_code == 0:
                return result.stdout
            else:
                return f"[沙箱错误 {result.exit_code}]\n{result.stderr}\n{result.stdout}"
                
        except Exception as e:
            info(f"[EXEC-SANDBOX] 沙箱执行失败，回退到本地: {e}")
    
    # 本地执行 (Fallback)
    info(f"[EXEC-LOCAL] 执行命令: {command[:200]}")
    
    tool = ExecTool()
    result = await tool.execute(command, timeout, cwd)
    if result["success"]:
        return result["output"]
    else:
        return f"错误: {result['error']}\n{result.get('output', '')}"
