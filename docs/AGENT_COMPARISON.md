# HeiMaClaw vs OpenClaw vs pi-mono 核心 Agent 实现对比

> 分析时间：2026-03-19

---

## 1. 架构对比

| 维度 | HeiMaClaw | OpenClaw | pi-mono |
|------|------------|----------|---------|
| **语言** | Python | TypeScript | TypeScript |
| **Agent 循环** | ReAct (简化版) | ACP + Event Bus | EventStream + 双 Loop |
| **会话管理** | SessionManager (内存) | Sessions (持久化) | AgentContext |
| **记忆系统** | MemoryManager (SQLite) | Memory (多种存储) | Context 实时管理 |
| **工具调用** | ReAct + Function Calling | Subagent 委托 | 同步工具调用 |
| **流式响应** | ❌ 无 | ✅ Streaming Card | ✅ streamSimple |
| **进度通知** | Typing Emoji | Real-time emoji | Event 驱动 |

---

## 2. 核心差异详解

### 2.1 Agent Loop 实现

**pi-mono (参考实现)**：
```typescript
// 双层 Loop：外层消息队列，内层工具执行
export function agentLoop(prompts, context, config, signal?, streamFn?):
  EventStream<AgentEvent, AgentMessage[]>
  
// 关键特性：
// 1. EventStream - 事件流驱动的响应
// 2. streamSimple - LLM 流式输出
// 3. abortSignal - 可取消的异步操作
// 4. toolResult 消息自动追加
```

**HeiMaClaw (当前实现)**：
```python
# 简化版 ReAct
class ReActEngine:
    MAX_ITERATIONS = 3
    
    async def execute(self, user_message, context):
        # 问题：
        # 1. 没有 EventStream
        # 2. 没有流式输出
        # 3. 工具结果追加逻辑不完善
```

### 2.2 会话管理

**OpenClaw**：
```typescript
// 持久化会话 + 会话 ID
interface Session {
  id: string
  agentId: string
  createdAt: number
  messages: Message[]
  context: Context
  metadata: Record<string, any>
}
```

**HeiMaClaw**：
```python
# 内存会话 + 自动生成 ID
class Session:
    session_id: str  # uuid4[:8]
    # 问题：每次重启会话丢失
```

### 2.3 工具执行

**OpenClaw**：
```typescript
// 通过 Subagent 委托执行
class SubagentManager {
  async spawn(config: SpawnConfig): Promise<SpawnResult>
  // 特点：
  // 1. 独立进程执行
  // 2. 通过 Event Bus 协调
  // 3. 支持后台任务
}
```

**HeiMaClaw**：
```python
# 直接在主进程执行
class ReActEngine:
    async def _execute_tools(self, tool_calls):
        for tool_call in tool_calls:
            result = await self.tool_registry.execute(...)
        # 问题：
        # 1. 阻塞主进程
        # 2. 没有并行执行
        # 3. 没有超时控制
```

### 2.4 记忆系统

**OpenClaw**：
```typescript
// 多层记忆 + 自动摘要
class Memory {
  // 1. workingMemory - 当前会话
  // 2. episodicMemory - 长期记忆
  // 3. semanticMemory - 知识库
  // 4. 自动摘要 + 检索
}
```

**HeiMaClaw**：
```python
# SQLite 存储 + 自动摘要
class MemoryManager:
    def get_context_for_llm(self, max_messages=50):
        # 问题：
        # 1. 没有多层次记忆
        # 2. 摘要需要 LLM 支持
        # 3. 上下文窗口有限
```

---

## 3. 效果差距原因

### 3.1 LLM 支持

| 功能 | OpenClaw | HeiMaClaw |
|------|----------|------------|
| **模型** | Claude Sonnet 4.6 | GLM-4.0520 |
| **Function Calling** | ✅ 原生支持 | ⚠️ 部分支持 |
| **流式输出** | ✅ | ❌ |
| **工具调用稳定性** | 高 | 低 |

### 3.2 错误处理

**OpenClaw**：
```typescript
// 完善的错误处理 + 重试机制
async function runAgentLoop(...) {
  try {
    // 完整的错误捕获
  } catch (error) {
    // 分类处理：
    // - 速率限制 -> 退避重试
    // - 会话过期 -> 刷新上下文
    // - LLM 错误 -> 降级策略
  }
}
```

**HeiMaClaw**：
```python
# 简化错误处理
try:
    result = await self._react_engine.execute(...)
except Exception as e:
    return {"error": str(e)}
# 问题：没有重试、没有降级
```

### 3.3 实时反馈

**OpenClaw**：
```typescript
// Typing Indicator + 进度更新
const typing = await addTypingIndicator({ messageId })
// 定期更新 emoji
// 完成后移除
```

**HeiMaClaw**：
```python
# 开始时添加，结束时移除
typing_reaction_id = await adapter.add_typing_indicator(message_id)
# 没有定期更新
```

---

## 4. 改进建议

### 4.1 短期（1-2周）

1. **切换到 Claude 模型**
   - 支持完整 Function Calling
   - 更好的推理能力
   
2. **实现流式输出**
   - 参考 pi-mono 的 streamSimple
   - 实时显示生成内容

3. **会话持久化**
   - 将会话保存到 SQLite
   - 支持跨重启恢复

### 4.2 中期（1个月）

1. **EventBus 深度集成**
   - 工具执行事件记录
   - 子 Agent 派发支持

2. **多层记忆系统**
   - Working Memory
   - Episodic Memory
   - Semantic Memory

3. **完善错误处理**
   - 速率限制退避
   - 自动重试
   - 降级策略

### 4.3 长期（2-3个月）

1. **流式卡片响应**
   - 实时更新进度
   - 代码块渲染

2. **多 Agent 协作**
   - 专家 Agent
   - 任务分解

3. **个性化记忆**
   - 用户偏好学习
   - 历史任务记录

---

## 5. 关键文件对照

| 功能 | pi-mono | OpenClaw | HeiMaClaw |
|------|---------|----------|------------|
| Agent Loop | `agent-loop.ts` | `agents/agent.ts` | `agent/react.py` |
| Session | `AgentContext` | `sessions/sessions.ts` | `agent/session.py` |
| Memory | `Context` | `memory/memory.ts` | `memory/manager.py` |
| Tools | `AgentTool` | `tools/tool.ts` | `agent/tools/registry.py` |
| Events | `EventStream` | `events/event-bus.ts` | `core/event_bus.py` |
| Streaming | `streamSimple` | `streaming-card.ts` | ❌ 无 |

---

## 6. 结论

**HeiMaClaw 与 OpenClaw 的差距主要来自**：

1. **模型能力**：GLM vs Claude
2. **架构完善度**：简化 ReAct vs 完整 Event Bus
3. **工程化程度**：原型 vs 生产级
4. **迭代时间**：几个月 vs 几年

**建议优先改进**：
1. 切换到 Claude 模型
2. 实现流式输出
3. 会话持久化
