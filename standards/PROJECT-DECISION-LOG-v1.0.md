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
