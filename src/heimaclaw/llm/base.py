"""
LLM 适配器基类

定义所有 LLM 适配器必须实现的通用接口。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, AsyncIterator


class LLMProvider(str, Enum):
    """LLM 提供商枚举"""
    # 国内
    GLM = "glm"           # 智谱
    DEEPSEEK = "deepseek" # DeepSeek
    QWEN = "qwen"         # 通义千问
    
    # 国外
    OPENAI = "openai"     # OpenAI
    CLAUDE = "claude"     # Claude
    GEMINI = "gemini"     # Gemini
    
    # 自定义
    VLLM = "vllm"         # vLLM 部署
    OLLAMA = "ollama"     # Ollama
    CUSTOM = "custom"     # 自定义


@dataclass
class LLMConfig:
    """LLM 配置"""
    provider: LLMProvider = LLMProvider.OPENAI
    model_name: str = "gpt-4"
    api_key: Optional[str] = None
    base_url: Optional[str] = None  # 自定义 API 地址
    
    # 生成参数
    temperature: float = 0.7
    max_tokens: int = 4096
    top_p: float = 1.0
    stream: bool = False
    
    # 工具调用
    tools: Optional[list[dict[str, Any]]] = None
    tool_choice: Optional[str] = "auto"
    
    # 额外参数
    extra_params: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolCall:
    """工具调用"""
    id: str
    name: str
    arguments: dict[str, Any]
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": "function",
            "function": {
                "name": self.name,
                "arguments": self.arguments,
            }
        }


@dataclass
class LLMResponse:
    """LLM 响应"""
    content: str
    model: str
    provider: LLMProvider
    
    # 使用统计
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    
    # 工具调用
    tool_calls: list[ToolCall] = field(default_factory=list)
    
    # 原始响应
    raw_response: Optional[dict[str, Any]] = None
    
    # 元数据
    finish_reason: str = "stop"
    latency_ms: int = 0


@dataclass
class Message:
    """消息"""
    role: str  # system / user / assistant / tool
    content: Optional[str] = None
    tool_calls: Optional[list[ToolCall]] = None
    tool_call_id: Optional[str] = None
    name: Optional[str] = None  # 工具名称（role=tool 时）
    
    def to_openai_format(self) -> dict[str, Any]:
        """转换为 OpenAI 格式"""
        msg: dict[str, Any] = {"role": self.role}
        
        if self.content is not None:
            msg["content"] = self.content
        
        if self.tool_calls:
            msg["tool_calls"] = [tc.to_dict() for tc in self.tool_calls]
        
        if self.tool_call_id:
            msg["tool_call_id"] = self.tool_call_id
        
        if self.name:
            msg["name"] = self.name
        
        return msg
    
    @classmethod
    def system(cls, content: str) -> "Message":
        """创建系统消息"""
        return cls(role="system", content=content)
    
    @classmethod
    def user(cls, content: str) -> "Message":
        """创建用户消息"""
        return cls(role="user", content=content)
    
    @classmethod
    def assistant(cls, content: str, tool_calls: Optional[list[ToolCall]] = None) -> "Message":
        """创建助手消息"""
        return cls(role="assistant", content=content, tool_calls=tool_calls)
    
    @classmethod
    def tool_result(cls, tool_call_id: str, name: str, content: str) -> "Message":
        """创建工具结果消息"""
        return cls(role="tool", tool_call_id=tool_call_id, name=name, content=content)


class LLMAdapter(ABC):
    """
    LLM 适配器抽象基类
    
    所有 LLM 适配器必须实现此接口。
    """
    
    def __init__(self, config: LLMConfig):
        """
        初始化适配器
        
        参数:
            config: LLM 配置
        """
        self.config = config
    
    @property
    @abstractmethod
    def provider(self) -> LLMProvider:
        """提供商类型"""
        pass
    
    @property
    @abstractmethod
    def is_available(self) -> bool:
        """检查是否可用（API Key 是否配置）"""
        pass
    
    @abstractmethod
    async def chat(
        self,
        messages: list[Message],
        **kwargs: Any,
    ) -> LLMResponse:
        """
        发送对话请求
        
        参数:
            messages: 消息列表
            **kwargs: 额外参数
            
        返回:
            LLM 响应
        """
        pass
    
    @abstractmethod
    async def chat_stream(
        self,
        messages: list[Message],
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """
        流式对话
        
        参数:
            messages: 消息列表
            **kwargs: 额外参数
            
        返回:
            异步迭代器，yield 文本片段
        """
        pass
    
    async def count_tokens(self, text: str) -> int:
        """
        计算 Token 数量（简单估算）
        
        参数:
            text: 文本内容
            
        返回:
            Token 数量
        """
        return len(text) // 4
    
    def get_model_info(self) -> dict[str, Any]:
        """
        获取模型信息
        
        返回:
            模型信息字典
        """
        return {
            "provider": self.provider.value,
            "model": self.config.model_name,
            "available": self.is_available,
        }
