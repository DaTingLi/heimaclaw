"""
会话记忆测试
"""

import tempfile
from pathlib import Path

from heimaclaw.memory.session import Message, Session, SessionMemory


def test_message_creation():
    """测试消息创建"""
    msg = Message(role="user", content="Hello")

    assert msg.role == "user"
    assert msg.content == "Hello"
    assert msg.timestamp > 0


def test_message_to_dict():
    """测试消息转字典"""
    msg = Message(role="assistant", content="Hi", message_id="123")
    data = msg.to_dict()

    assert data["role"] == "assistant"
    assert data["content"] == "Hi"
    assert data["message_id"] == "123"


def test_message_from_dict():
    """测试从字典创建消息"""
    data = {"role": "system", "content": "Welcome", "timestamp": 1234567890}
    msg = Message.from_dict(data)

    assert msg.role == "system"
    assert msg.content == "Welcome"
    assert msg.timestamp == 1234567890


def test_session_creation():
    """测试会话创建"""
    session = Session(
        session_id="test-session",
        agent_id="test-agent",
        channel="feishu",
        user_id="test-user",
    )

    assert session.session_id == "test-session"
    assert len(session.messages) == 0


def test_session_add_messages():
    """测试会话添加消息"""
    session = Session(
        session_id="test-session",
        agent_id="test-agent",
        channel="feishu",
        user_id="test-user",
    )

    msg1 = Message(role="user", content="Q1")
    msg2 = Message(role="assistant", content="A1")

    session.messages.append(msg1)
    session.messages.append(msg2)

    assert len(session.messages) == 2
    assert session.messages[0].content == "Q1"


def test_session_memory_creation():
    """测试会话记忆创建"""
    with tempfile.TemporaryDirectory() as tmpdir:
        memory = SessionMemory(
            agent_id="test-agent",
            session_id="test-session",
            channel="feishu",
            user_id="test-user",
            data_dir=Path(tmpdir),
        )

        assert memory.session.session_id == "test-session"
        assert memory.get_message_count() == 0


def test_session_memory_add_message():
    """测试会话记忆添加消息"""
    with tempfile.TemporaryDirectory() as tmpdir:
        memory = SessionMemory(
            agent_id="test-agent",
            session_id="test-session",
            channel="feishu",
            user_id="test-user",
            data_dir=Path(tmpdir),
        )

        memory.add_message("user", "Hello")
        memory.add_message("assistant", "Hi")

        assert memory.get_message_count() == 2


def test_session_memory_get_recent():
    """测试获取最近消息"""
    with tempfile.TemporaryDirectory() as tmpdir:
        memory = SessionMemory(
            agent_id="test-agent",
            session_id="test-session",
            channel="feishu",
            user_id="test-user",
            data_dir=Path(tmpdir),
        )

        for i in range(10):
            memory.add_message("user", f"Message {i}")

        recent = memory.get_recent_messages(5)

        assert len(recent) == 5
        assert recent[-1].content == "Message 9"


def test_session_memory_clear():
    """测试清空消息"""
    with tempfile.TemporaryDirectory() as tmpdir:
        memory = SessionMemory(
            agent_id="test-agent",
            session_id="test-session",
            channel="feishu",
            user_id="test-user",
            data_dir=Path(tmpdir),
        )

        memory.add_message("user", "Test")
        assert memory.get_message_count() == 1

        memory.clear_messages()
        assert memory.get_message_count() == 0


def test_session_memory_persistence():
    """测试持久化"""
    with tempfile.TemporaryDirectory() as tmpdir:
        # 创建并添加消息
        memory1 = SessionMemory(
            agent_id="test-agent",
            session_id="test-session",
            channel="feishu",
            user_id="test-user",
            data_dir=Path(tmpdir),
        )

        memory1.add_message("user", "Test persistence")

        # 重新加载
        memory2 = SessionMemory(
            agent_id="test-agent",
            session_id="test-session",
            channel="feishu",
            user_id="test-user",
            data_dir=Path(tmpdir),
        )

        assert memory2.get_message_count() == 1
        assert memory2.get_recent_messages(1)[0].content == "Test persistence"


def test_session_memory_max_messages():
    """测试最大消息数限制"""
    with tempfile.TemporaryDirectory() as tmpdir:
        memory = SessionMemory(
            agent_id="test-agent",
            session_id="test-session",
            channel="feishu",
            user_id="test-user",
            max_messages=5,
            data_dir=Path(tmpdir),
        )

        # 添加 10 条消息
        for i in range(10):
            memory.add_message("user", f"Message {i}")

        # 应该只保留最近的 5 条
        assert memory.get_message_count() == 5
        assert memory.get_recent_messages(1)[0].content == "Message 9"
