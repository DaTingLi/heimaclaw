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
                    # 尝试获取文本
                    content_text = content_obj.get("text", "")
                    # 如果没有文本，可能是文件或图片
                    if not content_text:
                        if "file_key" in content_obj:
                            content_text = f"[收到文件: {content_obj.get('file_name', 'unknown')}]"
                        elif "image_key" in content_obj:
                            content_text = "[收到一张图片]"
                        else:
                            content_text = "[收到一条非文本消息]"
                except Exception:
                    content_text = content
            else:
                content_text = str(content)

            # 【关键修复1】解析 mentions 并替换文本中的占位符
            mention_names = []
            if hasattr(msg, "mentions") and msg.mentions:
                for m in msg.mentions:
                    key = getattr(m, "key", "")
                    name = getattr(m, "name", "")
                    if key and name:
                        # 把类似 "@_user_1" 替换成真实的 "@HeimaClaw"
                        content_text = content_text.replace(key, f"@{name}")
                        mention_names.append(name)

            # 【关键修复2】确定 chat_type (非常重要)
            chat_type = getattr(msg, "chat_type", "")
            if not chat_type:
                chat_type = "group" if (msg.chat_id and msg.chat_id.startswith("oc_")) else "p2p"

            # 创建消息对象
            inbound_msg = InboundMessage(
                message_id=message_id,
                chat_id=msg.chat_id or "",
                user_id=user_id,
                user_name=sender.sender_id.user_id if sender.sender_id else "",
                content=content_text,
                message_type="text",
                chat_type=chat_type,
                mentions=mention_names,
                timestamp=time.time(),
                raw_data={"event": data.event},
            )

            # 回调处理 - Fire-and-Forget 模式（不阻塞）
            if self._message_callback:
                try:
                    import asyncio

                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            # Fire-and-Forget：只投递任务，不等待结果
                            asyncio.run_coroutine_threadsafe(
                                self._message_callback(inbound_msg), loop
                            )
                            # 不调用 future.result()！让回调在后台运行
                        else:
                            # 如果事件循环未运行，用后台任务方式启动
                            asyncio.ensure_future(self._message_callback(inbound_msg))
                    except RuntimeError:
                        # 没有事件循环，创建新的后台任务
                        asyncio.ensure_future(self._message_callback(inbound_msg))
                except Exception as e:
                    error(f"投递消息到处理队列失败: {e}")

        except Exception as e:
            error(f"处理飞书消息失败: {e}")

    async def send_message(self, message: OutboundMessage) -> bool:
        """
        发送飞书消息

        支持 text 和 interactive (卡片) 两种类型
        """
        try:
            chat_id = message.chat_id
            is_group = chat_id.startswith("oc_")
            receive_type = "chat_id" if is_group else "open_id"

            # 根据消息类型选择格式
            if message.message_type == "interactive":
                # 卡片消息：content 已经是 JSON 字符串
                msg_type = "interactive"
                content = (
                    message.content
                    if isinstance(message.content, str)
                    else json.dumps(message.content)
                )
            else:
                # 文本消息
                msg_type = "text"
                if isinstance(message.content, str):
                    content = json.dumps({"text": message.content})
                else:
                    content = json.dumps(message.content)

            # 创建消息请求
            request = (
                CreateMessageRequest.builder()
                .receive_id_type(receive_type)
                .request_body(
                    CreateMessageRequestBody.builder()
                    .receive_id(chat_id)
                    .msg_type(msg_type)
                    .content(content)
                    .build()
                )
                .build()
            )

            # 发送消息
            response = self.client.im.v1.message.create(request)

            if response.success():
                info("飞书消息发送成功")
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
                info("飞书消息发送成功")
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
                info("飞书消息发送成功")
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



    async def add_typing_indicator(self, message_id: str) -> Optional[str]:
        """
        添加 Typing Indicator（emoji reaction）

        参数:
            message_id: 消息 ID

        返回:
            reaction_id 或 None
        """
        try:
            from lark_oapi.api.im.v1 import CreateMessageReactionRequest

            request = (
                CreateMessageReactionRequest.builder()
                .message_id(message_id)
                .request_body(
                    {
                        "reaction_type": {
                            "emoji_type": "Typing"  # 使用 Typing emoji
                        }
                    }
                )
                .build()
            )

            response = self.client.im.v1.message_reaction.create(request)

            if response.success():
                reaction_id = getattr(response.data, 'reaction_id', None) if hasattr(response, 'data') else None
                info(f"添加 Typing Indicator 成功: {reaction_id}")
                return reaction_id
            else:
                error(f"添加 Typing Indicator 失败: code={response.code}, msg={response.msg}")
                return None

        except Exception as e:
            error(f"添加 Typing Indicator 异常: {e}")
            return None

    async def remove_typing_indicator(self, message_id: str, reaction_id: str) -> bool:
        """
        移除 Typing Indicator

        参数:
            message_id: 消息 ID
            reaction_id: Reaction ID

        返回:
            是否成功
        """
        try:
            from lark_oapi.api.im.v1 import DeleteMessageReactionRequest

            request = (
                DeleteMessageReactionRequest.builder()
                .message_id(message_id)
                .reaction_id(reaction_id)
                .build()
            )

            response = self.client.im.v1.message_reaction.delete(request)

            if response.success():
                info(f"移除 Typing Indicator 成功")
                return True
            else:
                error(f"移除 Typing Indicator 失败: code={response.code}, msg={response.msg}")
                return False

        except Exception as e:
            error(f"移除 Typing Indicator 异常: {e}")
            return False

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

    async def send_message_to_user(
        self,
        user_id: str,
        content: str,
    ) -> bool:
        """
        发送消息给用户

        参数:
            user_id: 用户 ID (open_id)
            content: 消息内容

        返回:
            是否发送成功
        """
        try:
            from lark_oapi.api.im.v1 import (
                CreateMessageRequest,
                CreateMessageRequestBody,
            )

            request = (
                CreateMessageRequest.builder()
                .receive_id_type("open_id")
                .request_body(
                    CreateMessageRequestBody.builder()
                    .receive_id(user_id)
                    .msg_type("text")
                    .content(json.dumps({"text": content}))
                    .build()
                )
                .build()
            )

            response = self.client.im.v1.message.create(request)

            if response.success():
                info("飞书消息发送成功")
                info(f"消息发送成功: {user_id}")
                return True
            else:
                error(f"消息发送失败: code={response.code}, msg={response.msg}")
                return False

        except Exception as e:
            error(f"发送消息异常: {e}")
            return False
