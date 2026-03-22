"""
视觉理解工具
可注册到 Agent Runner，自动处理图片理解
"""
import asyncio
from typing import Optional, Callable, Awaitable

from heimaclaw.console import info, warning


class VisionTool:
    """
    视觉理解工具
    支持同步/异步调用，多 Agent 并发安全
    """
    
    def __init__(
        self,
        get_vision_service_fn: Callable,  # 函数，获取 vision service 实例
    ):
        self._get_vision_service = get_vision_service_fn
        self._name = "vision_understand"
        self._description = "理解图片内容。当用户发送图片或提到图片时，自动使用此工具获取图片描述。"
        self._agent_id = "unknown"
    
    def set_agent_id(self, agent_id: str) -> None:
        """设置所属 Agent ID"""
        self._agent_id = agent_id
    
    @property
    def name(self) -> str:
        return self._name
    
    @property
    def description(self) -> str:
        return self._description
    
    @property
    def is_async(self) -> bool:
        return True  # 视觉理解是异步的
    
    async def execute(
        self,
        image_data: str,
        prompt: Optional[str] = None
    ) -> str:
        """
        执行图片理解
        
        Args:
            image_data: 图片 URL 或 base64
            prompt: 提问（可选，默认描述图片）
        
        Returns:
            图片理解结果
        """
        vision_service = self._get_vision_service()
        
        if not vision_service.is_enabled():
            return "[全局视觉理解未启用]"
        
        if not prompt:
            prompt = "请详细描述这张图片的内容，包括场景、物体、文字等一切信息。"
        
        result = await vision_service.understand_image(
            image_data=image_data,
            prompt=prompt,
            agent_id=self._agent_id
        )
        
        info(f"[VisionTool] {self._agent_id} 理解图片完成: {result[:50]}...")
        return result
    
    def __call__(
        self,
        image_data: str,
        prompt: Optional[str] = None
    ) -> Awaitable[str]:
        """同步调用接口"""
        return self.execute(image_data, prompt)


def create_vision_tool(get_vision_service_fn: Callable) -> VisionTool:
    """创建视觉理解工具"""
    return VisionTool(get_vision_service_fn)
