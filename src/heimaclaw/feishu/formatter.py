"""
飞书消息格式化模块
将 LLM 响应转换为飞书 Interactive Card 格式
"""
import re


def format_feishu_card(
    content: str,
    agent_name: str = "HeiMaClaw",
) -> dict:
    """
    将文本内容转换为飞书 Interactive Card 格式
    """
    elements = []
    lines = content.split("\n")

    for line in lines:
        line = line.rstrip()

        if not line.strip():
            elements.append({"tag": "hr"})
            continue

        formatted = _format_markdown(line)
        elements.append({"tag": "markdown", "content": formatted})

    card = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": f"🤖 {agent_name}",
                },
                "template": "blue",
            },
            "elements": elements,
        },
    }

    return card


def _format_markdown(text: str) -> str:
    """Markdown -> 飞书 Markdown"""
    # 粗体 **text**
    text = re.sub(r"\*\*(.+?)\*\*", r"**\1**", text)
    # 斜体
    text = re.sub(r"\*(.+?)\*", r"*\1*", text)
    text = re.sub(r"_(.+?)_", r"*\1*", text)
    # 行内代码
    text = re.sub(r"`(.+?)`", r"`\1`", text)
    # 链接
    text = re.sub(r"\[(.+?)\]\((.+?)\)", r"[\1](\2)", text)
    return text


def format_simple_text(content: str) -> dict:
    """简单文本消息"""
    return {"msg_type": "text", "content": content}
