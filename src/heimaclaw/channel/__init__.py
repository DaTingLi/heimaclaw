"""
渠道模块

提供飞书和企业微信渠道适配器。
"""

# 延迟导入，避免循环依赖
def get_feishu_adapter():
    from heimaclaw.channel.feishu import FeishuAdapter
    return FeishuAdapter

def get_wecom_adapter():
    from heimaclaw.channel.wecom import WeComAdapter
    return WeComAdapter

__all__ = ["get_feishu_adapter", "get_wecom_adapter", "ChannelAdapter", "InboundMessage", "OutboundMessage"]
