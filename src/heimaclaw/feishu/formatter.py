"""
飞书消息格式化模块
将 LLM 响应转换为飞书 Interactive Card 格式
"""

import json
import re


def format_feishu_card(
    content: str,
    agent_name: str = "HeiMaClaw",
) -> str:
    """
    将文本内容转换为飞书 Interactive Card 格式的 JSON 字符串
    """
    elements = []

    lines = content.split("\n")
    for line in lines:
        line = line.rstrip()

        # 空行
        if not line.strip():
            continue

        # 转换 Markdown
        formatted = _format_markdown(line)
        elements.append({"tag": "markdown", "content": formatted})

    # 如果没有元素，添加空文本
    if not elements:
        elements.append({"tag": "markdown", "content": " "})

    # 构建卡片（符合飞书规范）
    card = {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": f"🤖 {agent_name}"},
            "template": "blue",
        },
        "elements": elements,
    }

    return json.dumps(card)


def _format_markdown(text: str) -> str:
    """Markdown -> 飞书 Markdown"""
    # 代码块不转换
    if "```" in text:
        return text

    # 粗体
    text = re.sub(r"\*\*(.+?)\*\*", r"**\1**", text)
    # 斜体
    text = re.sub(r"\*(.+?)\*", r"*\1*", text)
    text = re.sub(r"_(.+?)_", r"*\1*", text)
    # 行内代码
    text = re.sub(r"`(.+?)`", r"`\1`", text)
    # 链接
    text = re.sub(r"\[(.+?)\]\((.+?)\)", r"[\1](\2)", text)

    return text


def format_simple_text(content: str) -> str:
    """简单文本消息"""
    return json.dumps({"text": content})
