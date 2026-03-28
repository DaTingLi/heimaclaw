"""
ReAct 推理引擎 - 简化版（参考 DeepAgents）

核心改进：
- 子 Agent 启动后立即返回 job_id
- 不再依赖 EventBus
- 通过 registry.check() 查询结果
"""

import asyncio
import json
import re
from dataclasses import dataclass, field
from typing import Any, Optional
from enum import Enum

from heimaclaw.agent.tools import ToolRegistry
from heimaclaw.agent.planner import Planner, ExecutionPlan, ExecutionStep, ExecutionMode
from heimaclaw.interfaces import ToolResult
from heimaclaw.console import info, error


class StepType(str, Enum):
    THOUGHT = "thought"
    ACTION = "action"
    OBSERVATION = "observation"
    RESPONSE = "response"
    ERROR = "error"


@dataclass
class Step:
    type: StepType
    content: str
    tool_name: Optional[str] = None
    result: Optional[str] = None
    success: bool = True


@dataclass
class ExecutionResult:
    steps: list[Step] = field(default_factory=list)
    final_response: str = ""
    success: bool = True
    error: Optional[str] = None


class ReActEngine:
    """
    ReAct 推理引擎 - 简化版
    
    不再使用 EventBus，改为：
    - subagent_spawner.launch() 立即返回 job_id
    - subagent_spawner.check() 查询结果
    """

    def __init__(
        self,
        tool_registry: ToolRegistry,
        llm_callable: Any = None,
        subagent_spawner: Any = None,
    ):
        self.tool_registry = tool_registry
        self.llm = llm_callable
        self.subagent_spawner = subagent_spawner
        self._planner = Planner(tool_registry, llm_callable)

    async def execute(
        self,
        user_message: str,
        context: list[dict[str, str]],
        system_prompt: str = "",
        session_id: str = "",
    ) -> ExecutionResult:
        """执行推理"""
        result = ExecutionResult()

        info(f"[Planner] 分析任务: {user_message[:50]}...")
        
        # 获取可用工具
        tools = self.tool_registry.get_openai_tools()
        
        # LLM 规划任务分解
        plan: ExecutionPlan = await self._planner.plan(user_message, tools)
        
        info(f"[Planner] 生成计划: {len(plan.steps)} 个步骤")
        info(f"[Planner] reasoning: {plan.reasoning[:80] if plan.reasoning else 'N/A'}...")
        
        for step in plan.steps:
            info(f"[Planner]   {step.step_id}: {step.description} (mode={step.execution_mode.value})")

        # 执行步骤
        step_results = {}
        
        # 按依赖关系分组执行
        execution_groups = self._build_execution_groups(plan.steps)
        
        info(f"[ReAct] 执行层级: {len(execution_groups)} groups")
        
        for group in execution_groups:
            # 判断是否并行
            can_parallel = all(
                not step.depends_on or all(d in step_results for d in step.depends_on)
                for step in group
            )
            
            if can_parallel and len(group) > 1:
                # 并行执行
                info(f"[ReAct] 并行执行 {len(group)} 个步骤")
                results = await self._execute_parallel(group)
                step_results.update(results)
            else:
                # 串行执行
                for step in group:
                    info(f"[ReAct] 串行执行: {step.step_id}")
                    res = await self._execute_step(step)
                    step_results[step.step_id] = res
                    result.steps.append(Step(
                        type=StepType.OBSERVATION,
                        content=res,
                        tool_name=step.tool_name,
                        success=not str(res).startswith("错误:"),
                    ))

        # 汇总结果
        all_results = list(step_results.values())
        if all_results:
            result.final_response = self._summarize_results(all_results)
        else:
            result.final_response = "任务执行完成"
        
        result.success = not any(str(r).startswith("错误:") for r in all_results)
        return result

    def _build_execution_groups(self, steps: list[ExecutionStep]) -> list[list[ExecutionStep]]:
        """根据依赖关系构建执行层级"""
        groups = []
        remaining = steps.copy()
        completed = set()
        
        while remaining:
            current_group = []
            still_remaining = []
            
            for step in remaining:
                deps_met = all(d in completed for d in step.depends_on)
                if deps_met:
                    current_group.append(step)
                else:
                    still_remaining.append(step)
            
            if not current_group:
                if groups and still_remaining:
                    groups.append(still_remaining)
                elif not groups:
                    groups.append(remaining)
                break
            
            groups.append(current_group)
            for step in current_group:
                completed.add(step.step_id)
            remaining = still_remaining
        
        return groups

    async def _execute_parallel(self, steps: list[ExecutionStep]) -> dict:
        """并行执行多个步骤"""
        async def run_step(step: ExecutionStep):
            return step.step_id, await self._execute_step(step)
        
        results = await asyncio.gather(*[run_step(s) for s in steps], return_exceptions=True)
        
        result_dict = {}
        for r in results:
            if isinstance(r, Exception):
                result_dict[r.args[0] if r.args else "unknown"] = f"错误: {str(r)}"
            else:
                result_dict[r[0]] = r[1]
        
        return result_dict

    async def _execute_step(self, step: ExecutionStep) -> str:
        """执行单个步骤"""
        if step.execution_mode == ExecutionMode.SUBAGENT and self.subagent_spawner:
            return await self._execute_via_subagent(step)
        else:
            return await self._execute_direct(step)

    async def _execute_direct(self, step: ExecutionStep) -> str:
        """直接执行工具"""
        try:
            tool_result: ToolResult = await self.tool_registry.execute(
                name=step.tool_name,
                parameters=step.parameters,
            )
            return str(tool_result.result) if tool_result.success else f"错误: {tool_result.error}"
        except Exception as e:
            return f"错误: {str(e)}"

    async def _execute_via_subagent(self, step: ExecutionStep) -> str:
        """通过子 Agent 执行（简化版）"""
        if not self.subagent_spawner:
            return await self._execute_direct(step)
        
        from heimaclaw.core.subagent_spawn import SpawnConfig
        
        # 创建配置
        spawn_config = SpawnConfig(
            task=step.subagent_task or step.description,
            agent_id="default",
            timeout_seconds=step.estimated_duration_seconds + 60,
        )
        
        # 启动子 Agent，立即返回 job_id
        info(f"[ReAct] 启动子 Agent: {spawn_config.task[:50]}...")
        spawn_result = await self.subagent_spawner.launch(spawn_config)
        
        if spawn_result.status != "accepted":
            return f"错误: 子 Agent 启动失败 - {spawn_result.error}"
        
        job_id = spawn_result.job_id
        info(f"[ReAct] 子 Agent 已启动，job_id={job_id}，等待完成...")
        
        # 等待完成（带超时）
        timeout = step.estimated_duration_seconds + 60
        start_time = asyncio.get_event_loop().time()
        
        while True:
            job = await self.subagent_spawner.check(job_id)
            
            if not job:
                error(f"[ReAct] 任务丢失: job_id={job_id}")
                return f"错误: 任务丢失 (job_id={job_id})"
            
            info(f"[ReAct] 子 Agent {job_id} 状态: {job.status.value}, result={job.result}, error={job.error}")
            
            if job.status.value == "success":
                info(f"[ReAct] 子 Agent {job_id} 完成, 返回: {job.result[:100] if job.result else 'None'}...")
                return job.result or "(无输出)"
            
            if job.status.value == "failed":
                error(f"[ReAct] 子 Agent {job_id} 失败: {job.error}")
                return f"错误: {job.error}"
            
            if job.status.value == "cancelled":
                return f"错误: 任务被取消"
            
            # 检查超时
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed >= timeout:
                await self.subagent_spawner.cancel(job_id)
                return f"错误: 执行超时 ({timeout}s)"
            
            # 等待一下再检查
            await asyncio.sleep(1)

    def _summarize_results(self, results: list[str]) -> str:
        """汇总结果"""
        if not results:
            return "执行完成，无输出"
        
        summary_parts = []
        for i, r in enumerate(results, 1):
            r_str = str(r)
            if len(r_str) > 500:
                r_str = r_str[:500] + "..."
            summary_parts.append(f"【步骤 {i}】\n{r_str}")
        
        return "工具执行完成，结果如下：\n\n" + "\n\n".join(summary_parts)
