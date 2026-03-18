"""
LLM 集成模块

提供多厂商 LLM 统一接口，支持：
- 国内：智谱(GLM)、DeepSeek、通义千问(Qwen)
- 国外：OpenAI、Claude
- 自定义：vLLM、Ollama
"""

from heimaclaw.llm.base import (
    LLMAdapter,
    LLMConfig,
    LLMProvider,
    LLMResponse,
    Message,
    ToolCall,
)
from heimaclaw.llm.openai_compatible import OpenAICompatibleAdapter
from heimaclaw.llm.providers import (
    PROVIDER_ADAPTERS,
    ClaudeAdapter,
    DeepSeekAdapter,
    GLMAdapter,
    OllamaAdapter,
    OpenAIAdapter,
    QwenAdapter,
    VLLMAdapter,
    create_adapter,
    get_adapter_class,
)
from heimaclaw.llm.registry import LLMRegistry, get_llm_registry

__all__ = [
    # 基础类
    "LLMAdapter",
    "LLMConfig",
    "LLMProvider",
    "LLMResponse",
    "Message",
    "ToolCall",
    # 注册表
    "LLMRegistry",
    "get_llm_registry",
    # 兼容适配器
    "OpenAICompatibleAdapter",
    # 具体实现
    "OpenAIAdapter",
    "ClaudeAdapter",
    "GLMAdapter",
    "DeepSeekAdapter",
    "QwenAdapter",
    "VLLMAdapter",
    "OllamaAdapter",
    # 工厂函数
    "create_adapter",
    "get_adapter_class",
    "PROVIDER_ADAPTERS",
]
