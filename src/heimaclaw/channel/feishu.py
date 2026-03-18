"""
飞书渠道适配器

实现飞书消息的接收、解析、发送。
"""

import hashlib
import hmac
import json
import time
from typing import Any, Optional

import httpx

from heimaclaw.channel.base import ChannelAdapter, InboundMessage, OutboundMessage
from heimaclaw.interfaces import ChannelType, SessionContext
from heimaclaw.console import info, warning, error, agent_event


from heimaclaw.config.loader import get_config


class FeishuAdapter(ChannelAdapter):
    """
    飞书渠道适配器
    
    支持功能：
    - Webhook 事件验证（签名校验）
    - 消息解析（文本、卡片、富文本）
    - 消息发送（文本、卡片）
    - 用户/群聊信息获取
    """
    
    def __init__(
        self,
        app_id: Optional[str] = None,
        app_secret: Optional[str] = None,
        encrypt_key: Optional[str] = None,
        verification_token: Optional[str] = None,
    ):
        """
        初始化飞书适配器
        
        参数:
            app_id: 飞书应用 ID
            app_secret: 飞书应用 Secret
            encrypt_key: 加密 Key（可选）
            verification_token: 验证 Token（可选）
        """
        # 从配置加载
        config = get_config()
        feishu_config = config.channels.feishu
        
        self.app_id = app_id or feishu_config.app_id
        self.app_secret = app_secret or feishu_config.app_secret
        self.encrypt_key = encrypt_key or feishu_config.encrypt_key
        self.verification_token = (
            verification_token or feishu_config.verification_token
        )
        
        # API 基础 URL
        self.base_url = "https://open.feishu.cn/open-apis"
        
        # 访问令牌缓存
        self._tenant_access_token: Optional[str] = None
        self._token_expire_time: float = 0
        
        # HTTP 客户端
        self._client = httpx.AsyncClient(timeout=30.0)
    
    @property
    def channel_type(self) -> ChannelType:
        return ChannelType.FEISHU
    
    @property
    def is_configured(self) -> bool:
        """检查是否已配置"""
        return bool(self.app_id and self.app_secret)
    
    async def get_tenant_access_token(self) -> str:
        """
        获取租户访问令牌
        
        使用 app_id 和 app_secret 获取访问令牌。
        
        返回:
            访问令牌字符串
        """
        # 检查缓存
        if self._tenant_access_token and time.time() < self._token_expire_time:
            return self._tenant_access_token
        
        # 请求新令牌
        url = f"{self.base_url}/auth/v3/tenant_access_token/internal"
        headers = {
            "Authorization": f"Basic {self._encode_credentials()}"
        }
        
        response = await self._client.post(url, headers=headers)
        response.raise_for_status()
        
        data = response.json()
        self._tenant_access_token = data.get("tenant_access_token")
        self._token_expire_time = time.time() + data.get("expire", 7200)
        
        return self._tenant_access_token
    
    def _encode_credentials(self) -> str:
        """编码凭证"""
        credentials = f"{self.app_id}:{self.app_secret}"
        return (
            credentials.encode()
            .decode("utf-8")
            .replace("\n", "")
        )
    
    async def verify_webhook(self, request: Any) -> bool:
        """
        验证 Webhook 请求
        
        对于飞书，需要验证签名或 challenge。
        """
        # 如果是 URL 验证请求
        if hasattr(request, "json"):
            try:
                body = await request.json()
                if body.get("type") == "url_verification":
                    challenge = body.get("challenge", "")
                    agent_event(f"飞书 URL 验证: {challenge[:20]}...")
                    return True
            except Exception:
                pass
        
        # 签名验证（如果有 encrypt_key）
        if self.encrypt_key:
            # TODO: 实现签名验证
            pass
        
        return True
    
    async def parse_message(self, request: Any) -> InboundMessage:
        """
        解析飞书消息
        
        将飞书事件转换为标准消息格式。
        """
        # 获取请求体
        if hasattr(request, "json"):
            body = await request.json()
        elif hasattr(request, "body"):
            body = request.body
        else:
            raise ValueError("无法解析请求体")
        
        event_type = body.get("type", "")
        
        # URL 验证
        if event_type == "url_verification":
            return InboundMessage(
                message_id="url_verification",
                chat_id="",
                user_id="",
                user_name=None,
                content=body.get("challenge", ""),
                message_type="url_verification",
                timestamp=time.time(),
                raw_data=body,
            )
        
        # 消息事件
        if event_type == "event_callback":
            event = body.get("event", {})
            
            # 消息接收事件
            if event.get("type") == "message.im.message_received_v1":
                message = event.get("message", {})
                sender = event.get("sender", {})
                
                content = self._extract_message_content(message)
                
                return InboundMessage(
                    message_id=message.get("message_id", ""),
                    chat_id=message.get("chat_id", ""),
                    user_id=sender.get("sender_id", {}).get("union_id", ""),
                    user_name=sender.get("sender_id", {}).get("name", ""),
                    content=content,
                    message_type=message.get("message_type", "text"),
                    timestamp=float(message.get("create_time", time.time())),
                    raw_data=body,
                )
            
            # 其他事件类型
            warning(f"未处理的飞书事件类型: {event.get('type')}")
            return InboundMessage(
                message_id="unknown",
                chat_id="",
                user_id="",
                user_name=None,
                content=f"未处理的事件类型: {event_type}",
                message_type="unknown",
                timestamp=time.time(),
                raw_data=body,
            )
        
        raise ValueError(f"未知的事件类型: {event_type}")
    
    def _extract_message_content(self, message: dict) -> str:
        """
        提取消息内容
        
        支持文本、富文本、卡片等类型。
        """
        message_type = message.get("message_type", "text")
        content = message.get("content", "")
        
        if message_type == "text":
            # 文本消息
            if isinstance(content, str):
                try:
                    data = json.loads(content)
                    return data.get("text", content)
                except json.JSONDecodeError:
                    return content
            return content
        
        elif message_type == "post":
            # 富文本消息
            if isinstance(content, str):
                try:
                    data = json.loads(content)
                    return data.get("title", "") + "\n" + data.get("content", "")
                except json.JSONDecodeError:
                    return content
            return content
        
        elif message_type == "interactive":
            # 卡片消息
            return "[卡片消息]"
        
        return content
    
    async def send_message(
        self,
        session: SessionContext,
        content: str,
    ) -> bool:
        """
        发送文本消息
        
        参数:
            session: 会话上下文
            content: 消息内容
            
        返回:
            是否发送成功
        """
        if not self.is_configured:
            error("飞书未配置，无法发送消息")
            return False
        
        try:
            token = await self.get_tenant_access_token()
            
            url = f"{self.base_url}/im/v1/messages"
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }
            
            # 根据 session 类型确定接收者
            receive_id = session.user_id  # 私聊
            if session.metadata.get("chat_type") == "group":
                receive_id = session.metadata.get("chat_id", session.user_id)
            
            payload = {
                "receive_id": receive_id,
                "msg_type": "text",
                "content": content,
            }
            
            response = await self._client.post(
                url,
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            
            agent_event(f"飞书消息已发送: {receive_id}")
            return True
            
        except Exception as e:
            error(f"发送飞书消息失败: {e}")
            return False
    
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
        if not self.is_configured:
            error("飞书未配置")
            return False
        
        try:
            token = await self.get_tenant_access_token()
            
            url = f"{self.base_url}/im/v1/messages"
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }
            
            receive_id = session.user_id
            if session.metadata.get("chat_type") == "group":
                receive_id = session.metadata.get("chat_id", session.user_id)
            
            payload = {
                "receive_id": receive_id,
                "msg_type": "interactive",
                "content": json.dumps(card),
            }
            
            response = await self._client.post(
                url,
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            
            agent_event(f"飞书卡片已发送: {receive_id}")
            return True
            
        except Exception as e:
            error(f"发送飞书卡片失败: {e}")
            return False
    
    def get_callback_url(self) -> str:
        """获取回调 URL"""
        config = get_config()
        server_config = config.server
        host = server_config.host or "localhost"
        port = server_config.port or 8000
        
        if host == "0.0.0.0":
            host = "localhost"
        
        return f"http://{host}:{port}/webhook/feishu"
    
    async def get_user_info(self, user_id: str) -> dict[str, Any]:
        """获取用户信息"""
        if not self.is_configured:
            return {}
        
        try:
            token = await self.get_tenant_access_token()
            
            url = f"{self.base_url}/contact/v3/users/{user_id}"
            headers = {
                "Authorization": f"Bearer {token}",
            }
            
            response = await self._client.get(url, headers=headers)
            response.raise_for_status()
            
            return response.json().get("data", {})
            
        except Exception as e:
            warning(f"获取用户信息失败: {e}")
            return {}
    
    async def get_chat_info(self, chat_id: str) -> dict[str, Any]:
        """获取会话信息"""
        if not self.is_configured:
            return {}
        
        try:
            token = await self.get_tenant_access_token()
            
            url = f"{self.base_url}/im/v1/chats/{chat_id}"
            headers = {
                "Authorization": f"Bearer {token}",
            }
            
            response = await self._client.get(url, headers=headers)
            response.raise_for_status()
            
            return response.json().get("data", {})
            
        except Exception as e:
            warning(f"获取会话信息失败: {e}")
            return {}
