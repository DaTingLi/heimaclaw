# 终端命令规范与列表 (CLI Commands Standard)

本文档基于 `src/heimaclaw/cli.py` 实际代码，梳理目前支持的全部终端命令。

## 1. 基础命令 (Base Commands)

- `heimaclaw --help` : 查看帮助。
- `heimaclaw --version` / `-v` : 显示版本信息。
- `heimaclaw init [--path/-p] [--force/-f]` : 初始化项目目录结构和默认配置。
- `heimaclaw start [--host/-h] [--port/-p] [--workers/-w] [--reload] [--feishu/--no-feishu] [--http/--no-http]` : 启动服务 (HTTP和/或飞书)。
- `heimaclaw start-ws` : 启动独立的飞书 WebSocket 长连接服务。
- `heimaclaw status` : 显示当前系统运行状态、沙箱状态、渠道状态（注意：不支持 `--status`）。
- `heimaclaw doctor` : 诊断运行环境（Python版本、KVM、Firecracker、端口等）。
- `heimaclaw stop [--force/-f]` : 停止服务。
- `heimaclaw restart [--force/-f]` : 重启服务。
- `heimaclaw pid` : 查看运行中的进程ID。
- `heimaclaw log [--lines/-n] [--follow/-f]` : 查看日志。

## 2. 配置管理 (Config App)

- `heimaclaw config show [key]` : 显示当前配置或指定键的配置。
- `heimaclaw config set <key> <value>` : 设置配置项（如 `channels.feishu.accounts.default.app_id`）。
- `heimaclaw config edit` : 使用默认编辑器编辑配置文件。

## 3. Agent 管理 (Agent App)

- `heimaclaw agent create <name> [--channel/-c] [--description/-d]` : 创建 JSON 格式的 Agent（默认保存至 `/opt/heimaclaw/data/agents` 或 `~/.heimaclaw/agents`）。
- `heimaclaw agent create-md <name> [--template/-t]` : 创建 Markdown 格式的 Agent (SOUL.md, IDENTITY.md 等)。
- `heimaclaw agent list` : 列出所有 Agent。
- `heimaclaw agent compile [name] [--force/-f] [--watch/-w]` : 将 Markdown 配置编译为 JSON。
- `heimaclaw agent set-policy <name> [--mode/-m] [--scope/-s] [--allow-users] [--allow-groups]` : 设置 Agent 的响应策略（@提及、允许的群组等）。
- `heimaclaw agent show-policy <name>` : 查看响应策略。

## 4. 绑定管理 (Bindings App)

**核心特点**: 当前基于细粒度的用户和群组进行绑定。

- `heimaclaw bindings bind-user <user_id> [--agent/-a]` : 绑定私聊用户到指定 Agent。
- `heimaclaw bindings bind-group <chat_id> [--agent/-a]` : 绑定群聊到指定 Agent。
- `heimaclaw bindings unbind-user <user_id>` : 解绑用户。
- `heimaclaw bindings unbind-group <chat_id>` : 解绑群聊。
- `heimaclaw bindings set-default <agent_name>` : 设置全局默认兜底 Agent。
- `heimaclaw bindings list` : 列表查看所有绑定。
- `heimaclaw bindings clear [--yes/-y]` : 清空绑定。
- `heimaclaw bindings discover` : 从历史会话中发现群聊 ID (`chat_id`)。

## 5. 工具管理 (Tool App)

- `heimaclaw tool install <source>` : 安装工具（支持本地路径、Git URL、PyPI）。
- `heimaclaw tool uninstall <name>` : 卸载工具。
- `heimaclaw tool list` : 列出已安装工具。
- `heimaclaw tool info <name>` : 查看工具详细信息。
- `heimaclaw tool enable <name>` : 启用工具。
- `heimaclaw tool disable <name>` : 禁用工具。
- `heimaclaw tool create <name> [--path/-p]` : 创建工具开发模板。

## 6. 会话管理 (Session App)

- `heimaclaw session-list` : 列出所有会话文件。
- `heimaclaw session-clear [--agent/-a]` : 清理指定 Agent 的会话。
- `heimaclaw session-clear-all [--yes/-y]` : 清理所有会话。

## 7. 监控统计 (Monitoring App)

- `heimaclaw monitoring token-stats [--agent/-a] [--provider/-p] [--days/-d]` : 显示 Token 消耗统计。
- `heimaclaw monitoring daily-usage [--agent/-a] [--days/-d]` : 显示每日使用量趋势。
- `heimaclaw monitoring clear-old [--days/-d]` : 清理过期数据。

## 8. 渠道向导 (Channel App)

- `heimaclaw channel setup <channel>` : 交互式配置飞书或企微（目前支持单渠道快速向导）。
