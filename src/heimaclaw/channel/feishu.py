"""
飞书渠道适配器

实现飞书（Lark）的消息接收和发送。
"""

import json
import time
from typing import Any, Optional

from httpx import AsyncClient

from heimaclaw.channel.base import ChannelAdapter, InboundMessage, OutboundMessage
from heimaclaw.console import agent_event, error, info
from heimaclaw.interfaces import ChannelType


class FeishuAdapter(ChannelAdapter):
    """
    飞书渠道适配器

    支持飞书机器人的消息收发。
    """

    channel_type = ChannelType.FEISHU
    base_url = "https://open.feishu.cn/open-apis"

    def __init__(self, config: dict[str, Any]) -> None:
        """
        初始化飞书适配器

        参数:
            config: 配置字典，包含:
                - app_id: 应用 ID
                - app_secret: 应用密钥
                - encrypt_key: 加密密钥（可选）
        """
        self.app_id = config.get("app_id", "")
        self.app_secret = config.get("app_secret", "")
        self.encrypt_key = config.get("encrypt_key", "")

        self._client = AsyncClient(timeout=30.0)
        self._tenant_access_token: Optional[str] = None
        self._token_expire_time: float = 0

    async def get_tenant_access_token(self) -> str:
        """
        获取租户访问令牌

        返回:
            访问令牌字符串
        """
        # 检查缓存
        if self._tenant_access_token and time.time() < self._token_expire_time:
            return self._tenant_access_token

        # 请求新令牌
        url = f"{self.base_url}/auth/v3/tenant_access_token/internal"

        # 飞书 API 要求在 body 中传递参数
        body = {
            "app_id": self.app_id,
            "app_secret": self.app_secret,
        }

        headers = {
            "Content-Type": "application/json",
        }

        try:
            response = await self._client.post(url, json=body, headers=headers)
            response.raise_for_status()

            data = response.json()

            if data.get("code") != 0:
                error(f"获取 token 失败: {data.get('msg')}")
                raise Exception(f"飞书 API 错误: {data.get('msg')}")

            self._tenant_access_token = data.get("tenant_access_token")
            expire = data.get("expire", 7200)
            self._token_expire_time = time.time() + expire - 300  # 提前 5 分钟过期

            info(f"飞书 token 获取成功，有效期: {expire} 秒")

            return self._tenant_access_token or ""

        except Exception as e:
            error(f"获取飞书 token 失败: {e}")
            raise

    async def verify_webhook(self, request: Any) -> bool:
        """
        验证 Webhook 请求
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

        return True

    async def parse_message(self, request: Any) -> Optional[InboundMessage]:
        """
        解析飞书消息
        """
        try:
            if hasattr(request, "json"):
                body = await request.json()
            elif isinstance(request, dict):
                body = request
            else:
                body = json.loads(str(request))

            # 验证签名（如果配置了加密密钥）
            if self.encrypt_key:
                # TODO: 实现签名验证
                pass

            # 解析事件
            event = body.get("event", {})
            message = event.get("message", {})
            sender = event.get("sender", {})

            return InboundMessage(
                message_id=message.get("message_id", ""),
                user_id=sender.get("sender_id", {}).get("open_id", ""),
                content=message.get("content", ""),
                timestamp=event.get("created_at", int(time.time())),
                raw_message=body,
            )

        except Exception as e:
            error(f"解析飞书消息失败: {e}")
            return None

    async def send_message(self, message: OutboundMessage) -> bool:
        """
        发送飞书消息
        """
        try:
            token = await self.get_tenant_access_token()

            url = f"{self.base_url}/im/v1/messages"
            params = {
                "receive_id_type": "open_id"
                if message.user_id.startswith("ou_")
                else "chat_id",
            }

            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }

            body = {
                "receive_id": message.user_id,
                "msg_type": "text",
                "content": json.dumps({"text": message.content}),
            }

            response = await self._client.post(
                url,
                params=params,
                json=body,
                headers=headers,
            )
            response.raise_for_status()

            data = response.json()
            return data.get("code") == 0

        except Exception as e:
            error(f"发送飞书消息失败: {e}")
            return False

    async def close(self) -> None:
        """关闭连接"""
        await self._client.aclose()

    def is_configured(self) -> bool:
        """是否已配置"""
        return bool(self.app_id and self.app_secret)

    def get_callback_url(self) -> str:
        """获取回调 URL"""
        # TODO: 从配置中获取
        return "/webhook/feishu"

    async def send_card(
        self,
        user_id: str,
        card: dict[str, Any],
    ) -> bool:
        """
        发送卡片消息

        参数:
            user_id: 用户 ID
            card: 卡片内容

        返回:
            是否发送成功
        """
        try:
            token = await self.get_tenant_access_token()

            url = f"{self.base_url}/im/v1/messages"
            params = {
                "receive_id_type": "open_id"
                if user_id.startswith("ou_")
                else "chat_id",
            }

            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }

            body = {
                "receive_id": user_id,
                "msg_type": "interactive",
                "content": json.dumps(card),
            }

            response = await self._client.post(
                url,
                params=params,
                json=body,
                headers=headers,
            )
            response.raise_for_status()

            data = response.json()
            return data.get("code") == 0

        except Exception as e:
            error(f"发送飞书卡片失败: {e}")
            return False

    async def get_user_info(self, user_id: str) -> dict[str, Any]:
        """
        获取用户信息

        参数:
            user_id: 用户 ID (open_id)

        返回:
            用户信息字典
        """
        try:
            token = await self.get_tenant_access_token()

            url = f"{self.base_url}/contact/v3/users/{user_id}"
            headers = {
                "Authorization": f"Bearer {token}",
            }

            response = await self._client.get(url, headers=headers)
            response.raise_for_status()

            data = response.json()

            if data.get("code") == 0:
                return data.get("data", {}).get("user", {})
            else:
                return {}

        except Exception as e:
            error(f"获取飞书用户信息失败: {e}")
            return {}

    async def get_chat_info(self, chat_id: str) -> dict[str, Any]:
        """
        获取会话信息

        参数:
            chat_id: 会话 ID

        返回:
            会话信息字典
        """
        try:
            token = await self.get_tenant_access_token()

            url = f"{self.base_url}/im/v1/chats/{chat_id}"
            headers = {
                "Authorization": f"Bearer {token}",
            }

            response = await self._client.get(url, headers=headers)
            response.raise_for_status()

            data = response.json()

            if data.get("code") == 0:
                return data.get("data", {})
            else:
                return {}

        except Exception as e:
            error(f"获取飞书会话信息失败: {e}")
            return {}
