# HeiMaClaw 端到端测试计划

**版本**: v1.0  
**创建日期**: 2026-03-19  
**目的**: 工业级应用测试覆盖

---

## 1. CLI 命令清单

### 1.1 主命令
| 命令 | 功能 | 优先级 |
|------|------|--------|
| `heimaclaw --help` | 显示帮助 | P0 |
| `heimaclaw --version` | 显示版本 | P0 |
| `heimaclaw init` | 初始化项目 | P0 |
| `heimaclaw start` | 启动服务 | P1 |
| `heimaclaw status` | 显示状态 | P1 |
| `heimaclaw doctor` | 环境诊断 | P0 |
| `heimaclaw start-ws` | 启动 WebSocket | P1 |

### 1.2 config 子命令
| 命令 | 功能 | 优先级 |
|------|------|--------|
| `heimaclaw config show` | 显示全部配置 | P0 |
| `heimaclaw config show <key>` | 显示指定配置 | P0 |
| `heimaclaw config set <key> <value>` | 设置配置项 | P1 |
| `heimaclaw config edit` | 编辑配置文件 | P2 |

### 1.3 agent 子命令
| 命令 | 功能 | 优先级 |
|------|------|--------|
| `heimaclaw agent create <name>` | 创建 Agent | P0 |
| `heimaclaw agent list` | 列出所有 Agent | P0 |
| `heimaclaw agent compile [name]` | 编译配置 | P0 |
| `heimaclaw agent compile --watch` | 监听模式 | P1 |
| `heimaclaw agent create-md <name>` | 创建 Markdown Agent | P1 |

### 1.4 channel 子命令
| 命令 | 功能 | 优先级 |
|------|------|--------|
| `heimaclaw channel setup feishu` | 配置飞书 | P1 |
| `heimaclaw channel setup wecom` | 配置企微 | P1 |

### 1.5 tool 子命令
| 命令 | 功能 | 优先级 |
|------|------|--------|
| `heimaclaw tool install <source>` | 安装工具 | P1 |
| `heimaclaw tool uninstall <name>` | 卸载工具 | P1 |
| `heimaclaw tool list` | 列出工具 | P0 |
| `heimaclaw tool info <name>` | 工具详情 | P1 |
| `heimaclaw tool enable <name>` | 启用工具 | P1 |
| `heimaclaw tool disable <name>` | 禁用工具 | P1 |
| `heimaclaw tool create <name>` | 创建工具 | P2 |

### 1.6 monitoring 子命令
| 命令 | 功能 | 优先级 |
|------|------|--------|
| `heimaclaw monitoring token-stats` | Token 统计 | P1 |
| `heimaclaw monitoring daily-usage` | 每日使用 | P1 |
| `heimaclaw monitoring clear-old` | 清理旧数据 | P2 |

### 1.7 bindings 子命令
| 命令 | 功能 | 优先级 |
|------|------|--------|
| `heimaclaw bindings bind-user <user>` | 绑定用户 | P1 |
| `heimaclaw bindings bind-group <chat>` | 绑定群聊 | P1 |
| `heimaclaw bindings unbind-user <user>` | 解绑用户 | P1 |
| `heimaclaw bindings unbind-group <chat>` | 解绑群聊 | P1 |
| `heimaclaw bindings set-default <agent>` | 设置默认 | P1 |
| `heimaclaw bindings list` | 列出绑定 | P0 |
| `heimaclaw bindings clear` | 清空绑定 | P2 |

### 1.8 会话命令
| 命令 | 功能 | 优先级 |
|------|------|--------|
| `heimaclaw session-list` | 列出会话 | P1 |
| `heimaclaw session-clear --agent <name>` | 清除会话 | P1 |
| `heimaclaw session-clear-all` | 清除所有 | P2 |

---

## 2. 测试场景（按优先级）

### P0 - 核心功能（必须通过）

#### T0-1: 帮助和版本
```bash
heimaclaw --help
heimaclaw --version
```
**预期**: 正常显示帮助信息和版本号

#### T0-2: 环境诊断
```bash
heimaclaw doctor
```
**预期**: 显示所有检查项状态

#### T0-3: 项目初始化
```bash
heimaclaw init --path /tmp/test-heimaclaw
heimaclaw config show
```
**预期**: 
- 目录结构正确创建
- config.toml 存在且格式正确

#### T0-4: 创建 Agent
```bash
heimaclaw agent create test-agent
heimaclaw agent list
heimaclaw config show
```
**预期**:
- Agent 目录和文件创建成功
- `heimaclaw agent list` 显示新 Agent

#### T0-5: Agent 编译
```bash
heimaclaw agent compile test-agent
ls -la ~/.heimaclaw/agents/test-agent/.compiled/
```
**预期**:
- Markdown → JSON 编译成功
- `.compiled/agent.compiled.json` 生成

#### T0-6: 配置热重载
```bash
# 启动服务（后台）
heimaclaw start &
sleep 2

# 修改配置
heimaclaw config set logging.level DEBUG

# 验证热重载触发
# 检查日志
```
**预期**: 配置变更自动重载

---

### P1 - 重要功能

#### T1-1: 渠道配置引导
```bash
heimaclaw channel setup feishu
# 输入测试 App ID 和 Secret
```
**预期**: 交互式配置完成

#### T1-2: Token 统计
```bash
heimaclaw monitoring token-stats
heimaclaw monitoring daily-usage
```
**预期**: 显示统计数据（可为空）

#### T1-3: Agent 绑定
```bash
heimaclaw bindings bind-user test-user-123 --agent test-agent
heimaclaw bindings list
heimaclaw bindings unbind-user test-user-123
```
**预期**: 绑定/解绑成功

#### T1-4: 会话管理
```bash
heimaclaw session-list
heimaclaw session-clear --agent test-agent
```
**预期**: 会话列表显示/清除成功

---

### P2 - 次要功能

#### T2-1: 工具管理
```bash
heimaclaw tool create my-tool --path /tmp
heimaclaw tool list
heimaclaw tool info my-tool
heimaclaw tool disable my-tool
heimaclaw tool enable my-tool
heimaclaw tool uninstall my-tool
```
**预期**: 工具创建、查询、启用/禁用、卸载正常

#### T2-2: 编译监听模式
```bash
heimaclaw agent compile --watch
# 修改 Markdown 文件
# 验证自动重新编译
```
**预期**: 文件变更自动触发编译

---

## 3. 测试数据

### 测试 Agent
- `test-agent` - 通用测试 Agent
- `test-bot` - Bot 测试用

### 测试用户/群组
- `user:test-001`
- `group:chat-001`

### 测试配置路径
- `/tmp/heimaclaw-test/` - 测试用临时目录
- `~/.heimaclaw/` - 用户目录

---

## 4. 测试执行

### 顺序执行
```bash
# 1. 环境检查
heimaclaw doctor

# 2. 初始化测试环境
heimaclaw init --path /tmp/heimaclaw-e2e

# 3. 核心功能测试
heimaclaw agent create e2e-test
heimaclaw agent compile e2e-test
heimaclaw agent list

# 4. 配置测试
heimaclaw config show
heimaclaw config set logging.level DEBUG

# 5. 绑定测试
heimaclaw bindings bind-user test-user --agent e2e-test
heimaclaw bindings list

# 6. 清理
heimaclaw session-clear --agent e2e-test
```

### 自动化测试脚本
```python
# tests/e2e/test_cli_e2e.py
import pytest
from typer.testing import CliRunner

runner = CliRunner()

def test_init():
    result = runner.invoke(app, ["init", "--path", "/tmp/test-heimaclaw"])
    assert result.exit_code == 0

def test_agent_create():
    result = runner.invoke(app, ["agent", "create", "test-agent"])
    assert result.exit_code == 0
```

---

## 5. 验收标准

| 级别 | 通过率 | 说明 |
|------|--------|------|
| P0 | 100% | 核心功能必须全部通过 |
| P1 | ≥90% | 重要功能允许少量失败 |
| P2 | ≥80% | 次要功能允许部分失败 |

---

## 6. 测试报告

测试结果应包含：
- ✅ 通过的命令数
- ❌ 失败的命令数
- ⏱ 执行时间
- 📊 覆盖率

---

**下一步**:
1. 创建自动化测试脚本
2. 执行 P0 测试
3. 修复失败的测试
