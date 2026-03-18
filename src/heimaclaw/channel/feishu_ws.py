"""
飞书 WebSocket 长连接适配器

使用飞书官方 SDK 建立长连接，无需配置 Webhook URL。
"""

import asyncio
import json
import threading
import time
from typing import Any, Callable, Optional

from heimaclaw.channel.base import ChannelAdapter, InboundMessage, OutboundMessage
from heimaclaw.console import error, info
from heimaclaw.interfaces import ChannelType

# 飞书 SDK
try:
    import lark_oapi as lark
    from lark_oapi.api.im.v1 import CreateMessageRequest, CreateMessageRequestBody

    LARK_AVAILABLE = True
except ImportError:
    LARK_AVAILABLE = False
    error("飞书 SDK 未安装，请运行: pip install lark-oapi")


class FeishuWebSocketAdapter(ChannelAdapter):
    """
    飞书 WebSocket 长连接适配器

    使用飞书官方 SDK 建立长连接，自动接收消息。
    """

    channel_type = ChannelType.FEISHU
    base_url = "https://open.feishu.cn/open-apis"

    def __init__(self, config: Optional[dict[str, Any]] = None) -> None:
        """
        初始化飞书 WebSocket 适配器

        参数:
            config: 配置字典，包含:
                - app_id: 应用 ID
                - app_secret: 应用密钥
        """
        config = config or {}
        self.app_id = config.get("app_id", "")
        self.app_secret = config.get("app_secret", "")

        if not LARK_AVAILABLE:
            raise ImportError("飞书 SDK 未安装")

        if not self.app_id or not self.app_secret:
            raise ValueError("飞书配置不完整，需要 app_id 和 app_secret")

        # 初始化飞书客户端
        self.client = (
            lark.Client.builder()
            .app_id(self.app_id)
            .app_secret(self.app_secret)
            .build()
        )

        self._ws_client = None
        self._ws_thread = None
        self._running = False
        self._message_callback: Optional[Callable] = None

        # 消息去重缓存
        self._processed_messages: dict[str, float] = {}
        self._cache_expire_seconds = 3600

        info(f"飞书 WebSocket 适配器初始化完成，App ID: {self.app_id[:10]}...")

    def is_configured(self) -> bool:
        """是否已配置"""
        return bool(self.app_id and self.app_secret)

    def get_callback_url(self) -> str:
        """获取回调 URL（长连接模式不需要）"""
        return ""

    async def start_listening(
        self,
        message_callback: Callable[[InboundMessage], Any],
    ) -> None:
        """
        启动 WebSocket 长连接

        参数:
            message_callback: 消息回调函数
        """
        self._message_callback = message_callback
        self._running = True

        # 创建事件处理器
        event_handler = (
            lark.EventDispatcherHandler.builder("", "")
            .register_p2_im_message_receive_v1(self._handle_message_event)
            .build()
        )

        # 创建 WebSocket 客户端
        self._ws_client = lark.ws.Client(
            self.app_id,
            self.app_secret,
            event_handler=event_handler,
            log_level=lark.LogLevel.INFO,
        )

        info("飞书 WebSocket 连接启动中...")

        # 在单独的线程中运行 WebSocket
        def run_ws():
            try:
                self._ws_client.start()
            except Exception as e:
                error(f"飞书 WebSocket 异常: {e}")

        self._ws_thread = threading.Thread(target=run_ws, daemon=True)
        self._ws_thread.start()

        info("飞书 WebSocket 连接已启动（后台线程）")

        # 保持运行
        while self._running:
            await asyncio.sleep(1)

    def _handle_message_event(self, data: Any) -> None:
        """
        处理飞书消息事件

        参数:
            data: 飞书事件数据
        """
        try:
            if not data.event or not data.event.message:
                return

            msg = data.event.message

            # 消息去重检查
            message_id = msg.message_id
            if not message_id:
                return

            if self._is_duplicate_message(message_id):
                info(f"重复消息已忽略: {message_id[:20]}...")
                return

            # 标记消息已处理
            self._mark_message_processed(message_id)

            # 清理过期缓存
            self._cleanup_message_cache()

            # 解析消息
            sender = data.event.sender
            user_id = sender.sender_id.open_id if sender.sender_id else ""

            # 解析消息内容
            content = msg.content
            if isinstance(content, str):
                try:
                    content_obj = json.loads(content)
                    content_text = content_obj.get("text", "")
                except Exception:
                    content_text = content
            else:
                content_text = str(content)

            # 创建消息对象
            inbound_msg = InboundMessage(
                message_id=message_id,
                user_id=user_id,
                content=content_text,
                timestamp=int(time.time()),
                raw_message=data,
            )

            # 回调处理
            if self._message_callback:
                try:
                    # 在事件循环中调用回调
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(self._message_callback(inbound_msg))
                    loop.close()
                except Exception as e:
                    error(f"消息回调失败: {e}")

        except Exception as e:
            error(f"处理飞书消息失败: {e}")

    async def send_message(self, message: OutboundMessage) -> bool:
        """
        发送飞书消息

        参数:
            message: 出站消息

        返回:
            是否发送成功
        """
        try:
            # 创建消息请求
            request = (
                CreateMessageRequest.builder()
                .receive_id_type(
                    "open_id" if message.user_id.startswith("ou_") else "chat_id"
                )
                .request_body(
                    CreateMessageRequestBody.builder()
                    .receive_id(message.user_id)
                    .msg_type("text")
                    .content(json.dumps({"text": message.content}))
                    .build()
                )
                .build()
            )

            # 发送消息
            response = self.client.im.v1.message.create(request)

            if response.success():
                info(f"飞书消息发送成功: {message.user_id}")
                return True
            else:
                error(f"飞书消息发送失败: code={response.code}, msg={response.msg}")
                return False

        except Exception as e:
            error(f"发送飞书消息异常: {e}")
            return False

    async def send_card(self, user_id: str, card: dict[str, Any]) -> bool:
        """发送卡片消息"""
        try:
            request = (
                CreateMessageRequest.builder()
                .receive_id_type("open_id" if user_id.startswith("ou_") else "chat_id")
                .request_body(
                    CreateMessageRequestBody.builder()
                    .receive_id(user_id)
                    .msg_type("interactive")
                    .content(json.dumps(card))
                    .build()
                )
                .build()
            )

            response = self.client.im.v1.message.create(request)
            return response.success()

        except Exception as e:
            error(f"发送飞书卡片失败: {e}")
            return False

    async def get_user_info(self, user_id: str) -> dict[str, Any]:
        """获取用户信息"""
        try:
            from lark_oapi.api.contact.v3 import GetUserRequest

            request = GetUserRequest.builder().user_id(user_id).build()

            response = self.client.contact.v3.user.get(request)

            if response.success():
                return response.data.user
            else:
                return {}

        except Exception as e:
            error(f"获取飞书用户信息失败: {e}")
            return {}

    async def get_chat_info(self, chat_id: str) -> dict[str, Any]:
        """获取会话信息"""
        try:
            from lark_oapi.api.im.v1 import GetChatRequest

            request = GetChatRequest.builder().chat_id(chat_id).build()

            response = self.client.im.v1.chat.get(request)

            if response.success():
                return response.data
            else:
                return {}

        except Exception as e:
            error(f"获取飞书会话信息失败: {e}")
            return {}

    async def verify_webhook(self, request: Any) -> bool:
        """验证 Webhook（长连接模式不需要）"""
        return True

    async def parse_message(self, request: Any) -> Optional[InboundMessage]:
        """解析消息（长连接模式自动处理）"""
        return None

    async def close(self) -> None:
        """关闭连接"""
        self._running = False
        # 飞书 SDK 暂不支持优雅关闭
        info("飞书 WebSocket 适配器已停止")

    def _is_duplicate_message(self, message_id: str) -> bool:
        """检查消息是否重复"""
        return message_id in self._processed_messages

    def _mark_message_processed(self, message_id: str) -> None:
        """标记消息已处理"""
        self._processed_messages[message_id] = time.time()

    def _cleanup_message_cache(self) -> None:
        """清理过期缓存"""
        current = time.time()
        expired = [
            msg_id
            for msg_id, timestamp in self._processed_messages.items()
            if current - timestamp > self._cache_expire_seconds
        ]
        for msg_id in expired:
            del self._processed_messages[msg_id]
