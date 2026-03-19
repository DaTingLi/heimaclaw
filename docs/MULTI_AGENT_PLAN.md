# HeiMaClaw 多 Agent 群聊支持计划

**版本**: v2.0  
**更新日期**: 2026-03-19  
**状态**: ✅ v0.2 简化版已完成

---

## 🎉 v0.2 简化设计已完成！

### 核心改进

| 旧设计 | 新设计 |
|--------|--------|
| 手动配置群组 ID | ✅ **自动发现，无需配置** |
| 分散的 bindings 配置 | ✅ **统一在 agent.json** |
| 复杂流程 | ✅ **邀请即用** |

---

## 📋 策略系统

### 响应模式 (mode)

| 模式 | 说明 |
|------|------|
| `mention` | 只响应 @提及（**默认**） |
| `open` | 响应所有人 |
| `disabled` | 完全禁用 |

### 作用范围 (scope)

| 范围 | 说明 |
|------|------|
| `private` | 只私聊 |
| `group` | 只群聊 |
| `both` | 私聊 + 群聊（**默认**） |

---

## 🚀 使用流程（简化版）

### Step 1: 创建 Agent

```bash
heimaclaw agent create python-helper
heimaclaw agent create frontend-helper
```

### Step 2: 配置策略（可选）

```bash
# 查看当前策略
heimaclaw agent show-policy python-helper

# 修改策略
heimaclaw agent set-policy python-helper --mode mention --scope both
```

### Step 3: 邀请机器人进群

```
飞书 → 创建群 → 添加机器人 → 邀请 python-helper
```

**完成！无需任何额外配置！**

### Step 4: 开始使用

```
@Python助手 帮我写个函数     → Python助手 响应
@前端助手 帮我写个页面       → 前端助手 响应
（私聊直接对话，无需 @）
```

---

## 📁 agent.json 策略配置

```json
{
  "name": "python-helper",
  "policy": {
    "mode": "mention",           // mention / open / disabled
    "scope": "both",            // private / group / both
    "allow_all_users": true,    // 允许所有用户
    "allow_all_groups": true,   // 允许所有群
    "whitelist_users": [],      // 用户白名单
    "whitelist_groups": []       // 群白名单
  }
}
```

---

## 🛡️ 安全策略

### 白名单机制

```bash
# 只允许特定用户
heimaclaw agent set-policy python-helper \
    --allow-users \
    --no-allow-groups

# 设置用户白名单（编辑 agent.json）
"whitelist_users": ["ou_xxx", "ou_yyy"]

# 设置群白名单
"whitelist_groups": ["oc_xxx"]
```

### 默认安全配置

- `mode: mention` - 群聊必须 @才响应
- `scope: both` - 支持私聊和群聊
- `allow_all_users: true` - 允许所有人

---

## 🔄 路由逻辑

```
收到消息
    ↓
获取 Agent 策略 (从 agent.json)
    ↓
检查 scope（范围）
    ├─ private → 只响应私聊
    ├─ group → 只响应群聊
    └─ both → 继续检查
    ↓
检查 mode（模式）
    ├─ disabled → 不响应
    ├─ open → 检查白名单后响应
    └─ mention → 群聊必须有 @，检查白名单后响应
    ↓
响应 / 不响应
```

---

## 📝 CLI 命令

```bash
# 创建 Agent（自动带默认策略）
heimaclaw agent create <name>

# 设置策略
heimaclaw agent set-policy <name> --mode mention --scope both

# 查看策略
heimaclaw agent show-policy <name>

# 其他命令
heimaclaw agent list
heimaclaw agent compile <name>
heimaclaw start
```

---

## 📁 相关文件

| 文件 | 说明 |
|------|------|
| `src/heimaclaw/agent/policy.py` | PolicyManager 策略管理 |
| `src/heimaclaw/agent/__init__.py` | 导出 PolicyManager |

---

## 🔮 未来计划

| 版本 | 功能 | 说明 |
|------|------|------|
| v0.3 | 关键词自动路由 | 根据内容关键词路由 |
| v0.4 | Router Agent | LLM 智能分发 |

---

_文档更新: 2026-03-19 - v0.2 简化版已完成_
