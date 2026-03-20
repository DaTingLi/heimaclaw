"""
DeepAgents Wrapper - 使用真正的 create_deep_agent

参考 /root/dt/ai_coding/heimaclaw/reference/deepagents_demo/test_deepagents_glm_autonomous.py
"""

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
    DeepAgents 封装器
    
    使用真正的 create_deep_agent + LocalShellBackend
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
            
            # 创建 LLM
            llm = ChatOpenAI(
                model=self.model_name,
                base_url=self.base_url,
                api_key=self.api_key,
                temperature=0.7,
                max_tokens=8192,
            )
            
            # 创建 Backend
            backend = LocalShellBackend(
                root_dir="./heimaclaw_workspace",
                env=os.environ.copy(),
                virtual_mode=True,  # 虚拟模式，不真实执行命令
            )
            
            # 创建 Agent
            self._agent = create_deep_agent(
                model=llm,
                backend=backend,
                system_prompt=SYSTEM_PROMPT,
            )
            
            info("[DeepAgentsWrapper] 初始化完成 (create_deep_agent + LocalShellBackend)")
            
        except Exception as e:
            error(f"[DeepAgentsWrapper] 初始化失败: {e}")
            raise
    
    async def run(self, user_message: str) -> str:
        """运行 agent"""
        if self._agent is None:
            await self.initialize()
        
        try:
            info(f"[DeepAgentsWrapper] 执行: {user_message[:50]}...")
            
            result = self._agent.invoke(
                {"messages": [{"role": "user", "content": user_message}]}
            )
            
            final_message = result["messages"][-1].content
            info(f"[DeepAgentsWrapper] 完成: {str(final_message)[:100]}...")
            return final_message
            
        except Exception as e:
            error(f"[DeepAgentsWrapper] 执行失败: {e}")
            return f"执行失败: {e}"
