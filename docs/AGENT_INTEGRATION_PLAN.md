# Agent 运行时集成计划

## 目标
将 MemoryManager 集成到 AgentRunner，实现对话时自动使用记忆

## 当前架构

```
AgentRunner.run()
  ↓
self.session_manager.add_message()
  ↓
self.llm.chat()
  ↓
self.sender.send()
```

## 目标架构

```
AgentRunner.run()
  ↓
self.memory_manager.add_message()  ← 记录消息到记忆
  ↓
context = self.memory_manager.get_context_for_llm()  ← 获取上下文
  ↓
self.llm.chat(context)  ← 使用上下文
  ↓
self.memory_manager.add_message()  ← 记录回复
  ↓
self.sender.send()
```

## 集成步骤

### Step 1: 修改 AgentRunner 初始化
```python
# 添加 MemoryManager
from heimaclaw.memory import MemoryManager

class AgentRunner:
    def __init__(self, ...):
        # 现有代码...
        
        # 添加 MemoryManager
        self.memory_manager = MemoryManager(
            agent_id=self.agent_id,
            session_id=session_id,
            channel=self.channel,
            user_id=user_id,
        )
```

### Step 2: 修改 run 方法
```python
async def run(self, user_message: str):
    # 1. 添加用户消息到记忆
    self.memory_manager.add_message("user", user_message)
    
    # 2. 获取上下文
    context = self.memory_manager.get_context_for_llm()
    
    # 3. 调用 LLM
    response = await self.llm.chat(
        messages=context["messages"],
        system_prompt=context["system_prompt"],
    )
    
    # 4. 添加回复到记忆
    self.memory_manager.add_message("assistant", response.content)
    
    # 5. 发送回复
    await self.sender.send(response.content)
```

### Step 3: 测试
- 单元测试
- 集成测试
- 端到端测试

## 预计时间
- 开发：1-2 小时
- 测试：1 小时
- 文档：30 分钟
- 总计：2-3 小时

## 成功标准
- 对话自动记录到记忆
- 上下文自动组装
- Token 预算有效控制
- 所有测试通过
