# 项目状态看板（模块 & 任务驱动版）
最后更新：2026-03-18

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
- [x] 数据模型定义（AgentConfig、SessionContext、Message 等）

### 沙箱抽象层模块（接口完成度 70%）
- [x] SandboxBackend 抽象基类
- [x] FirecrackerBackend 实现（含降级模式）
- [x] WarmPool 预热池
- [x] 实例创建/销毁
- [x] 命令执行（降级模式）
- [ ] vsock 通信
- [ ] 快照创建/恢复
- [ ] cgroup v2 限流
- [ ] seccomp 过滤

### Agent 运行时模块（接口完成度 80%）
- [x] AgentRunner 运行器
- [x] SessionManager 会话管理器
- [x] ToolRegistry 工具注册表
- [x] 会话创建/查询/更新/删除
- [x] 消息存储/获取
- [x] 工具注册/执行（装饰器模式）
- [x] OpenAI 格式工具定义
- [x] 消息处理循环框架
- [ ] LLM 调用集成（已实现，待联调）
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
- [x] OpenAICompatibleAdapter（OpenAI 兼容）
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
- [ ] 完整测试覆盖

### FastAPI 服务骨架（接口完成度 50%）
- [x] 基础 FastAPI 应用
- [x] 飞书 webhook 端点
- [x] 企业微信 webhook 端点
- [ ] 消息路由到 Agent
- [ ] 会话管理 API

### CI/CD 流水线（接口完成度 80%）
- [x] GitHub Actions 工作流
- [x] ruff lint 检查
- [x] pytest 测试
- [x] wheel 构建
- [x] PyPI 发布配置
- [x] GitHub Release 发布

### 控制台输出模块（接口完成度 100%）
- [x] rich 颜色主题
- [x] 多级别日志函数
- [x] NO_COLOR 支持
- [x] 表格/面板输出

## 当前活跃分支
- master

## 下一步意图
1. 集成测试：Agent 运行时 + LLM + 渠道
2. 完善 Firecracker microVM 隔离
3. 实现完整的消息处理链路

## 关键指标
- 已定义接口数：7
- 已实现接口数：7（ConfigLoader、SandboxBackend、CLI、WarmPool、AgentRunner、ChannelAdapter、LLMAdapter）
- 阻塞项：0
- 代码行数：约 7000+ 行

## 模块 SPEC 文档
- [x] CLI 模块 SPEC
- [x] 沙箱模块 SPEC
- [x] Agent 运行时 SPEC
- [x] 渠道适配器 SPEC
- [x] LLM 集成 SPEC

## LLM 支持矩阵

| 厂商 | Provider | 模型示例 | API 格式 | 状态 |
|------|----------|---------|---------|------|
| **国内** |
| 智谱 GLM | `glm` | glm-4 | OpenAI 兼容 | 已实现 |
| DeepSeek | `deepseek` | deepseek-chat | OpenAI 兼容 | 已实现 |
| 通义千问 | `qwen` | qwen-turbo | OpenAI 兼容 | 已实现 |
| **国外** |
| OpenAI | `openai` | gpt-4 | 原生 | 已实现 |
| Claude | `claude` | claude-3-sonnet | 原生 | 已实现 |
| **自定义** |
| vLLM | `vllm` | 用户部署 | OpenAI 兼容 | 已实现 |
| Ollama | `ollama` | llama2 | OpenAI 兼容 | 已实现 |
