"""MemoryManager 完整测试套件"""

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
        assert manager.session_memory is not None
        assert manager.daily_memory is not None
        assert manager.longterm_memory is not None


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

        assert manager.session_memory.get_message_count() == 2


def test_get_context_for_llm():
    """测试获取 LLM 上下文"""
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = MemoryManager(
            agent_id="test",
            session_id="session1",
            channel="feishu",
            user_id="user1",
            data_dir=Path(tmpdir),
        )

        manager.add_message("user", "What's your name?")
        manager.add_message("assistant", "I am test")

        context = manager.get_context_for_llm()

        assert "system_prompt" in context
        assert "messages" in context
        assert len(context["messages"]) == 2
        assert "context_info" in context
        assert context["context_info"]["session_messages"] == 2


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

        manager.extract_important_event("User prefers Chinese", event_type="preference")

        content = manager.longterm_memory.get_content()
        assert "User prefers Chinese" in content


def test_add_daily_event():
    """测试添加日常事件"""
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = MemoryManager(
            agent_id="test",
            session_id="session1",
            channel="feishu",
            user_id="user1",
            data_dir=Path(tmpdir),
        )

        manager.add_daily_event("Started conversation", event_type="general")

        events = manager.daily_memory.get_events()
        assert "Started conversation" in events


def test_get_usage_report():
    """测试获取使用报告"""
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = MemoryManager(
            agent_id="test",
            session_id="session1",
            channel="feishu",
            user_id="user1",
            data_dir=Path(tmpdir),
        )

        manager.add_message("user", "Test")
        manager.get_context_for_llm()

        report = manager.get_usage_report()

        assert "max_tokens" in report
        assert "usage" in report
        assert report["usage"]["total_used"] > 0


def test_cleanup_expired():
    """测试清理过期记忆"""
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = MemoryManager(
            agent_id="test",
            session_id="session1",
            channel="feishu",
            user_id="user1",
            data_dir=Path(tmpdir),
        )

        cleaned = manager.cleanup_expired()

        assert "session" in cleaned
        assert "daily" in cleaned
        assert "total" in cleaned
        assert isinstance(cleaned["total"], int)
