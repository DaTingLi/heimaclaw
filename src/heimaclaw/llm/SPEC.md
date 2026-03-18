# LLM 集成模块 Spec 文档 v1.0

## 1. 概述与目标
- **项目/模块名称**：HeiMaClaw LLM 集成模块
- **业务/功能目标**：提供统一的 LLM 调用接口，支持多厂商切换
- **范围**：
  - 包含：适配器抽象、多厂商实现、工具调用、流式输出
  - 不包含：Prompt 管理（由 Agent 运行时处理）

## 2. 需求来源与约束
- **来源文档**：DEVELOPMENT-NORM-v1.0.md
- **性能要求**：
  - 响应延迟 < 5s（首字节）
  - 支持流式输出
- **安全/合规要求**：
  - API Key 加密存储
  - 敏感信息不记录日志
- **时间窗口**：Phase 2 - 核心运行时

## 3. 系统架构
- **分层图**：
  ```
  LLMModule
    ├── LLMAdapter（抽象接口）
    │   ├── OpenAICompatibleAdapter（OpenAI 兼容）
    │   │   ├── GLMAdapter（智谱）
    │   │   ├── DeepSeekAdapter
    │   │   ├── QwenAdapter（通义千问）
    │   │   ├── VLLMAdapter
    │   │   └── OllamaAdapter
    │   ├── OpenAIAdapter
    │   └── ClaudeAdapter
    ├── LLMRegistry（注册表）
    │   ├── 多模型管理
    │   ├── 动态切换
    │   └── 统一接口
    └── 数据模型
        ├── LLMConfig
        ├── LLMResponse
        ├── Message
        └── ToolCall
  ```

## 4. 支持的厂商

### 国内厂商

| 厂商 | Provider | 默认模型 | API 格式 |
|------|----------|---------|---------|
| 智谱 GLM | `glm` | glm-4 | OpenAI 兼容 |
| DeepSeek | `deepseek` | deepseek-chat | OpenAI 兼容 |
| 通义千问 | `qwen` | qwen-turbo | OpenAI 兼容 |

### 国外厂商

| 厂商 | Provider | 默认模型 | API 格式 |
|------|----------|---------|---------|
| OpenAI | `openai` | gpt-4 | 原生 |
| Claude | `claude` | claude-3-sonnet | 原生 |

### 自定义部署

| 类型 | Provider | 说明 | API 格式 |
|------|----------|------|---------|
| vLLM | `vllm` | 自部署模型 | OpenAI 兼容 |
| Ollama | `ollama` | 本地运行 | OpenAI 兼容 |

## 5. 数据模型

### LLMConfig

| 字段 | 类型 | 说明 |
|------|------|------|
| provider | LLMProvider | 提供商类型 |
| model_name | str | 模型名称 |
| api_key | Optional[str] | API Key |
| base_url | Optional[str] | 自定义 API 地址 |
| temperature | float | 温度参数 |
| max_tokens | int | 最大 Token 数 |
| top_p | float | Top-p 参数 |
| tools | Optional[list] | 工具定义 |
| tool_choice | Optional[str] | 工具选择策略 |

### LLMResponse

| 字段 | 类型 | 说明 |
|------|------|------|
| content | str | 响应内容 |
| model | str | 使用的模型 |
| provider | LLMProvider | 提供商 |
| prompt_tokens | int | 输入 Token |
| completion_tokens | int | 输出 Token |
| total_tokens | int | 总 Token |
| tool_calls | list[ToolCall] | 工具调用 |
| finish_reason | str | 结束原因 |
| latency_ms | int | 延迟（毫秒）|

### Message

| 字段 | 类型 | 说明 |
|------|------|------|
| role | str | 角色（system/user/assistant/tool）|
| content | Optional[str] | 内容 |
| tool_calls | Optional[list] | 工具调用 |
| tool_call_id | Optional[str] | 工具调用 ID |

## 6. 接口设计

### LLMAdapter 接口

| 方法 | 功能 | 参数 | 返回 |
|------|------|------|------|
| chat | 对话请求 | messages, **kwargs | LLMResponse |
| chat_stream | 流式对话 | messages, **kwargs | AsyncIterator[str] |
| count_tokens | 计算 Token | text | int |
| get_model_info | 获取模型信息 | 无 | dict |
| close | 关闭客户端 | 无 | None |

### LLMRegistry 接口

| 方法 | 功能 | 参数 | 返回 |
|------|------|------|------|
| register | 注册适配器 | name, config, set_default | LLMAdapter |
| get | 获取适配器 | name | LLMAdapter |
| set_default | 设置默认 | name | None |
| list_adapters | 列出适配器 | 无 | list[dict] |
| chat | 发送对话 | messages, adapter_name | LLMResponse |

## 7. 使用示例

### 基础使用

```python
from heimaclaw.llm import LLMConfig, LLMProvider, get_llm_registry, Message

# 创建配置
config = LLMConfig(
    provider=LLMProvider.GLM,
    model_name="glm-4",
    api_key="your-api-key",
)

# 注册到全局注册表
registry = get_llm_registry()
registry.register("default", config, set_default=True)

# 发送对话
messages = [
    Message.system("你是一个助手"),
    Message.user("你好"),
]

response = await registry.chat(messages)
print(response.content)
```

### 使用 vLLM 自定义部署

```python
config = LLMConfig(
    provider=LLMProvider.VLLM,
    base_url="http://localhost:8000/v1",
    model_name="your-model-name",
)

registry.register("local", config)
```

### 多模型切换

```python
# 注册多个模型
registry.register("fast", fast_config)  # 快速模型
registry.register("smart", smart_config)  # 智能模型

# 按需切换
response = await registry.chat(messages, adapter_name="fast")
```

## 8. 工具调用

支持 OpenAI 格式的工具调用：

```python
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "获取天气",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string"}
                }
            }
        }
    }
]

config = LLMConfig(
    provider=LLMProvider.OPENAI,
    model_name="gpt-4",
    tools=tools,
)

response = await registry.chat(messages)

# 处理工具调用
for tool_call in response.tool_calls:
    result = execute_tool(tool_call.name, tool_call.arguments)
    # 发送工具结果...
```

## 9. 错误处理

```python
try:
    response = await registry.chat(messages)
except ValueError as e:
    # 配置错误（API Key 未配置等）
    pass
except httpx.HTTPStatusError as e:
    # API 请求失败
    pass
except Exception as e:
    # 其他错误
    pass
```

## 10. 性能与可扩展性
- **瓶颈点**：API 调用延迟
- **优化方案**：
  - 流式输出降低首字节延迟
  - Token 缓存减少重复计算
  - 连接复用
- **扩容方案**：多实例负载均衡

## 11. 测试策略
- **单元测试覆盖**：
  - 配置验证
  - 消息格式转换
  - 响应解析
- **E2E 测试场景**：
  - 完整对话流程
  - 工具调用
  - 多模型切换

## 12. 部署与运维
- **配置管理**：config.toml
- **密钥管理**：环境变量或加密存储
- **监控指标**：
  - 调用次数
  - 平均延迟
  - Token 使用量
  - 错误率

## 13. 风险与备选方案
- **主要风险**：
  - API 限流
  - 服务不可用
  - Token 超限

- **备选方案**：
  - 多厂商降级
  - 本地模型备份
  - 请求重试

## 14. 附录
- **参考资料**：
  - OpenAI API：https://platform.openai.com/docs
  - Claude API：https://docs.anthropic.com
  - 智谱 API：https://open.bigmodel.cn/dev/api
  - vLLM：https://github.com/vllm-project/vllm

版本：v1.0
