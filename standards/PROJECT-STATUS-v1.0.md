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

### FastAPI 服务骨架（接口完成度 50%）
- [x] 基础 FastAPI 应用
- [x] 飞书 webhook 端点
- [x] 企业微信 webhook 端点
- [ ] 消息路由到 Agent
- [ ] 会话管理 API

### 接口定义模块（接口完成度 100%）
- [x] ConfigProvider 接口
- [x] SandboxBackend 接口
- [x] ChannelAdapter 接口
- [x] SessionStore 接口
- [x] ToolRegistry 接口
- [x] AgentRunner 接口
- [x] 数据模型定义（AgentConfig、SessionContext、Message 等）

### CI/CD 流水线（接口完成度 80%）
- [x] GitHub Actions 工作流
- [x] ruff lint 检查
- [x] pytest 测试
- [x] wheel 构建
- [x] PyPI 发布配置
- [x] GitHub Release 发布

## 进行中模块

### 控制台输出模块（接口完成度 90%）
- [x] rich 颜色主题
- [x] 多级别日志函数
- [x] NO_COLOR 支持
- [x] 表格/面板输出
- [ ] 文件日志集成

## 待启动模块

### 沙箱抽象层模块
- [ ] Firecracker 后端实现
- [ ] 预热池管理
- [ ] 快照恢复
- [ ] vsock 通信
- [ ] cgroup v2 限流

### Agent 运行时模块
- [ ] Agent 生命周期管理
- [ ] 会话管理
- [ ] 工具调用循环
- [ ] 消息持久化

### 渠道适配器模块
- [ ] 飞书适配器实现
- [ ] 企业微信适配器实现
- [ ] 消息解析
- [ ] 消息发送

## 当前活跃分支
- main
- feat/cli-skeleton（待推送）

## 下一步意图
1. 将 CLI 骨架代码推送到 GitHub
2. 完善 channel setup 交互式配置
3. 实现 Firecracker 沙箱后端

## 关键指标
- 已定义接口数：6
- 已实现接口数：2（ConfigLoader、CLI 命令）
- 阻塞项：0
