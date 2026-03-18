# Agent 运行时模块 Spec 文档 v1.0

## 1. 概述与目标
- **项目/模块名称**：HeiMaClaw Agent 运行时模块
- **业务/功能目标**：管理 Agent 生命周期、会话、工具调用，实现 AI Agent 核心执行循环
- **范围**：
  - 包含：AgentRunner、SessionManager、ToolRegistry
  - 不包含：渠道适配（由渠道模块处理）、沙箱实现（由沙箱模块处理）

## 2. 需求来源与约束
- **来源文档**：DEVELOPMENT-NORM-v1.0.md、MODULE-INTERFACE-STANDARD-v1.0.md
- **性能要求**：
  - 消息处理延迟 < 1s（不含 LLM 调用）
  - 工具执行可配置超时
- **安全/合规要求**：
  - 工具调用在沙箱中执行
  - 敏感信息（API Key）内存存储
- **时间窗口**：Phase 2 - 核心运行时

## 3. 系统架构
- **分层图**：
  ```
  AgentModule
    ├── AgentRunner（运行器）
    │   ├── 生命周期管理
    │   ├── 消息处理循环
    │   ├── LLM 调用
    │   └── 工具编排
    ├── SessionManager（会话管理器）
    │   ├── 会话创建/查询/更新/删除
    │   ├── 消息存储
    │   └── 持久化
    └── ToolRegistry（工具注册表）
        ├── 工具注册/注销
        ├── 工具查找
        └── 工具执行
  ```
- **技术选型**：
  - asyncio：异步操作
  - dataclasses：数据结构
  - json：序列化
- **关键依赖**：Python 3.10+

## 4. 数据模型
- **核心实体**：
  | 实体 | 说明 |
  |------|------|
  | Session | 会话对象 |
  | Message | 消息对象 |
  | RegisteredTool | 已注册工具 |
  | AgentConfig | Agent 配置 |

- **字段说明**：
  | 实体 | 字段 | 类型 | 说明 |
  |------|------|------|------|
  | Session | session_id | str | 会话唯一标识 |
  | Session | agent_id | str | 关联 Agent |
  | Session | status | SessionStatus | 会话状态 |
  | Session | messages | list[Message] | 消息列表 |
  | Message | role | str | 角色（user/assistant/system/tool）|
  | Message | content | str | 消息内容 |
  | Message | tool_name | str | 工具名称（可选）|
  | RegisteredTool | definition | ToolDefinition | 工具定义 |
  | RegisteredTool | handler | Callable | 处理函数 |
  | RegisteredTool | is_async | bool | 是否异步 |

## 5. 接口设计
- **AgentRunner API**：
  | 方法 | 功能 | 参数 | 返回 |
  |------|------|------|------|
  | start | 启动 Agent | 无 | None |
  | stop | 停止 Agent | 无 | None |
  | process_message | 处理消息 | user_id, channel, content, session_id | str |
  | set_api_key | 设置 API Key | api_key | None |

- **SessionManager API**：
  | 方法 | 功能 | 参数 | 返回 |
  |------|------|------|------|
  | create | 创建会话 | agent_id, channel, user_id | Session |
  | get | 获取会话 | session_id | Session |
  | update | 更新会话 | session | None |
  | delete | 删除会话 | session_id | None |
  | add_message | 添加消息 | session_id, role, content | Message |
  | get_messages | 获取消息 | session_id, limit | list[Message] |
  | list_active | 列出活跃会话 | agent_id | list[Session] |
  | close_idle | 关闭空闲会话 | max_idle_seconds | int |

- **ToolRegistry API**：
  | 方法 | 功能 | 参数 | 返回 |
  |------|------|------|------|
  | register | 注册工具（装饰器）| name, description, parameters | Callable |
  | register_function | 注册工具函数 | name, description, handler | None |
  | unregister | 注销工具 | name | None |
  | get | 获取工具 | name | RegisteredTool |
  | list_all | 列出所有工具 | 无 | list[ToolDefinition] |
  | execute | 执行工具 | name, parameters | ToolResult |
  | get_openai_tools | 获取 OpenAI 格式 | 无 | list[dict] |

## 6. 关键流程
- **消息处理流程**：
  1. 接收用户消息
  2. 获取或创建会话
  3. 添加用户消息到会话
  4. 构建消息历史
  5. 调用 LLM
  6. 检查工具调用
  7. 如有工具调用，执行并递归
  8. 返回最终响应
  9. 添加助手消息到会话

- **工具执行流程**：
  1. 从响应提取工具调用
  2. 记录工具调用消息
  3. 在沙箱中执行（如启用）
  4. 记录工具结果消息
  5. 递归调用 LLM

## 7. 安全设计
- **鉴权**：通过渠道适配器验证用户
- **输入校验**：消息内容长度限制
- **隔离/沙箱**：工具调用在沙箱中执行

## 8. 性能与可扩展性
- **瓶颈点**：LLM 调用延迟、工具执行时间
- **优化方案**：
  - 异步并发处理
  - 消息历史截断
  - 工具执行超时控制
- **扩容方案**：多 Agent 实例、分布式会话存储

## 9. 测试策略
- **单元测试覆盖**：
  - 会话创建/查询/更新/删除
  - 消息添加/获取
  - 工具注册/执行
  - Agent 启动/停止
- **E2E 测试场景**：
  - 完整消息处理流程
  - 工具调用循环
  - 会话持久化

## 10. 部署与运维
- **容器化**：支持
- **监控指标**：
  - 活跃会话数
  - 消息处理延迟
  - 工具调用次数/成功率
  - LLM 调用延迟

## 11. 风险与备选方案
- **主要风险**：
  - LLM API 不稳定
  - 会话数据丢失
  - 工具执行超时
- **备选方案**：
  - 多 LLM 提供商支持
  - 会话数据备份
  - 工具执行降级

## 12. 附录
- **参考资料**：
  - LangChain Agent 设计：https://python.langchain.com/docs/modules/agents/
  - nanobot 参考：/root/dt/ai_coding/heimaclaw/reference/nanobot
- **决策记录**：决策 005（CLI 框架选型）

版本：v1.0
