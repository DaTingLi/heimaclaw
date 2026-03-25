# Agent 配置管理规范 v1.0

> 定义 Agent 与飞书 AppID/AppSecret 的配置管理标准

---

## 一、背景

HeiMaClaw 采用多进程架构，每个 Agent 运行在独立进程中，通过飞书 WebSocket 连接与用户交互。每个 Agent 必须绑定唯一的飞书 AppID + AppSecret 凭证。

### 1.1 当前架构

```
┌─────────────────────────────────────────────────────────┐
│  HeiMaClaw (Multi-Process)                              │
├─────────────────────────────────────────────────────────┤
│  Main Process (FeishuWorkerManager)                     │
│  ├── Worker: default  (AppID: cli_a9301f...)           │
│  │   └── Agent: heimaclaw                              │
│  └── Worker: coder_heima (AppID: cli_a935c9...)        │
│      └── Agent: heima_coder                            │
├─────────────────────────────────────────────────────────┤
│  Docker Sandbox Backend (shared)                       │
│  └── Container: 4159c3ce95e0 (python:3.10-slim)        │
└─────────────────────────────────────────────────────────┘
```

### 1.2 配置文件位置

| 路径 | 说明 |
|------|------|
| `/root/.heimaclaw/agents/{agent_name}/agent.json` | Agent 配置主文件 |
| `/root/dt/ai_coding/heimaclaw/config/config.toml` | 全局默认配置 |

---

## 二、Agent 配置结构

### 2.1 标准 agent.json 结构

```json
{
    "name": "coder_heima",
    "description": "coder_heima Agent - 群内显示名 heima_coder",
    "display_name": "heima_coder",
    "channel": "feishu",
    "enabled": true,
    "feishu": {
        "app_id": "cli_a935c9e5abe1dcc0",
        "app_secret": "4rkgZTz4PlTHVVjL4oQJOgJtJNshm3FM"
    },
    "sandbox": {
        "enabled": false,
        "memory_mb": 128,
        "cpu_count": 1,
        "type": "docker"
    },
    "llm": {
        "provider": "openai",
        "model_name": "glm-4",
        "base_url": "https://open.bigmodel.cn/api/coding/paas/v4",
        "api_key": "de4e3dc9f9d14c75bb2b4a38df59b2b9.CuO0DXKvTfYWVhVu",
        "temperature": 0.7,
        "max_tokens": 8192
    }
}
```

### 2.2 字段说明

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `name` | string | ✅ | Agent 唯一标识，用于内部路由 |
| `display_name` | string | ✅ | 飞书显示名称，用于 @ 匹配 |
| `description` | string | ❌ | Agent 功能描述 |
| `channel` | string | ✅ | 渠道类型，目前仅支持 `feishu` |
| `enabled` | boolean | ✅ | 是否启用该 Agent |
| `feishu.app_id` | string | ✅ | 飞书应用 AppID，格式：`cli_xxx` |
| `feishu.app_secret` | string | ✅ | 飞书应用 AppSecret |
| `llm.model_name` | string | ✅ | LLM 模型名称 |
| `llm.api_key` | string | ✅ | LLM API 密钥 |

---

## 三、AppID 与 AppSecret 管理规范

### 3.1 命名规则

| 实体 | 命名规则 | 示例 |
|------|----------|------|
| Agent 名称 | `snake_case`，字母+数字+下划线 | `coder_heima`, `default` |
| Display Name | 英文单词，可包含下划线 | `heima_coder`, `heimaclaw` |
| AppID | 飞书自动生成，格式 `cli_` 开头 | `cli_a935c9e5abe1dcc0` |

### 3.2 约束条件

```
1. 每个 AppID 只能绑定一个 Agent（唯一性约束）
2. 同一飞书应用下可以有多个 Bot，但建议 1:1 映射
3. app_secret 必须保密，禁止提交到版本控制系统
```

### 3.3 验证规则

| 验证项 | 规则 | 错误码 |
|--------|------|--------|
| AppID 格式 | 必须以 `cli_` 开头，长度 ≥ 10 | `INVALID_APP_ID` |
| AppSecret 格式 | 非空，长度 ≥ 16 | `INVALID_APP_SECRET` |
| Agent 名称 | 字母、数字、下划线，2-32字符 | `INVALID_AGENT_NAME` |
| Display Name | 非空，用于飞书 @ 匹配 | `INVALID_DISPLAY_NAME` |
| 唯一性 | 同一 app_id 不能重复加载 | `DUPLICATE_APP_ID` |

---

## 四、加载流程

### 4.1 FeishuWorkerManager 启动流程

```
1. 读取 ~/.heimaclaw/agents/ 目录下所有子目录
2. 每个子目录必须有 agent.json 文件
3. 解析 feishu.app_id 和 feishu.app_secret
4. 检查是否已有相同 app_id 的 Worker 运行
5. 如无重复，创建 FeishuWorker 进程
6. 每个 Worker 独立运行 Agent + WebSocket 适配器
```

### 4.2 关键代码路径

**文件**: `src/heimaclaw/feishu_multiprocess.py`

```python
class FeishuWorkerManager:
    def _load_agent_configs(self) -> list[AgentInfo]:
        """加载所有 Agent 配置"""
        agents_dir = Path.home() / ".heimaclaw" / "agents"
        
        for agent_dir in agents_dir.iterdir():
            config_file = agent_dir / "agent.json"
            # ... 解析配置
            agent_info = AgentInfo(
                name=agent_name,
                display_name=data.get("display_name", agent_name),
                app_id=app_id,
                app_secret=app_secret,
                llm_config=llm_cfg,
                # ...
            )
        return agents
    
    def start(self):
        """启动所有 Worker"""
        agents = self._load_agent_configs()
        for agent_info in agents:
            # 检查 app_id 重复
            existing = [w for w in self.workers.values() 
                       if w.agent_info.app_id == agent_info.app_id]
            if existing:
                info(f"跳过 {agent_info.name}，App 已存在 Worker")
                continue
            worker = FeishuWorker(agent_info)
            worker.start()
```

---

## 五、待完善功能

### 5.1 缺失的管理能力

| 功能 | 当前状态 | 优先级 |
|------|----------|--------|
| Agent 配置验证 | 无 | P0 |
| CLI 查看 Agent 列表 | 无 | P0 |
| Agent CRUD 管理 | 无 | P1 |
| 敏感信息加密存储 | 无 | P1 |
| 配置备份/版本控制 | 无 | P2 |

### 5.2 建议实现的 CLI 命令

```bash
# 列出所有 Agent
heimaclaw agent list

# 查看 Agent 详情
heimaclaw agent show <agent_name>

# 添加新 Agent（交互式）
heimaclaw agent add

# 更新 Agent 配置
heimaclaw agent update <agent_name> --feishu-app-id cli_xxx

# 删除 Agent
heimaclaw agent delete <agent_name>

# 验证配置完整性
heimaclaw agent validate
```

### 5.3 AgentManager 核心接口（建议实现）

```python
class AgentManager:
    """Agent 配置管理器"""
    
    def list_agents() -> list[AgentInfo]:
        """列出所有已配置的 Agent"""
        pass
    
    def get_agent(name: str) -> AgentInfo:
        """获取指定 Agent 配置"""
        pass
    
    def create_agent(config: CreateAgentRequest) -> AgentInfo:
        """创建新 Agent"""
        pass
    
    def update_agent(name: str, config: UpdateAgentRequest) -> AgentInfo:
        """更新 Agent 配置"""
        pass
    
    def delete_agent(name: str) -> bool:
        """删除 Agent"""
        pass
    
    def validate_app_id(app_id: str) -> ValidationResult:
        """验证 AppID 格式"""
        pass
    
    def validate_app_secret(secret: str) -> ValidationResult:
        """验证 AppSecret 格式"""
        pass
```

---

## 六、安全建议

### 6.1 敏感信息保护

| 方案 | 说明 | 优先级 |
|------|------|--------|
| 环境变量 | `HEIMA_{AGENT}_APP_SECRET` | P1 |
| 加密存储 | 使用 Fernet 对 app_secret 加密 | P2 |
| 密钥管理服务 | 接入 KMS/HashiCorp Vault | P3 |

### 6.2 配置审计

- 记录所有配置变更的时间、操作者、变更内容
- 定期检查 app_secret 有效性
- 禁止在日志中输出完整 app_secret

---

## 七、当前 Agent 映射表

| Agent Name | AppID | AppSecret (前8位) | Display Name | LLM Model |
|------------|-------|-------------------|--------------|-----------|
| `coder_heima` | `cli_a935c9...` | `4rkgZTz4...` | `heima_coder` | glm-4 |
| `default` | `cli_a9301f...` | `EWPY3k4f...` | `heimaclaw` | glm-5 |

---

## 八、版本历史

| 版本 | 日期 | 修改内容 |
|------|------|----------|
| v1.0 | 2026-03-25 | 初始版本，定义 Agent 配置结构和管理规范 |

---

*本规范为 HeiMaClaw 项目内部标准，请结合 ARCHITECTURE-v1.0.md 理解整体架构。*

---

## 九、已实现功能（2026-03-25 更新）

### 9.1 AgentManager 类

**文件**: `src/heimaclaw/agent/manager.py`

```python
class AgentManager:
    # 验证方法
    validate_app_id(app_id) -> ValidationResult
    validate_app_secret(app_secret) -> ValidationResult
    validate_agent_name(name) -> ValidationResult
    validate_all(name) -> list[ValidationResult]
    
    # CRUD 操作
    list_agents() -> list[AgentInfo]
    get_agent(name) -> AgentInfo
    create_agent(request) -> (bool, str, AgentInfo)
    update_agent(name, request) -> (bool, str)
    delete_agent(name) -> (bool, str)
    
    # 加密存储
    encrypt_existing(name) -> (bool, str)
    encrypt_all() -> (int, int)
```

### 9.2 CLI 命令

| 命令 | 功能 |
|------|------|
| `agent list [-v]` | 列出所有 Agent |
| `agent list -v --show-secrets` | 详细模式，显示密钥 |
| `agent validate [name]` | 验证配置 |
| `agent add <name> -i <app_id> -s <secret>` | 创建 Agent（自动加密） |
| `agent update <name> [-d] [-s] [-k]` | 更新配置（自动加密） |
| `agent delete <name> [-f]` | 删除 Agent |
| `agent encrypt [--all]` | 加密现有敏感信息 |

### 9.3 加密存储

- **算法**: Fernet (AES-128-CBC + HMAC-SHA256)
- **密钥文件**: `~/.heimaclaw/.key` (权限 600)
- **存储格式**: `ENC:gAAAAAB...` (Base64 编码)
- **兼容性**: `feishu_multiprocess.py` 启动时自动解密

### 9.4 安全流程

```
agent add → 明文 secret → Fernet.encrypt() → ENC:xxx → agent.json
                                                            ↓
heimaclaw start → _load_agent_configs() → _decrypt_if_needed() → 明文 → WebSocket
```

---

_更新时间: 2026-03-25 06:20_
