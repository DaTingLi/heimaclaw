# HeiMaClaw 混合配置系统方案

## 1. 双层配置系统

### 源配置（Markdown）- 开发友好
```
~/.heimaclaw/agents/my-agent/
├── agent.json           # 基础配置（保持兼容）
├── SOUL.md             # 核心定位（新增）
├── TOOLS.md            # 工具规范（新增）
├── IDENTITY.md         # 身份信息（新增）
├── USER.md             # 用户信息（新增）
├── MEMORY.md           # 长期记忆（新增）
└── memory/             # 日常记忆（新增）
    └── 2026-03-19.md
```

### 编译配置（JSON）- 性能优化
```
~/.heimaclaw/agents/my-agent/
└── .compiled/
    ├── agent.compiled.json    # 编译后的完整配置
    ├── memory.json            # 记忆索引
    └── context.json           # 上下文压缩
```

## 2. 记忆上下文系统（工业级）

### 分层记忆架构
```
Level 1: 会话记忆（Session）
  - 当前会话的完整消息历史
  - 存储位置：~/.heimaclaw/data/sessions/{session_id}.json
  - 保留时长：7 天（可配置）
  - 大小限制：1000 条消息

Level 2: 日常记忆（Daily）
  - 每天的关键事件总结
  - 存储位置：~/.heimaclaw/agents/{agent}/memory/YYYY-MM-DD.md
  - 保留时长：30 天（可配置）
  - 压缩比例：1000 条消息 → 1 天的总结

Level 3: 长期记忆（Long-term）
  - 重要事件、用户画像、项目信息
  - 存储位置：~/.heimaclaw/agents/{agent}/MEMORY.md
  - 保留时长：永久
  - 容量：100KB（自动压缩）

Level 4: 向量记忆（Vector）
  - 语义检索的相关记忆
  - 存储位置：~/.heimaclaw/data/vectors/
  - 索引：FAISS / ChromaDB
  - 检索速度：< 10ms
```

### 记忆管理策略
```python
class MemoryManager:
    """工业级记忆管理"""
    
    async def add_message(self, message: Message):
        """添加消息到记忆系统"""
        # 1. 写入会话记忆（Level 1）
        await self.session_memory.add(message)
        
        # 2. 实时压缩到日常记忆（Level 2）
        if should_summarize():
            summary = await self.compress_to_daily()
            await self.daily_memory.add(summary)
        
        # 3. 定期提取到长期记忆（Level 3）
        if is_important(message):
            await self.longterm_memory.add(message)
        
        # 4. 向量化存储（Level 4）
        await self.vector_memory.index(message)
    
    async def get_context(self, query: str) -> Context:
        """获取上下文（智能检索）"""
        context = Context()
        
        # 1. 完整的最近会话（最近 10 条）
        context.add(self.session_memory.get_recent(10))
        
        # 2. 今天的日常记忆
        context.add(self.daily_memory.get_today())
        
        # 3. 相关的长期记忆（向量检索）
        relevant = await self.vector_memory.search(query, top_k=5)
        context.add(relevant)
        
        # 4. 用户画像
        context.add(self.user_profile)
        
        return context
```

## 3. 配置编译器

### 编译流程
```python
class ConfigCompiler:
    """配置编译器：Markdown → JSON"""
    
    async def compile(self, agent_dir: Path):
        """编译 agent 配置"""
        config = {
            "metadata": self._load_agent_json(agent_dir),
            "soul": self._parse_soul_md(agent_dir / "SOUL.md"),
            "tools": self._parse_tools_md(agent_dir / "TOOLS.md"),
            "identity": self._parse_identity_md(agent_dir / "IDENTITY.md"),
            "user": self._parse_user_md(agent_dir / "USER.md"),
            "memory": await self._compile_memory(agent_dir),
        }
        
        # 保存编译后的配置
        output = agent_dir / ".compiled" / "agent.compiled.json"
        output.write_text(json.dumps(config, ensure_ascii=False, indent=2))
        
        return config
```

### CLI 命令
```bash
# 编译单个 agent
heimaclaw compile my-agent

# 编译所有 agent
heimaclaw compile --all

# 监听模式（自动编译）
heimaclaw compile --watch

# 增量编译（只编译修改的）
heimaclaw compile --incremental
```

## 4. 向后兼容

### 保持 JSON 配置
```json
// agent.json（保持不变）
{
  "name": "my-agent",
  "description": "Agent 描述",
  "channel": "feishu",
  "enabled": true,
  "llm": {
    "provider": "glm",
    "model_name": "glm-4-flash"
  }
}
```

### Markdown 扩展（可选）
```markdown
# SOUL.md（新增，可选）

如果没有 SOUL.md，则使用 agent.json 的 description
如果有 SOUL.md，则合并配置
```

## 5. 性能优化

### 编译缓存
```
.compiled/
├── agent.compiled.json
├── cache.json          # 缓存元数据
└── hashes.json         # 文件哈希（用于增量编译）
```

### 热重载
```python
class HotReloader:
    """热重载监听器"""
    
    async def watch(self, agent_dir: Path):
        """监听配置变化"""
        watcher = aionotify.Watcher()
        watcher.watch(agent_dir, aionotify.MODIFY)
        
        async for event in watcher:
            if event.name.endswith('.md'):
                # 增量编译
                await self.compiler.compile_incremental(agent_dir)
                
                # 通知 Agent 重载配置
                await self.notify_reload(agent_dir)
```

## 6. 记忆上下文处理（工业级）

### Token 预算管理
```python
class ContextBudget:
    """上下文 Token 预算管理"""
    
    def __init__(self, max_tokens: int = 128000):
        self.max_tokens = max_tokens
        self.allocations = {
            "system_prompt": 2000,
            "recent_messages": 10000,
            "daily_memory": 5000,
            "longterm_memory": 8000,
            "user_profile": 2000,
            "tools": 50000,
            "response": 50000,
        }
    
    def allocate(self, context: Context) -> Context:
        """按预算分配上下文"""
        total = 0
        result = Context()
        
        for key, budget in self.allocations.items():
            content = getattr(context, key)
            tokens = count_tokens(content)
            
            if tokens > budget:
                # 压缩内容
                content = self._compress(content, budget)
            
            result[key] = content
            total += min(tokens, budget)
        
        return result
```

### 智能压缩
```python
class ContextCompressor:
    """上下文智能压缩"""
    
    async def compress_session(self, messages: list[Message]) -> str:
        """压缩会话记忆"""
        # 使用 LLM 生成摘要
        prompt = f"""
        请总结以下对话的关键信息：
        
        {format_messages(messages)}
        
        要求：
        1. 提取重要决策和结果
        2. 保留用户偏好和习惯
        3. 记录待办事项
        4. 压缩到 500 字以内
        """
        
        summary = await self.llm.generate(prompt)
        return summary
```

## 7. 实施步骤

### Phase 1: 基础设施（1-2 天）
- [ ] 创建 Markdown 解析器
- [ ] 实现配置编译器
- [ ] 添加 CLI 命令

### Phase 2: 记忆系统（2-3 天）
- [ ] 实现分层记忆架构
- [ ] 添加上下文预算管理
- [ ] 集成向量检索（可选）

### Phase 3: 热重载（1 天）
- [ ] 实现文件监听
- [ ] 添加增量编译
- [ ] 配置自动重载

### Phase 4: 文档和测试（1-2 天）
- [ ] 编写使用文档
- [ ] 添加单元测试
- [ ] 性能基准测试

总计：5-8 天完成核心功能

## 8. 对比总结

| 特性 | OpenClaw | HeiMaClaw 当前 | HeiMaClaw 优化后 |
|------|----------|---------------|-----------------|
| 配置易用性 | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ |
| 启动性能 | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| 安全隔离 | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| 记忆系统 | ⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐⭐ |
| 个性化 | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ |
| 上下文管理 | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ |
| 工业级 | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |

## 9. 最终效果

### 开发体验（易用性）
```bash
# 创建新 agent
heimaclaw create my-agent

# 编辑 Markdown 配置
vim ~/.heimaclaw/agents/my-agent/SOUL.md
vim ~/.heimaclaw/agents/my-agent/TOOLS.md

# 自动编译
heimaclaw compile --watch

# 启动服务
heimaclaw start
```

### 运行时性能（性能）
```python
# 直接加载编译后的 JSON
config = load_compiled_config("my-agent")

# 性能：< 1ms（vs Markdown 解析 50-100ms）
```

### 记忆上下文（工业级）
```python
# 智能检索相关记忆
context = await memory_manager.get_context("用户的问题")

# Token 预算管理
allocated = budget_manager.allocate(context)

# 性能：< 10ms 检索，自动压缩
```

---

_这个方案结合了 OpenClaw 的易用性和 HeiMaClaw 的性能与安全性，打造真正的工业级 Agent 平台！_ 🚀
