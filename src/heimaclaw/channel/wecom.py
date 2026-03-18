"""
企业微信渠道适配器

实现企业微信消息的接收、解析、发送。
"""

import hashlib
import hmac
import json
import time
import xml.etree.ElementTree
from typing import Any, Optional

import httpx

from heimaclaw.channel.base import ChannelAdapter, InboundMessage, OutboundMessage
from heimaclaw.interfaces import ChannelType, SessionContext
from heimaclaw.console import info, warning, error, agent_event
from heimaclaw.config.loader import get_config


class WeComAdapter(ChannelAdapter):
    """
    企业微信渠道适配器
    
    支持功能：
    - Webhook 事件验证（签名校验、解密）
    - 消息解析（文本、卡片）
    - 消息发送（文本、卡片）
    - 用户/群聊信息获取
    """
    
    def __init__(
        self,
        corp_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        secret: Optional[str] = None,
        token: Optional[str] = None,
        encoding_aes_key: Optional[str] = None,
    ):
        """
        初始化企业微信适配器
        
        参数:
            corp_id: 企业 ID
            agent_id: 应用 ID
            secret: 应用 Secret
            token: Token
            encoding_aes_key: EncodingAESKey
        """
        # 从配置加载
        config = get_config()
        wecom_config = config.channels.wecom
        
        self.corp_id = corp_id or wecom_config.corp_id
        self.agent_id = agent_id or wecom_config.agent_id
        self.secret = secret or wecom_config.secret
        self.token = token or wecom_config.token
        self.encoding_aes_key = encoding_aes_key or wecom_config.encoding_aes_key
        
        # API 基础 URL
        self.base_url = "https://qyapi.weixin.qq.com/cgi-bin"
        
        # 访问令牌缓存
        self._access_token: Optional[str] = None
        self._token_expire_time: float = 0
        
        # HTTP 客户端
        self._client = httpx.AsyncClient(timeout=30.0)
    
    @property
    def channel_type(self) -> ChannelType:
        return ChannelType.WECOM
    
    @property
    def is_configured(self) -> bool:
        """检查是否已配置"""
        return bool(self.corp_id and self.agent_id and self.secret)
    
    async def get_access_token(self) -> str:
        """
        获取访问令牌
        
        使用 corp_id 和 secret 获取访问令牌。
        
        返回:
            访问令牌字符串
        """
        # 检查缓存
        if self._access_token and time.time() < self._token_expire_time:
            return self._access_token
        
        # 请求新令牌
        url = f"{self.base_url}/gettoken"
        params = {
            "corpid": self.corp_id,
            "corpsecret": self.secret,
        }
        
        response = await self._client.get(url, params=params)
        response.raise_for_status()
        
        data = response.json()
        self._access_token = data.get("access_token")
        self._token_expire_time = time.time() + data.get("expires_in", 7200)
        
        return self._access_token
    
    async def verify_webhook(self, request: Any) -> bool:
        """
        验证 Webhook 请求
        
        对于企业微信，需要验证签名和解密消息。
        """
        # URL 验证请求（首次配置时）
        if hasattr(request, "query_params"):
            msg_signature = request.query_params.get("msg_signature")
            timestamp = request.query_params.get("timestamp")
            nonce = request.query_params.get("nonce")
            echostr = request.query_params.get("echostr")
            
            if echostr:
                # 验证签名
                if self._verify_signature(
                    timestamp or "",
                    nonce or "",
                    echostr or "",
                    msg_signature or "",
                ):
                    agent_event("企业微信 URL 验证成功")
                    return True
                else:
                    warning("企业微信 URL 验证失败")
                    return False
        
        # 消息回调验证
        return True
    
    def _verify_signature(
        self,
        timestamp: str,
        nonce: str,
        echostr: str,
        signature: str,
    ) -> bool:
        """
        验证签名
        
        参数:
            timestamp: 时间戳
            nonce: 随机数
            echostr: 回调字符串
            signature: 签名
            
        返回:
            是否验证通过
        """
        # 拼接字符串并排序
        items = [self.token, timestamp, nonce, echostr]
        items.sort()
        
        # SHA1 计算
        sha1 = hashlib.sha1("".join(items).encode()).hexdigest()
        
        return sha1 == signature
    
    def _decrypt_message(self, encrypted: str) -> str:
        """
        解密消息
        
        使用 AES-256-CBC 解密消息。
        
        参数:
            encrypted: 加密的消息（Base64 编码）
            
        返回:
            解密后的消息 JSON 字符串
        """
        if not self.encoding_aes_key:
            return encrypted
        
        try:
            import base64
            from Crypto.Cipher import AES
            
            # 解码 AES Key
            aes_key = base64.b64decode(self.encoding_aes_key + "=")
            
            # 解码加密消息
            encrypted_data = base64.b64decode(encrypted)
            
            # 提取 IV（前 16 字节）
            iv = encrypted_data[:16]
            ciphertext = encrypted_data[16:]
            
            # 解密
            cipher = AES.new(aes_key, AES.MODE_CBC, iv)
            decrypted = cipher.decrypt(ciphertext)
            
            # 去除 PKCS7 填充
            pad = decrypted[-1]
            decrypted = decrypted[:-pad]
            
            return decrypted.decode("utf-8")
            
        except Exception as e:
            warning(f"解密消息失败: {e}")
            return encrypted
    
    async def parse_message(self, request: Any) -> InboundMessage:
        """
        解析企业微信消息
        
        将企业微信事件转换为标准消息格式。
        """
        # 获取请求体
        if hasattr(request, "body"):
            body = request.body
        else:
            raise ValueError("无法获取请求体")
        
        # 解析 XML
        try:
            root = xml.etree.ElementTree.fromstring(body)
        except Exception as e:
            raise ValueError(f"解析 XML 失败: {e}")
        
        # 获取消息类型
        msg_type = root.findtext("MsgType", "unknown")
        
        # 事件消息
        if msg_type == "event":
            event = root.findtext("Event", "")
            
            return InboundMessage(
                message_id=root.findtext("MsgId", ""),
                chat_id=root.findtext("FromUserName", ""),
                user_id=root.findtext("FromUserName", ""),
                user_name=None,
                content=f"[事件] {event}",
                message_type="event",
                timestamp=time.time(),
                raw_data={"xml": body.decode() if isinstance(body, bytes) else body},
            )
        
        # 文本消息
        if msg_type == "text":
            content = root.findtext("Content", "")
            
            return InboundMessage(
                message_id=root.findtext("MsgId", ""),
                chat_id=root.findtext("FromUserName", ""),
                user_id=root.findtext("FromUserName", ""),
                user_name=None,
                content=content,
                message_type="text",
                timestamp=time.time(),
                raw_data={"xml": body.decode() if isinstance(body, bytes) else body},
            )
        
        # 其他类型
        return InboundMessage(
            message_id=root.findtext("MsgId", ""),
            chat_id=root.findtext("FromUserName", ""),
            user_id=root.findtext("FromUserName", ""),
            user_name=None,
            content=f"[{msg_type}] 消息",
            message_type=msg_type,
            timestamp=time.time(),
            raw_data={"xml": body.decode() if isinstance(body, bytes) else body},
        )
    
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
            error("企业微信未配置")
            return False
        
        try:
            token = await self.get_access_token()
            
            url = f"{self.base_url}/message/send"
            params = {"access_token": token}
            
            payload = {
                "touser": session.user_id,
                "msgtype": "text",
                "agentid": self.agent_id,
                "text": {"content": content},
            }
            
            response = await self._client.post(
                url,
                params=params,
                json=payload,
            )
            response.raise_for_status()
            
            agent_event(f"企业微信消息已发送: {session.user_id}")
            return True
            
        except Exception as e:
            error(f"发送企业微信消息失败: {e}")
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
            error("企业微信未配置")
            return False
        
        try:
            token = await self.get_access_token()
            
            url = f"{self.base_url}/message/send"
            params = {"access_token": token}
            
            payload = {
                "touser": session.user_id,
                "msgtype": "template_card",
                "agentid": self.agent_id,
                "template_card": card,
            }
            
            response = await self._client.post(
                url,
                params=params,
                json=payload,
            )
            response.raise_for_status()
            
            agent_event(f"企业微信卡片已发送: {session.user_id}")
            return True
            
        except Exception as e:
            error(f"发送企业微信卡片失败: {e}")
            return False
    
    def get_callback_url(self) -> str:
        """获取回调 URL"""
        config = get_config()
        server_config = config.server
        host = server_config.host or "localhost"
        port = server_config.port or 8000
        
        if host == "1.0.0.0":
            host = "localhost"
        
        return f"http://{host}:{port}/webhook/wecom"
    
    async def get_user_info(self, user_id: str) -> dict[str, Any]:
        """获取用户信息"""
        if not self.is_configured:
            return {}
        
        try:
            token = await self.get_access_token()
            
            url = f"{self.base_url}/user/get"
            params = {
                "access_token": token,
                "userid": user_id,
            }
            
            response = await self._client.get(url, params=params)
            response.raise_for_status()
            
            return response.json()
            
        except Exception as e:
            warning(f"获取用户信息失败: {e}")
            return {}
    
    async def get_chat_info(self, chat_id: str) -> dict[str, Any]:
        """获取会话信息"""
        # 企业微信没有直接的会话信息 API
        return {"chat_id": chat_id}
