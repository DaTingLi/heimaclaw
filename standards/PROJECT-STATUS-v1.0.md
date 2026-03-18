# 项目状态看板（模块 & 任务驱动版）
最后更新：2026-03-18 18:40

## 已完成模块

### CLI 骨架模块（接口完成度 100%）
- [x] heimaclaw --help（帮助信息）
- [x] heimaclaw --version（版本显示）
- [x] heimaclaw init（项目初始化）
- [x] heimaclaw start（启动服务）
- [x] heimaclaw status（状态显示）
- [x] heimaclaw doctor（环境诊断）
- [x] heimaclaw config show/set/edit（配置管理）
- [x] heimaclaw agent create/list（Agent 管理）
- [x] heimaclaw channel setup（渠道配置）

### 配置系统模块（接口完成度 80%）
- [x] ConfigLoader 配置加载器
- [x] Pydantic 配置模型定义
- [x] 多路径配置查找
- [ ] 环境变量覆盖
- [ ] 配置热重载

### 接口定义模块（接口完成度 100%）
- [x] ConfigProvider 接口
- [x] SandboxBackend 接口
- [x] ChannelAdapter 接口
- [x] SessionStore 接口
- [x] ToolRegistry 接口
- [x] AgentRunner 接口
- [x] 数据模型定义

### 沙箱抽象层模块（接口完成度 85%）
- [x] SandboxBackend 抽象基类
- [x] FirecrackerBackend 实现
- [x] WarmPool 预热池
- [x] 实例创建/销毁
- [x] 命令执行
- [x] Firecracker 安装（v1.15.0）
- [x] Linux kernel（v5.15.0）
- [x] Alpine rootfs（128MB）
- [x] microVM 启动测试
- [ ] vsock 通信
- [ ] 快照创建/恢复
- [ ] cgroup v2 限流
- [ ] seccomp 过滤

### Agent 运行时模块（接口完成度 90%）
- [x] AgentRunner 运行器
- [x] SessionManager 会话管理器
- [x] ToolRegistry 工具注册表
- [x] 会话创建/查询/更新/删除
- [x] 消息存储/获取
- [x] 工具注册/执行（装饰器模式）
- [x] OpenAI 格式工具定义
- [x] 消息处理循环框架
- [x] LLM 调用集成
- [ ] 沙箱中工具执行

### 渠道适配器模块（接口完成度 60%）
- [x] ChannelAdapter 抽象基类
- [x] FeishuAdapter 飞书适配器
- [x] WeComAdapter 企业微信适配器
- [x] 消息解析框架
- [x] Token 缓存管理
- [ ] 完整的消息发送测试
- [ ] 卡片消息完整实现
- [ ] 企业微信消息解密

### LLM 集成模块（接口完成度 90%）
- [x] LLMAdapter 抽象基类
- [x] OpenAICompatibleAdapter
- [x] OpenAI 适配器
- [x] Claude 适配器
- [x] GLM 智谱适配器
- [x] DeepSeek 适配器
- [x] Qwen 通义千问适配器
- [x] vLLM 自定义部署适配器
- [x] Ollama 本地模型适配器
- [x] LLMRegistry 注册表
- [x] 工具调用支持
- [x] 流式输出
- [x] 真实 API 测试（智谱 GLM）

### FastAPI 服务模块（接口完成度 90%）
- [x] 基础 FastAPI 应用
- [x] 飞书 webhook 端点
- [x] 企业微信 webhook 端点
- [x] Agent 自动加载
- [x] 消息路由到 Agent
- [x] 会话管理 API
- [x] Agent 管理 API
- [x] 服务启动测试
- [ ] 真实飞书/企微联调

### CI/CD 流水线（接口完成度 100%）
- [x] GitHub Actions 工作流
- [x] ruff lint 检查
- [x] pytest 测试
- [x] wheel 构建
- [x] PyPI 发布配置
- [x] GitHub Release 发布
- [x] CI 通过验证 ✅

### 控制台输出模块（接口完成度 100%）
- [x] rich 颜色主题
- [x] 多级别日志函数
- [x] NO_COLOR 支持
- [x] 表格/面板输出

## 当前活跃分支
- master

## 已验证功能

### 服务启动
```
heimaclaw start
✓ 加载 3 个 Agent
✓ 服务运行在 0.0.0.0:8000
✓ API 端点可用
```

### Firecracker
```
✓ 安装成功: v1.15.0
✓ KVM 硬件虚拟化可用
✓ microVM 启动测试成功
✓ kernel: /opt/heimaclaw/images/vmlinux
✓ rootfs: /opt/heimaclaw/images/rootfs.ext4
```

### LLM 调用
```
智谱 GLM API
✓ 响应延迟: 598ms
✓ Token 统计正确
✓ 两轮对话正常
```

### CI/CD
```
✓ 代码检查
✓ 类型检查
✓ 单元测试
✓ 构建 wheel
```

## 下一步意图
1. 真实飞书/企微联调测试
2. 实现 vsock 通信
3. 生产部署（systemd + 监控）

## 关键指标
- 已定义接口数：7
- 已实现接口数：7
- 阻塞项：0
- 代码行数：约 9000+ 行
- CI/CD：通过 ✅
- Firecracker：已安装 ✅

## 模块 SPEC 文档
- [x] CLI 模块 SPEC
- [x] 沙箱模块 SPEC
- [x] Agent 运行时 SPEC
- [x] 渠道适配器 SPEC
- [x] LLM 集成 SPEC

## LLM 支持矩阵

| 厂商 | Provider | 模型示例 | API 格式 | 测试状态 |
|------|----------|---------|---------|---------|
| 智谱 GLM | `glm` | glm-4-flash | OpenAI 兼容 | ✅ 已测试 |
| DeepSeek | `deepseek` | deepseek-chat | OpenAI 兼容 | 待测试 |
| 通义千问 | `qwen` | qwen-turbo | OpenAI 兼容 | 待测试 |
| OpenAI | `openai` | gpt-4 | 原生 | 待测试 |
| Claude | `claude` | claude-3-sonnet | 原生 | 待测试 |
| vLLM | `vllm` | 用户部署 | OpenAI 兼容 | 待测试 |
| Ollama | `ollama` | llama2 | OpenAI 兼容 | 待测试 |

## 工具系统完成

### CLI 工具命令
```
heimaclaw tool install <source>   # 安装工具
heimaclaw tool uninstall <name>   # 卸载工具
heimaclaw tool list               # 列出工具
heimaclaw tool info <name>        # 查看详情
heimaclaw tool enable <name>      # 启用工具
heimaclaw tool disable <name>     # 禁用工具
heimaclaw tool create <name>      # 创建模板
```

### 测试验证
```
✓ 工具安装成功（sysinfo）
✓ 工具加载成功（2个函数）
✓ get_system_info 执行成功
✓ get_disk_usage 执行成功
✓ OpenAI 格式导出成功
```

### 示例工具
- sysinfo: 系统信息查询（get_system_info, get_disk_usage）
- weather: 示例工具（weather_example）

## 生产部署完成

### 部署组件
- [x] systemd 服务配置
- [x] 开机自启
- [x] 资源限制
- [x] 日志轮转配置

### Token 监控系统
- [x] TokenUsageTracker（SQLite 存储）
- [x] 每次 LLM 调用自动记录
- [x] 按时间/Agent/提供商过滤
- [x] 每日使用量查询
- [x] 旧记录自动清理

### 监控 API 端点
```
GET /api/monitoring/health        - 健康检查
GET /api/monitoring/token-stats   - Token 统计
GET /api/monitoring/daily-usage   - 每日使用量
GET /api/monitoring/agent-usage/{id} - Agent 统计
```

### 监控 CLI 命令
```bash
heimaclaw monitoring token-stats  - Token 统计
heimaclaw monitoring daily-usage  - 每日使用量
heimaclaw monitoring clear-old    - 清理旧记录
```

### 部署文档
- deploy/README.md（完整部署指南）
- deploy/heimaclaw.service（systemd 配置）
