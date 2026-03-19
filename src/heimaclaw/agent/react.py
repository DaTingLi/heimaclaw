"""
ReAct 推理引擎

基于 pi-mono 双层 Loop 理念 + Thought/Action/Observation 模式

核心流程：
1. Thought: 分析问题，制定计划
2. Action: 执行工具
3. Observation: 观察结果
4. 循环直到完成
"""

import asyncio
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from heimaclaw.agent.tools import ToolRegistry
from heimaclaw.interfaces import ToolResult


class StepType(str, Enum):
    """步骤类型"""

    THOUGHT = "thought"
    ACTION = "action"
    OBSERVATION = "observation"
    RESPONSE = "response"
    ERROR = "error"


@dataclass
class Step:
    """执行步骤"""

    type: StepType
    content: str
    tool_name: Optional[str] = None
    tool_args: Optional[dict] = None
    result: Optional[str] = None
    success: bool = True


@dataclass
class ExecutionResult:
    """执行结果"""

    steps: list[Step] = field(default_factory=list)
    final_response: str = ""
    success: bool = True
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "steps": [
                {
                    "type": s.type.value,
                    "content": s.content,
                    "tool": s.tool_name,
                    "args": s.tool_args,
                    "result": s.result,
                    "success": s.success,
                }
                for s in self.steps
            ],
            "final_response": self.final_response,
            "success": self.success,
            "error": self.error,
        }


class ReActEngine:
    """
    ReAct 推理引擎

    特性：
    - 双层循环（外层：思考，内层：工具执行）
    - Thought/Action/Observation 模式
    - 并行工具执行
    - 结果验证
    - 最大迭代次数保护
    """

    MAX_ITERATIONS = 10  # 最大迭代次数
    MAX_PARALLEL_TOOLS = 3  # 最大并行工具数

    def __init__(
        self,
        tool_registry: ToolRegistry,
        llm_callable: Any,  # LLM 调用接口
    ):
        self.tool_registry = tool_registry
        self.llm = llm_callable
        self._streaming_callback = None

    def set_streaming_callback(self, callback):
        """设置流式回调"""
        self._streaming_callback = callback

    async def execute(
        self,
        user_message: str,
        context: list[dict[str, str]],
        system_prompt: str = "",
    ) -> ExecutionResult:
        """
        执行 ReAct 推理

        参数:
            user_message: 用户消息
            context: 对话历史
            system_prompt: 系统提示

        返回:
            ExecutionResult: 执行结果
        """
        result = ExecutionResult()
        messages = context.copy()

        # 添加用户消息
        messages.append({"role": "user", "content": user_message})

        iteration = 0
        has_tool_calls = True

        # 外层循环：处理消息直到没有工具调用
        while has_tool_calls and iteration < self.MAX_ITERATIONS:
            iteration += 1

            # 调用 LLM
            response = await self._call_llm(messages, system_prompt)

            # 添加助手响应
            content = response.get("content", "")
            messages.append({"role": "assistant", "content": content})

            # 检查是否有工具调用
            tool_calls = response.get("tool_calls", [])

            if not tool_calls:
                has_tool_calls = False
                result.final_response = response.get("content", "")
                result.steps.append(
                    Step(
                        type=StepType.RESPONSE,
                        content=response.get("content", ""),
                    )
                )
            else:
                # 内层循环：执行工具
                tool_results = await self._execute_tools(tool_calls, messages)

                # 处理工具结果
                for tool_result in tool_results:
                    messages.append(
                        {
                            "role": "tool",
                            "content": tool_result,
                        }
                    )

                    result.steps.append(
                        Step(
                            type=StepType.OBSERVATION,
                            content=tool_result,
                            success=tool_result.get("success", True),
                        )
                    )

        if iteration >= self.MAX_ITERATIONS:
            result.error = f"达到最大迭代次数 ({self.MAX_ITERATIONS})"
            result.success = False

        return result

    async def _call_llm(
        self,
        messages: list[dict[str, str]],
        system_prompt: str,
    ) -> dict:
        """调用 LLM（简化版，不使用工具）"""
        # 构建提示
        prompt = self._build_react_prompt(system_prompt)

        # 直接调用 LLM
        try:
            # 将 dict 转换为简单格式
            llm_messages = []
            for msg in messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if role in ("user", "assistant", "system"):
                    llm_messages.append({"role": role, "content": content})

            # 添加系统提示
            if prompt:
                llm_messages.insert(0, {"role": "system", "content": prompt})

            response = await self.llm(
                messages=llm_messages,
            )

            # 解析响应
            if hasattr(response, "content"):
                return {"content": response.content, "tool_calls": None}
            elif isinstance(response, dict):
                return {"content": response.get("content", ""), "tool_calls": None}
            else:
                return {"content": str(response), "tool_calls": None}

        except Exception as e:
            return {"content": f"LLM 调用失败: {e}", "tool_calls": None}

    def _build_react_prompt(self, system_prompt: str) -> str:
        """构建 ReAct 提示"""
        base = """你是一个智能助手，可以执行各种工具来完成用户任务。

当你需要执行操作时，使用 tool_calls 格式。

格式示例：
{
  "thought": "我需要先查看 /tmp 目录的内容",
  "action": {
    "name": "exec",
    "arguments": {"command": "ls -la /tmp"}
  }
}

当你知道答案时，直接回复，不要调用工具。

"""
        if system_prompt:
            base += f"\n系统提示：{system_prompt}"

        return base

    async def _execute_tools(
        self,
        tool_calls: list[dict],
        messages: list[dict],
    ) -> list[str]:
        """执行工具（可并行）"""
        tasks = []

        for tool_call in tool_calls:
            func = tool_call.get("function", {})
            tool_name = func.get("name", "")
            tool_args = func.get("arguments", {})

            if isinstance(tool_args, str):
                try:
                    tool_args = json.loads(tool_args)
                except Exception:
                    tool_args = {}

            # 创建执行任务
            task = self._execute_single_tool(tool_name, tool_args)
            tasks.append((tool_call, task))

        # 并行执行
        results = await asyncio.gather(
            *[task for _, task in tasks], return_exceptions=True
        )

        # 处理结果
        output = []
        for i, result in enumerate(results):
            tool_call = tasks[i][0]
            func = tool_call.get("function", {})
            tool_name = func.get("name", "")

            if isinstance(result, Exception):
                output.append(f"工具执行错误: {str(result)}")
            else:
                output.append(str(result))

        return output

    async def _execute_single_tool(
        self,
        tool_name: str,
        tool_args: dict,
    ) -> str:
        """执行单个工具"""
        result: ToolResult = await self.tool_registry.execute(
            tool_name=tool_name,
            parameters=tool_args,
        )

        if result.success:
            return result.result
        else:
            return f"错误: {result.error}"
