"""MemoryManager v2.0 完整测试套件"""

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
        assert manager._store is not None
        assert manager._auto_summary is not None


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

        # v2.0: 通过 store 查询
        count = manager._store.get_message_count("session1")
        assert count == 2


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

        # v2.0: 返回 list[dict]
        context = manager.get_context_for_llm()

        assert isinstance(context, list)
        assert len(context) == 2
        assert context[0]["role"] == "user"
        assert context[1]["role"] == "assistant"


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

        manager.extract_important_event(
            "User prefers Chinese",
            event_type="preference",
            importance=8,
        )

        # v2.0: 通过 store 查询
        events = manager._store.get_events(user_id="user1")
        assert len(events) >= 1
        assert any("Chinese" in e["content"] for e in events)


def test_auto_extract_events():
    """测试自动提取事件"""
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = MemoryManager(
            agent_id="test",
            session_id="session1",
            channel="feishu",
            user_id="user1",
            data_dir=Path(tmpdir),
        )

        manager.add_message("user", "记住我喜欢用中文交流")
        manager.add_message("assistant", "好的")

        count = manager.auto_extract_events()
        assert count >= 1


def test_create_summary():
    """测试创建摘要"""
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

        manager.create_summary("这是一个测试会话")

        # v2.0: 摘要已存储
        summary = manager._store.get_latest_summary("session1")
        assert summary is not None
        assert "测试会话" in summary["summary"]


def test_get_usage_report():
    """测试使用报告"""
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = MemoryManager(
            agent_id="test",
            session_id="session1",
            channel="feishu",
            user_id="user1",
            data_dir=Path(tmpdir),
        )

        manager.add_message("user", "Hello")

        report = manager.get_usage_report()

        assert "session_id" in report
        assert "message_count" in report
        assert report["message_count"] == 1


def test_cleanup_expired():
    """测试清理过期数据"""
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = MemoryManager(
            agent_id="test",
            session_id="session1",
            channel="feishu",
            user_id="user1",
            data_dir=Path(tmpdir),
        )

        result = manager.cleanup_expired()

        assert "cleaned" in result


def test_get_user_profile():
    """测试用户画像"""
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = MemoryManager(
            agent_id="test",
            session_id="session1",
            channel="feishu",
            user_id="user1",
            data_dir=Path(tmpdir),
        )

        manager.update_user_profile("language", "Chinese", confidence=8)

        profile = manager.get_user_profile()
        assert profile.get("language") == "Chinese"
