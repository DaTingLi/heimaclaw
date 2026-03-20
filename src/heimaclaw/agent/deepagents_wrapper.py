"""
DeepAgents Wrapper - 使用真正的 create_deep_agent (异步版本)
"""

import asyncio
import os
from typing import Optional

from langchain_openai import ChatOpenAI

from heimaclaw.console import info, error


SYSTEM_PROMPT = """你是 HeimaClaw 高级智能助手。

对于**任何**用户需求，你必须：
1. **第一步自动调用 write_todos 工具**，把任务拆解成清晰的 To-Do List（带状态）。
2. 根据需要**自主生成任意数量的 subagent**（名字、职责你自己决定）。
3. 所有文件操作严格限制在 ./heimaclaw_workspace 目录内。
4. 最后用中文完整总结过程和结果。

使用中文思考和回复。"""


class DeepAgentsWrapper:
    """
    DeepAgents 封装器 (异步版本)
    
    - 使用 ainvoke() 替代 invoke()，避免阻塞事件循环
    - 添加超时管理 (300秒)
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
            from deepagents import create_deep_agent
            from deepagents.backends import LocalShellBackend
            
            llm = ChatOpenAI(
                model=self.model_name,
                base_url=self.base_url,
                api_key=self.api_key,
                temperature=0.7,
                max_tokens=8192,
            )
            
            backend = LocalShellBackend(
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
            
            # 【终极修复】使用原生的 ainvoke()，这是 LangGraph 支持的标准异步调用
            # 相比于 to_thread(invoke)，ainvoke 能够更好地和 asyncio 框架融合，防止内部协程泄漏或死锁
            import asyncio
            result = await asyncio.wait_for(
                self._agent.ainvoke({"messages": messages}),
                timeout=timeout
            )
            
            final_message = result["messages"][-1].content
            info(f"[DeepAgentsWrapper] 完成: {str(final_message)[:100]}...")
            return final_message
            
        except asyncio.TimeoutError:
            error(f"[DeepAgentsWrapper] 执行超时 ({timeout}s)")
            return f"执行超时 ({timeout}秒)，任务过于复杂，请简化请求。"
        except Exception as e:
            error(f"[DeepAgentsWrapper] 执行失败: {e}")
            return f"执行失败: {e}"
