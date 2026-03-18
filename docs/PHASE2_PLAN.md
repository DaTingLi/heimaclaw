# Phase 2: 记忆系统规划

## 🎯 目标

构建工业级的4层记忆系统，实现智能上下文管理和 Token 预算控制。

---

## 📋 架构设计

### 4层记忆架构

```
┌─────────────────────────────────────────────┐
│ Level 1: 会话记忆（Session Memory）         │
│ - 当前会话完整消息历史                      │
│ - 保留：7天                                │
│ - 大小：1000条消息                          │
│ - 存储：~/.heimaclaw/data/sessions/         │
└─────────────────────────────────────────────┘
         ↓ 压缩
┌─────────────────────────────────────────────┐
│ Level 2: 日常记忆（Daily Memory）           │
│ - 每天的关键事件总结                        │
│ - 保留：30天                               │
│ - 压缩比：1000条 → 1个总结                  │
│ - 存储：~/.heimaclaw/agents/{agent}/memory/ │
└─────────────────────────────────────────────┘
         ↓ 提炼
┌─────────────────────────────────────────────┐
│ Level 3: 长期记忆（Long-term Memory）       │
│ - 重要事件、用户画像、项目信息              │
│ - 保留：永久                                │
│ - 容量：100KB（自动压缩）                   │
│ - 存储：~/.heimaclaw/agents/{agent}/MEMORY.md│
└─────────────────────────────────────────────┘
         ↓ 向量化
┌─────────────────────────────────────────────┐
│ Level 4: 向量记忆（Vector Memory）          │
│ - 语义检索相关记忆                          │
│ - 索引：FAISS / ChromaDB                    │
│ - 检索速度：< 10ms                          │
│ - 存储：~/.heimaclaw/data/vectors/          │
└─────────────────────────────────────────────┘
```

---

## 📐 模块设计

### 2.1 记忆管理器（MemoryManager）
**位置**：`src/heimaclaw/memory/manager.py`
**职责**：
- 统一管理4层记忆
- 消息添加和检索
- 记忆压缩和清理
- Token 预算控制

**核心方法**：
```python
class MemoryManager:
    async def add_message(message: Message) -> None
    async def get_context(query: str, max_tokens: int) -> Context
    async def compress_session() -> str
    async def extract_important() -> list[Event]
    async def search_vectors(query: str, top_k: int) -> list[Memory]
```

### 2.2 会话记忆（SessionMemory）
**位置**：`src/heimaclaw/memory/session.py`
**职责**：
- 存储当前会话的完整消息历史
- 快速访问最近消息
- 自动过期清理

**存储格式**：
```json
{
  "session_id": "xxx",
  "messages": [
    {"role": "user", "content": "...", "timestamp": 1234567890},
    {"role": "assistant", "content": "...", "timestamp": 1234567891}
  ],
  "created_at": 1234567890,
  "updated_at": 1234567900
}
```

### 2.3 日常记忆（DailyMemory）
**位置**：`src/heimaclaw/memory/daily.py`
**职责**：
- 每天的关键事件总结
- Markdown 格式存储
- 自动压缩

**存储格式**：
```markdown
# 2026-03-19 - Daily Memory

## 📋 今日事件

### 重要事件
- 事件1描述
- 事件2描述

## 💬 重要对话

- 用户偏好：xxx
- 关键决策：xxx
```

### 2.4 长期记忆（LongTermMemory）
**位置**：`src/heimaclaw/memory/longterm.py`
**职责**：
- 重要事件永久保存
- 用户画像管理
- 项目信息记录

**存储格式**：
```markdown
# MEMORY.md

## 🎯 核心定位

## 👤 用户画像

## 📅 重要事件

## 💡 学到的经验
```

### 2.5 向量记忆（VectorMemory）
**位置**：`src/heimaclaw/memory/vector.py`
**职责**：
- 语义检索
- 向量索引
- 相似度计算

**技术栈**：
- 可选：FAISS 或 ChromaDB
- 嵌入模型：可选（如 OpenAI Embeddings）

### 2.6 Token 预算管理（ContextBudget）
**位置**：`src/heimaclaw/memory/budget.py`
**职责**：
- Token 预算分配
- 上下文裁剪
- 压缩策略

**预算分配**：
```
总预算：128K tokens
├─ 系统提示：2K
├─ 最近消息：10K
├─ 日常记忆：5K
├─ 长期记忆：8K
├─ 用户画像：2K
├─ 工具定义：50K
└─ 响应预留：50K
```

### 2.7 上下文压缩（ContextCompressor）
**位置**：`src/heimaclaw/memory/compressor.py`
**职责**：
- 会话压缩
- 智能摘要
- 保留关键信息

**压缩策略**：
1. 提取重要消息
2. 生成摘要
3. 保留关键实体
4. 记录决策结果

---

## 🔄 工作流程

### 消息添加流程
```
用户消息
  ↓
1. 写入会话记忆（Level 1）
  ↓
2. 检查是否需要压缩
  ↓ (每100条)
3. 压缩到日常记忆（Level 2）
  ↓
4. 提取重要事件
  ↓
5. 写入长期记忆（Level 3）
  ↓
6. 向量化存储（Level 4）
```

### 上下文检索流程
```
用户查询
  ↓
1. 获取最近10条消息（Level 1）
  ↓
2. 获取今天的日常记忆（Level 2）
  ↓
3. 向量检索相关记忆（Level 4）
  ↓
4. 获取用户画像和长期记忆（Level 3）
  ↓
5. Token 预算分配
  ↓
6. 组装最终上下文
```

---

## 📊 Token 预算管理

### 分配策略
```python
class ContextBudget:
    def __init__(self, max_tokens: int = 128000):
        self.allocations = {
            "system_prompt": 2000,
            "recent_messages": 10000,
            "daily_memory": 5000,
            "longterm_memory": 8000,
            "user_profile": 2000,
            "tools": 50000,
            "response": 50000,
        }
    
    def allocate(self, context: dict) -> dict:
        """按预算分配上下文"""
        result = {}
        for key, budget in self.allocations.items():
            content = context.get(key, "")
            tokens = count_tokens(content)
            
            if tokens > budget:
                # 压缩或裁剪
                content = self._compress(content, budget)
            
            result[key] = content
        
        return result
```

### 压缩策略
1. **系统提示**：不可压缩
2. **最近消息**：保留最近N条
3. **日常记忆**：摘要压缩
4. **长期记忆**：提取关键信息
5. **工具定义**：按需加载
6. **响应预留**：固定大小

---

## 🧪 测试计划

### 单元测试
- [ ] `test_session_memory.py`
- [ ] `test_daily_memory.py`
- [ ] `test_longterm_memory.py`
- [ ] `test_vector_memory.py`（可选）
- [ ] `test_context_budget.py`
- [ ] `test_context_compressor.py`
- [ ] `test_memory_manager.py`

### 集成测试
- [ ] 完整流程测试
- [ ] 性能测试
- [ ] Token 预算测试
- [ ] 压缩效果测试

---

## 📅 时间安排

### Phase 2.1: 记忆管理器（1天）
- [ ] SessionMemory
- [ ] DailyMemory
- [ ] LongTermMemory
- [ ] 单元测试

### Phase 2.2: Token 预算管理（0.5天）
- [ ] ContextBudget
- [ ] ContextCompressor
- [ ] 单元测试

### Phase 2.3: 向量检索（0.5天，可选）
- [ ] VectorMemory
- [ ] FAISS 集成
- [ ] 单元测试

### Phase 2.4: 集成和文档（0.5天）
- [ ] MemoryManager
- [ ] 集成测试
- [ ] 使用文档

---

## ✅ 成功标准

### 功能标准
- ✅ 4层记忆完整实现
- ✅ Token 预算控制有效
- ✅ 压缩比 > 10:1
- ✅ 检索速度 < 10ms

### 质量标准
- ✅ 测试覆盖率 > 80%
- ✅ 类型提示完整
- ✅ 文档完整

### 性能标准
- ✅ 上下文组装 < 100ms
- ✅ 记忆压缩 < 500ms
- ✅ 向量检索 < 10ms

---

## 🔧 技术栈

### 核心依赖
- Python 3.10+
- asyncio
- dataclasses

### 可选依赖
- FAISS 或 ChromaDB（向量检索）
- tiktoken（Token 计数）
- OpenAI Embeddings（向量化）

---

## 📝 注意事项

### 设计原则
1. **渐进式**：Level 4 向量检索为可选
2. **可配置**：Token 预算可调整
3. **向后兼容**：不影响现有功能
4. **可扩展**：易于添加新的记忆层

### 性能考虑
1. **异步操作**：使用 asyncio 提高性能
2. **缓存机制**：避免重复计算
3. **懒加载**：按需加载记忆
4. **批量处理**：批量向量化

---

_Phase 2 规划完成，准备开始实施！_ 🚀
