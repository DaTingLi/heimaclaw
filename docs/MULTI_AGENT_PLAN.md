# HeiMaClaw 多 Agent 群聊支持计划

**版本**: v1.1  
**创建日期**: 2026-03-19  
**更新日期**: 2026-03-19  
**状态**: ✅ v0.2 已完成

---

## 📋 现状

### ✅ v0.2 已完成

| 功能 | 状态 | 说明 |
|------|------|------|
| @提及解析 | ✅ 完成 | 支持中文 Agent 名称 |
| route_with_mentions() | ✅ 完成 | 多 Agent 路由 |
| setup-group 命令 | ✅ 完成 | 群组多 Agent 配置 |
| list-group 命令 | ✅ 完成 | 查看群组配置 |
| remove-group 命令 | ✅ 完成 | 移除群组配置 |

### 已实现代码

```python
# 解析 @提及
router = AgentRouter()
mentions = router.parse_mentions("@Python助手 帮我写函数")
# ['Python助手']

# @提及路由
agents = router.route_with_mentions(
    content="@Python助手 帮我写函数",
    user_id="user123",
    chat_id="group456",
    is_group=True
)
# ['Python助手'] 或 ['e2e-test-agent']（模糊匹配）
```

### 新增 CLI 命令

```bash
# 配置群组多 Agent
heimaclaw bindings setup-group <群ID> --agents python-helper,frontend-helper --default python-helper

# 列出群组配置
heimaclaw bindings list-group

# 移除群组配置
heimaclaw bindings remove-group <群ID>
```

---

## 🎯 整体计划

| 版本 | 功能 | 优先级 | 状态 |
|------|------|--------|------|
| **v0.2** | @提及触发 | P0 | ✅ **已完成** |
| v0.3 | 关键词路由 | P1 | 待开发 |
| v0.4 | Router Agent | P2 | 待开发 |

---

## 📖 v0.2 使用指南

### 场景：飞书群支持多个 Agent

#### Step 1: 创建多个 Agent

```bash
heimaclaw agent create python-helper
heimaclaw agent create frontend-helper
heimaclaw agent create db-helper
```

#### Step 2: 配置群组多 Agent

```bash
heimaclaw bindings setup-group ocxxx-123 \
    --agents python-helper,frontend-helper,db-helper \
    --default python-helper
```

#### Step 3: 启动服务

```bash
heimaclaw start
```

#### Step 4: 在飞书群中使用

```
群成员: @Python助手 帮我写个排序函数
       → Python助手 响应

群成员: @前端助手 帮我写个页面
       → 前端助手 响应

群成员: @Python助手 @前端助手 一起帮我
       → 两个 Agent 都响应

群成员: 帮我查下数据库（无人 @）
       → 默认 Agent (python-helper) 响应
```

---

## 🔄 路由逻辑

```
收到消息
    ↓
解析 @提及 (@Python助手, @前端助手, ...)
    ↓
有 @提及？
    ├─ 是 → 路由到被 @ 的 Agents（并行响应）
    └─ 否 → 使用默认路由（群绑定 > 用户绑定 > 全局默认）
```

---

## 📝 Agent 名称配置

为了让 @提及正确工作，需要在 SOUL.md 中配置名称：

```markdown
# SOUL.md
## 🎯 身份

- **我叫**：Python助手
- **@名称**：@Python助手
- **我擅长**：Python 开发
```

---

## 🔮 v0.3 计划：关键词路由

```json
{
  "groups": {
    "ocxxx-123": {
      "mode": "keyword",
      "keyword_routing": {
        "python-helper": ["python", "函数", "bug", "django"],
        "frontend-helper": ["前端", "页面", "react", "vue"],
        "db-helper": ["数据库", "sql", "mysql"]
      }
    }
  }
}
```

用户发送： "我的数据库连接有问题"
→ 自动路由到 db-helper

---

## 🔮 v0.4 计划：Router Agent

使用 LLM 智能分析意图并分发任务。

```
用户消息 → Router Agent → LLM 分析意图 → 分发给子 Agent
```

---

## 📁 相关文件

| 文件 | 说明 |
|------|------|
| `src/heimaclaw/agent/router.py` | AgentRouter v2.0 |
| `src/heimaclaw/cli.py` | bindings 命令 |
| `docs/MULTI_AGENT_PLAN.md` | 本文档 |

---

_文档更新: 2026-03-19 - v0.2 已完成_
