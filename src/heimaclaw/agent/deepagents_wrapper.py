"""
DeepAgents 包装器

集成 DeepAgents 框架，提供 LLM Agent 能力。
"""

import asyncio
import os
from typing import Optional

from deepagents import create_deep_agent
from deepagents.backends.protocol import ExecuteResponse
from langchain_openai import ChatOpenAI

from heimaclaw.agent.system_prompt import SYSTEM_PROMPT
from heimaclaw.agent.firecracker_deepagents_backend import FirecrackerDeepAgentsBackend
from heimaclaw.console import info, error


class DeepAgentsWrapper:
    """DeepAgents LLM Agent 包装器"""

    def __init__(
        self,
        model_name: str = "glm-5",
        base_url: str = "https://open.bigmodel.cn/api/coding/paas/v4",
        api_key: str = None,
    ):
        self.model_name = model_name
        self.base_url = base_url
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self._agent = None
        self._agent_lock = asyncio.Lock()

    async def initialize(self):
        """异步初始化 Agent"""
        async with self._agent_lock:
            if self._agent is not None:
                return

            llm = ChatOpenAI(
                model=self.model_name,
                base_url=self.base_url,
                api_key=self.api_key,
                temperature=0.7,
                max_tokens=8192,
            )

            from heimaclaw.agent.tools import get_tool_registry
            registry = get_tool_registry()

            if registry.sandbox_backend and registry.sandbox_instance_id:
                backend = FirecrackerDeepAgentsBackend(
                    root_dir="/root/heimaclaw_workspace",
                    sandbox_backend=registry.sandbox_backend,
                    instance_id=registry.sandbox_instance_id,
                    env=os.environ.copy(),
                    virtual_mode=False,
                )
                info("[DeepAgentsWrapper] 使用 FirecrackerDeepAgentsBackend")
            else:
                from deepagents.backends import LocalShellBackend
                backend = LocalShellBackend(
                    root_dir="./heimaclaw_workspace",
                    env=os.environ.copy(),
                    virtual_mode=True,
                )
                info("[DeepAgentsWrapper] 使用本地后端 (Fallback)")

            self._agent = create_deep_agent(
                model=llm,
                backend=backend,
                system_prompt=SYSTEM_PROMPT,
            )
            info("[DeepAgentsWrapper] 初始化完成")

    def _ensure_initialized(self):
        """确保 Agent 已初始化"""
        if self._agent is None:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    future = asyncio.ensure_future(self.initialize())
                    loop.run_until_complete(future)
                else:
                    loop.run_until_complete(self.initialize())
            except RuntimeError:
                asyncio.run(self.initialize())

    def execute(self, user_message: str, history: list = None) -> str:
        """执行 Agent"""
        self._ensure_initialized()
        history = history or []
        try:
            result = self._agent.invoke(
                {"input": user_message, "chat_history": history}
            )
            return result.get("output", "")
        except Exception as e:
            error(f"[DeepAgentsWrapper] 执行错误: {e}")
            return f"执行错误: {e}"

    def run(self, history: list = None) -> str:
        """运行 Agent（runner.py 调用入口）

        Args:
            history: 消息历史 [{"role": "user", "content": "..."}, ...]
        Returns:
            Agent 响应文本
        """
        import sys
        print(f"[DeepAgentsWrapper.run] 被调用, history长度={len(history) if history else 0}", flush=True, file=sys.stderr)
        
        if not history:
            print("[DeepAgentsWrapper.run] 历史为空，返回空字符串", flush=True, file=sys.stderr)
            return ""

        # 从历史中提取最后一条用户消息
        user_message = ""
        chat_history = []
        for msg in history:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if isinstance(content, list):
                content = "\n".join(
                    item.get("text", str(item)) if isinstance(item, dict) else str(item)
                    for item in content
                )
            if role == "user":
                user_message = content
            elif role == "assistant":
                chat_history.append({"role": "assistant", "content": content})

        print(f"[DeepAgentsWrapper.run] user_msg={user_message[:50]}...", flush=True, file=sys.stderr)
        return self.execute(user_message, history=chat_history)


__all__ = ["DeepAgentsWrapper"]
