# Heimaclaw 架构文档 v1.0

> 基于实际代码的架构说明

---

## 一、当前实现

### 1.1 核心技术栈

| 组件 | 版本 | 说明 |
|------|------|------|
| Python | 3.12.13 | 运行环境 |
| DeepAgents | 0.5.0 | 核心 Agent 框架 |
| LangGraph | 1.1.3 | 状态图执行引擎 |
| LangChain | 1.2.13 | LLM 工具链 |
| TodoListMiddleware | 内置 | 自动 write_todos 注入 |

### 1.2 Agent 实现

**文件**: `src/heimaclaw/agent/deepagents_wrapper.py`

```python
class DeepAgentsWrapper:
    def __init__(self, base_url, api_key, model_name):
        self.base_url = base_url
        self.api_key = api_key
        self.model_name = model_name
        self._agent = None
    
    async def initialize(self):
        from deepagents import create_deep_agent
        from deepagents.backends import LocalShellBackend
        
        # 1. 创建 LLM
        llm = ChatOpenAI(
            model=self.model_name,
            base_url=self.base_url,
            api_key=self.api_key,
            temperature=0.7,
            max_tokens=8192,
        )
        
        # 2. 创建 Backend (LocalShellBackend)
        backend = LocalShellBackend(
            root_dir="./heimaclaw_workspace",
            env=os.environ.copy(),
            virtual_mode=True,  # 虚拟模式
        )
        
        # 3. 创建 Agent
        self._agent = create_deep_agent(
            model=llm,
            backend=backend,
            system_prompt=SYSTEM_PROMPT,
        )
```

### 1.3 System Prompt

**文件**: `src/heimaclaw/agent/deepagents_wrapper.py`

```python
SYSTEM_PROMPT = """你是 HeimaClaw 高级智能助手。

对于**任何**用户需求，你必须：
1. **第一步自动调用 write_todos 工具**，把任务拆解成清晰的 To-Do List（带状态）。
2. 根据需要**自主生成任意数量的 subagent**（名字、职责你自己决定）。
3. 所有文件操作严格限制在 ./heimaclaw_workspace 目录内。
4. 最后用中文完整总结过程和结果。

使用中文思考和回复。"""
```

---

## 二、执行流程

```
用户消息
    ↓
Runner._execute_loop()
    ↓
DeepAgentsWrapper.run(user_message)
    ↓
create_deep_agent() → StateGraph
    ↓
LangGraph 状态机自动执行：
    ┌─────────────────────────────────────┐
    │  LLM (GLM-5)                       │
    │    ↓                                │
    │  判断是否需要调用工具                 │
    │    ↓                                │
    │  如果有 tool_calls:                  │
    │    → LocalShellBackend.execute()    │
    │    → 返回 ToolMessage               │
    │    → 循环直到完成                   │
    │                                     │
    │  如果没有 tool_calls:                │
    │    → 返回最终结果                   │
    └─────────────────────────────────────┘
    ↓
返回结果给用户
```

---

## 三、关键组件

### 3.1 DeepAgents (真正的 create_deep_agent)

- **来源**: `from deepagents import create_deep_agent`
- **作用**: 创建 LangGraph StateGraph，自动管理工具调用循环
- **特点**: 
  - 内置递归限制
  - 自动状态管理
  - TodoListMiddleware 集成

### 3.2 LocalShellBackend

- **来源**: `from deepagents.backends import LocalShellBackend`
- **作用**: 执行 shell 命令的后端
- **参数**:
  - `root_dir`: 工作目录
  - `virtual_mode`: 虚拟模式（True=不真实执行）

### 3.3 TodoListMiddleware

- **来源**: `from langchain.agents.middleware import TodoListMiddleware`
- **作用**: 自动注入 write_todos 工具和提示

---

## 四、与旧版本对比

| 特性 | 旧版 (ReAct) | 新版 (DeepAgents) |
|------|--------------|------------------|
| 工具循环 | 手动 while 循环 | StateGraph 自动 |
| 递归控制 | max_depth 限制 | 内置 recursion_limit |
| 状态管理 | 手动 history 列表 | StateGraph 自动 |
| 停止条件 | 手动判断 | 自动检测 |
| write_todos | 手动调用 | Middleware 自动注入 |

---

## 五、启动方式

```bash
# 使用 Python 3.12 启动
cd /root/dt/ai_coding/heimaclaw
nohup heimaclaw start > logs/heimaclaw.log 2>&1 &

# 日志查看
tail -f logs/heimaclaw.log
```

### 启动日志确认

```
[Runner] DeepAgents 初始化成功
[DeepAgentsWrapper] 初始化完成 (create_deep_agent + LocalShellBackend)
```

---

## 六、相关文件

| 文件 | 说明 |
|------|------|
| `src/heimaclaw/agent/deepagents_wrapper.py` | DeepAgents 封装器 |
| `src/heimaclaw/agent/runner.py` | Agent 执行器入口 |
| `src/heimaclaw/agent/tools/write_tool.py` | write_file 工具 |
| `src/heimaclaw/agent/todos/tool_handler.py` | write_todos 处理器 |
| `src/heimaclaw/memory/manager.py` | 记忆管理 |

---

## 七、Python 3.12 环境

```bash
# 查看版本
python3.12 --version

# 安装的包
pip list | grep -E "deepagents|langgraph|langchain"
```

---

## 八、已知问题

### 8.1 virtual_mode=True

当前 LocalShellBackend 使用 `virtual_mode=True`，这意味着命令不会真实执行。如果需要真实执行，需要改为 `virtual_mode=False` 并确保安全。

### 8.2 API Key

API Key 通过 `DeepAgentsWrapper.__init__` 传入，实际值来自 `runner.py` 中的 `_llm_adapter.config.api_key`。

---

_文档更新时间: 2026-03-20_
