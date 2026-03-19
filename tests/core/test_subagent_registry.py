"""
Subagent Registry 单元测试
"""

import pytest
from pathlib import Path
from datetime import datetime
import tempfile

from heimaclaw.core.subagent_registry import (
    SubagentRegistry,
    SubagentRun,
    SubagentStatus,
)


@pytest.fixture
def temp_registry():
    """创建临时 Registry"""
    with tempfile.TemporaryDirectory() as tmpdir:
        registry = SubagentRegistry(state_dir=Path(tmpdir) / "subagent-state")
        yield registry


def test_register_run(temp_registry):
    """测试注册子 Agent"""
    run = SubagentRun(
        task="测试任务",
        requester_session_key="session:main:test",
        agent_id="test-agent",
    )
    
    run_id = temp_registry.register(run)
    
    assert run_id == run.run_id
    
    # 验证可以获取
    retrieved = temp_registry.get(run_id)
    assert retrieved is not None
    assert retrieved.task == "测试任务"


def test_update_status(temp_registry):
    """测试更新状态"""
    run = SubagentRun(task="测试", requester_session_key="session:main:test")
    run_id = temp_registry.register(run)
    
    # 标记为运行中
    temp_registry.mark_started(run_id)
    retrieved = temp_registry.get(run_id)
    assert retrieved.status == SubagentStatus.RUNNING
    assert retrieved.started_at is not None
    
    # 标记为完成
    temp_registry.mark_completed(run_id, "任务成功")
    retrieved = temp_registry.get(run_id)
    assert retrieved.status == SubagentStatus.COMPLETED
    assert retrieved.result_text == "任务成功"
    assert retrieved.completed_at is not None


def test_list_for_requester(temp_registry):
    """测试列出子 Agent"""
    session_key = "session:main:test"
    
    # 注册 3 个运行
    for i in range(3):
        run = SubagentRun(
            task=f"任务 {i}",
            requester_session_key=session_key,
        )
        temp_registry.register(run)
    
    # 列出
    runs = temp_registry.list_for_requester(session_key)
    assert len(runs) == 3
    
    # 列出活动的
    temp_registry.mark_completed(runs[0].run_id, "done")
    active = temp_registry.list_active()
    assert len(active) == 2


def test_count_active(temp_registry):
    """测试统计活动子 Agent"""
    session_key = "session:main:test"
    
    # 注册 5 个运行
    for i in range(5):
        run = SubagentRun(requester_session_key=session_key)
        temp_registry.register(run)
    
    count = temp_registry.count_active_for_session(session_key)
    assert count == 5
    
    # 完成 2 个
    runs = temp_registry.list_for_requester(session_key)
    temp_registry.mark_completed(runs[0].run_id, "done")
    temp_registry.mark_completed(runs[1].run_id, "done")
    
    count = temp_registry.count_active_for_session(session_key)
    assert count == 3


def test_persistence():
    """测试持久化到磁盘"""
    with tempfile.TemporaryDirectory() as tmpdir:
        state_dir = Path(tmpdir) / "subagent-state"
        
        # 创建 Registry 并注册
        registry1 = SubagentRegistry(state_dir=state_dir)
        run = SubagentRun(
            task="持久化测试",
            requester_session_key="session:main:test",
        )
        run_id = registry1.register(run)
        
        # 创建新 Registry（模拟重启）
        registry2 = SubagentRegistry(state_dir=state_dir)
        
        # 应该能恢复
        retrieved = registry2.get(run_id)
        assert retrieved is not None
        assert retrieved.task == "持久化测试"


def test_to_dict_from_dict():
    """测试序列化和反序列化"""
    run = SubagentRun(
        run_id="test-123",
        task="测试任务",
        requester_session_key="session:main:test",
        child_session_key="session:child:test-123",
        agent_id="test-agent",
        model="claude-sonnet-4.5",
        status=SubagentStatus.COMPLETED,
        started_at=datetime(2026, 3, 19, 10, 0, 0),
        completed_at=datetime(2026, 3, 19, 10, 5, 0),
        result_text="任务成功完成",
        tokens_used=1500,
        tool_calls=3,
    )
    
    # 序列化
    data = run.to_dict()
    assert data["run_id"] == "test-123"
    assert data["task"] == "测试任务"
    assert data["status"] == "completed"
    
    # 反序列化
    loaded = SubagentRun.from_dict(data)
    assert loaded.run_id == "test-123"
    assert loaded.task == "测试任务"
    assert loaded.status == SubagentStatus.COMPLETED
    assert loaded.tokens_used == 1500
