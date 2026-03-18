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

## 进行中模块

### Agent 运行时模块（接口完成度 0%）
- [ ] Agent 生命周期管理
- [ ] 会话管理
- [ ] 工具调用循环
- [ ] 消息持久化

## 待启动模块

### 渠道适配器模块
- [ ] 飞书适配器实现
- [ ] 企业微信适配器实现
- [ ] 消息解析
- [ ] 消息发送

## 当前活跃分支
- master

## 下一步意图
1. 实现 Agent 运行时模块（会话管理、工具调用循环）
2. 完善渠道适配器（飞书/企微）
3. 安装 Firecracker 实现完整 microVM 隔离

## 关键指标
- 已定义接口数：6
- 已实现接口数：4（ConfigLoader、SandboxBackend、CLI 命令、WarmPool）
- 阻塞项：0

## 模块 SPEC 文档
- [x] CLI 模块 SPEC
- [x] 沙箱模块 SPEC
