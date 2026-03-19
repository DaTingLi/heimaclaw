# HeiMaClaw 多 Agent 群聊支持计划

**版本**: v1.0  
**创建日期**: 2026-03-19  
**目标**: 在同一个飞书群中支持多个不同的 Agent

---

## 1. 现状分析

### 当前设计
- 每个群只能绑定一个 Agent
- 路由基于 `chat_id` 单一维度

### nanobot 参考实现
- Session key = `channel:chat_id`
- 支持 Subagent 背景任务
- 支持 Agent 间通信

---

## 2. 方案设计

### 方案 A: @提及触发（推荐）

用户在群中 @某个Agent 名称，该 Agent 响应。

```
群「技术部」
    @Python助手 帮我写个函数  → Python助手 响应
    @前端助手 帮我写个页面  → 前端助手 响应
    没人@，大家都能看到    → 默认 Agent 响应（可选）
```

**实现**：
1. 消息解析：检测 `@Agent名称` 模式
2. 路由决策：匹配到 Agent 则路由到该 Agent
3. 多 Agent 并行响应（可选）

### 方案 B: 关键词路由

根据消息内容关键词路由到对应 Agent。

```
群「技术部」
    包含「python」「函数」「Bug」→ Python助手
    包含「前端」「页面」「CSS」 → 前端助手
    包含「数据库」「SQL」      → 数据库助手
```

### 方案 C: Router Agent

一个主 Agent 作为入口，根据意图分发任务。

```
用户消息 → Router Agent → 分析意图 → 分发给子 Agent
                              ↓
                    ┌─────────┼─────────┐
                    ↓         ↓         ↓
              Python助手  前端助手  数据库助手
```

---

## 3. 实现计划

### Phase 1: @提及触发（v0.2）

#### 3.1 修改消息解析
```python
# 在收到飞书消息时解析 @提及
def parse_mentions(content: str) -> List[str]:
    """解析消息中的 @提及列表"""
    import re
    pattern = r'@(\w+)'
    return re.findall(pattern, content)
```

#### 3.2 修改 Router
```python
# 在 AgentRouter 中添加多 Agent 支持
def route_to_agents(chat_id: str, mentions: List[str]) -> List[str]:
    """根据提及返回对应的 Agent 列表"""
    # 查找每个被提及的 Agent
    agents = []
    for mention in mentions:
        agent = find_agent_by_name(mention)
        if agent:
            agents.append(agent)
    return agents
```

#### 3.3 修改消息处理
```python
# 单 Agent 响应（最快响应）
# 或多 Agent 并行响应（都需要）
async def process_group_message(message: str, chat_id: str):
    mentions = parse_mentions(message)
    
    if mentions:
        # 多 Agent 模式
        for agent_name in mentions:
            agent = get_agent(agent_name)
            await agent.process(message, chat_id)
    else:
        # 单 Agent 模式（使用默认/绑定）
        agent = get_bound_agent(chat_id)
        await agent.process(message, chat_id)
```

### Phase 2: 关键词路由（v0.3）

```python
# 关键词配置
AGENT_KEYWORDS = {
    "Python助手": ["python", "函数", "bug", "django", "flask"],
    "前端助手": ["前端", "react", "vue", "css", "页面"],
    "数据库助手": ["数据库", "sql", "mysql", "redis"],
}
```

### Phase 3: Router Agent（v0.4）

```python
class RouterAgent:
    """智能路由 Agent"""
    
    async def route(self, message: str) -> str:
        """分析消息，返回最适合的 Agent 名称"""
        # 使用 LLM 分析意图
        response = await self.llm.chat([
            {"role": "user", "content": f"分析用户需求，返回最匹配的 Agent：{message}"}
        ])
        return response.content
```

---

## 4. 配置设计

### 4.1 群组多 Agent 配置

```json
{
  "groups": {
    "tech-group-123": {
      "mode": "mention",  // "mention" | "keyword" | "router"
      "agents": ["python-helper", "frontend-helper", "db-helper"],
      "default": "python-helper",
      "keyword_routing": {
        "python-helper": ["python", "函数"],
        "frontend-helper": ["前端", "页面"]
      }
    }
  }
}
```

### 4.2 SOUL.md 配置（让 Agent 知道自己的名字）

```markdown
# SOUL.md
## 🎯 身份

- **我叫**：Python助手
- **我的名字**：@Python助手
- **我擅长**：Python 开发

## 🤝 协作规则

- 如果用户在群里 @我，我就响应
- 如果消息中有 Python 相关关键词，我也可以响应
- 我只在被 @ 或者关键词匹配时响应
```

---

## 5. 飞书消息格式

### 5.1 @提及消息

飞书消息中包含 `mention` 字段：
```json
{
  "msg_type": "text",
  "content": {
    "text": "@Python助手 帮我写个排序函数"
  },
  "mentions": [
    {"name": "Python助手", "id": "ou_xxx"}
  ]
}
```

### 5.2 解析

```python
from lark_oapi.adapter.event import MentionedEvent

def parse_mentions_from_event(event) -> List[str]:
    mentions = event.mentions or []
    return [m.name for m in mentions]
```

---

## 6. 实现步骤

### Step 1: 修改 AgentRouter
- 支持 `route_to_mentioned_agents()` 方法
- 支持 `route_by_keywords()` 方法

### Step 2: 修改 FeishuWSHandler
- 解析消息中的 @提及
- 传递给 Router

### Step 3: 修改 AgentRunner
- 支持 `process_for_group()` 方法
- 支持并行响应

### Step 4: 添加配置
- `groups` 配置
- Agent 名称配置

---

## 7. 测试计划

### 测试场景

```bash
# 场景1: @单 Agent
群里发送: "@Python助手 帮我写个快排"
预期: 只有 Python助手 响应

# 场景2: @多 Agent
群里发送: "@Python助手 @前端助手 一起帮我"
预期: Python助手 和 前端助手 都响应

# 场景3: 无 @使用默认
群里发送: "帮我写个函数"
预期: 默认 Agent 响应

# 场景4: 关键词路由
群里发送: "我的数据库有问题"
预期: 数据库助手（如果配置了关键词）响应
```

---

## 8. 优先级

| Phase | 功能 | 优先级 | 难度 |
|-------|------|--------|------|
| v0.2 | @提及触发 | P0 | 中 |
| v0.3 | 关键词路由 | P1 | 低 |
| v0.4 | Router Agent | P2 | 高 |

---

## 9. 参考资料

- nanobot subagent: `/reference/nanobot/nanobot/agent/subagent.py`
- nanobot session: `/reference/nanobot/nanobot/session/manager.py`
- openclaw-lark: `/reference/openclaw-lark-main/`

---

_计划创建日期: 2026-03-19_
