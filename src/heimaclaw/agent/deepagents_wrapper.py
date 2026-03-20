"""
DeepAgents Wrapper - 使用真正的 create_deep_agent (异步版本)
"""

import asyncio
import os
from typing import Optional

from langchain_openai import ChatOpenAI

from heimaclaw.console import info, error


# 导入 deepagents
from deepagents import create_deep_agent
from deepagents.backends import LocalShellBackend
from deepagents.backends.protocol import ExecuteResponse


class NonBlockingLocalBackend(LocalShellBackend):
    """
    非阻塞本地后端 - 拦截阻塞型命令并强制后台执行
    
    匹配关键词: claude, gemini, server, npm run, npm start
    自动转为: nohup xxx > ./heimaclaw_workspace/cli_agent.log 2>&1 &
    """
    
    def execute(self, command: str, *, timeout: int | None = None) -> ExecuteResponse:
        info(f"[Backend.execute] 被调用: {command[:80]}...")
        # 需要拦截的阻塞型命令关键词（使用单词边界，避免误匹配文件路径）
        # 例如: "server" 不能匹配 "fruits_server.log"
        block_patterns = [
            r"\bclaude\b",
            r"\bgemini\b",
            r"\bserver\b",
            r"npm\s+run",
            r"npm\s+start",
        ]
        import re
        cmd_lower = command.lower()
        
        is_blocking_cmd = any(re.search(p, cmd_lower) for p in block_patterns)
        # 如果是阻塞命令且没有以 & 结尾（后台运行）
        if is_blocking_cmd and not command.strip().endswith("&"):
            info(f"[Backend拦截] 检测到阻塞型命令，已自动转入后台: {command}")
            safe_command = (
                f"nohup {command} > ./heimaclaw_workspace/cli_agent.log 2>&1 & "
                f"echo '后台任务已启动，日志: ./heimaclaw_workspace/cli_agent.log'"
            )
            return super().execute(safe_command, timeout=timeout)
        
        return super().execute(command, timeout=timeout)


SYSTEM_PROMPT = """你是 HeimaClaw 高级智能助手。

对于**任何**用户需求，你必须：
1. **第一步自动调用 write_todos 工具**，把任务拆解成清晰的 To-Do List（带状态）。
2. 根据需要**自主生成任意数量的 subagent**（名字、职责你自己决定）。
3. 所有文件操作严格限制在 ./heimaclaw_workspace 目录内。
4. 最后用中文完整总结过程和结果。
5. **claude 和 gemini 等 AI CLI 工具会被自动后台化执行**，你只需要调用它们，结果会写入日志文件。

使用中文思考和回复。"""


class DeepAgentsWrapper:
    """
    DeepAgents 封装器 (异步版本)
    
    - 使用 ainvoke() 替代 invoke()，避免阻塞事件循环
    - 添加超时管理 (300秒)
    - 使用 NonBlockingLocalBackend 拦截阻塞命令
    """
    
    def __init__(self, base_url: str, api_key: str, model_name: str = "glm-5"):
        self.base_url = base_url
        self.api_key = api_key
        self.model_name = model_name
        self._agent = None
    
    async def initialize(self):
        """初始化 DeepAgents"""
        if self._agent is not None:
            return
        
        try:
            llm = ChatOpenAI(
                model=self.model_name,
                base_url=self.base_url,
                api_key=self.api_key,
                temperature=0.7,
                max_tokens=8192,
            )
            
            backend = NonBlockingLocalBackend(
                root_dir="./heimaclaw_workspace",
                env=os.environ.copy(),
                virtual_mode=True,
            )
            
            self._agent = create_deep_agent(
                model=llm,
                backend=backend,
                system_prompt=SYSTEM_PROMPT,
            )
            
            info("[DeepAgentsWrapper] 初始化完成 (async)")
            
        except Exception as e:
            error(f"[DeepAgentsWrapper] 初始化失败: {e}")
            raise
    
    async def run(self, messages: list[dict], timeout: int = 300) -> str:
        """
        运行 agent (异步 + 超时)
        
        Args:
            messages: 完整消息历史
            timeout: 超时秒数 (默认300秒)
        """
        if self._agent is None:
            await self.initialize()
        
        try:
            last_user_msg = ""
            for msg in reversed(messages):
                if msg.get("role") == "user":
                    last_user_msg = msg.get("content", "")
                    break
            
            info(f"[DeepAgentsWrapper] 执行: {last_user_msg[:50]}... (历史 {len(messages)} 条, 超时 {timeout}s)")
            
            # 彻底清理消息格式，确保兼容 LangGraph
            import json
            valid_messages = []
            for i, msg in enumerate(messages):
                if not isinstance(msg, dict):
                    continue
                if "role" not in msg:
                    continue
                
                msg = dict(msg)  # 复制，避免修改原数据
                
                # 处理 tool_calls：确保 arguments 是有效 JSON
                if msg.get("tool_calls"):
                    cleaned_tool_calls = []
                    for tc in msg["tool_calls"]:
                        tc = dict(tc) if tc else {}
                        tc_id = tc.get("id")
                        if not tc_id:
                            tc_id = f"tool_{i}_{len(cleaned_tool_calls)}"
                            tc["id"] = tc_id
                        
                        func = tc.get("function", {})
                        if func:
                            func = dict(func)
                            args = func.get("arguments", "{}")
                            # 如果 arguments 不是有效 JSON，替换为 {}
                            if isinstance(args, str):
                                try:
                                    json.loads(args)
                                except (json.JSONDecodeError, TypeError):
                                    args = "{}"
                                    info(f"[DeepAgentsWrapper] 修复消息 {i} 的 tool_call arguments")
                            func["arguments"] = args
                            tc["function"] = func
                        cleaned_tool_calls.append(tc)
                    msg["tool_calls"] = cleaned_tool_calls
                
                # content 不能为 None
                if msg.get("content") is None:
                    msg["content"] = ""
                
                valid_messages.append(msg)
            
            messages = valid_messages
            info(f"[DeepAgentsWrapper] 消息已清理，共 {len(messages)} 条")
            
            # 【关键修复】将耗时的同步 invoke 放入线程池执行，不阻塞主事件循环
            import asyncio
            result = await asyncio.wait_for(
                asyncio.to_thread(self._agent.invoke, {"messages": messages}),
                timeout=timeout
            )
            
            # 调试：打印 result 结构
            info(f"[DeepAgentsWrapper] result keys: {list(result.keys()) if isinstance(result, dict) else type(result)}")
            info(f"[DeepAgentsWrapper] messages count: {len(result.get('messages', [])) if isinstance(result, dict) else 'N/A'}")
            
            final_message = result["messages"][-1].content
            return final_message if final_message else "好的，有什么我可以帮你的吗？"
            
        except asyncio.TimeoutError:
            error(f"[DeepAgentsWrapper] 执行超时 ({timeout}秒)")
            return f"执行超时 ({timeout}秒)，任务过于复杂，请简化请求。"
        except Exception as e:
            import traceback
            error(f"[DeepAgentsWrapper] 执行错误: {e}")
            error(f"[DeepAgentsWrapper] 堆栈: {traceback.format_exc()}")
            return f"执行错误: {str(e)}"
