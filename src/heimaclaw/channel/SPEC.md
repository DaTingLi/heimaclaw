# 渠道适配器模块 Spec 文档 v1.0

## 1. 概述与目标
- **项目/模块名称**：HeiMaClaw 渠道适配器模块
- **业务/功能目标**：提供飞书和企业微信消息的收发能力
- **范围**：
  - 包含：飞书适配器、企业微信适配器、消息解析、发送、卡片支持
  - 不包含：LLM 处理（由 Agent 运行时处理）

## 2. 需求来源与约束
- **来源文档**：DEVELOPMENT-NORM-v1.0.md、MODULE-INTERFACE-STANDARD-v1.0.md
- **参考实现**：
  - openclaw-lark-main（飞书）
  - wecom-openclaw-plugin-main（企业微信）
- **安全/合规要求**：
  - 签名验证
  - 消息解密（企业微信）
  - Token 缓存管理
- **时间窗口**：Phase 2 - 核心运行时

## 3. 系统架构
- **分层图**：
  ```
  ChannelModule
    ├── ChannelAdapter（抽象基类）
    │   ├── FeishuAdapter（飞书）
    │   └── WeComAdapter（企业微信）
    ├── 消息模型
    │   ├── InboundMessage（入站消息）
    │   └── OutboundMessage（出站消息）
    └── Webhook 处理
        ├── 签名验证
        ├── 消息解析
        └── 消息路由
  ```

- **技术选型**：
  - httpx：异步 HTTP 客户端
  - xml.etree.ElementTree：XML 解析（企业微信）
  - JSON：消息格式

- **关键依赖**：
  - httpx>=0.26.0
  - pycryptodome（可选，用于企业微信解密）

## 4. 数据模型
- **InboundMessage**：
  | 字段 | 类型 | 说明 |
  |------|------|------|
  | message_id | str | 消息 ID |
  | chat_id | str | 会话 ID |
  | user_id | str | 用户 ID |
  | user_name | Optional[str] | 用户名称 |
  | content | str | 消息内容 |
  | message_type | str | 消息类型 |
  | timestamp | float | 时间戳 |
  | raw_data | dict | 原始数据 |

- **OutboundMessage**：
  | 字段 | 类型 | 说明 |
  |------|------|------|
  | chat_id | str | 目标会话 ID |
  | content | str | 消息内容 |
  | message_type | str | 消息类型 |
  | parse_mode | bool | 是否解析 Markdown |

## 5. 接口设计
- **ChannelAdapter 接口**：
  | 方法 | 功能 | 参数 | 返回 |
  |------|------|------|------|
  | channel_type | 渠道类型 | 无 | ChannelType |
  | is_configured | 是否配置 | 无 | bool |
  | verify_webhook | 验证请求 | request | bool |
  | parse_message | 解析消息 | request | InboundMessage |
  | send_message | 发送消息 | session, content | bool |
  | send_card | 发送卡片 | session, card | bool |
  | get_callback_url | 回调 URL | 无 | str |
  | get_user_info | 用户信息 | user_id | dict |
  | get_chat_info | 会话信息 | chat_id | dict |

- **飞书特有**：
  | 方法 | 功能 |
  |------|------|
  | get_tenant_access_token | 获取租户访问令牌 |

- **企业微信特有**：
  | 方法 | 功能 |
  |------|------|
  | get_access_token | 获取访问令牌 |
  | _verify_signature | 验证签名 |
  | _decrypt_message | 解密消息 |

## 6. 关键流程
- **消息接收流程**：
  1. Webhook 接收 HTTP 请求
  2. 验证签名（企业微信）或 URL 验证（飞书）
  3. 解析消息（XML/JSON）
  4. 转换为 InboundMessage
  5. 路由到对应 Agent

- **消息发送流程**：
  1. Agent 生成响应内容
  2. 获取访问令牌（缓存）
  3. 构建消息体
  4. 发送到渠道 API
  5. 返回发送结果

## 7. 安全设计
- **鉴权**：
  - 飞书： Tenant Access Token
  - 企业微信: Corp Access Token
- **输入校验**：
  - 签名验证
  - 消息格式验证
- **Token 管理**：
  - 缓存机制（避免频繁请求）
  - 自动刷新（过期前刷新）

## 8. 性能与可扩展性
- **瓶颈点**：
  - Token 获取延迟
  - 消息发送延迟
- **优化方案**：
  - Token 缓存
  - 异步批量发送
  - HTTP 连接复用

## 9. 测试策略
- **单元测试覆盖**：
  - 签名验证
  - 消息解析
  - Token 获取
  - 消息发送

- **E2E 测试场景**：
  - 完整消息收发流程
  - 多消息类型处理
  - 错误恢复

## 10. 部署与运维
- **容器化**：支持
- **监控指标**：
  - 消息接收数
  - 消息发送数
  - Token 刷新次数
  - API 调用延迟

## 11. 风险与备选方案
- **主要风险**：
  - API 限流
  - 签名验证失败
  - Token 过期

- **备选方案**：
  - 重试机制
  - 降级为文本消息
  - 多 Token 备份

## 12. 附录
- **参考资料**：
  - 飞书开放平台：https://open.feishu.cn/document/
  - 企业微信 API：https://developer.work.weixin.qq.com/document/
  - OpenClaw Lark 插件：/root/dt/ai_coding/heimaclaw/reference/openclaw-lark-main
  - OpenClaw 企业微信插件：/root/dt/ai_coding/heimaclaw/reference/wecom-openclaw-plugin-main

- **决策记录**：决策 004（渠道选择）

版本：v1.0
