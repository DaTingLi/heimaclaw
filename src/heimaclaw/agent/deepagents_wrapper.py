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
from heimaclaw.agent.docker_deepagents_backend import DockerDeepAgentsBackend
from heimaclaw.console import info, error


class DeepAgentsWrapper:
    """DeepAgents LLM Agent 包装器"""

    def __init__(
        self,
        model_name: str = "glm-5",
        base_url: str = "https://open.bigmodel.cn/api/coding/paas/v4",
        api_key: str = None,
        agent_name: str = "HeimaClaw",
    ):
        self.model_name = model_name
        self.base_url = base_url
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.agent_name = agent_name
        self._agent = None
        self._agent_lock = asyncio.Lock()
        self._init_task = None

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
                backend_type = getattr(registry.sandbox_backend, 'backend_type', 'firecracker')
                if backend_type == 'docker':
                    backend = DockerDeepAgentsBackend(
                        root_dir="/root/heimaclaw_workspace",
                        docker_backend=registry.sandbox_backend,
                        instance_id=registry.sandbox_instance_id,
                        env=os.environ.copy(),
                    )
                    from heimaclaw.console import console
                    console.print("\n[blue bold][Sandbox: Docker] 正在使用 Docker 容器隔离执行[/blue bold]\n")
                else:
                    backend = FirecrackerDeepAgentsBackend(
                        root_dir="/root/heimaclaw_workspace",
                        sandbox_backend=registry.sandbox_backend,
                        instance_id=registry.sandbox_instance_id,
                        env=os.environ.copy(),
                        virtual_mode=False,
                    )
                    from heimaclaw.console import console
                    console.print("\n[blue bold][Sandbox: Firecracker] 正在使用硬件级沙箱隔离执行[/blue bold]\n")
            else:
                from deepagents.backends import LocalShellBackend
                backend = LocalShellBackend(
                    root_dir="./heimaclaw_workspace",
                    env=os.environ.copy(),
                    virtual_mode=True,
                )
                from heimaclaw.console import console
                console.print("\n[magenta bold][Sandbox: Local Process] 正在使用本地子进程执行（无沙箱隔离）[/magenta bold]\n")

            # 根据 agent_name 生成专属 system prompt（使用模板）
            agent_system_prompt = SYSTEM_PROMPT.format(agent_name=self.agent_name)
            self._agent = create_deep_agent(
                model=llm,
                backend=backend,
                system_prompt=agent_system_prompt,
            )
            info(f"[DeepAgentsWrapper] 初始化完成，agent_name={self.agent_name}")

    def _ensure_initialized(self):
        """确保 Agent 已初始化"""
        if self._agent is None:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # Already in async context - just ensure the coroutine runs
                    if not hasattr(self, '_init_task') or self._init_task is None or self._init_task.done():
                        self._init_task = asyncio.ensure_future(self.initialize())
                        # Don't block - let it run in background
                        print("[DeepAgentsWrapper] 初始化已在后台启动", flush=True)
                else:
                    loop.run_until_complete(self.initialize())
            except RuntimeError:
                asyncio.run(self.initialize())
            except Exception as e:
                print(f"[DeepAgentsWrapper] 初始化异常: {e}", flush=True)

    def execute(self, user_message: str, history: list = None) -> str:
        """执行 Agent"""
        import sys
        print(f"[DeepAgentsWrapper.execute] 调用, user_message={user_message[:30]}...", flush=True, file=sys.stderr)
        self._ensure_initialized()
        if self._agent is None:
            print("[DeepAgentsWrapper.execute] _agent still None after _ensure_initialized!", flush=True, file=sys.stderr)
            return "Agent 初始化失败"
        
        # 组装 messages
        messages = []
        if history:
            messages.extend(history)
        
        # 【关键】在用户消息前加强身份约束，防止模型忽略 system prompt
        identity_prefix = f"[重要身份规则：你的名字是 {self.agent_name}，不是 HeimaClaw或其他名字。你必须以你的真实名字自我介绍。]"
        enhanced_message = f"{identity_prefix}\n\n{user_message}"
        
        # 添加当前用户消息
        if user_message:
            messages.append(("human", enhanced_message))
            
        try:
            print(f"[DeepAgentsWrapper.execute] 调用 _agent.invoke, messages长度={len(messages)}", flush=True, file=sys.stderr)
            result = self._agent.invoke(
                {"messages": messages}
            )
            print(f"[DeepAgentsWrapper.execute] invoke完成, result类型={type(result)}, keys={list(result.keys()) if isinstance(result, dict) else 'N/A'}", flush=True, file=sys.stderr)
            # DeepAgents 返回格式可能是 {'messages': [...]} 或 {'output': '...'}
            if isinstance(result, dict):
                if 'output' in result:
                    return result.get('output', '')
                elif 'messages' in result:
                    msgs = result['messages']
                    if msgs and len(msgs) > 0:
                        last_msg = msgs[-1]
                        if hasattr(last_msg, 'content'):
                            return last_msg.content
                        elif isinstance(last_msg, dict):
                            return last_msg.get('content', '')
            return str(result)
        except Exception as e:
            import traceback
            traceback.print_exc()
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

        # 从历史中提取最后一条用户消息，前面的全部作为历史
        last_msg = history[-1]
        user_message = last_msg.get("content", "")
        if isinstance(user_message, list):
            user_message = "\n".join(
                item.get("text", str(item)) if isinstance(item, dict) else str(item)
                for item in user_message
            )

        chat_history = []
        for msg in history[:-1]:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if isinstance(content, list):
                content = "\n".join(
                    item.get("text", str(item)) if isinstance(item, dict) else str(item)
                    for item in content
                )
            
            # Langchain 接收 tuples 作为 message
            if role in ["user", "human"]:
                chat_history.append(("human", content))
            elif role in ["assistant", "ai"]:
                chat_history.append(("ai", content))

        print(f"[DeepAgentsWrapper.run] user_msg={user_message[:50]}...", flush=True, file=sys.stderr)
        return self.execute(user_message, history=chat_history)


__all__ = ["DeepAgentsWrapper"]
