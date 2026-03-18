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
