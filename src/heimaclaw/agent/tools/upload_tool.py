
import os
import json
from typing import Any, Dict
import lark_oapi as lark
from lark_oapi.api.im.v1 import CreateImageRequest, CreateImageRequestBody

from heimaclaw.config.loader import get_config
from heimaclaw.console import info, error

def get_upload_image_definition() -> Dict[str, Any]:
    return {
        "name": "upload_and_send_image",
        "description": "如果你的工作生成了图表、绘图、图片文件，使用此工具将本地的图片文件上传并发送给飞书用户（在返回的消息中以富文本展示）",
        "parameters": {
            "type": "object",
            "properties": {
                "local_path": {
                    "type": "string",
                    "description": "你要发送的图片在本地的绝对路径，例如 /root/heimaclaw_workspace/chart.png"
                },
                "image_type": {
                    "type": "string",
                    "enum": ["message"],
                    "description": "必须是 'message'"
                }
            },
            "required": ["local_path", "image_type"]
        }
    }

def upload_image_handler(local_path: str, image_type: str = "message") -> str:
    """
    将本地图片上传到飞书，并返回图片可以嵌入的 Markdown 标签或 JSON
    """
    if not os.path.exists(local_path):
        return f"错误：本地文件不存在 {local_path}"
        
    config = get_config()
    feishu = config.channels.feishu
    if hasattr(feishu, "accounts") and feishu.accounts:
        account = feishu.get_default_account()
        app_id = account.app_id
        app_secret = account.app_secret
    else:
        app_id = feishu.app_id
        app_secret = feishu.app_secret

    try:
        client = lark.Client.builder().app_id(app_id).app_secret(app_secret).build()
        
        # 准备文件
        with open(local_path, "rb") as f:
            image_bytes = f.read()
            
        request = (
            CreateImageRequest.builder()
            .request_body(
                CreateImageRequestBody.builder()
                .image_type(image_type)
                .image(image_bytes)
                .build()
            )
            .build()
        )
        
        response = client.im.v1.image.create(request)
        if response.success():
            image_key = response.data.image_key
            info(f"图片上传成功，获取到 image_key: {image_key}")
            # 返回一个特殊的标记，让前端/回复能够识别并组合成富文本卡片
            return f"✅ 图片上传成功! (飞书 Image Key: {image_key})。请在你的最终回复中使用这个 Key 来给用户展示图片。"
        else:
            return f"❌ 上传失败: {response.code} {response.msg}"
    except Exception as e:
        return f"❌ 上传异常: {str(e)}"
