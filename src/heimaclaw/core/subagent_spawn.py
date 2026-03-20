"""
SubagentSpawner - 简化的子 Agent 分派器

核心设计（参考 DeepAgents）：
- 启动后立即返回 job_id，不等待
- 使用 Registry 追踪状态
- 主 Agent 通过 job_id 查询结果

不再依赖 EventBus 事件机制。
"""

import asyncio
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional


class SubagentStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class SubagentJob:
    """子 Agent 任务"""
    job_id: str
    task: str
    status: SubagentStatus = SubagentStatus.PENDING
    result: Optional[str] = None
    error: Optional[str] = None


class SimpleRegistry:
    """简化的任务注册表"""
    
    def __init__(self):
        self._jobs: dict[str, SubagentJob] = {}
    
    def create(self, task: str) -> SubagentJob:
        job_id = str(uuid.uuid4())[:8]
        job = SubagentJob(job_id=job_id, task=task)
        self._jobs[job_id] = job
        return job
    
    def get(self, job_id: str) -> Optional[SubagentJob]:
        return self._jobs.get(job_id)
    
    def update(self, job_id: str, status: SubagentStatus, result: str = None, error: str = None):
        job = self._jobs.get(job_id)
        if job:
            job.status = status
            if result is not None:
                job.result = result
            if error is not None:
                job.error = error


@dataclass
class SpawnConfig:
    """派生配置"""
    task: str
    agent_id: Optional[str] = None
    timeout_seconds: Optional[int] = None


@dataclass
class SpawnResult:
    """派生结果"""
    status: str  # "accepted" | "forbidden" | "error"
    job_id: Optional[str] = None
    note: Optional[str] = None
    error: Optional[str] = None


class SubagentSpawner:
    """
    简化的子 Agent 分派器
    
    核心变化：
    - 不再依赖 EventBus
    - 使用简单的 Registry 追踪状态
    - launch() 立即返回 job_id
    - check() 查询状态和结果
    """

    def __init__(
        self,
        agent_runner_factory: Callable,
        max_concurrent: int = 5,
    ):
        self.agent_runner_factory = agent_runner_factory
        self.max_concurrent = max_concurrent
        self._registry = SimpleRegistry()
        self._running_count = 0

    async def launch(self, config: SpawnConfig) -> SpawnResult:
        """
        启动子 Agent，立即返回 job_id
        
        Args:
            config: 派生配置
        
        Returns:
            SpawnResult with job_id
        """
        # 检查并发限制
        if self._running_count >= self.max_concurrent:
            return SpawnResult(
                status="forbidden",
                error=f"达到最大并发数 ({self.max_concurrent})"
            )
        
        # 创建任务
        job = self._registry.create(config.task)
        
        # 异步执行
        self._running_count += 1
        asyncio.create_task(self._run(job.job_id, config))
        
        return SpawnResult(
            status="accepted",
            job_id=job.job_id,
            note=f"后台任务已启动，job_id: {job.job_id}"
        )

    async def _run(self, job_id: str, config: SpawnConfig):
        """执行子 Agent"""
        job = self._registry.get(job_id)
        if not job:
            return
        
        try:
            job.status = SubagentStatus.RUNNING
            
            # 创建 Agent Runner
            runner = self.agent_runner_factory(
                agent_id=config.agent_id or "default",
                session_key=f"subagent:{job_id}",
                model=None,
            )
            
            # 启动 Runner
            await runner.start()
            
            # 执行命令
            result_text = await self._execute_command(runner, config.task)
            
            # 标记成功
            job.status = SubagentStatus.SUCCESS
            job.result = result_text
            
        except asyncio.TimeoutError:
            job.status = SubagentStatus.FAILED
            job.error = "执行超时"
            
        except Exception as e:
            job.status = SubagentStatus.FAILED
            job.error = str(e)
            
        finally:
            self._running_count -= 1
            try:
                await runner.stop()
            except:
                pass

    async def _execute_command(self, runner, task: str) -> str:
        """执行命令"""
        import re
        
        # 从 task 中提取命令
        command = None
        
        if "执行命令:" in task:
            match = re.search(r'执行命令:\s*(.+)', task)
            if match:
                command = match.group(1).strip()
        
        if not command:
            command = task
        
        # 执行
        tool_result = await runner.tool_registry.execute(
            name="exec",
            parameters={"command": command},
        )
        
        if tool_result.success:
            return str(tool_result.result)
        else:
            return f"错误: {tool_result.error}"

    async def check(self, job_id: str) -> Optional[SubagentJob]:
        """
        检查任务状态
        
        Args:
            job_id: 任务 ID
        
        Returns:
            SubagentJob 或 None
        """
        return self._registry.get(job_id)

    async def cancel(self, job_id: str) -> bool:
        """取消任务"""
        job = self._registry.get(job_id)
        if not job:
            return False
        
        if job.status in (SubagentStatus.SUCCESS, SubagentStatus.FAILED):
            return False
        
        job.status = SubagentStatus.CANCELLED
        return True
