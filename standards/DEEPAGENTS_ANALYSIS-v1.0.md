# DeepAgents 源码分析

**版本**: v1.0
**分析日期**: 2026-03-20
**参考来源**: `/root/dt/ai_coding/heimaclaw/reference/deepagents-main`

---

## 1. 核心架构概览

```
┌─────────────────────────────────────────────────────────────┐
│                     Deep Agent (create_deep_agent)           │
│                                                              │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐     │
│  │   Executor  │───►│  Supervisor │───►│   Worker    │     │
│  │             │◄───│  (LLM)     │◄───│  (Tool)     │     │
│  └─────────────┘    └─────────────┘    └─────────────┘     │
└─────────────────────────────────────────────────────────────┘
                           │
              ┌────────────┴────────────┐
              │     Backend (execute)   │
              └─────────────────────────┘
```

---

## 2. Backend 接口设计

### 2.1 LocalShellBackend

```python
class LocalShellBackend:
    def execute(
        command: str,
        cwd: str | None = None,
        env: dict | None = None,
        timeout: int = 120,           # 默认 120s 超时
        max_output_bytes: int = 100_000,  # 最大输出 100KB
    ) -> ToolResult:
        # 1. subprocess.run 执行
        # 2. 捕获 stdout/stderr
        # 3. 截断大输出
```

---

## 3. 异步子代理机制 (async_subagents)

### 3.1 核心原则

```
✓ 启动后台任务后立即返回 job_id
✓ 不自动轮询检查状态
✓ 只在用户明确要求时检查
✓ job_id 保存在 agent state 中
```

### 3.2 工具列表

| 工具 | 功能 |
|------|------|
| `launch_async_subagent` | 启动后台任务，立即返回 job_id |
| `check_async_subagent` | 检查任务状态/结果 |
| `cancel_async_subagent` | 取消任务 |

### 3.3 工作流程

```
用户: "部署网站"
Agent: launch_async_subagent(task="部署")
      → 返回 "job_id: abc123"

用户: "任务完成了吗？"
Agent: check_async_subagent(job_id="abc123")
      → 返回 {status: "success", result: "完成！"}
```

---

## 4. 对 Heimaclaw 的启发

### 4.1 简化子代理

```
之前：事件驱动（复杂、不稳定）
现在：job_id 追踪 + 状态注册表
```

### 4.2 借鉴点

| 特性 | DeepAgents | Heimaclaw |
|------|-----------|-----------|
| 子代理 | job_id 追踪 | Registry |
| 执行超时 | subprocess(timeout) | asyncio.wait_for |
| 大输出 | 截断 | 实现限制 |
| 异步模式 | 立即返回 | 类似 |

---

## 8. 记忆机制 (MemoryMiddleware)

### 8.1 核心设计

```
启动时加载 AGENTS.md 文件 → 注入到 System Prompt
    ↓
Agent 执行时可以看到记忆内容
    ↓
Agent 学到新知识 → 调用 edit_file 更新 AGENTS.md
```

### 8.2 实现代码

```python
class MemoryMiddleware:
    def __init__(self, backend, sources=["~/.deepagents/AGENTS.md"]):
        self.backend = backend
        self.sources = sources
    
    def before_agent(self, state, runtime, config):
        # 从文件系统加载记忆文件
        contents = self.backend.download_files(self.sources)
        return {"memory_contents": contents}
    
    def modify_request(self, request):
        # 注入到 System Prompt
        memory = self._format_agent_memory(contents)
        request.system_message += memory
```

### 8.3 记忆指南 (Agent 行为规则)

```
1. 学习优先级：用户的反馈/偏好必须立即记忆
2. 第一行动：需要记忆时，先更新记忆再响应用户
3. 编码模式：不要只修复具体错误，要记住背后的原则
4. 安全底线：绝不存储 API keys、密码等凭证
```

### 8.4 Store Backend - 持久化存储

```python
# LangGraph 的 BaseStore 用于跨会话持久化
StoreBackend:
    - 上传文件到 Store
    - 下载文件从 Store
    - 支持 v1/v2 格式
```

### 8.5 对 Heimaclaw 的启发

```
Heimaclaw 可以这样实现记忆：

1. 启动时加载 ~/.heimaclaw/AGENTS.md
2. 记忆内容注入到 System Prompt
3. Agent 学到新知识 → 更新记忆文件
4. 可选：实现 Store Backend 跨会话持久化
```

**与我们现有的 memory/ 目录设计一致！**
