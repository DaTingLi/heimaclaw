"""
Agent 运行器模块

管理 Agent 的生命周期和执行循环。
"""

import json
from typing import Any, Optional

from heimaclaw.agent.react import ExecutionResult, ReActEngine
from heimaclaw.agent.session import Session, SessionManager
from heimaclaw.agent.tools import ToolRegistry, get_tool_registry
from heimaclaw.console import agent_event, error, info, warning

# 工具模块会在导入时自动注册 exec/read_file/write_file 工具
from heimaclaw.interfaces import (
    AgentConfig,
    AgentStatus,
    ChannelType,
)
from heimaclaw.llm.base import LLMProvider

# LLM 相关导入
from heimaclaw.llm.base import Message as LLMMessage
from heimaclaw.llm.registry import get_llm_registry
from heimaclaw.memory.manager import MemoryManager
from heimaclaw.core.event_bus import EventBus, Event, EventType
from heimaclaw.core.subagent_spawn import SubagentSpawner, SpawnConfig, SpawnResult
from heimaclaw.core.subagent_registry import SubagentRegistry

# 监控导入
from heimaclaw.monitoring.metrics import record_token_usage
from heimaclaw.sandbox.base import SandboxBackend
from heimaclaw.sandbox.firecracker import FirecrackerBackend
from heimaclaw.sandbox.pool import WarmPool


def _register_all_tools():
    """注册所有内置工具到全局注册表"""
    from heimaclaw.agent.tools.exec_tool import exec_handler
    from heimaclaw.agent.tools.read_tool import read_handler
    from heimaclaw.agent.tools.write_tool import write_handler

    registry = get_tool_registry()

    # exec 工具
    registry.register(
        name="exec",
        description="执行 Shell 命令并返回输出结果",
        handler=exec_handler,
        parameters={
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "要执行的命令"},
                "timeout": {
                    "type": "integer",
                    "description": "超时时间(秒)",
                    "default": 30,
                },
                "cwd": {"type": "string", "description": "工作目录", "default": "/tmp"},
            },
            "required": ["command"],
        },
        timeout_ms=60000,
    )

    # read_file 工具
    registry.register(
        name="read_file",
        description="读取文件内容",
        handler=read_handler,
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件路径"},
                "limit": {
                    "type": "integer",
                    "description": "最多读取行数",
                    "default": 0,
                },
            },
            "required": ["path"],
        },
        timeout_ms=10000,
    )

    # write_file 工具
    registry.register(
        name="write_file",
        description="写入内容到文件",
        handler=write_handler,
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件路径"},
                "content": {"type": "string", "description": "内容"},
            },
            "required": ["path", "content"],
        },
        timeout_ms=10000,
    )


class AgentRunner:
    """
    Agent 运行器

    负责单个 Agent 的生命周期管理和消息处理。
    """

    def __init__(
        self,
        agent_id: str,
        config: AgentConfig,
        session_manager: Optional[SessionManager] = None,
        tool_registry: Optional[ToolRegistry] = None,
        sandbox_backend: Optional[SandboxBackend] = None,
        warm_pool: Optional[WarmPool] = None,
        llm_config: Optional[dict[str, Any]] = None,
    ):
        """
        初始化 Agent 运行器

        参数:
            agent_id: Agent ID
            config: Agent 配置
            session_manager: 会话管理器
            tool_registry: 工具注册表
            sandbox_backend: 沙箱后端
            warm_pool: 预热池
            llm_config: LLM 配置（包含 api_key 等）
        """
        self.agent_id = agent_id
        self.config = config

        self.session_manager = session_manager or SessionManager()
        self.tool_registry = tool_registry or get_tool_registry()
        # 注册所有内置工具
        _register_all_tools()
        self.sandbox_backend = sandbox_backend

        self._status = AgentStatus.STOPPED
        self._warm_pool = warm_pool
        self._sandbox_instance_id: Optional[str] = None
        self._active_sessions: dict[str, Session] = {}

        # LLM 配置
        self._llm_config = llm_config or {}
        self._llm_adapter_name: Optional[str] = None
        self._llm_adapter = None

        # 记忆管理器
        self._memory_manager: Optional[MemoryManager] = None

        # 事件总线
        self._event_bus: Optional[EventBus] = None

        # 子 Agent 派生器
        self._subagent_spawner: Optional[SubagentSpawner] = None

        # ReAct 推理引擎
        self._react_engine: Optional[ReActEngine] = None

        # 上下文模式: "full"=完整历史, "compact"=摘要历史, "minimal"=仅当前
        # 强制使用 full 模式启用记忆
        self._context_mode = "full"

    @property
    def status(self) -> AgentStatus:
        """获取 Agent 状态"""
        return self._status

    async def start(self) -> None:
        """
        启动 Agent

        初始化沙箱实例和 LLM，准备接收消息。
        """
        if self._status == AgentStatus.RUNNING:
            return

        agent_event(f"启动 Agent: {self.agent_id}")
        self._status = AgentStatus.CREATING

        try:
            # 初始化沙箱
            if self.config.sandbox_enabled:
                await self._initialize_sandbox()

            # 初始化 LLM
            await self._initialize_llm()

            # 初始化记忆管理器
            if self._memory_manager is None:
                self._memory_manager = MemoryManager(
                    agent_id=self.agent_id,
                    session_id="default",
                    channel="feishu",
                    user_id="default",
                    data_dir=f"/tmp/heimaclaw_memory_{self.agent_id}",
                )

            # 初始化事件总线
            self._event_bus = EventBus(base_dir=f"/tmp/heimaclaw_events_{self.agent_id}")

            # 初始化子 Agent 派生器
            self._subagent_registry = SubagentRegistry(state_dir=f"/tmp/heimaclaw_subagent_{self.agent_id}")
            self._subagent_spawner = SubagentSpawner(
                event_bus=self._event_bus,
                registry=self._subagent_registry,
                agent_runner_factory=self._create_subagent_runner,
            )

            # 初始化 ReAct 推理引擎
            if self._llm_adapter:
                self._react_engine = ReActEngine(
                    tool_registry=self.tool_registry,
                    llm_callable=self._llm_adapter.chat,
                )

            self._status = AgentStatus.RUNNING
            agent_event(f"Agent 已启动: {self.agent_id}")

        except Exception as e:
            self._status = AgentStatus.ERROR
            error(f"Agent 启动失败: {e}")
            raise

    async def stop(self) -> None:
        """
        停止 Agent

        清理沙箱实例，关闭所有会话。
        """
        if self._status == AgentStatus.STOPPED:
            return

        agent_event(f"停止 Agent: {self.agent_id}")

    def _create_subagent_runner(self, **kwargs) -> "AgentRunner":
        """创建子 Agent Runner 的工厂方法"""
        from heimaclaw.agent.runner import AgentRunner
        return AgentRunner(
            agent_id=kwargs.get("agent_id", "subagent"),
            config=self.config,
            llm_config=kwargs.get("llm_config"),
        )

    async def spawn_subagent(
        self,
        task: str,
        session_key: str,
        model: Optional[str] = None,
    ) -> SpawnResult:
        """
        派生子 Agent 执行任务

        Args:
            task: 任务描述
            session_key: 会话 ID
            model: 模型名称（可选）

        Returns:
            SpawnResult
        """
        if not self._subagent_spawner:
            return SpawnResult(status="error", error="SubagentSpawner 未初始化")

        config = SpawnConfig(
            task=task,
            agent_id=self.agent_id,
            model=model,
            mode="run",
            timeout_seconds=300,
        )

        return await self._subagent_spawner.spawn(
            config=config,
            requester_session_key=session_key,
            requester_agent_id=self.agent_id,
        )

        # 销毁沙箱实例
        if self._sandbox_instance_id and self.sandbox_backend:
            await self.sandbox_backend.destroy_instance(self._sandbox_instance_id)
            self._sandbox_instance_id = None

        # 清理会话
        self._active_sessions.clear()

        self._status = AgentStatus.STOPPED
        agent_event(f"Agent 已停止: {self.agent_id}")

    async def process_message(
        self,
        user_id: str,
        channel: ChannelType,
        content: str,
        session_id: Optional[str] = None,
        is_group: bool = False,
    ) -> str:
        """
        处理用户消息

        参数:
            user_id: 用户 ID
            channel: 渠道类型
            content: 消息内容
            session_id: 会话 ID（可选，不提供则创建新会话）
            is_group: 是否群聊（群聊不保持会话历史）

        返回:
            Agent 响应内容
        """
        if self._status != AgentStatus.RUNNING:
            raise RuntimeError(f"Agent 状态异常: {self._status}")

        # 判断是否是群聊（群聊不保持会话历史）
        is_group_chat = is_group

        # 获取或创建会话
        if session_id:
            session = await self.session_manager.get(session_id)
            if not session:
                raise ValueError(f"会话不存在: {session_id}")
        else:
            session = await self.session_manager.create(
                agent_id=self.agent_id,
                channel=channel,
                user_id=user_id,
            )
            self._active_sessions[session.session_id] = session

        # 标记是否加载历史
        session.context["load_history"] = not is_group_chat

        # 添加用户消息到会话管理器
        await self.session_manager.add_message(
            session_id=session.session_id,
            role="user",
            content=content,
        )

        # 添加用户消息到记忆管理器
        if self._memory_manager:
            self._memory_manager.add_message("user", content, session.user_id)

        agent_event(
            f"收到消息: session={session.session_id}, "
            f"user={user_id}, content={content[:50]}..."
        )

        try:
            # 执行处理循环
            response = await self._execute_loop(session)

            # 确保响应是字符串（提取 LLMResponse.content）
            if hasattr(response, 'content'):
                response = response.content
            elif not isinstance(response, str):
                response = str(response)

            # 添加助手消息到会话管理器
            await self.session_manager.add_message(
                session_id=session.session_id,
                role="assistant",
                content=response,
            )

            # 添加助手消息到记忆管理器
            if self._memory_manager:
                self._memory_manager.add_message("assistant", response, session.user_id)

            # DEBUG: 记录返回类型
            info(f"[DEBUG] process_message 返回类型: {type(response)}, 值: {str(response)[:80]}")
            return response

        except Exception as e:
            error(f"处理消息失败: {e}")

            # 添加错误消息
            await self.session_manager.add_message(
                session_id=session.session_id,
                role="assistant",
                content=f"处理消息时发生错误: {e}",
            )

            raise

    async def _initialize_sandbox(self) -> None:
        """初始化沙箱实例"""
        if not self.sandbox_backend:
            # 使用默认 Firecracker 后端
            self.sandbox_backend = FirecrackerBackend()
            await self.sandbox_backend.initialize()

        # 从预热池获取或创建实例
        if self._warm_pool:
            instance = await self._warm_pool.claim(self.agent_id)
            self._sandbox_instance_id = instance.instance_id
        else:
            instance = await self.sandbox_backend.create_instance(
                agent_id=self.agent_id,
                memory_mb=self.config.sandbox_memory_mb,
                cpu_count=self.config.sandbox_cpu_count,
            )
            self._sandbox_instance_id = instance.instance_id

        info(f"沙箱实例已创建: {self._sandbox_instance_id}")

    async def _initialize_llm(self) -> None:
        """初始化 LLM 适配器"""
        if not self._llm_config:
            warning("未配置 LLM，将使用模拟响应")
            return

        from heimaclaw.llm import LLMConfig

        # 解析 provider
        provider_str = self._llm_config.get("provider", "openai")
        try:
            provider = LLMProvider(provider_str)
        except ValueError:
            provider = LLMProvider.OPENAI

        # 创建 LLM 配置
        llm_config = LLMConfig(
            provider=provider,
            model_name=self._llm_config.get("model_name", "gpt-4"),
            api_key=self._llm_config.get("api_key"),
            base_url=self._llm_config.get("base_url"),
            temperature=self._llm_config.get("temperature", 0.7),
            max_tokens=self._llm_config.get("max_tokens", 4096),
        )

        # 注册到全局注册表
        registry = get_llm_registry()
        adapter_name = f"{self.agent_id}-llm"
        registry.register(adapter_name, llm_config)
        self._llm_adapter_name = adapter_name
        self._llm_adapter = registry.get(adapter_name)

        info(f"LLM 已配置: {provider.value}/{llm_config.model_name}")

    async def _execute_loop(self, session: Session) -> str:
        """
        执行处理循环

        使用 ReAct 推理引擎，支持：
        - 双层循环（思考 + 执行）
        - 并行工具执行
        - 反思机制

        参数:
            session: 会话对象

        返回:
            最终响应
        """
        # 获取会话历史（群聊模式不加载历史）
        messages = await self.session_manager.get_messages(session.session_id)
        if not session.context.get("load_history", True):
            # 群聊模式：只保留最新消息（当前用户消息）
            if messages:
                messages = [messages[-1]]

        # 构建消息历史
        history = self._build_message_history(messages)

        # 注入记忆上下文（根据上下文模式）
        info(f"[DEBUG] Memory context_mode: {self._context_mode}, memory_manager: {self._memory_manager}")
        if self._memory_manager and self._context_mode != "minimal":
            self._memory_manager.session_id = session.session_id
            self._memory_manager.user_id = session.user_id

            memory_context = self._memory_manager.get_context_for_llm()
            info(f"[DEBUG] Memory context: {len(memory_context) if memory_context else 0} messages")
            if memory_context:
                if self._context_mode == "full":
                    history = memory_context + history
                elif self._context_mode == "compact":
                    # 只注入摘要，不注入完整历史
                    summary = memory_context[0] if memory_context else None
                    if summary:
                        history = [summary] + history

        # 使用 ReAct 引擎执行
        if self._react_engine and self._llm_adapter:
            try:
                # 获取用户消息（最后一条用户消息）
                user_message = ""
                for msg in reversed(history):
                    if msg.get("role") == "user":
                        user_message = msg.get("content", "")
                        break

                result: ExecutionResult = await self._react_engine.execute(
                    user_message=user_message,
                    context=history,  # 包含完整上下文
                )

                # DEBUG: 检查 result 类型和 final_response
                info(f"[DEBUG] react.execute 返回类型: {type(result)}, final_response 类型: {type(result.final_response) if hasattr(result, 'final_response') else 'N/A'}")
                if hasattr(result, 'final_response'):
                    info(f"[DEBUG] final_response 值: {str(result.final_response)[:100]}")

                # 记录执行步骤
                for step in result.steps:
                    if step.tool_name:
                        await self.session_manager.add_message(
                            session_id=session.session_id,
                            role="assistant",
                            content=step.content,
                            tool_name=step.tool_name,
                        )

                return result.final_response

            except Exception as e:
                error(f"ReAct 执行失败: {e}")
                # 降级到普通 LLM 调用

        # 降级：使用普通 LLM 调用
        response = await self._call_llm(history)

        tool_calls = response.get("tool_calls", [])

        if tool_calls:
            for tool_call in tool_calls:
                tool_name = tool_call.get("name") or tool_call.get("function", {}).get(
                    "name", ""
                )
                tool_params = tool_call.get("parameters") or tool_call.get(
                    "function", {}
                ).get("arguments", {})

                await self.session_manager.add_message(
                    session_id=session.session_id,
                    role="assistant",
                    content="",
                    tool_name=tool_name,
                    tool_call_id=tool_call.get("id", ""),
                )

                tool_result = await self._execute_tool(
                    tool_name=tool_name,
                    parameters=tool_params,
                )

                await self.session_manager.add_message(
                    session_id=session.session_id,
                    role="tool",
                    content=json.dumps(
                        tool_result.result if tool_result.success else tool_result.error
                    ),
                    tool_name=tool_name,
                    tool_call_id=tool_call.get("id", ""),
                )

            return await self._execute_loop(session)

        # 确保返回字符串
        if hasattr(response, "content"):
            return response.content
        elif isinstance(response, dict):
            return response.get("content", "")
        else:
            return str(response)

    async def _call_llm(self, messages: list[dict[str, Any]]) -> dict[str, Any]:
        """
        调用 LLM

        参数:
            messages: 消息历史

        返回:
            LLM 响应字典
        """
        if not self._llm_adapter_name:
            # 模拟响应
            return {
                "content": "这是一个模拟的响应。请配置 API Key 以使用真实 LLM。",
                "tool_calls": None,
            }

        try:
            # 转换消息格式
            llm_messages = []
            for msg in messages:
                llm_msg = LLMMessage(role=msg["role"], content=msg.get("content"))
                llm_messages.append(llm_msg)

            # 调用 LLM
            import time

            start_time = time.time()

            registry = get_llm_registry()
            response = await registry.chat(
                messages=llm_messages,
                adapter_name=self._llm_adapter_name,
                tools=self.tool_registry.get_openai_tools(),
            )

            latency_ms = int((time.time() - start_time) * 1000)

            # 记录 token 使用
            record_token_usage(
                agent_id=self.agent_id,
                provider=response.provider.value,
                model=response.model,
                prompt_tokens=response.prompt_tokens,
                completion_tokens=response.completion_tokens,
                latency_ms=latency_ms,
            )

            # 转换响应
            result = {
                "content": response.content,
                "tool_calls": (
                    [tc.to_dict() for tc in response.tool_calls]
                    if response.tool_calls
                    else None
                ),
            }

            info(f"LLM 响应: {response.total_tokens} tokens, {latency_ms}ms")

            # 发射 LLM 响应事件
            if self._event_bus:
                await self._event_bus.emit(Event(
                    type=EventType.MESSAGE_RECEIVED,
                    agent_id=self.agent_id,
                    session_key=session_key,
                    data={
                        "content": response.content,
                        "model": response.model,
                        "tokens": response.total_tokens,
                    },
                ))

            # DEBUG: 检查 result["content"] 的类型和值
            info(f"[DEBUG] _call_llm result['content'] 类型: {type(result['content'])}, 值: {str(result['content'])[:80]}")

            return result

        except Exception as e:
            error(f"LLM 调用失败: {e}")
            return {
                "content": f"LLM 调用失败: {e}",
                "tool_calls": None,
            }

    def _build_message_history(
        self,
        messages: list[Any],
    ) -> list[dict[str, Any]]:
        """
        构建消息历史

        参数:
            messages: 消息列表

        返回:
            格式化的消息历史
        """
        history = []

        for msg in messages:
            if msg.role == "user":
                history.append({"role": "user", "content": msg.content})
            elif msg.role == "assistant":
                if msg.tool_name:
                    # 工具调用消息
                    history.append(
                        {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": msg.tool_call_id,
                                    "type": "function",
                                    "function": {
                                        "name": msg.tool_name,
                                        "arguments": msg.content,
                                    },
                                }
                            ],
                        }
                    )
                else:
                    history.append({"role": "assistant", "content": msg.content})
            elif msg.role == "tool":
                history.append(
                    {
                        "role": "tool",
                        "tool_call_id": msg.tool_call_id,
                        "content": msg.content,
                    }
                )
            elif msg.role == "system":
                history.append({"role": "system", "content": msg.content})

        return history

    async def _execute_tool(
        self,
        tool_name: str,
        parameters: dict[str, Any],
    ) -> Any:
        """
        执行工具

        参数:
            tool_name: 工具名称
            parameters: 工具参数

        返回:
            工具执行结果
        """
        return await self.tool_registry.execute(tool_name, parameters)

    def set_api_key(self, api_key: str) -> None:
        """
        设置 API Key

        参数:
            api_key: API Key
        """
        if self._llm_config:
            self._llm_config["api_key"] = api_key
