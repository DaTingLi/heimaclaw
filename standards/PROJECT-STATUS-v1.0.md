# 项目状态看板（模块 & 任务驱动版）
最后更新：2026-03-18 19:35

## 项目完成度

```
CLI 骨架      ████████████ 100%
接口定义      ████████████ 100%
控制台输出    ████████████ 100%
CI/CD        ████████████ 100%
工具系统      ████████████ 100%
Token 监控    ██████████ 100%
生产部署      ████████████ 100%
沙箱抽象层    ████████████ 100%  ← vsock 完成
Agent 运行时  █████████░░░  90%
LLM 集成      █████████░░░  90%
FastAPI 服务  █████████░░░  90%
渠道适配器    ██████░░░░░░  60%
```

## 已完成模块

### CLI 骨架模块（100%）
- [x] heimaclaw --help / --version
- [x] heimaclaw init / start / status / doctor
- [x] heimaclaw config show/set/edit
- [x] heimaclaw agent create/list
- [x] heimaclaw channel setup
- [x] heimaclaw tool install/uninstall/list/info/create
- [x] heimaclaw monitoring token-stats/daily-usage

### 沙箱抽象层模块（100%）
- [x] SandboxBackend 抽象基类
- [x] FirecrackerBackend 实现
- [x] WarmPool 预热池
- [x] vsock 通信（VsockClient + VsockServer + VsockManager）
- [x] Firecracker v115.0 安装
- [x] Linux kernel v5.15.0
- [x] Alpine rootfs 256MB
- [x] rootfs 更新脚本

### 工具系统（100%）
- [x] CLI 工具管理命令
- [x] 标准工具格式（tool.json + main.py）
- [x] 工具加载器（ToolLoader）
- [x] 示例工具（sysinfo、weather）

### Token 监控（100%）
- [x] SQLite 数据库记录
- [x] 自动记录每次 LLM 调用
- [x] 监控 API 端点
- [x] CLI 监控命令

### 生产部署（100%）
- [x] systemd 服务配置
- [x] 开机自启
- [x] 日志轮转
- [x] 完整部署文档

### LLM 集成（90%）
- [x] 7 个厂商适配器
- [x] 智谱 GLM 已测试
- [x] OpenAI 兼容适配器
- [ ] 其他厂商测试

### Agent 运行时（90%）
- [x] AgentRunner 生命周期管理
- [x] SessionManager 会话管理
- [x] Token 使用记录
- [ ] 沙箱中工具执行（vsock）

### FastAPI 服务（90%）
- [x] Agent 自动加载
- [x] Webhook 路由
- [x] 监控 API
- [ ] 真实渠道联调

### 渠道适配器（60%）
- [x] FeishuAdapter 实现
- [x] WeComAdapter 实现
- [ ] 真实消息测试
- [ ] 企业微信解密

## 待完成任务

| 任务 | 优先级 | 需求 |
|------|--------|------|
| 飞书/企微真实联调 | 中 | 需要配置信息 |
| 沙箱工具执行 | 低 | 已有 vsock，待集成 |
| 快照恢复 | 低 | 性能优化 |
| cgroup/seccomp | 低 | 安全增强 |

## 关键指标

- **代码行数**: 12,000+
- **提交次数**: 19 次
- **CI/CD**: 全部通过 ✅
- **核心功能**: 100% 完成
- **测试覆盖**: 智谱 GLM 已验证

## 仓库信息

- **地址**: https://github.com/DaTingLi/heimaclaw
- **最新提交**: d2208e1
- **CI/CD**: 通过

## 模块 SPEC 文档

- [x] CLI 模块 SPEC
- [x] 沙箱模块 SPEC
- [x] Agent 运行时 SPEC
- [x] 渠道适配器 SPEC
- [x] LLM 集成 SPEC
