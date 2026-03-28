"""
Planner - LLM 驱动的任务分解规划器
"""

import json
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from heimaclaw.agent.tools import ToolRegistry
from heimaclaw.console import info, error


class ExecutionMode(str, Enum):
    DIRECT = "direct"
    SUBAGENT = "subagent"


@dataclass
class ExecutionStep:
    step_id: str
    description: str
    tool_name: str
    parameters: dict[str, Any]
    depends_on: list[str] = field(default_factory=list)
    execution_mode: ExecutionMode = ExecutionMode.DIRECT
    estimated_duration_seconds: int = 10
    subagent_task: Optional[str] = None  # 子 Agent 的具体任务

    def to_dict(self) -> dict:
        return {
            "step_id": self.step_id,
            "description": self.description,
            "tool_name": self.tool_name,
            "parameters": self.parameters,
            "depends_on": self.depends_on,
            "execution_mode": self.execution_mode.value,
            "subagent_task": self.subagent_task,
        }


@dataclass
class ExecutionPlan:
    steps: list[ExecutionStep]
    original_request: str
    requires_subagent: bool
    reasoning: str = ""
    
    def to_dict(self) -> dict:
        return {
            "step_count": len(self.steps),
            "requires_subagent": self.requires_subagent,
            "reasoning": self.reasoning,
            "steps": [s.to_dict() for s in self.steps],
        }


class Planner:
    """LLM 驱动的任务分解规划器"""

    def __init__(self, tool_registry: ToolRegistry, llm_callable: Any = None):
        self.tool_registry = tool_registry
        self.llm = llm_callable

    async def plan(
        self,
        user_message: str,
        available_tools: list[dict[str, Any]],
    ) -> ExecutionPlan:
        if not self.llm:
            return await self._plan_with_rules(user_message, available_tools)
        return await self._plan_with_llm(user_message, available_tools)

    async def _plan_with_llm(
        self,
        user_message: str,
        available_tools: list[dict[str, Any]],
    ) -> ExecutionPlan:
        from heimaclaw.llm.base import Message as LLMMessage
        
        # 获取工具的参数信息
        tool_info = {}
        for t in available_tools:
            func = t.get("function", {})
            name = func.get("name", "unknown")
            props = func.get("parameters", {}).get("properties", {})
            param_names = list(props.keys())
            tool_info[name] = {"params": param_names}
        
        tools_json = json.dumps(tool_info, indent=2)
        
        prompt = f"""你是一个任务规划助手。用户请求：

{user_message}

可用工具及参数：
{tools_json}

请规划执行步骤。规则：
0. **创建飞书文档/表格**：如果用户要求创建飞书文档、飞书表格、在线文档等，使用 create_feishu_doc 工具：
   - 参数：{{"type": "doc", "title": "文档标题"}} 或 {{"type": "sheet", "title": "表格标题"}}
   - 注意：只需要 title 参数，folder_token 可选
1. 如果需要运行 Python 文件，先用 exec 执行 cat 读取文件内容
2. 如果文件需要依赖（如 flask），用 exec 执行 pip install 和 python 命令
3. 如果要运行长期运行的程序（如Flask、HTTP服务），必须使用后台执行：
   - 格式：cd /tmp && nohup python /tmp/hello_flask.py > /tmp/flask.log 2>&1 &
   - 或者使用：(python /tmp/xxx.py &) && sleep 2 && echo "服务已启动"
   - 关键：命令末尾必须加 & 让它在后台运行
4. exec 工具的参数是 {{"command": "命令"}}
5. read_file 工具的参数是 {{"path": "/文件路径"}}

**关键规则**：
- "安装依赖"、"运行"、"后台启动" 的步骤，execution_mode 必须设为 "subagent"
- subagent_task 必须是 "执行命令: <具体shell命令>" 格式，不能是描述！
- 示例：subagent_task: "执行命令: cd /tmp && pip install flask -q && nohup python hello.py > app.log 2>&1 &"
- 只有 "读取文件"、"查看" 等只读操作才能用 execution_mode="direct"
- create_feishu_doc 工具使用 execution_mode="direct"

返回 JSON：
{{
  "reasoning": "规划理由",
  "requires_subagent": true,
  "steps": [
    {{
      "step_id": "step_1",
      "description": "读取文件内容",
      "tool_name": "exec",
      "parameters": {{"command": "cat /文件路径"}},
      "depends_on": [],
      "execution_mode": "direct",
      "subagent_task": null
    }},
    {{
      "step_id": "step_2",
      "description": "安装依赖并运行",
      "tool_name": "exec",
      "parameters": {{"command": "cd /tmp && pip install flask -q && nohup python /文件路径 > /tmp/app.log 2>&1 & sleep 2 && echo Flask已启动在端口8922"}},
      "depends_on": ["step_1"],
      "execution_mode": "subagent",
      "subagent_task": "执行命令: cd /tmp && pip install flask -q && nohup python /文件路径 > /tmp/app.log 2>&1 & sleep 2 && echo 服务已启动"
    }}
  ]
}}"""

        try:
            response = await self.llm(
                messages=[LLMMessage(role="user", content=prompt)],
                tools=None,
            )
            
            content = getattr(response, "content", "") or ""
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                plan_data = json.loads(json_match.group())
                
                steps = []
                for step_data in plan_data.get("steps", []):
                    step = ExecutionStep(
                        step_id=step_data["step_id"],
                        description=step_data["description"],
                        tool_name=step_data["tool_name"],
                        parameters=step_data.get("parameters", {}),
                        depends_on=step_data.get("depends_on", []),
                        execution_mode=ExecutionMode(step_data.get("execution_mode", "direct")),
                        subagent_task=step_data.get("subagent_task"),
                    )
                    steps.append(step)
                
                return ExecutionPlan(
                    steps=steps,
                    original_request=user_message,
                    requires_subagent=plan_data.get("requires_subagent", False),
                    reasoning=plan_data.get("reasoning", ""),
                )
        
        except Exception as e:
            error(f"[Planner] LLM 规划失败: {e}")
        
        return await self._plan_with_rules(user_message, available_tools)

    async def _plan_with_rules(
        self,
        user_message: str,
        available_tools: list[dict[str, Any]],
    ) -> ExecutionPlan:
        """使用规则进行简单的任务分解"""
        steps = []
        file_path = self._extract_file_path(user_message)
        
        if file_path and file_path.endswith(".py"):
            # 先读取文件
            steps.append(ExecutionStep(
                step_id="step_1",
                description=f"读取 Python 文件: {file_path}",
                tool_name="exec",
                parameters={"command": f"cat {file_path}"},
                depends_on=[],
                execution_mode=ExecutionMode.DIRECT,
                estimated_duration_seconds=3,
            ))
            
            # 检查是否需要安装依赖
            needs_install = any(k in user_message for k in ["环境", "依赖", "安装", "flask", "pip"])
            
            if needs_install:
                # 安装依赖并运行
                steps.append(ExecutionStep(
                    step_id="step_2",
                    description=f"安装依赖并运行: {file_path}",
                    tool_name="exec",
                    parameters={"command": f"pip install flask -q && python {file_path}"},
                    depends_on=["step_1"],
                    execution_mode=ExecutionMode.SUBAGENT,
                    estimated_duration_seconds=60,
                    subagent_task=f"执行命令: pip install flask -q && python {file_path}",
                ))
            else:
                # 直接运行
                steps.append(ExecutionStep(
                    step_id="step_2",
                    description=f"执行 Python 文件: {file_path}",
                    tool_name="exec",
                    parameters={"command": f"python {file_path}"},
                    depends_on=["step_1"],
                    execution_mode=ExecutionMode.SUBAGENT,
                    estimated_duration_seconds=30,
                    subagent_task=f"执行命令: python {file_path}",
                ))
        else:
            steps.append(ExecutionStep(
                step_id="step_1",
                description=f"执行: {user_message}",
                tool_name="exec",
                parameters={"command": user_message},
                depends_on=[],
                execution_mode=ExecutionMode.DIRECT,
                estimated_duration_seconds=10,
            ))
        
        return ExecutionPlan(
            steps=steps,
            original_request=user_message,
            requires_subagent=any(s.execution_mode == ExecutionMode.SUBAGENT for s in steps),
            reasoning="使用规则进行简单的任务分解",
        )

    def _extract_file_path(self, message: str) -> Optional[str]:
        patterns = [
            r'(/[^\s]+\.py)',
            r'(/[^\s]+\.sh)',
            r'(/[^\s]+\.js)',
        ]
        for pattern in patterns:
            match = re.search(pattern, message)
            if match:
                return match.group(1)
        return None
