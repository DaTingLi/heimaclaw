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
