# 多进程飞书服务架构

**日期**: 2026-03-22  
**架构**: Multi-Process Feishu Service  
**状态**: 开发中

---

## 背景问题

飞书官方 SDK (`lark-oapi`) 的 WebSocket 客户端在同一进程的多个实例中存在 event loop 冲突：
```
Error: This event loop is already running
```

这导致无法在单一进程中同时运行多个飞书 App 的 WebSocket 连接。

---

## 解决方案：多进程架构

### 架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                    Main Process (Manager)                        │
│                  进程管理 + 配置加载                              │
└─────────────────────────────────────────────────────────────────┘
           │                    │                    │
           │ IPC               │ IPC               │ IPC
           ▼                    ▼                    ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│  Worker Proc 1   │  │  Worker Proc 2   │  │  Worker Proc N   │
│ FeishuAdapter    │  │ FeishuAdapter    │  │ FeishuAdapter    │
│ (cli_a930...)   │  │ (cli_a935...)   │  │ (cli_xxx...)    │
│     +           │  │     +           │  │     +           │
│  AgentRunner    │  │  AgentRunner    │  │  AgentRunner    │
│ (独立 event loop)│  │ (独立 event loop)│  │ (独立 event loop)│
└─────────────────┘  └─────────────────┘  └─────────────────┘
```

### 核心组件

#### 1. FeishuWorker (mp.Process)
- 继承 `multiprocessing.Process`
- 每个 worker 在独立进程中运行
- 创建独立的 `asyncio.new_event_loop()`
- 运行独立的 FeishuWebSocketAdapter + AgentRunner

#### 2. MultiProcessFeishuService
- 管理所有 Worker 进程
- 加载和分发 Agent 配置
- 处理进程生命周期（启动/停止/状态）

#### 3. AgentInfo (dataclass)
```python
@dataclass
class AgentInfo:
    name: str           # Agent 名称
    app_id: str        # 飞书 App ID
    app_secret: str    # 飞书 App Secret
    llm_config: dict   # LLM 配置
    sandbox_enabled: bool
    workspace: str     # 工作目录
```

---

## 实现文件

- `src/heimaclaw/feishu_multiprocess.py` - 多进程架构实现

---

## 使用方法

### 启动服务
```bash
# 自动加载 ~/.heimaclaw/agents/ 下所有 Agent
python -m heimaclaw.feishu_multiprocess
```

### Agent 配置
每个 Agent 的 `agent.json` 需要包含独立的飞书配置：

```json
{
  "name": "coder_heima",
  "enabled": true,
  "feishu": {
    "app_id": "cli_a935c9e5abe1dcc0",
    "app_secret": "4rkgZTz4PlTHVVjL4oQJOgJtJNshm3FM"
  },
  "llm": {
    "provider": "zhipu",
    "model_name": "glm-4",
    "api_key": "your-api-key"
  }
}
```

---

## 工业级特性

### 1. 故障隔离
- 每个 App 在独立进程中运行
- 一个 App 崩溃不影响其他 App
- 独立进程可以独立重启

### 2. 资源隔离
- 独立的内存空间
- 独立的 event loop
- 独立的 Agent Runner 实例

### 3. 水平扩展
- 可以启动多个 Worker 处理高并发
- 支持动态添加/移除 Agent

### 4. 进程管理
- PID 文件记录
- 信号处理 (SIGINT/SIGTERM)
- 超时控制和优雅关闭

---

## 注意事项

### 1. 进程间通信
- 使用 `multiprocessing.Manager().dict()` 共享状态
- 避免使用全局变量
- 进程间消息传递需要序列化

### 2. 文件路径
- Agent 配置从 `~/.heimaclaw/agents/` 加载
- Session 数据存储在 `/tmp/heimaclaw/sessions/<agent_name>/`

### 3. 性能考虑
- 每个进程约占用 100-200MB 内存
- 进程创建有约 1-2 秒开销
- 建议预启动所有 Worker

---

## 待完成

- [ ] 与现有 CLI 命令集成
- [ ] PID 文件管理
- [ ] 日志聚合
- [ ] 健康检查接口
- [ ] 动态添加/移除 Worker

---

**Author**: DT@高级开发工程师  
**Reviewer**: 李大婷
