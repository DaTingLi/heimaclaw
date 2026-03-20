# write_todos 工具实现规范

**版本**: v1.0
**实现日期**: 2026-03-20
**参考来源**: LangChain `agents/middleware/todo.py`

---

## 1. 设计概述

参考 LangChain 的 `TodoListMiddleware`，在 Heimaclaw 中实现完整的 `write_todos` 工具，
让 LLM 能够自主创建、管理和更新任务列表，实现智能任务规划。

## 2. 架构

```
用户消息
    |
    v
LLM（具备 write_todos 工具）
    |
    ├── write_todos([{content, status}, ...])
    |       |
    |       v
    |   TodoManager（状态管理）
    |       ├── validate_todos()  验证格式
    |       ├── update_todos()    更新状态
    |       ├── get_progress()    查询进度
    |       └── format_display()  格式化显示
    |
    ├── exec/read_file/write_file（执行工具）
    |
    └── 回复用户
```

## 3. 核心类型

### 3.1 Todo

```python
class Todo(TypedDict):
    content: str                                  # 任务内容
    status: Literal["pending", "in_progress", "completed"]  # 状态
```

### 3.2 任务状态流转

```
pending ──► in_progress ──► completed
                              │
                              ├── 遇到错误 ──► 保持 in_progress
                              └── 需要新任务 ──► 创建新 pending 任务
```

## 4. 工具定义

### 4.1 OpenAI 格式

```json
{
  "name": "write_todos",
  "parameters": {
    "type": "object",
    "properties": {
      "todos": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "content": {"type": "string"},
            "status": {"type": "string", "enum": ["pending", "in_progress", "completed"]}
          },
          "required": ["content", "status"]
        }
      }
    },
    "required": ["todos"]
  }
}
```

### 4.2 使用规则（完整版，参考 LangChain）

| 场景 | 是否使用 write_todos |
|------|---------------------|
| 复杂多步骤任务（>=3步） | ✓ 必须使用 |
| 非平凡复杂任务 | ✓ 使用 |
| 用户明确要求 | ✓ 必须使用 |
| 用户提供多个任务 | ✓ 必须使用 |
| 计划可能需要修订 | ✓ 使用 |
| 单一简单任务 | ✗ 不使用 |
| 可在3步内完成 | ✗ 不使用 |
| 纯对话/信息查询 | ✗ 不使用 |

## 5. 核心规则（参考 LangChain WRITE_TODOS_TOOL_DESCRIPTION）

### 5.1 状态管理规则

1. **开始前标记**: 开始任务前立即标记为 `in_progress`
2. **即时完成**: 完成任务后立即标记为 `completed`，不要批量
3. **错误保持**: 遇到错误保持 `in_progress`，创建新任务描述问题
4. **唯一进行**: 每个模型轮次只能调用一次 `write_todos`
5. **持续进行**: 除非全部完成，否则至少一个 `in_progress`

### 5.2 完成标准

只有满足以下所有条件才能标记 `completed`：
- 完全完成任务
- 没有未解决的问题或错误
- 工作完整，不是部分完成
- 没有阻塞因素

### 5.3 防并行调用

参考 LangChain `after_model` 检查：
```python
# 检查同一轮次是否有多个 write_todos 调用
write_todos_calls = [tc for tc in tool_calls if tc["name"] == "write_todos"]
if len(write_todos_calls) > 1:
    return error("write_todos 不应并行调用")
```

## 6. 文件结构

```
src/heimaclaw/agent/todos/
    __init__.py          # 模块导出
    types.py             # Todo 类型 + 工具定义
    manager.py           # TodoManager 状态管理
    tool_handler.py      # write_todos 异步处理函数
```

## 7. 集成方式

在 `runner.py` 的 `_register_all_tools()` 中注册：

```python
from heimaclaw.agent.todos.types import get_write_todos_definition
from heimaclaw.agent.todos.tool_handler import write_todos_handler

write_todos_def = get_write_todos_definition()
registry.register(
    name=write_todos_def["name"],
    description=write_todos_def["description"],
    handler=write_todos_handler,
    parameters=write_todos_def["parameters"],
    timeout_ms=5000,
)
```

## 8. 与 Planner 的关系

| 组件 | 职责 | 使用方式 |
|------|------|---------|
| Planner | 初始任务分解 | 自动调用，生成步骤列表 |
| write_todos | 动态任务管理 | LLM 自主决定何时调用 |
| ReAct Engine | 执行步骤 | 按步骤执行工具调用 |

### 8.1 推荐流程

```
用户消息
    |
    v
LLM 第1轮: write_todos（创建任务列表）
    |
    v
LLM 第2轮: 执行第1个任务
    |
    v
LLM 第3轮: write_todos（更新进度，标记第1个完成，第2个进行中）
    |
    v
LLM 第4轮: 执行第2个任务
    |
    v
LLM 第5轮: write_todos（全部完成）+ 回复用户
```

## 9. LangChain 源码参考

| LangChain 组件 | Heimaclaw 对应 |
|---------------|---------------|
| `TodoListMiddleware` | `todos/` 模块 |
| `Todo` TypedDict | `todos/types.py` Todo 类 |
| `PlanningState` | `todos/types.py` PlanningState |
| `write_todos` @tool | `todos/tool_handler.py` write_todos_handler |
| `after_model` 并行检查 | `todos/manager.py` validate_todos |
| `WRITE_TODOS_TOOL_DESCRIPTION` | `todos/types.py` WRITE_TODOS_TOOL_DESCRIPTION |
| System Prompt 注入 | LLM System Prompt 中说明 |

## 10. 后续优化方向

1. **并行调用防护**: 在 ReAct 引擎层面检测并阻止并行 write_todos
2. **System Prompt**: 将 write_todos 使用规则注入到 System Prompt
3. **会话隔离**: 每个 session 独立的 TodoManager 实例
4. **持久化**: 任务列表保存到文件，跨会话恢复
