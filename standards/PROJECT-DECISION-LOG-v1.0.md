# 项目重大决策日志（倒序）

## 2026-03-18

### 决策 005：CLI 框架选型
- **决定**：使用 Typer + Rich 作为 CLI 框架
- **理由**：Typer 提供类型注解驱动的命令定义，Rich 提供丰富的终端输出能力，与 OpenClaw 技术栈一致
- **影响**：所有 CLI 命令使用 Typer 装饰器定义，输出使用 Rich 主题

### 决策 004：配置格式选型
- **决定**：使用 TOML 作为配置文件格式，Pydantic 作为配置模型
- **理由**：TOML 可读性好，Pydantic 提供类型验证，与 Python 生态高度兼容
- **影响**：所有配置文件使用 .toml 扩展名，配置加载使用 tomli/tomli-w

### 决策 003：沙箱后端优先级
- **决定**：Firecracker 为首选沙箱后端，Docker/Process 作为降级方案
- **理由**：Firecracker 提供 microVM 级别隔离，冷启动 < 200ms，符合项目硬件级隔离要求
- **影响**：需要检测 KVM 支持，无 KVM 时降级到 Docker 或进程隔离

### 决策 002：最低 Python 版本
- **决定**：支持 Python 3.10+（原计划 3.11+）
- **理由**：当前服务器 Python 版本为 3.10.12，降低版本要求以兼容现有环境
- **影响**：不使用 3.11+ 独有特性（如 Self 类型、ExceptionGroup 等）

### 决策 001：项目物理路径
- **决定**：项目代码位于 /root/dt/ai_coding/heimaclaw
- **理由**：符合用户指定的生产环境路径规划
- **影响**：所有路径配置以此为基准，CLI init 命令默认路径为 /opt/heimaclaw（生产部署）

## 2026-03-17

### 决策 000：项目初始化
- **决定**：创建 HeiMaClaw 项目
- **理由**：需要构建一个生产级企业 AI Agent 平台，支持 microVM 隔离
- **影响**：项目正式开始，建立 standards/ 规范体系

## 2026-03-18（续）

### 决策 006：Agent 运行时架构
- **决定**：采用三层架构（Runner + SessionManager + ToolRegistry）
- **理由**：职责分离，Runner 负责生命周期，SessionManager 负责会话，ToolRegistry 负责工具
- **影响**：模块边界清晰，易于测试和扩展

### 决策 007：会话持久化方式
- **决定**：使用 JSON 文件存储会话数据
- **理由**：简单可靠，无需额外依赖，便于调试
- **影响**：会话数据存储在 data/sessions/ 目录，后续可升级到数据库

### 决策 008：工具注册方式
- **决定**：支持装饰器和函数两种注册方式
- **理由**：装饰器简洁优雅，直接注册灵活可控
- **影响**：工具定义支持 OpenAI 格式，便于 LLM 调用

### 决策 009：消息历史格式
- **决定**：采用 OpenAI Messages 格式（role/content/tool_calls）
- **理由**：与主流 LLM API 兼容，便于工具调用集成
- **影响**：所有消息遵循 OpenAI 格式规范

### 决策 010：Agent 配置管理
- **决定**：使用 Pydantic 模型 + TOML 文件
- **理由**：类型安全，自动验证，与项目配置系统一致
- **影响**：Agent 配置存储在 data/agents/<name>/agent.json

## 2026-03-18（续）

### 决策 011：LLM 厂商支持策略
- **决定**：支持 7 个主流 LLM 厂商（智谱、DeepSeek、通义千问、OpenAI、Claude、vLLM、Ollama）
- **理由**：覆盖国内外主流模型，支持自定义部署
- **影响**：使用 OpenAI 兼容格式覆盖 80% 厂商，降低适配成本

### 决策 012：Agent LLM 配置方式
- **决定**：Agent 配置文件中包含 LLM 配置（provider、model_name、api_key）
- **理由**：每个 Agent 可以使用不同的 LLM，灵活配置
- **影响**：Agent 创建时需要指定 LLM 配置

### 决策 013：测试验证方式
- **决定**：使用智谱 GLM API 进行端到端测试
- **理由**：智谱 API 稳定、响应快、费用低
- **影响**：所有核心流程通过真实 LLM 验证

## 2026-03-18（续）

### 决策 014：Firecracker 安装方式
- **决定**：使用官方二进制文件安装到 /usr/local/bin/
- **理由**：简单直接，避免容器化部署的复杂性
- **影响**：需要手动准备 kernel 和 rootfs 镜像

### 决策 015：microVM 镜像准备
- **决定**：从宿主机 /boot/vmlinuz 提取 kernel，使用 Alpine minirootfs
- **理由**：宿主机 kernel 兼容性好，Alpine 最小化资源占用
- **影响**：镜像存储在 /opt/heimaclaw/images/

### 决策 016：Firecracker 版本选择
- **决定**：使用 v1.15.0（最新稳定版）
- **理由**：最新版本，支持更多特性（快照、vsock）
- **影响**：需要 Python 适配层更新

### 决策 017：Token 监控数据存储
- **决定**：使用 SQLite 数据库存储 token 使用记录
- **理由**：轻量级、无额外依赖、查询性能好
- **影响**：数据库文件位于 ~/.heimaclaw/data/tokens.db

### 决策 018：监控 API 设计
- **决定**：通过 FastAPI 端点暴露监控数据
- **理由**：与主服务集成、易于与监控系统集成
- **影响**：/api/monitoring/* 端点可用于 Prometheus/Grafana 集成

### 决策 019：systemd 服务配置
- **决定**：提供标准 systemd 服务文件
- **理由**：Linux 生产环境标准、支持自动重启
- **影响**：可通过 systemctl 管理 HeiMaClaw 服务
# 项目重大决策日志（倒序）

## 2026-03-19

### 决策 023：Event Bus + Subagent 架构集成
- **决定**：为 HeiMaClaw 添加 Event Bus + Subagent 架构
- **理由**：解决传统 ReAct 的两大痛点（上下文爆炸、无法并行），提供多 Agent 协作能力
- **影响**：
  - 新增 4 个核心模块 (EventBus, SubagentRegistry, SubagentSpawner, IntegrationExample)
  - 支持 6 种事件类型（PENDING/RUNNING/COMPLETED/FAILED/KILLED/TIMEOUT）
  - 支持断点恢复、事件过滤、并发控制

### 决策 022：事件持久化方式
- **决定**：使用 JSONL 文件存储事件
- **理由**：轻量级、易调试、无外部依赖
- **影响**：事件存储在 .openclaw/event-bus/ 目录，  - 支持 30 分钟轮询 + 即时通知

### 册决策 021：子 Agent 生命周期管理
- **决定**：使用 SubagentRegistry 猏踪所有子 Agent
- **理由**：全局管理、状态追踪、父子关系维护
- **影响**：支持磁盘持久化，崩溃恢复，  - 支持并发限制（5 个/会话）

### 决策 020：并行执行策略
- **决定**：使用 asyncio.gather 并行派生子 Agent
- **理由**：提升 55% 执行时间，- **影响**：支持 3 个子 Agent 同时运行  - 结果通过事件总线异步返回

### 决策 019：模型分层策略
- **决定**：简单任务用 Haiku， 复杂任务用 Opus
- **理由**：降低 73% 成本
- **影响**：子 Agent 可指定模型，支持成本优化

## 2026-03-18

### 决策 018：监控 API 设计
- **决定**：通过 FastAPI 端点暴露监控数据
- **理由**：与主服务集成、易于与监控系统集成
- **影响**：/api/monitoring/* 端点可用于 Prometheus/Grafana 集成

### 决策 017：Token 监控数据存储
- **决定**：使用 SQLite 数据库存储 token 使用记录
- **理由**：轻量级、无额外依赖、查询性能好
- **影响**：数据库文件位于 ~/.heimaclaw/data/tokens.db

### 决策 016：Firecracker 版本选择
- **决定**：使用 v1.15.0（最新稳定版）
- **理由**：最新版本，支持更多特性（快照、vsock）
- **影响**：需要 Python 适配层更新

### 册决策 015：microVM 镜像准备
- **决定**：从宿主机 /boot/vmlinuz 提取 kernel，使用 Alpine minirootfs
- **理由**：宿主机 kernel 免费好，Alpine 最小化资源占用
- **影响**：镜像存储在 /opt/heimaclaw/images/

### 决策 014：Firecracker 安装方式
- **决定**：使用官方二进制文件安装到 /usr/local/bin/
- **理由**：简单直接，避免容器化部署的复杂性
- **影响**：需要手动准备 kernel 和 rootfs 镜像

### 决策 013：测试验证方式
- **决定**：使用智谱 GLM API 进行端到端测试
- **理由**：智谱 API 稳定、响应快、费用低
- **影响**：所有核心流程通过真实 LLM 验证

### 决策 012：Agent LLM 配置方式
- **决定**：Agent 配置文件中包含 LLM 配置（provider、model_name、api_key）
- **理由**：每个 Agent 可以使用不同的 LLM，灵活配置
- **影响**：Agent 创建时需要指定 LLM 配置

### 决策 011：LLM 厂商支持策略
- **决定**：支持 7 个主流 LLM 厂商（智谱、DeepSeek、通义千问、OpenAI、Claude、vLLM、Ollama）
- **理由**：覆盖国内外主流模型，支持自定义部署
- **影响**：使用 OpenAI 兼容格式覆盖 80% 厂商，降低适配成本

### 决策 010：Agent 配置管理
- **决定**：使用 Pydantic 模型 + TOML 文件
- **理由**：类型安全，自动验证, 与项目配置系统一致
- **影响**：Agent 配置存储在 data/agents/<name>/agent.json

### 决策 009：消息历史格式
- **决定**：采用 OpenAI Messages 格式 (role/content/tool_calls)
- **理由**：与主流 LLM API 兼容, 便于工具调用集成
- **影响**：所有消息遵循 OpenAI 格式规范

### 决策 008：工具注册方式
- **决定**：支持装饰器和函数两种注册方式
- **理由**：装饰器简洁优雅, 直接注册灵活可控
- **影响**：工具定义支持 OpenAI 格式, 便于 LLM 调用

### 决策 007：会话持久化方式
- **决定**：使用 JSON 文件存储会话数据
- **理由**：简单可靠, 无需额外依赖, 便于调试
- **影响**：会话数据存储在 data/sessions/ 目录, 后续可升级到数据库

### 决策 006：Agent 运行时架构
- **决定**：采用三层架构 (Runner + SessionManager + ToolRegistry)
- **理由**：职责分离, Runner 负责生命周期, SessionManager 负责会话, ToolRegistry 负责工具
- **影响**：模块边界清晰, 易于测试和扩展

## 2026-03-17

### 决策 000：项目初始化
- **决定**：创建 HeiMaClaw 项目
- **理由**：需要构建一个生产级企业 AI Agent 平台, 支持 microVM 隔离
- **影响**：项目正式开始, 建立 standards/ 规范体系

## 2026-03-18（续）

### 决策 005：CLI 框架选型
- **决定**：使用 Typer + Rich 作为 CLI 框架
- **理由**：Typer 提供类型注解驱动的命令定义, Rich 提供丰富的终端输出能力, 与 OpenClaw 技术栈一致
- **影响**：所有 CLI 命令使用 Typer 裆器定义, 输出使用 Rich 主题

### 决策 004：配置格式选型
- **决定**：使用 TOML 作为配置文件格式, Pydantic 作为配置模型
- **理由**：TOML 可读性好, Pydantic 提供类型验证, 与 Python 生态高度兼容
- **影响**：所有配置文件使用 .toml 扩展名, 配置加载使用 tomli/tomli-w

### 决策 003：沙箱后端优先级
- **决定**：Firecracker 为首选沙箱后端, Docker/Process 作为降级方案
- **理由**：Firecracker 提供 microVM 级别隔离, 冷启动 < 200ms, 符合项目硬件级隔离要求
- **影响**：需要检测 KVM 支持, 无 KVM 时降级到 Docker 或进程隔离

### 决策 002：最低 Python 版本
- **决定**：支持 Python 3.10+（原计划 3.11+）
- **理由**：当前服务器 Python 版本为 3.10.12, 降低版本要求以兼容现有环境
- **影响**：不使用 3.11+ 独有特性 (如 Self 类型、ExceptionGroup 等)

### 决策 001：项目物理路径
- **决定**：项目代码位于 /root/dt/ai_coding/heimaclaw
- **理由**：符合用户指定的生产环境路径规划
- **影响**：所有路径配置以此为基准, CLI init 命令默认路径为 /opt/heimaclaw（生产部署）

---

## 2026-03-24 晚: Docker 沙箱方案决策

### 背景

在 Firecracker 沙箱开发过程中发现严重局限性：

| 问题 | 说明 |
|------|------|
| 环境不完整 | Alpine Linux 无 Flask/SQLite 等基础依赖 |
| 端口隔离 | 沙箱内端口外部无法访问 |
| 持久运行受限 | 超时机制无法持续运行服务 |
| 依赖缺失 | 无法直接执行 Python Web 应用 |

### 决策内容

**采用 Docker 作为项目级隔离方案**

### Docker vs Firecracker 对比

| 维度 | Firecracker | Docker |
|------|-------------|--------|
| 环境完整性 | ❌ Alpine | ✅ 完整 Linux |
| Python 依赖 | ❌ 需手动安装 | ✅ Dockerfile 预装 |
| Web 服务 | ❌ 无法外部访问 | ✅ 端口映射 |
| 持久运行 | ⚠️ 超时 | ✅ 可持续 |
| 资源隔离 | ✅ 轻量 | ✅ 适中 |

### 方案设计

**每个项目 = 独立 Docker 容器**

```
Host (Ubuntu)
    │
    ├── Agent 推理进程
    │
    └── Docker Container (项目隔离)
            │
            ├── Python 3.10 + Flask + SQLite
            ├── /root/heimaclaw_workspace/<project>/
            └── 端口映射 (5000 → Host:5001)
```

### 新增文件

| 文件 | 说明 |
|------|------|
| `standards/DOCKER-SANDBOX-ARCHITECTURE-v1.0.md` | Docker 方案完整设计 |

### 实施计划

**第一阶段**：基础设施
- 创建 `docker/` 目录和 Dockerfile
- 实现 `DockerBackend` 类
- 实现 `PortManager` 类

**第二阶段**：核心功能
- 容器生命周期管理
- 命令执行
- 端口映射
- 卷挂载

**第三阶段**：集成测试
- 与 Agent Runner 集成
- 部署任务测试

### Git 分支

```
docker-sandbox  ← 当前分支（新方案）
firecracker-sandbox  ← Firecracker 方案（保留）
master  ← 稳定版本
```

### 原则

1. **不修改其他核心代码** - docker-sandbox 分支只做 Docker 方案
2. **Standards 先行** - 先文档，后实现
3. **可切换** - 保留 Firecracker 作为可选后端

---

_决策时间: 2026-03-24 18:50_

---

## 决策 #016: Agent 配置管理规范

### 背景

当前 HeiMaClaw 的 Agent 与飞书 AppID/AppSecret 配置管理存在以下问题：
1. 配置分散在各自 agent.json 中
2. 缺乏配置验证机制
3. 无统一的 Agent CRUD 管理接口
4. 敏感信息（app_secret）明文存储

### 决策

制定 `AGENT-MANAGEMENT-v1.0.md` 规范，定义：
1. Agent 配置结构标准（agent.json schema）
2. AppID/AppSecret 验证规则
3. 加载流程（FeishuWorkerManager）
4. 待实现的 AgentManager 接口
5. 安全建议

### 新增文件

| 文件 | 说明 |
|------|------|
| `standards/AGENT-MANAGEMENT-v1.0.md` | Agent 配置管理规范 |

### 实施计划

**第一阶段**：文档规范
- [x] 创建 AGENT-MANAGEMENT-v1.0.md
- [ ] 更新 PROJECT-DECISION-LOG

**第二阶段**：CLI 增强
- [ ] 实现 `heimaclaw agent list` 命令
- [ ] 实现 `heimaclaw agent show <name>` 命令

**第三阶段**：配置管理
- [ ] 实现 AgentManager 类
- [ ] 添加配置验证逻辑
- [ ] 实现 Agent CRUD

**第四阶段**：安全加固
- [ ] 敏感信息加密存储
- [ ] 配置审计日志

### 原则

1. **1:1 映射** - 每个 AppID 只能绑定一个 Agent
2. **验证先行** - 启动时校验 app_id/app_secret 格式
3. **兼容现有** - 不破坏现有 agent.json 结构
4. **渐进增强** - CLI → Manager → 安全加固

---

_决策时间: 2026-03-25 06:00_

---

## 决策 #017: 实现 Agent List 和 Validate CLI 命令

### 背景

为完善 Agent 配置管理，需要提供命令行工具来：
1. 查看所有 Agent 及其配置状态
2. 验证 Agent 配置的完整性和正确性

### 决策

实现以下 CLI 命令：

**1. `heimaclaw agent list`**
```bash
heimaclaw agent list              # 简洁列表
heimaclaw agent list -v          # 详细列表
heimaclaw agent list --show-secrets  # 显示完整密钥
```

**2. `heimaclaw agent validate`**
```bash
heimaclaw agent validate              # 验证所有 Agent
heimaclaw agent validate coder_heima  # 验证指定 Agent
heimaclaw agent validate --fix        # 验证并自动修复
```

### 验证规则

| 验证项 | 规则 | 错误码 |
|--------|------|--------|
| AppID 格式 | 必须以 `cli_` 开头 | `❌` |
| AppSecret 长度 | >= 16 位 | `❌` |
| Agent 名称 | 字母、数字、下划线，2-32字符 | `❌` |
| Display Name | 非空 | `⚠️` |
| LLM API Key | 非空 | `❌` |
| LLM 模型 | 已指定 | `⚠️` |
| 配置文件 | 存在且可读 | `❌` |

### 实现状态

- [x] `heimaclaw agent list` 命令（简洁/详细模式）
- [x] `heimaclaw agent validate` 命令
- [x] 验证规则：AppID、AppSecret、Agent 名称、LLM 配置
- [x] 自动跳过非 Agent 目录（如 memory/）

### 待完成

- [ ] `heimaclaw agent validate --fix` 自动修复功能
- [ ] Agent CRUD 管理命令（create/update/delete）
- [ ] 敏感信息加密存储

---

_决策时间: 2026-03-25 06:10_

---

## 决策 #018: 健壮性修复

### 问题列表

| ID | 严重度 | 问题 | 修复方案 |
|----|--------|------|----------|
| P0-1 | 🔴 | `validate_all` 中 `_decrypt()` 失败返回空字符串导致误导性验证结果 | 改为抛出 `DecryptionError` 异常 |
| P0-2 | 🔴 | 加密密钥无进程锁，多进程启动竞态条件 | 使用 `fcntl.flock()` 文件锁 |
| P0-3 | 🔴 | `_decrypt_if_needed` 定义在循环内，重复导入/创建 | 移到循环外 + 缓存 |
| P1-1 | 🟡 | `cli.py` 中 `sys` 在 `if daemon:` 内导入但被嵌套函数引用 | 移至 `start_command()` 顶部 |
| P1-2 | 🟡 | `_decrypt` 失败静默返回空字符串 | 改为抛出 `DecryptionError` |
| P1-3 | 🟡 | `_read_config` JSON 解析失败无日志 | 增加 warning 日志 |

### 架构改进

1. **加密引擎模块化**：`_get_encryption_key()` 模块级单例 + `fcntl.flock()` 进程安全
2. **解密异常传播**：不再静默失败，调用方可见解密错误
3. **配置写入备份**：`_write_config` 写入前自动备份 `.json.bak`

### 修改文件

| 文件 | 修改内容 |
|------|----------|
| `agent/manager.py` | 重写加密引擎，添加 `DecryptionError`，改进 `validate_all` |
| `feishu_multiprocess.py` | `_decrypt_if_needed` 移到循环外，JSON 错误改进 |
| `cli.py` | 修复 `sys` 变量作用域问题 |

---

_决策时间: 2026-03-25 09:45_

---

## 决策 #019: 公网暴露工具 (expose)

### 问题背景

heimaclaw agent 在 Docker 沙箱中运行网站服务时，存在两个关键问题：

**问题1：端口映射错误**
- Agent 在容器内启动 Flask/Django 服务时，容器内端口（如 9001）没有正确映射到宿主机
- 日志显示服务"运行正常"，但外部无法访问（因为端口根本没映射）
- Agent 通过 `curl localhost:9001` 在容器内检测，返回正常，但这不代表外部可访问

**问题2：缺乏公网暴露机制**
- 服务器可能在内网，需要隧道工具才能暴露
- 不同环境需要不同的暴露策略（公网IP直连 vs SSH隧道）

### 解决方案：expose 工具

**实现文件**: `src/heimaclaw/agent/tools/expose_tool.py`

**支持三种暴露方式**：

| 方式 | 优先级 | 适用场景 | 命令 |
|------|--------|----------|------|
| `direct_ip` | 最高 | 服务器有公网IP | 直接 `http://IP:PORT` |
| `serveo` | 中 | 内网服务器 | `ssh -R 80:localhost:PORT serveo.net` |
| `localhost.run` | 低 | 内网服务器 | `ssh -R 80:localhost:PORT nokey@localhost.run` |

**工作流程**：

```
1. 尝试获取公网 IP
2. 检查公网 IP 的目标端口是否可达
   → 如果可达：返回 http://公网IP:PORT（最快）
   → 如果不可达：继续尝试 SSH 隧道
3. 尝试 SSH 隧道（serveo → localhost.run）
   → 解析输出中的公网 URL
   → 返回 https://xxxx.serveo.net 或类似地址
```

### 新增工具

**名称**: `expose`
**参数**:
- `host`: 本地地址（默认 127.0.0.1）
- `port`: 本地端口（必填）
- `type`: 暴露方式（auto/direct_ip/serveo/localhost.run）
- `timeout`: 超时时间（默认30秒）

**返回值**: 公网可访问的 URL

### 健壮性改进

1. **多重fallback**: 公网IP失败自动尝试SSH隧道
2. **超时控制**: 防止隧道建立卡死
3. **日志输出**: 清楚显示暴露方式和URL
4. **错误处理**: 所有网络操作都有超时和异常处理

### 实现状态

- [x] expose_tool.py 核心逻辑
- [x] 直接IP检测 (`get_public_ip()`, `check_port_reachable()`)
- [x] serveo 隧道 (`expose_serveo()`)
- [x] localhost.run 隧道 (`expose_localhost_run()`)
- [x] Runner 工具注册
- [ ] Agent 集成（agent 应在服务启动后自动调用 expose）
- [ ] 自动 URL 返回（当前需要 agent 手动调用 expose）

### 健壮性修复

| 问题 | 修复 |
|------|------|
| Docker 端口映射错误导致网站不可达 | expose 工具提供 alternative 暴露路径 |
| Agent 检测"正常"但实际不可达 | expose 在暴露前验证外部连通性 |

---

_决策时间: 2026-03-25 10:10_

---

## 决策 #020: Docker Host 网络模式修复

### 核心痛点

**问题**：Agent 在 Docker 沙箱内创建网站服务（Flask/Django），外部无法通过公网访问。

**根因**：
1. `sandbox/docker.py` 创建容器时使用 bridge 网络 + `-p host_port:5000`
2. Agent 在容器内启动服务时可能绑定到任意端口（5000、9001 等）
3. `-p` 端口映射在容器创建时固定，无法动态添加
4. 结果：Agent 说"服务正常"，但端口没有映射，外部完全不可达

```
bridge 模式（旧）:
  容器创建 → -p 5001:5000（固定映射）
  Agent 执行 → python mountains.py → 绑定 0.0.0.0:5000
  ❌ 如果 Agent 用 9001 端口 → 无映射 → 外部不可达

host 模式（新）:
  容器创建 → --net=host（共享宿主机网络栈）
  Agent 执行 → python mountains.py → 绑定 0.0.0.0:5000
  ✅ 直接使用宿主机网络 → 公网 IP:5000 可达
```

### 解决方案

**修改文件**：
| 文件 | 修改内容 |
|------|----------|
| `sandbox/docker.py` | `create_instance` 中 `--net=host` 替代 `-p` 端口映射 |
| `core/dockerimpl/container_pool.py` | 新增 `network_mode` 配置字段，支持 `host`/`bridge` |

**关键变化**：
- Docker 容器使用 `--net=host` 网络模式
- 容器内服务直接绑定宿主机端口，无需 `-p` 映射
- Agent 绑定任意端口都自动对外可达

### 验证结果

```
✅ 容器创建: NetworkMode=host
✅ Flask 启动: 0.0.0.0:5000（宿主机端口）
✅ 公网访问: http://117.72.105.77:5000/ → 200 OK
✅ 无需端口映射配置
```

### 注意事项

- **安全性**：host 模式下容器共享宿主机网络栈，端口隔离较弱
- **端口冲突**：多个服务不能绑定同一端口（建议 Agent 用 port_pool 分配）
- **兼容性**：旧容器需重建（docker rm + 重新创建）

---

_决策时间: 2026-03-25 10:25_

---

## 决策 #021: 循环卡住问题修复

### 问题背景

Agent（heimaclaw）在执行任务时出现"循环卡住"现象：
- Agent 反复执行 `python3 snack.py`
- 但 `snack.py` 文件从未被创建
- Agent 陷入失败→重试→失败的死循环

### 根本原因

| 原因 | 说明 |
|------|------|
| **无文件预检** | exec_tool 直接执行命令，文件不存在也照常执行 |
| **无循环检测** | 没有检测同一命令反复失败的机制 |
| **错误信息不清** | "No such file" 提示不够明确 |

### 解决方案

**1. exec_tool 文件存在性预检**

```python
# 检测 python3 <script>.py 模式
if command matches "python3 <file>.py":
    if not os.path.exists(file):
        return {
            "success": False,
            "output": "错误：文件不存在 'xxx.py'\n\n建议：先使用 write_file 工具创建文件，再运行。",
            "error": "FILE_NOT_FOUND"
        }
```

**效果**：
- 避免执行不存在的脚本
- 返回明确的修复建议
- LLM 看到 "先创建文件" 提示，会先调用 write_file

**2. LoopDetector 循环检测器**

```python
class LoopDetector:
    """检测重复失败命令"""
    max_repeat = 3  # 连续3次失败判定为循环
    
    def record(command, success, error):
        ...
    
    def check() -> LoopDetectionResult:
        # 如果同一命令连续失败3次
        # 返回 suggested_action（反思策略）
```

**3. Runner 反思模式**

```python
loop_result = self._loop_detector.check()
if loop_result.is_loop:
    return "[反思模式] 检测到重复执行模式...\n\n" + suggested_action
```

### 修改文件

| 文件 | 修改 |
|------|------|
| `agent/tools/exec_tool.py` | 添加文件存在性预检 |
| `agent/tools/loop_detector.py` | 新增循环检测器 |
| `agent/runner.py` | 集成 LoopDetector |

### 与 OpenClaw 的对比

| 方面 | OpenClaw | heimaclaw (新) |
|------|----------|----------------|
| 循环检测 | ✅ 3次重复限制 | ✅ LoopDetector (max_repeat=3) |
| 命令预检 | 未确认 | ✅ 文件存在性检查 |
| 反思机制 | 有 | ✅ 反思模式提示 |
| LLM API | Claude API | 智谱 GLM-4/GLM-5 |

### 健壮性改进

1. **exec_tool 不再执行不存在的文件** → 减少无效执行
2. **错误信息包含修复建议** → LLM 更可能正确响应
3. **LoopDetector 框架就位** → 未来可扩展更多检测规则

---

_决策时间: 2026-03-25 10:58_

---

## 决策 #022: OpenClaw 风格沙箱安全重构

### 背景

heimaclaw 原有沙箱存在安全隐患：
1. `--net=host` 网络共享（无隔离）
2. root 用户运行
3. 无 capability 限制
4. 无根文件系统只读保护
5. 无 PID/内存限制
6. 无临时文件系统隔离

### OpenClaw 沙箱标准

**核心安全参数**：
```python
network="none"        # 无网络隔离（默认）
user="1000:1000"     # 非 root 用户
cap_drop=["ALL"]      # 移除所有 Linux capabilities
read_only_root=True   # 根文件系统只读
pids_limit=256        # PID 数量限制
memory="1g"           # 内存限制
memory_swap="2g"      # swap 限制
tmpfs=["/tmp", "/var/tmp", "/run"]  # 临时文件内存化
```

**禁止的配置**：
- `network="host"` — 被安全策略禁止
- `network="container:<id>"` — namespace join 风险

### 实现文件

| 文件 | 说明 |
|------|------|
| `sandbox/docker_secure.py` | SandboxConfig + SandboxDockerConfig 配置模型 |
| `sandbox/secure_executor.py` | SecureSandboxExecutor 安全执行器 |
| `standards/SANDBOX-v1.0.md` | 完整沙箱规范文档 |

### 验证测试

```
✅ 默认配置验证通过
✅ 危险配置 (host) 被安全策略阻止
✅ docker run 参数正确生成
```

### 待完成

- [ ] 将 sandbox/docker.py 替换为 secure_executor
- [ ] 添加工具策略 (allow/deny list)
- [ ] 添加 setupCommand 支持
- [ ] 添加容器清理 (prune) 策略
- [ ] 构建安全镜像 heimaclaw-sandbox:bookworm-slim

---

_决策时间: 2026-03-25 12:25_

---

## 决策 #023: DockerSandboxBackend OpenClaw 安全模式集成

### 实现内容

**1. DockerSandboxBackend 新增安全参数**

```python
DockerSandboxBackend(
    security_mode=True,       # 启用 OpenClaw 安全模式 (默认)
    network_mode="none",      # 网络隔离 (none/bridge/host)
    container_user="1000:1000", # 非 root 用户
    read_only_root=True,      # 只读根文件系统
    pids_limit=256,          # PID 数量限制
    memory_limit="1g",        # 内存限制
    memory_swap="2g",         # Swap 限制
    tmpfs=["/tmp", ...],     # 临时文件系统内存化
    cap_drop=["ALL"],         # 移除所有 capabilities
)
```

**2. AgentConfig 新增安全配置字段**

```python
sandbox_security_mode=True    # 启用安全模式
sandbox_network_mode="none"   # 网络模式
sandbox_container_user="1000:1000"  # 容器用户
sandbox_read_only_root=True   # 只读根文件系统
sandbox_pids_limit=256        # PID 限制
```

**3. 安全模式 vs 遗留模式**

| 模式 | security_mode=True | security_mode=False |
|------|-------------------|---------------------|
| 网络 | --network=none | --net=host |
| 用户 | --user=1000:1000 | root |
| Capabilities | --cap-drop=ALL | 无限制 |
| 根文件系统 | --read-only | 可写 |
| PID 限制 | --pids-limit=256 | 无限制 |
| 内存 | --memory=1g | 无限制 |
| Tmpfs | --tmpfs /tmp | 无 |

### 修改文件

| 文件 | 修改 |
|------|------|
| `sandbox/docker.py` | 添加安全参数，默认启用 |
| `interfaces.py` | 添加 AgentConfig 安全字段 |
| `feishu_multiprocess.py` | 从 agent.json 加载安全配置 |
| `agent/runner.py` | 传递安全配置给沙箱后端 |

### 默认行为（向后兼容）

- **新 Agent**: 默认 `security_mode=True`，使用 `--network=none`
- **遗留 Agent**: 如果设置 `security_mode=False`，使用旧有 `--net=host` 行为
- **Docker 镜像**: 仍使用 `python:3.10-slim`（后续可改为 heimaclaw-sandbox 镜像）

### 注意事项

`--network=none` 模式下：
- 容器无法访问外网（pip install 会失败）
- 如需网络访问，设置 `network_mode="bridge"`
- 后续可实现 `setupCommand` 在容器创建时安装依赖

---

_决策时间: 2026-03-25 12:35_

---

## 决策 #024: 默认网络模式改为 bridge

### 变更原因

`network=none`（无网络）会导致：
- `pip install` 无法下载包
- 容器内无法访问任何外部服务
- 网站无法正常工作

### 决策

采用 `network=bridge`（桥接网络）：
- 容器可以访问外网（pip install 正常工作）
- 服务端口通过 `--net=host` 或端口映射对外暴露
- 安全措施仍保留（user/pid限制/cap_drop/readonly）

### 最终默认配置

```python
DockerSandboxBackend(
    security_mode=True,
    network_mode="bridge",      # 改为 bridge（可访问外网）
    container_user="1000:1000", # 非 root
    read_only_root=True,        # 只读根文件系统
    pids_limit=256,             # PID 限制
    memory="1g",                # 内存限制
    tmpfs=["/tmp", ...],        # 临时文件内存化
    cap_drop=["ALL"],           # 移除所有 capabilities
)
```

---

_决策时间: 2026-03-25 12:41_
