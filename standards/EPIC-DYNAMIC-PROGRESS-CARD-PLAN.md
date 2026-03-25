# 核心特性架构设计方案：基于飞书动态卡片的 Agent 实时进度播报

**文档状态**: 预研阶段 (Tech Spike)
**设计原则**: 绝对隔离、非侵入式修改、防御性编程 (Fail-Safe)
**目标**: 让大模型在调用 `write_todos` 规划和执行任务时，飞书端能有一张**动态刷新**的进度条卡片，实现类似 Claude/Devin 的极致交互体验，且**绝不阻塞或破坏**现有大模型核心推理链路。

---

## 1. 当前代码架构的瓶颈与风险评估

在动手前，必须清晰认知目前系统存在的客观限制（基于真实代码扫描）：

| 模块 | 现状事实 | 改造风险评级 | 应对策略 |
| :--- | :--- | :--- | :--- |
| **通信层** (`FeishuAdapter`) | 目前仅实现了 `send_card` 和 `send_message` (POST 请求)。缺乏更新已有消息的能力。 | **低** | 按照飞书开放平台文档，安全追加一个 `PATCH /open-apis/im/v1/messages/{message_id}` 接口方法，完全不影响现有发信逻辑。 |
| **核心层** (`EventBus`) | `agent/runner.py` 第 41 行显示 `EventBus` 被强行注释禁用，且历史代码基于高 IO 的 JSONL 文件落盘。 | **高** (易引发死锁/IO阻塞) | **放弃强行复活全量 EventBus！** 改为在 `SessionManager` 或 `AgentRunner` 中实现一个极轻量级的、纯内存的 `asyncio.Queue` 或回调机制 (UI EventEmitter)，切断与历史遗留问题的耦合。 |
| **工具层** (`write_todos`) | `tool_handler.py` 内部逻辑闭环，状态更新后 `return`，外部无法感知内部状态跃迁。 | **低** | 在 `write_todos_handler` 增加一个可选的非阻塞回调函数注入点。 |
| **调度层** (`AgentRunner`) | 核心推理处于 `run_in_executor` 的线程池中，高度敏感。 | **极高** | 状态更新的动作必须是**异步且非阻塞的 (Fire and Forget)**。即便飞书 API 报错或超时，也绝不能让大模型的思考停滞。 |

---

## 2. 颗粒度极细的无损落地方案 (Actionable Blueprint)

为了保证“不影响已有系统”，我们采用**旁路监听 (Bypass Observer)** 模式进行改造。按照以下 4 个阶段进行：

### 阶段一：基础设施扩充（飞书 API 层）
**目标文件**: `src/heimaclaw/channel/feishu.py`
**具体动作**: 
1. 在 `FeishuAdapter` 类中新增 `update_card` 异步方法。
2. 核心逻辑：获取飞书 `tenant_access_token`，构造 `PATCH` 请求。
```python
# 伪代码参考 (不影响现有任何代码)：
async def update_card(self, message_id: str, card: dict) -> bool:
    """按飞书 API 规范更新已有卡片"""
    url = f"https://open.feishu.cn/open-apis/im/v1/messages/{message_id}"
    payload = {"content": json.dumps(card)}
    # 使用 httpx 发送 PATCH 请求，并包裹在 try-except 中，失败不抛出异常。
```

### 阶段二：建立极轻量 UI 事件通道（内存状态层）
**目标文件**: `src/heimaclaw/agent/runner.py` 与 `src/heimaclaw/agent/todos/tool_handler.py`
**具体动作**:
1. 避开有历史包袱的 `EventBus`，我们在 `Session` 对象或 `MemoryManager` 中挂载一个轻量的回调函数列表。
2. 让 `write_todos_handler` 接收一个全局或上下文注入的 `on_progress_update` 回调。
```python
# 伪代码参考 (工具层)：
async def write_todos_handler(todos: list[dict]):
    # ... 原有校验和更新逻辑 ...
    updated_todos = manager.update_todos(todos)
    
    # 【新增旁路触发】
    from heimaclaw.core.ui_events import dispatch_progress
    dispatch_progress(updated_todos) # 纯内存派发，瞬间返回
    return "Todos updated."
```

### 阶段三：卡片生命周期管理（会话调度层）
**目标文件**: `src/heimaclaw/agent/runner.py` -> `process_message` 方法
**具体动作**:
1. 当用户发来需求，大模型开始 `_execute_loop` **之前**，先调用 `send_card` 发送一张初始进度的飞书卡片（如：“⏳ 智能体正在解析需求...”）。
2. 获取飞书返回的 `message_id`，并将其持久化到当前 `session.context["progress_msg_id"]` 中。
3. 启动一个后台监听 Task（与 `_execute_loop` 并行运行）。

### 阶段四：状态渲染与节流保护（表现层）
**具体动作**:
1. 当后台监听 Task 收到 `dispatch_progress` 发来的 `updated_todos` 数据时，进入渲染逻辑。
2. **UI 渲染**：将 `pending`、`in_progress`、`completed` 状态转换为飞书的 Markdown 语法（例如：✅ 表示完成，⏳ 表示进行中）。
3. **节流保护 (Throttling / Debounce)**：这是**最关键的防崩溃设计**。大模型可能在 1 秒内连续调用 3 次工具，如果直接请求飞书接口，会触发飞书开放平台的 `Rate Limit` 封控。必须引入 `asyncio.sleep(1)` 或节流阀，确保每 2 秒最多只发送一次 `update_card` 请求。

---

## 3. 为什么这个方案是“极致工业级”的？

1. **绝对防呆 (Fail-Safe)**：我们完全绕开了历史遗留的 `EventBus`（不用承担落盘 IO 死锁的风险）。即使飞书网络波动导致卡片更新失败，由于采用了后台独立 Task 发送请求，大模型的核心思考线程 (`run_in_executor`) 不会受到哪怕 1 毫秒的阻塞。
2. **高内聚低耦合**：`FeishuAdapter` 只管发 HTTP 请求；`write_todos` 只管触发一个内存钩子；业务装配全部在 `AgentRunner` 内完成。哪一个环节出问题，直接把那几行钩子代码注释掉，系统瞬间退回原有状态，风险为零。
3. **真实体验越级**：用户在飞书中看到的不再是一片死寂，而是真实可感的任务被一个个“打钩”的过程，这将极大掩盖大模型“思考时间过长”带来的体验焦虑。

---

**下一步建议**：
您可以花点时间审阅这份文档中的架构逻辑（特别是第一阶段对飞书 PATCH 接口的扩展，和第四阶段的防刷屏节流保护）。如果您觉得方案完全可控，我们再制定具体的代码实施步骤。