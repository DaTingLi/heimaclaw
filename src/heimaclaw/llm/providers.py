"""
LLM 提供商适配器

包含各厂商的具体实现：
- OpenAI: GPT-4、GPT-3.5-Turbo
- Claude: Claude-3 系列
- GLM: 智谱 ChatGLM
- DeepSeek: DeepSeek Chat/Coder
- Qwen: 通义千问
- VLLM: 本地 vLLM 部署
- Ollama: 本地 Ollama
"""

from typing import Any, AsyncIterator

from heimaclaw.llm.base import (
    LLMAdapter,
    LLMConfig,
    LLMProvider,
    LLMResponse,
    Message,
)
from heimaclaw.llm.openai_compatible import OpenAICompatibleAdapter


# ============================================================================
# 国内厂商（OpenAI 兼容）
# ============================================================================

class GLMAdapter(OpenAICompatibleAdapter):
    """
    智谱 GLM 适配器
    
    支持模型：
    - glm-4: 通用大模型
    - glm-4-flash: 快速模型
    - glm-4-air: 空中模型
    - glm-3-turbo: 快速模型
    """
    
    @property
    def provider(self) -> LLMProvider:
        return LLMProvider.GLM
    
    @property
    def is_available(self) -> bool:
        return bool(self.config.api_key)


class DeepSeekAdapter(OpenAICompatibleAdapter):
    """
    DeepSeek 适配器
    
    支持模型：
    - deepseek-chat: 通用对话
    - deepseek-coder: 代码专用
    """
    
    @property
    def provider(self) -> LLMProvider:
        return LLMProvider.DEEPSEEK
    
    @property
    def is_available(self) -> bool:
        return bool(self.config.api_key)


class QwenAdapter(OpenAICompatibleAdapter):
    """
    通义千问 适配器
    
    支持模型：
    - qwen-turbo: 快速模型
    - qwen-plus: 增强模型
    - qwen-max: 旗舰模型
    - qwen-long: 长文本模型
    """
    
    @property
    def provider(self) -> LLMProvider:
        return LLMProvider.QWEN
    
    @property
    def is_available(self) -> bool:
        return bool(self.config.api_key)


# ============================================================================
# 国外厂商
# ============================================================================

class OpenAIAdapter(OpenAICompatibleAdapter):
    """
    OpenAI 适配器
    
    支持模型：
    - gpt-4: GPT-4
    - gpt-4-turbo: GPT-4 Turbo
    - gpt-4o: GPT-4 Omni
    - gpt-3.5-turbo: GPT-3.5 Turbo
    """
    
    @property
    def provider(self) -> LLMProvider:
        return LLMProvider.OPENAI
    
    @property
    def is_available(self) -> bool:
        return bool(self.config.api_key)


class ClaudeAdapter(LLMAdapter):
    """
    Claude 适配器
    
    支持模型：
    - claude-3-opus: 最强模型
    - claude-3-sonnet: 平衡模型
    - claude-3-haiku: 快速模型
    - claude-3.5-sonnet: 最新模型
    """
    
    # Claude API 地址
    BASE_URL = "https://api.anthropic.com/v1"
    
    # 模型映射
    MODEL_MAPPING = {
        "claude-3-opus": "claude-3-opus-20240229",
        "claude-3-sonnet": "claude-3-sonnet-20240229",
        "claude-3-haiku": "claude-3-haiku-20240307",
        "claude-3.5-sonnet": "claude-3-5-sonnet-20241022",
    }
    
    @property
    def provider(self) -> LLMProvider:
        return LLMProvider.CLAUDE
    
    @property
    def is_available(self) -> bool:
        return bool(self.config.api_key)
    
    async def chat(
        self,
        messages: list[Message],
        **kwargs: Any,
    ) -> LLMResponse:
        """
        发送对话请求
        
        注意：Claude API 格式与 OpenAI 略有不同。
        """
        if not self.is_available:
            raise ValueError("Claude API Key 未配置")
        
        import httpx
        import time
        
        start_time = time.time()
        
        # 构建请求
        url = f"{self.BASE_URL}/messages"
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.config.api_key,
            "anthropic-version": "2023-06-01",
        }
        
        # 分离 system 消息
        system_msg = ""
        chat_messages = []
        
        for msg in messages:
            if msg.role == "system":
                system_msg = msg.content or ""
            else:
                chat_messages.append({
                    "role": msg.role,
                    "content": msg.content or "",
                })
        
        body = {
            "model": self.MODEL_MAPPING.get(
                self.config.model_name, self.config.model_name
            ),
            "messages": chat_messages,
            "system": system_msg,
            "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
            "temperature": kwargs.get("temperature", self.config.temperature),
            "top_p": kwargs.get("top_p", self.config.top_p),
        }
        
        # 发送请求
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(url, headers=headers, json=body)
            response.raise_for_status()
            
            data = response.json()
            
            # 解析响应
            content = ""
            for block in data.get("content", []):
                if block.get("type") == "text":
                    content += block.get("text", "")
            
            usage = data.get("usage", {})
            
            return LLMResponse(
                content=content,
                model=data.get("model", self.config.model_name),
                provider=self.provider,
                prompt_tokens=usage.get("input_tokens", 0),
                completion_tokens=usage.get("output_tokens", 0),
                total_tokens=usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
                raw_response=data,
                finish_reason=data.get("stop_reason", "stop"),
                latency_ms=int((time.time() - start_time) * 1000),
            )
    
    async def chat_stream(
        self,
        messages: list[Message],
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """流式对话（暂不实现）"""
        raise NotImplementedError("Claude 流式输出暂未实现")


# ============================================================================
# 自定义部署
# ============================================================================

class VLLMAdapter(OpenAICompatibleAdapter):
    """
    vLLM 适配器
    
    用于连接自部署的 vLLM 服务。
    
    使用方法：
    1. 启动 vLLM 服务：
       vllm serve <model_path> --host 0.0.0.0 --port 8000
    
    2. 配置：
       config = LLMConfig(
           provider=LLMProvider.VLLM,
           base_url="http://localhost:8000/v1",
           model_name="<model_name>",
       )
    """
    
    @property
    def provider(self) -> LLMProvider:
        return LLMProvider.VLLM
    
    @property
    def is_available(self) -> bool:
        # vLLM 不需要 API Key
        return bool(self.config.base_url)


class OllamaAdapter(OpenAICompatibleAdapter):
    """
    Ollama 适配器
    
    用于连接本地 Ollama 服务。
    
    使用方法：
    1. 启动 Ollama：
       ollama serve
    
    2. 拉取模型：
       ollama pull llama2
    
    3. 配置：
       config = LLMConfig(
           provider=LLMProvider.OLLAMA,
           base_url="http://localhost:11434/v1",
           model_name="llama2",
       )
    """
    
    @property
    def provider(self) -> LLMProvider:
        return LLMProvider.OLLAMA
    
    @property
    def is_available(self) -> bool:
        # Ollama 不需要 API Key
        return bool(self.config.base_url or True)


# ============================================================================
# 适配器注册表
# ============================================================================

PROVIDER_ADAPTERS: dict[LLMProvider, type[LLMAdapter]] = {
    LLMProvider.OPENAI: OpenAIAdapter,
    LLMProvider.CLAUDE: ClaudeAdapter,
    LLMProvider.GLM: GLMAdapter,
    LLMProvider.DEEPSEEK: DeepSeekAdapter,
    LLMProvider.QWEN: QwenAdapter,
    LLMProvider.VLLM: VLLMAdapter,
    LLMProvider.OLLAMA: OllamaAdapter,
}


def get_adapter_class(provider: LLMProvider) -> type[LLMAdapter]:
    """
    获取适配器类
    
    参数:
        provider: 提供商类型
        
    返回:
        适配器类
    """
    if provider not in PROVIDER_ADAPTERS:
        # 未知提供商使用 OpenAI 兼容适配器
        return OpenAICompatibleAdapter
    
    return PROVIDER_ADAPTERS[provider]


def create_adapter(config: LLMConfig) -> LLMAdapter:
    """
    创建适配器实例
    
    参数:
        config: LLM 配置
        
    返回:
        适配器实例
    """
    adapter_class = get_adapter_class(config.provider)
    return adapter_class(config)
