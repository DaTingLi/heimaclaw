# 终端命令规范与列表 (CLI Commands Standard)

本文档基于 `src/heimaclaw/cli.py` 实际代码，梳理目前支持的全部终端命令。

## 1. 基础命令 (Base Commands)

### 1.1 服务管理

- `heimaclaw --help` : 查看帮助
- `heimaclaw --version` / `-v` : 显示版本信息
- `heimaclaw init [--path/-p <path>] [--force/-f]` : 初始化项目目录结构和默认配置
- `heimaclaw start` : 启动 HeiMaClaw 服务（HTTP API + 飞书长连接）
- `heimaclaw start-ws` : 启动独立的飞书 WebSocket 长连接服务
- `heimaclaw status` : 显示当前系统运行状态、沙箱状态、渠道状态
- `heimaclaw doctor` : 诊断运行环境（Python版本、KVM、Firecracker、端口、网络连通性等）
- `heimaclaw stop [--force/-f]` : 停止服务
- `heimaclaw restart [--force/-f]` : 重启服务
- `heimaclaw pid` : 查看运行中的进程 ID
- `heimaclaw log [--lines/-n <lines>] [--follow/-f]` : 查看全局日志

## 2. 配置管理 (Config App)

- `heimaclaw config show [key]` : 显示当前配置或指定键的配置
- `heimaclaw config set <key> <value>` : 设置配置项（如 `channels.feishu.app_id xxx`）
- `heimaclaw config edit` : 使用默认编辑器编辑配置文件

## 3. Agent 管理 (Agent App)

- `heimaclaw agent create <name> [--workspace <path>]` : 极简创建 Agent 环境及 Markdown 配置
- `heimaclaw agent list` : 列出所有 Agent
- `heimaclaw agent clear-history <name>` : 清除指定 Agent 的历史会话
- `heimaclaw agent set-llm <name> --provider <provider> --model <model>` : 设置 Agent 的 LLM 配置
- `heimaclaw agent set-policy <name> [--mode/-m <mode>] [--scope/-s <scope>]` : 设置 Agent 的响应策略
- `heimaclaw agent show-policy <name>` : 显示 Agent 的响应策略

## 4. 绑定管理 (Bindings App)

- `heimaclaw bindings bind-user <user_id> [--agent/-a <name>]` : 绑定私聊用户到指定 Agent
- `heimaclaw bindings bind-group <chat_id> [--agent/-a <name>]` : 绑定群聊到指定 Agent
- `heimaclaw bindings unbind-user <user_id>` : 解绑用户
- `heimaclaw bindings unbind-group <chat_id>` : 解绑群聊
- `heimaclaw bindings set-default <agent_name>` : 设置全局默认兜底 Agent
- `heimaclaw bindings list` : 列表查看所有绑定
- `heimaclaw bindings clear [--yes/-y]` : 清空绑定
- `heimaclaw bindings discover` : 从历史会话中发现群聊 ID

## 5. 渠道配置 (Channel App)

- `heimaclaw channel setup <channel>` : 交互式配置渠道（飞书 feishu / 企业微信 wecom）
  - 注意：此命令为交互式引导配置，不支持 `--app-id`、`--app-secret` 等命令行参数
  - 配置完成后会自动保存到配置文件

## 6. 工具管理 (Tool App)

- `heimaclaw tool install <source>` : 安装工具（支持本地路径、Git URL、PyPI）
- `heimaclaw tool uninstall <name>` : 卸载工具
- `heimaclaw tool list` : 列出已安装工具
- `heimaclaw tool info <name>` : 查看工具详细信息
- `heimaclaw tool enable <name>` : 启用工具
- `heimaclaw tool disable <name>` : 禁用工具

## 7. 监控统计 (Monitoring App)

- `heimaclaw monitoring token-stats [--agent/-a <name>] [--days/-d <days>]` : 显示 Token 消耗统计
- `heimaclaw monitoring daily-usage [--agent/-a <name>] [--days/-d <days>]` : 显示每日使用量趋势
- `heimaclaw monitoring clear-old [--days/-d <days>]` : 清理过期数据

## 8. 任务状态 (Task App)

- `heimaclaw task-status` : 查看当前子任务(Subagent)的执行状态

## 使用示例

### 创建新 Agent

```bash
heimaclaw agent create my_agent --workspace /path/to/agents/my_agent
cd /path/to/agents/my_agent/my_agent
# 编辑 SOUL.md, IDENTITY.md, TOOLS.md 等配置文件
heimaclaw start  # 启动服务
```

### 配置飞书渠道

```bash
heimaclaw channel setup feishu
# 按提示输入 App ID 和 App Secret
```

### 绑定用户到 Agent

```bash
heimaclaw bindings bind-user ou_xxxxx --agent my_agent
heimaclaw bindings set-default my_agent
```

### 查看状态

```bash
heimaclaw status
heimaclaw doctor
heimaclaw log --follow
```

---

**更新日期**: 2026-03-22  
**版本**: v1.0
