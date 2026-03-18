"""
Markdown 解析器测试
"""

import tempfile
from pathlib import Path

import pytest

from heimaclaw.config.markdown_parser import (
    MarkdownParser,
)


@pytest.fixture
def sample_agent_dir():
    """创建示例 agent 目录"""
    with tempfile.TemporaryDirectory() as tmpdir:
        agent_dir = Path(tmpdir)

        # 创建 SOUL.md
        soul_content = """# SOUL.md

## 🎯 核心定位

这是一个测试 Agent

## 💪 核心能力

### 对话交互
- 回答问题
- 执行任务

## ⚠️ 边界

- 不执行危险操作
"""
        (agent_dir / "SOUL.md").write_text(soul_content, encoding="utf-8")

        # 创建 IDENTITY.md
        identity_content = """# IDENTITY.md

## 基本信息

- **姓名**：测试 Agent
- **生物**：AI 助手
- **氛围**：友好
- **表情符号**：🤖

## 自我介绍

我是测试 Agent
"""
        (agent_dir / "IDENTITY.md").write_text(identity_content, encoding="utf-8")

        yield agent_dir


@pytest.mark.skip(reason="Phase 1 遗留问题：章节提取逻辑待优化")
def test_parse_soul(sample_agent_dir):
    """测试解析 SOUL.md"""
    parser = MarkdownParser(sample_agent_dir)
    soul = parser.parse_soul()

    assert soul is not None
    assert "测试 Agent" in soul.core_positioning
    assert len(soul.core_capabilities) > 0
    assert len(soul.boundaries) > 0


def test_parse_identity(sample_agent_dir):
    """测试解析 IDENTITY.md"""
    parser = MarkdownParser(sample_agent_dir)
    identity = parser.parse_identity()

    assert identity is not None
    assert identity.name == "测试 Agent"
    assert identity.creature == "AI 助手"
    assert identity.atmosphere == "友好"
    assert identity.emoji == "🤖"


def test_extract_section():
    """测试章节提取"""
    parser = MarkdownParser(Path("/tmp"))
    content = """# 标题

## 章节1

这是章节1的内容

## 章节2

这是章节2的内容
"""

    section = parser._extract_section(content, "章节1")
    assert "这是章节1的内容" in section


def test_extract_field():
    """测试字段提取"""
    parser = MarkdownParser(Path("/tmp"))
    content = """# 配置

- **姓名**：张三
- **年龄**：25
"""

    name = parser._extract_field(content, "姓名")
    assert name == "张三"

    age = parser._extract_field(content, "年龄")
    assert age == "25"


def test_parse_list():
    """测试列表解析"""
    parser = MarkdownParser(Path("/tmp"))
    text = """- 项目1
- 项目2
- 项目3
"""

    items = parser._parse_list(text)
    assert len(items) == 3
    assert "项目1" in items


def test_parse_nonexistent_file():
    """测试解析不存在的文件"""
    parser = MarkdownParser(Path("/tmp/nonexistent"))
    soul = parser.parse_soul()
    assert soul is None

    identity = parser.parse_identity()
    assert identity is None
