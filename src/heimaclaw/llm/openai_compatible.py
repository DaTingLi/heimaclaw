"""
OpenAI 兼容适配器

支持所有使用 OpenAI API 格式的模型：
- 国内：智谱(GLM)、DeepSeek、通义千问(Qwen)
- 自定义：vLLM、Ollama
"""

import json
import time
from typing import Any, AsyncIterator, Optional

import httpx

from heimaclaw.console import error
from heimaclaw.llm.base import (
    LLMAdapter,
    LLMConfig,
    LLMProvider,
    LLMResponse,
    Message,
    ToolCall,
)


class OpenAICompatibleAdapter(LLMAdapter):
    """
    OpenAI 兼容适配器

    支持 OpenAI API 格式的所有服务。
    """

    # 各厂商的默认配置
    PROVIDER_CONFIGS = {
        LLMProvider.OPENAI: {
            "base_url": "https://api.openai.com/v1",
            "default_model": "gpt-4",
        },
        LLMProvider.GLM: {
            "base_url": "https://open.bigmodel.cn/api/paas/v4",
            "default_model": "glm-4",
        },
        LLMProvider.DEEPSEEK: {
            "base_url": "https://api.deepseek.com/v1",
            "default_model": "deepseek-chat",
        },
        LLMProvider.QWEN: {
            "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "default_model": "qwen-turbo",
        },
        LLMProvider.VLLM: {
            "base_url": "http://localhost:8000/v1",
            "default_model": "",
        },
        LLMProvider.OLLAMA: {
            "base_url": "http://localhost:11434/v1",
            "default_model": "llama2",
        },
    }

    def __init__(self, config: LLMConfig):
        """
        初始化适配器

        参数:
            config: LLM 配置
        """
        super().__init__(config)

        # 获取提供商配置
        provider_config = self.PROVIDER_CONFIGS.get(config.provider, {})

        # 设置 API 地址
        self.base_url = config.base_url or provider_config.get(
            "base_url", "https://api.openai.com/v1"
        )

        # HTTP 客户端
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def provider(self) -> LLMProvider:
        """提供商类型"""
        return self.config.provider

    @property
    def is_available(self) -> bool:
        """检查是否可用"""
        return bool(self.config.api_key)

    async def _get_client(self) -> httpx.AsyncClient:
        """获取 HTTP 客户端"""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=120.0)
        return self._client

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
        if not self.is_available:
            raise ValueError(f"{self.provider.value} API Key 未配置")

        start_time = time.time()

        # 构建请求
        url = f"{self.base_url}/chat/completions"
        headers = self._get_headers()
        body = self._build_request_body(messages, **kwargs)

        try:
            client = await self._get_client()
            response = await client.post(url, headers=headers, json=body)
            response.raise_for_status()

            data = response.json()
            return self._parse_response(data, start_time)

        except httpx.HTTPStatusError as e:
            error(f"LLM API 请求失败: {e.response.status_code}")
            raise
        except Exception as e:
            error(f"LLM API 请求异常: {e}")
            raise

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
            异步迭代器
        """
        if not self.is_available:
            raise ValueError(f"{self.provider.value} API Key 未配置")

        # 构建请求
        url = f"{self.base_url}/chat/completions"
        headers = self._get_headers()
        body = self._build_request_body(messages, stream=True, **kwargs)

        try:
            client = await self._get_client()

            async with client.stream(
                "POST", url, headers=headers, json=body
            ) as response:
                response.raise_for_status()

                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]

                        if data_str == "[DONE]":
                            break

                        try:
                            data = json.loads(data_str)
                            delta = data.get("choices", [{}])[0].get("delta", {})
                            content = delta.get("content", "")

                            if content:
                                yield content
                        except json.JSONDecodeError:
                            continue

        except Exception as e:
            error(f"LLM 流式请求异常: {e}")
            raise

    def _get_headers(self) -> dict[str, str]:
        """获取请求头"""
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.config.api_key}",
        }

    def _build_request_body(
        self,
        messages: list[Message],
        stream: bool = False,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """构建请求体"""
        body: dict[str, Any] = {
            "model": self.config.model_name,
            "messages": [m.to_openai_format() for m in messages],
            "temperature": kwargs.get("temperature", self.config.temperature),
            "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
            "top_p": kwargs.get("top_p", self.config.top_p),
            "stream": stream,
        }

        # 添加工具（支持 config 和 kwargs 两种方式）
        tools = kwargs.get("tools") or self.config.tools
        if tools:
            body["tools"] = tools
            if self.config.tool_choice:
                body["tool_choice"] = self.config.tool_choice

        # 添加额外参数
        body.update(self.config.extra_params)

        return body

    def _parse_response(
        self,
        data: dict[str, Any],
        start_time: float,
    ) -> LLMResponse:
        """解析响应"""
        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})
        usage = data.get("usage", {})

        content = message.get("content", "") or ""

        # 解析工具调用
        tool_calls = []
        for tc in message.get("tool_calls", []):
            func = tc.get("function", {})
            args_str = func.get("arguments", "{}")

            try:
                args = json.loads(args_str) if isinstance(args_str, str) else args_str
            except json.JSONDecodeError:
                args = {}

            tool_calls.append(
                ToolCall(
                    id=tc.get("id", ""),
                    name=func.get("name", ""),
                    arguments=args,
                )
            )

        return LLMResponse(
            content=content,
            model=data.get("model", self.config.model_name),
            provider=self.provider,
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
            tool_calls=tool_calls,
            raw_response=data,
            finish_reason=choice.get("finish_reason", "stop"),
            latency_ms=int((time.time() - start_time) * 1000),
        )

    async def close(self) -> None:
        """关闭客户端"""
        if self._client:
            await self._client.aclose()
            self._client = None
