# HeiMaClaw

生产级企业 AI Agent 平台

## 概述

HeiMaClaw 是一个生产级的企业 AI Agent 平台，核心特点：

- **microVM 隔离**：每个 Agent/会话运行在独立 microVM（Firecracker）中，实现硬件级隔离
- **双渠道支持**：支持飞书和企业微信
- **CLI 驱动**：所有操作通过命令行完成，类似 OpenClaw
- **高可用架构**：预热池、快照恢复、资源限流

## 快速开始

### 安装

```bash
# 从源码安装
git clone https://github.com/DaTingLi/heimaclaw.git
cd heimaclaw
pip install -e .

# 或从 PyPI 安装（发布后）
pip install heimaclaw
```

### 初始化

```bash
# 初始化项目
heimaclaw init

# 查看配置
heimaclaw config show

# 诊断环境
heimaclaw doctor
```

### 启动服务

```bash
# 启动服务
heimaclaw start

# 开发模式（自动重载）
heimaclaw start --reload
```

### 创建 Agent

```bash
# 创建飞书 Agent
heimaclaw agent create my-bot --channel feishu

# 列出所有 Agent
heimaclaw agent list
```

### 配置渠道

```bash
# 配置飞书
heimaclaw channel setup feishu

# 配置企业微信
heimaclaw channel setup wecom
```

## 项目结构

```
heimaclaw/
├── src/heimaclaw/        # 源代码
│   ├── cli.py            # CLI 入口
│   ├── server.py         # FastAPI 服务
│   ├── console.py        # 控制台输出
│   ├── interfaces.py     # 接口定义
│   └── config/           # 配置模块
├── tests/                # 测试
├── standards/            # 开发规范
├── config/               # 配置文件
├── logs/                 # 日志
├── data/                 # 数据
└── sandboxes/            # 沙箱实例
```

## 命令参考

### 全局命令

| 命令 | 说明 |
|------|------|
| `heimaclaw --version` | 显示版本 |
| `heimaclaw --help` | 显示帮助 |
| `heimaclaw init` | 初始化项目 |
| `heimaclaw start` | 启动服务 |
| `heimaclaw status` | 显示状态 |
| `heimaclaw doctor` | 环境诊断 |

### 配置命令

| 命令 | 说明 |
|------|------|
| `heimaclaw config show` | 显示配置 |
| `heimaclaw config set <key> <value>` | 设置配置项 |
| `heimaclaw config edit` | 编辑配置文件 |

### Agent 命令

| 命令 | 说明 |
|------|------|
| `heimaclaw agent create <name>` | 创建 Agent |
| `heimaclaw agent list` | 列出 Agent |

### 渠道命令

| 命令 | 说明 |
|------|------|
| `heimaclaw channel setup feishu` | 配置飞书 |
| `heimaclaw channel setup wecom` | 配置企业微信 |

## 开发

### 环境要求

- Python 3.11+
- KVM 支持（可选，用于 microVM 隔离）
- Firecracker（可选，用于 microVM）

### 开发安装

```bash
# 克隆仓库
git clone https://github.com/DaTingLi/heimaclaw.git
cd heimaclaw

# 创建虚拟环境
python -m venv venv
source venv/bin/activate

# 安装开发依赖
pip install -e ".[dev]"

# 运行测试
pytest

# 代码检查
ruff check src/
mypy src/
```

## License

MIT
# Trigger CI
