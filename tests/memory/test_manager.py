"""MemoryManager 测试"""

import tempfile
from pathlib import Path

from heimaclaw.memory.manager import MemoryManager


def test_memory_manager_creation():
    """测试创建"""
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = MemoryManager(
            agent_id="test",
            session_id="session1",
            channel="feishu",
            user_id="user1",
            data_dir=Path(tmpdir),
        )
        assert manager.agent_id == "test"


def test_add_message():
    """测试添加消息"""
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = MemoryManager(
            agent_id="test",
            session_id="session1",
            channel="feishu",
            user_id="user1",
            data_dir=Path(tmpdir),
        )

        manager.add_message("user", "Hello")
        manager.add_message("assistant", "Hi")

        context = manager.get_context_for_llm()
        assert len(context["messages"]) == 2


def test_extract_important_event():
    """测试提取重要事件"""
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = MemoryManager(
            agent_id="test",
            session_id="session1",
            channel="feishu",
            user_id="user1",
            data_dir=Path(tmpdir),
        )

        manager.extract_important_event("Test event")
        # 验证长期记忆中有内容
        content = manager.longterm_memory.get_content()
        assert "Test event" in content
