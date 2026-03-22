"""
渠道适配器基类

定义所有渠道适配器必须实现的通用接口。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional

from heimaclaw.interfaces import ChannelType, SessionContext


@dataclass
class InboundMessage:
    """入站消息"""

    message_id: str
    chat_id: str
    user_id: str
    content: str
    timestamp: float
    user_name: Optional[str] = None
    message_type: str = "text"  # text / post / interactive
    chat_type: str = "p2p"  # p2p=私聊, group=群聊
    mentions: list[str] = field(default_factory=list)  # 被 @ 的用户 ID 列表
    image_urls: list[str] = field(default_factory=list)  # 图片 URL 列表（已下载或外部URL）
    image_keys: list[str] = field(default_factory=list)  # 飞书图片 Key（需要下载）
    raw_data: dict[str, Any] = field(default_factory=dict)


@dataclass
class OutboundMessage:
    """出站消息"""

    chat_id: str
    content: str
    message_type: str = "text"

    parse_mode: bool = False


class ChannelAdapter(ABC):
    """
    渠道适配器抽象基类

    所有渠道适配器（飞书、企业微信）必须实现此接口。
    """

    @property
    @abstractmethod
    def channel_type(self) -> ChannelType:
        """渠道类型"""
        pass

    @property
    @abstractmethod
    def is_configured(self) -> bool:
        """是否已配置"""
        pass

    @abstractmethod
    async def verify_webhook(self, request: Any) -> bool:
        """
        验证 Webhook 请求

        参数:
            request: HTTP 请求对象

        返回:
            是否验证通过
        """
        pass

    @abstractmethod
    async def parse_message(self, request: Any) -> InboundMessage:
        """
        解析消息

        参数:
            request: HTTP 请求对象

        返回:
            解析后的消息
        """
        pass

    @abstractmethod
    async def send_message(
        self,
        session: SessionContext,
        content: str,
    ) -> bool:
        """
        发送消息

        参数:
            session: 会话上下文
            content: 消息内容

        返回:
            是否发送成功
        """
        pass

    @abstractmethod
    async def send_card(
        self,
        session: SessionContext,
        card: dict[str, Any],
    ) -> bool:
        """
        发送卡片消息

        参数:
            session: 会话上下文
            card: 卡片内容

        返回:
            是否发送成功
        """
        pass

    @abstractmethod
    def get_callback_url(self) -> str:
        """
        获取回调 URL

        返回:
            Webhook 回调 URL
        """
        pass

    @abstractmethod
    async def get_user_info(self, user_id: str) -> dict[str, Any]:
        """
        获取用户信息

        参数:
            user_id: 用户 ID

        返回:
            用户信息字典
        """
        pass

    @abstractmethod
    async def get_chat_info(self, chat_id: str) -> dict[str, Any]:
        """
        获取会话信息

        参数:
            chat_id: 会话 ID

        返回:
            会话信息字典
        """
        pass
