#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HeiMaClaw Event Bus + Subagent 验证脚本
"""

import sys
from pathlib import Path

def test_imports():
    """测试模块导入"""
    print("Testing module imports...")
    
    try:
        from heimaclaw.core import EventBus, Event, EventType, EventLevel
        print("  [OK] EventBus imported")
    except Exception as e:
        print(f"  [FAIL] EventBus import error: {e}")
        return False
    
    try:
        from heimaclaw.core import SubagentRegistry, SubagentRun, SubagentStatus
        print("  [OK] SubagentRegistry imported")
    except Exception as e:
        print(f"  [FAIL] SubagentRegistry import error: {e}")
        return False
    
    try:
        from heimaclaw.core import SubagentSpawner, SpawnConfig
        print("  [OK] SubagentSpawner imported")
    except Exception as e:
        print(f"  [FAIL] SubagentSpawner import error: {e}")
        return False
    
    return True


def test_event_bus_basic():
    """测试 Event Bus 基本功能"""
    print("\nTesting Event Bus basic operations...")
    
    import tempfile
    from heimaclaw.core import EventBus, Event, EventType, EventLevel
    
    with tempfile.TemporaryDirectory() as tmpdir:
        bus = EventBus(base_dir=Path(tmpdir) / "event-bus")
        
        # 测试发射事件
        event = Event(
            type=EventType.TASK_ASSIGNED,
            level=EventLevel.INFO,
            agent_id="test-agent",
            data={"task": "test task"},
        )
        
        try:
            import asyncio
            asyncio.run(bus.emit(event))
            print("  [OK] Event emitted successfully")
        except Exception as e:
            print(f"  [FAIL] Event emit error: {e}")
            return False
    
    return True


def test_subagent_registry():
    """测试 Subagent Registry 基本功能"""
    print("\nTesting Subagent Registry...")
    
    import tempfile
    from heimaclaw.core import SubagentRegistry, SubagentRun
    
    with tempfile.TemporaryDirectory() as tmpdir:
        registry = SubagentRegistry(state_dir=Path(tmpdir) / "subagent-state")
        
        # 测试注册
        run = SubagentRun(
            task="Test task",
            requester_session_key="session:test:123",
        )
        
        try:
            run_id = registry.register(run)
            retrieved = registry.get(run_id)
            
            if retrieved and retrieved.task == "Test task":
                print("  [OK] Subagent registered and retrieved")
                return True
            else:
                print("  [FAIL] Subagent registration failed")
                return False
        except Exception as e:
            print(f"  [FAIL] Registry error: {e}")
            return False


def main():
    """主测试函数"""
    print("=" * 60)
    print("HeiMaClaw Event Bus + Subagent Verification")
    print("=" * 60)
    
    results = []
    results.append(test_imports())
    results.append(test_event_bus_basic())
    results.append(test_subagent_registry())
    
    print("\n" + "=" * 60)
    if all(results):
        print("[SUCCESS] All tests passed!")
        print("\nEvent Bus + Subagent architecture integrated successfully!")
        print("\nNext steps:")
        print("  - View docs: cat docs/EVENT_BUS_SUBAGENT.md")
        print("  - Run examples: python -m heimaclaw.core.integration_example")
        print("  - Run tests: pytest tests/core/ -v")
        return 0
    else:
        print("[FAIL] Some tests failed")
        print("\nPlease check error messages and fix issues")
        return 1


if __name__ == "__main__":
    sys.exit(main())
