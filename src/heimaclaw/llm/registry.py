"""
LLM 注册表

管理所有 LLM 适配器实例，支持多模型切换。
"""

from typing import Any, Optional

from heimaclaw.llm.base import (
    LLMAdapter,
    LLMConfig,
    LLMProvider,
    LLMResponse,
    Message,
)
from heimaclaw.llm.providers import create_adapter
from heimaclaw.console import info, warning, error


class LLMRegistry:
    """
    LLM 注册表
    
    管理多个 LLM 适配器实例，支持：
    - 按名称注册适配器
    - 动态切换默认模型
    - 统一调用接口
    """
    
    def __init__(self):
        """初始化注册表"""
        self._adapters: dict[str, LLMAdapter] = {}
        self._default_name: Optional[str] = None
    
    def register(
        self,
        name: str,
        config: LLMConfig,
        set_default: bool = False,
    ) -> LLMAdapter:
        """
        注册 LLM 适配器
        
        参数:
            name: 适配器名称
            config: LLM 配置
            set_default: 是否设为默认
            
        返回:
            适配器实例
        """
        adapter = create_adapter(config)
        self._adapters[name] = adapter
        
        if set_default or self._default_name is None:
            self._default_name = name
        
        info(f"注册 LLM 适配器: {name} ({config.provider.value}/{config.model_name})")
        
        return adapter
    
    def get(self, name: Optional[str] = None) -> LLMAdapter:
        """
        获取适配器
        
        参数:
            name: 适配器名称（为空则返回默认）
            
        返回:
            适配器实例
        """
        adapter_name = name or self._default_name
        
        if not adapter_name:
            raise ValueError("没有注册的 LLM 适配器")
        
        if adapter_name not in self._adapters:
            raise ValueError(f"LLM 适配器不存在: {adapter_name}")
        
        return self._adapters[adapter_name]
    
    def set_default(self, name: str) -> None:
        """
        设置默认适配器
        
        参数:
            name: 适配器名称
        """
        if name not in self._adapters:
            raise ValueError(f"LLM 适配器不存在: {name}")
        
        self._default_name = name
        info(f"设置默认 LLM: {name}")
    
    def list_adapters(self) -> list[dict[str, Any]]:
        """
        列出所有适配器
        
        返回:
            适配器信息列表
        """
        result = []
        
        for name, adapter in self._adapters.items():
            info_dict = adapter.get_model_info()
            info_dict["name"] = name
            info_dict["is_default"] = (name == self._default_name)
            result.append(info_dict)
        
        return result
    
    async def chat(
        self,
        messages: list[Message],
        adapter_name: Optional[str] = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """
        发送对话请求
        
        参数:
            messages: 消息列表
            adapter_name: 适配器名称
            **kwargs: 额外参数
            
        返回:
            LLM 响应
        """
        adapter = self.get(adapter_name)
        return await adapter.chat(messages, **kwargs)
    
    async def close_all(self) -> None:
        """关闭所有适配器"""
        for adapter in self._adapters.values():
            try:
                await adapter.close()
            except Exception as e:
                warning(f"关闭适配器失败: {e}")
    
    @property
    def default_adapter(self) -> Optional[LLMAdapter]:
        """获取默认适配器"""
        if self._default_name:
            return self._adapters.get(self._default_name)
        return None
    
    @property
    def adapter_count(self) -> int:
        """适配器数量"""
        return len(self._adapters)


# 全局注册表实例
_global_registry: Optional[LLMRegistry] = None


def get_llm_registry() -> LLMRegistry:
    """
    获取全局 LLM 注册表
    
    返回:
        LLM 注册表实例
    """
    global _global_registry
    
    if _global_registry is None:
        _global_registry = LLMRegistry()
    
    return _global_registry


def reset_registry() -> None:
    """重置全局注册表"""
    global _global_registry
    _global_registry = None
