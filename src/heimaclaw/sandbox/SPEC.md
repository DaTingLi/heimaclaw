# 沙箱模块 Spec 文档 v1.0

## 1. 概述与目标
- **项目/模块名称**：HeiMaClaw 沙箱模块
- **业务/功能目标**：提供 microVM 级别的沙箱隔离，确保每个 Agent/会话在独立环境中执行
- **范围**：
  - 包含：Firecracker 后端、预热池、快照管理、vsock 通信
  - 不包含：Agent 业务逻辑（由 Agent 运行时模块处理）

## 2. 需求来源与约束
- **来源文档**：DEVELOPMENT-NORM-v1.0.md
- **性能要求**：
  - 冷启动 < 200ms
  - 预热后获取 < 50ms
  - 单实例内存 < 20MB（目标）
- **安全/合规要求**：
  - KVM 硬件级隔离
  - 独立 guest kernel
  - cgroup v2 限流
  - seccomp 过滤
  - 路径隔离
  - 命令注入防护
  - 资源耗尽防护
- **时间窗口**：Phase 2 - 核心运行时

## 3. 系统架构
- **分层图**：
  ```
  SandboxModule
    ├── SandboxBackend（抽象接口）
    │   ├── FirecrackerBackend（首选）
    │   ├── DockerBackend（备选）
    │   └── ProcessBackend（降级）
    ├── WarmPool（预热池）
    │   ├── 实例预热
    │   ├── 快速获取
    │   └── 自动补充
    └── VsockChannel（通信通道）
        ├── 命令发送
        ├── 结果接收
        └── 超时处理
  ```
- **技术选型**：
  - Firecracker：microVM 实现
  - vsock：宿主机与 VM 通信
  - asyncio：异步操作
- **关键依赖**：Python 3.10+, KVM, Firecracker

## 4. 数据模型
- **核心实体**：
  - InstanceInfo：实例信息
  - ExecutionResult：执行结果
  - InstanceStatus：实例状态枚举

- **字段说明**：
  | 实体 | 字段 | 类型 | 说明 |
  |------|------|------|------|
  | InstanceInfo | instance_id | str | 实例唯一标识 |
  | InstanceInfo | agent_id | str | 关联的 Agent ID |
  | InstanceInfo | status | InstanceStatus | 实例状态 |
  | InstanceInfo | memory_mb | int | 内存大小 |
  | InstanceInfo | vsock_port | int | vsock 端口 |
  | ExecutionResult | exit_code | int | 退出码 |
  | ExecutionResult | stdout | str | 标准输出 |
  | ExecutionResult | stderr | str | 标准错误 |
  | ExecutionResult | duration_ms | int | 执行耗时 |

## 5. 接口设计
- **主要 API**：
  | 方法 | 功能 | 参数 | 返回 |
  |------|------|------|------|
  | create_instance | 创建实例 | agent_id, memory_mb, cpu_count | InstanceInfo |
  | destroy_instance | 销毁实例 | instance_id | None |
  | execute | 执行命令 | instance_id, command, timeout_ms | ExecutionResult |
  | create_snapshot | 创建快照 | instance_id, snapshot_id | str |
  | pause_instance | 暂停实例 | instance_id | None |
  | resume_instance | 恢复实例 | instance_id | None |

- **WarmPool API**：
  | 方法 | 功能 | 参数 | 返回 |
  |------|------|------|------|
  | warm_up | 预热实例 | 无 | None |
  | claim | 获取实例 | agent_id | InstanceInfo |
  | release | 释放实例 | instance | None |
  | drain | 清空池 | 无 | None |

## 6. 关键流程
- **创建实例流程**：
  1. 生成实例 ID
  2. 分配 vsock 端口
  3. 复制 rootfs
  4. 生成 Firecracker 配置
  5. 启动 Firecracker 进程
  6. 等待就绪（100ms）
  7. 返回实例信息

- **预热池获取流程**：
  1. 检查池中是否有实例
  2. 有则立即返回（< 50ms）
  3. 无则创建新实例
  4. 异步补充池

## 7. 安全设计
- **鉴权**：仅限本地进程访问
- **输入校验**：命令字符串过滤危险字符
- **隔离/沙箱**：
  - KVM 硬件虚拟化
  - 独立 kernel
  - 独立网络命名空间
  - cgroup 资源限制
  - seccomp 系统调用过滤

## 8. 性能与可扩展性
- **瓶颈点**：
  - Firecracker 冷启动时间
  - rootfs 复制时间
- **优化方案**：
  - 预热池减少冷启动
  - 快照恢复加速启动
  - CoW 文件系统减少复制
- **扩容方案**：支持多主机分布式部署

## 9. 测试策略
- **单元测试覆盖**：
  - 实例创建/销毁
  - 命令执行
  - 预热池管理
  - 错误处理
- **E2E 测试场景**：
  - 完整的 Agent 执行流程
  - 预热池高并发获取
  - 快照创建/恢复

## 10. 部署与运维
- **容器化**：不支持（需要 KVM）
- **监控指标**：
  - 实例数量
  - 预热池大小
  - 创建/销毁次数
  - 平均启动时间
  - 执行延迟

## 11. 风险与备选方案
- **主要风险**：
  - KVM 不可用
  - Firecracker 版本兼容性
  - 内存资源消耗
- **备选方案**：
  - KVM 不可用：降级到 Docker 或进程隔离
  - 内存不足：减小预热池大小或单实例内存

## 12. 附录
- **参考资料**：
  - Firecracker 文档：https://github.com/firecracker-microvm/firecracker
  - vsock 文档：https://man7.org/linux/man-pages/man7/vsock.7.html
- **决策记录**：决策 003（沙箱后端优先级）

版本：v1.0
