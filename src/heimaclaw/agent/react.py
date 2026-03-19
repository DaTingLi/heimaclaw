"""
ReAct 推理引擎

基于 pi-mono 双层 Loop 理念 + Thought/Action/Observation 模式
"""
import json
import re
from dataclasses import dataclass, field
from typing import Any, Optional
from enum import Enum

from heimaclaw.agent.events import AgentEvent, EventType, EventStream, create_event_stream
from heimaclaw.agent.tools import ToolRegistry, get_tool_registry
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
    """

    MAX_ITERATIONS = 3  # 减少迭代次数避免重复调用

    def __init__(
        self,
        tool_registry: ToolRegistry,
        llm_callable: Any,
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
        """执行 ReAct 推理"""
        from heimaclaw.llm.base import Message as LLMMessage

        result = ExecutionResult()
        messages = context.copy()

        # 添加用户消息
        messages.append({"role": "user", "content": user_message})

        iteration = 0
        has_tool_calls = True

        tool_result_summary = ""  # 累积工具执行结果
        
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
                result.final_response = content
                result.steps.append(Step(
                    type=StepType.RESPONSE,
                    content=content,
                ))
            else:
                # 执行工具
                tool_results = await self._execute_tools(tool_calls, messages)

                # 累积工具结果（用于最终回复）
                for i, tool_result in enumerate(tool_results):
                    tool_text = str(tool_result)
                    tool_result_summary += f"\n{tool_text}"
                    messages.append({
                        "role": "tool",
                        "content": tool_text,
                    })
                    result.steps.append(Step(
                        type=StepType.OBSERVATION,
                        content=tool_text,
                        success=True,
                    ))

        # 如果达到最大迭代次数但有工具执行结果，用工具结果作为回复
        if iteration >= self.MAX_ITERATIONS and tool_result_summary:
            result.final_response = f"工具执行完成，结果如下：{tool_result_summary}"
            result.success = True

        return result

    async def _call_llm(
        self,
        messages: list[dict[str, str]],
        system_prompt: str,
    ) -> dict:
        """调用 LLM（支持工具）"""
        from heimaclaw.llm.base import Message as LLMMessage

        prompt = self._build_react_prompt(system_prompt)

        try:
            # 构建消息
            llm_messages = []
            for msg in messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if role in ("user", "assistant", "system"):
                    llm_messages.append(LLMMessage(role=role, content=content))

            # 添加系统提示
            if prompt:
                llm_messages.insert(0, LLMMessage(role="system", content=prompt))

            # 获取工具定义
            tools = self.tool_registry.get_openai_tools()

            # 调用 LLM
            response = await self.llm(
                messages=llm_messages,
                tools=tools if tools else None,
            )

            # DEBUG: 打印原始响应
            print(f"[DEBUG] LLM 原始响应 type={type(response)}, content={getattr(response, 'content', 'N/A')}, tool_calls={getattr(response, 'tool_calls', 'N/A')}")
            
            # 解析响应
            if hasattr(response, "tool_calls") and response.tool_calls:
                return {
                    "content": getattr(response, "content", "") or "",
                    "tool_calls": [
                        tc.to_dict() if hasattr(tc, "to_dict") else tc
                        for tc in response.tool_calls
                    ]
                }
            elif isinstance(response, dict):
                return {"content": response.get("content", ""), "tool_calls": None}
            else:
                # 确保提取 .content 属性
                if hasattr(response, "content"):
                    return {"content": response.content or "", "tool_calls": None}
                else:
                    return {"content": str(response), "tool_calls": None}

        except Exception as e:
            return {"content": f"LLM 调用失败: {e}", "tool_calls": None}

    def _build_react_prompt(self, system_prompt: str) -> str:
        """构建 ReAct 提示"""
        tools = self.tool_registry.get_openai_tools()
        tools_desc = []
        for t in tools:
            func = t.get("function", {})
            name = func.get("name", "unknown")
            desc = func.get("description", "")
            tools_desc.append(f"- {name}: {desc}")

        base = f"""你是一个智能助手，可以通过工具来完成任务。

可用工具：
{chr(10).join(tools_desc)}

当你需要执行操作时，使用以下格式：
```json
{{"name": "工具名", "arguments": {{"参数名": "参数值"}}}}
```

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
        """执行工具"""
        results = []

        for tool_call in tool_calls:
            try:
                func = tool_call.get("function", {})
                name = func.get("name", "")
                args = func.get("arguments", {})

                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except:
                        args = {}

                result: ToolResult = await self.tool_registry.execute(
                    name=name,
                    parameters=args,
                )

                if result.success:
                    results.append(str(result.result))
                else:
                    results.append(f"错误: {result.error}")

            except Exception as e:
                results.append(f"工具执行异常: {e}")

        return results
