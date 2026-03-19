"""
Subagent Spawner - 子 Agent 派生工具

参考：
- OpenClaw subagent-spawn.ts
- sessions_spawn 工具

功能：
- 派生独立的子 Agent
- 支持模型覆盖（成本优化）
- 支持并行执行
- 自动发送完成事件
"""

import asyncio
from dataclasses import dataclass, field
from typing import Any, Optional, Callable
from pathlib import Path

from .event_bus import EventBus, Event, EventType, EventLevel
from .subagent_registry import SubagentRegistry, SubagentRun, SubagentStatus


@dataclass
class SpawnConfig:
    """派生配置"""

    task: str  # 任务描述
    agent_id: Optional[str] = None  # 指定 Agent ID
    model: Optional[str] = None  # 模型覆盖
    mode: str = "run"  # "run" 或 "session"
    sandbox: str = "inherit"  # "inherit" 或 "require"
    timeout_seconds: Optional[int] = None
    workspace_dir: Optional[str] = None
    tools_allowlist: Optional[list[str]] = None  # 工具白名单
    thinking: str = "off"  # "off" | "on" | "stream"


@dataclass
class SpawnResult:
    """派生结果"""

    status: str  # "accepted" | "forbidden" | "error"
    child_session_key: Optional[str] = None
    run_id: Optional[str] = None
    note: Optional[str] = None
    error: Optional[str] = None


class SubagentSpawner:
    """
    子 Agent 派生器
    
    负责派生、监控和通知子 Agent。
    """

    def __init__(
        self,
        event_bus: EventBus,
        registry: SubagentRegistry,
        agent_runner_factory: Callable,
        max_concurrent_per_session: int = 5,
    ):
        self.event_bus = event_bus
        self.registry = registry
        self.agent_runner_factory = agent_runner_factory
        self.max_concurrent_per_session = max_concurrent_per_session

    async def spawn(
        self,
        config: SpawnConfig,
        requester_session_key: str,
        requester_agent_id: str,
    ) -> SpawnResult:
        """
        派生子 Agent
        
        Args:
            config: 派生配置
            requester_session_key: 父 Agent 会话 ID
            requester_agent_id: 父 Agent ID
        
        Returns:
            SpawnResult
        """
        # 1. 检查并发限制
        active_count = self.registry.count_active_for_session(requester_session_key)
        if active_count >= self.max_concurrent_per_session:
            return SpawnResult(
                status="forbidden",
                error=f"已达到最大并发数 ({self.max_concurrent_per_session})",
            )

        # 2. 创建运行记录
        run = SubagentRun(
            requester_session_key=requester_session_key,
            task=config.task,
            agent_id=config.agent_id or requester_agent_id,
            model=config.model,
            mode=config.mode,
            sandbox=config.sandbox,
            timeout_seconds=config.timeout_seconds,
        )

        # 3. 生成子会话 ID
        run.child_session_key = f"{requester_session_key}:subagent:{run.run_id}"

        # 4. 注册到 Registry
        self.registry.register(run)

        # 5. 发射 SPAWNED 事件
        await self.event_bus.emit(Event(
            type=EventType.SUBAGENT_SPAWNED,
            level=EventLevel.INFO,
            agent_id=requester_agent_id,
            session_key=requester_session_key,
            run_id=run.run_id,
            data={
                "child_session_key": run.child_session_key,
                "task": config.task,
                "model": config.model,
            },
        ))

        # 6. 异步启动子 Agent（不阻塞）
        asyncio.create_task(self._run_subagent(run, config))

        return SpawnResult(
            status="accepted",
            child_session_key=run.child_session_key,
            run_id=run.run_id,
            note="子 Agent 已异步启动。完成时将通过事件通知。",
        )

    async def _run_subagent(self, run: SubagentRun, config: SpawnConfig):
        """
        运行子 Agent（内部方法）
        """
        try:
            # 标记为运行中
            self.registry.mark_started(run.run_id)

            # 发射 STARTED 事件
            await self.event_bus.emit(Event(
                type=EventType.SUBAGENT_STARTED,
                level=EventLevel.INFO,
                agent_id=run.agent_id,
                session_key=run.child_session_key,
                run_id=run.run_id,
                data={"task": run.task},
            ))

            # 创建 Agent Runner
            runner = self.agent_runner_factory(
                agent_id=run.agent_id,
                session_key=run.child_session_key,
                model=run.model,
                workspace_dir=config.workspace_dir,
                tools_allowlist=config.tools_allowlist,
                thinking=config.thinking,
            )

            # 执行任务
            result = await runner.execute(
                user_message=run.task,
                context=[],  # 子 Agent 有独立的上下文窗口
                system_prompt="",
            )

            # 提取结果文本
            result_text = result.final_response or "(无输出)"

            # 标记为完成
            self.registry.mark_completed(run.run_id, result_text)

            # 发射 COMPLETED 事件
            await self.event_bus.emit(Event(
                type=EventType.SUBAGENT_COMPLETED,
                level=EventLevel.INFO,
                agent_id=run.agent_id,
                session_key=run.child_session_key,
                run_id=run.run_id,
                data={
                    "result_text": result_text,
                    "tokens_used": result.tokens_used if hasattr(result, "tokens_used") else 0,
                },
            ))

        except asyncio.TimeoutError:
            # 超时
            self.registry.update(run.run_id, status=SubagentStatus.TIMEOUT)
            await self.event_bus.emit(Event(
                type=EventType.SUBAGENT_FAILED,
                level=EventLevel.ERROR,
                agent_id=run.agent_id,
                session_key=run.child_session_key,
                run_id=run.run_id,
                data={"error": "执行超时"},
            ))

        except Exception as e:
            # 失败
            error_msg = str(e)
            self.registry.mark_failed(run.run_id, error_msg)

            await self.event_bus.emit(Event(
                type=EventType.SUBAGENT_FAILED,
                level=EventLevel.ERROR,
                agent_id=run.agent_id,
                session_key=run.child_session_key,
                run_id=run.run_id,
                data={"error": error_msg},
            ))

    async def kill(self, run_id: str, requester_session_key: str) -> bool:
        """
        杀死子 Agent
        
        Args:
            run_id: 运行 ID
            requester_session_key: 请求者会话（验证权限）
        
        Returns:
            是否成功
        """
        run = self.registry.get(run_id)
        if not run:
            return False

        # 验证权限
        if run.requester_session_key != requester_session_key:
            return False

        # 检查状态
        if run.status not in {SubagentStatus.PENDING, SubagentStatus.RUNNING}:
            return False

        # 标记为被杀死
        self.registry.mark_killed(run_id)

        # 发射 KILLED 事件
        await self.event_bus.emit(Event(
            type=EventType.SUBAGENT_KILLED,
            level=EventLevel.WARNING,
            agent_id=run.agent_id,
            session_key=run.child_session_key,
            run_id=run_id,
            data={},
        ))

        return True

    async def wait_for_completion(
        self,
        run_id: str,
        timeout_seconds: Optional[int] = None,
    ) -> Optional[str]:
        """
        等待子 Agent 完成
        
        Args:
            run_id: 运行 ID
            timeout_seconds: 超时时间
        
        Returns:
            结果文本（None 表示失败）
        """
        start_time = asyncio.get_event_loop().time()

        while True:
            run = self.registry.get(run_id)
            if not run:
                return None

            # 已完成
            if run.status == SubagentStatus.COMPLETED:
                return run.result_text

            # 失败
            if run.status in {SubagentStatus.FAILED, SubagentStatus.KILLED, SubagentStatus.TIMEOUT}:
                return None

            # 超时检查
            if timeout_seconds:
                elapsed = asyncio.get_event_loop().time() - start_time
                if elapsed >= timeout_seconds:
                    return None

            # 等待一段时间再检查
            await asyncio.sleep(1)
