"""
Subagent Registry - 子 Agent 注册表

参考：
- OpenClaw subagent-registry.ts
- Kubernetes Pod 管理设计

功能：
- 跟踪所有子 Agent 的生命周期
- 管理父子 Agent 关系
- 支持查询和取消操作
- 事件持久化（崩溃恢复）
"""

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Optional
import uuid


class SubagentStatus(str, Enum):
    """子 Agent 状态"""

    PENDING = "pending"      # 等待启动
    RUNNING = "running"      # 运行中
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"        # 失败
    KILLED = "killed"        # 被杀死
    TIMEOUT = "timeout"      # 超时


@dataclass
class SubagentRun:
    """子 Agent 运行记录"""

    run_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    child_session_key: str = ""
    requester_session_key: str = ""  # 父 Agent 会话

    # 任务信息
    task: str = ""
    agent_id: Optional[str] = None
    model: Optional[str] = None

    # 状态
    status: SubagentStatus = SubagentStatus.PENDING
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # 结果
    result_text: Optional[str] = None
    error: Optional[str] = None

    # 配置
    mode: str = "run"  # "run" (一次性) 或 "session" (持久会话)
    sandbox: str = "inherit"  # "inherit" 或 "require"
    timeout_seconds: Optional[int] = None

    # 统计
    tokens_used: int = 0
    tool_calls: int = 0

    # 类常量（兼容性）
    STATUS_PENDING = SubagentStatus.PENDING
    STATUS_RUNNING = SubagentStatus.RUNNING
    STATUS_COMPLETED = SubagentStatus.COMPLETED
    STATUS_FAILED = SubagentStatus.FAILED
    STATUS_KILLED = SubagentStatus.KILLED
    STATUS_TIMEOUT = SubagentStatus.TIMEOUT

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "run_id": self.run_id,
            "child_session_key": self.child_session_key,
            "requester_session_key": self.requester_session_key,
            "task": self.task,
            "agent_id": self.agent_id,
            "model": self.model,
            "status": self.status.value,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "result_text": self.result_text,
            "error": self.error,
            "mode": self.mode,
            "sandbox": self.sandbox,
            "timeout_seconds": self.timeout_seconds,
            "tokens_used": self.tokens_used,
            "tool_calls": self.tool_calls,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SubagentRun":
        """从字典创建"""
        return cls(
            run_id=data.get("run_id", str(uuid.uuid4())[:8]),
            child_session_key=data.get("child_session_key", ""),
            requester_session_key=data.get("requester_session_key", ""),
            task=data.get("task", ""),
            agent_id=data.get("agent_id"),
            model=data.get("model"),
            status=SubagentStatus(data.get("status", "pending")),
            started_at=datetime.fromisoformat(data["started_at"]) if data.get("started_at") else None,
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
            result_text=data.get("result_text"),
            error=data.get("error"),
            mode=data.get("mode", "run"),
            sandbox=data.get("sandbox", "inherit"),
            timeout_seconds=data.get("timeout_seconds"),
            tokens_used=data.get("tokens_used", 0),
            tool_calls=data.get("tool_calls", 0),
        )


class SubagentRegistry:
    """
    子 Agent 注册表
    
    全局管理所有子 Agent 的生命周期。
    """

    def __init__(self, state_dir: Path | str = ".openclaw/subagent-state"):
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)

        self.state_file = self.state_dir / "registry.json"

        # 运行时注册表
        self._runs: dict[str, SubagentRun] = {}

        # 从磁盘恢复
        self._restore_from_disk()

    def _restore_from_disk(self):
        """从磁盘恢复注册表"""
        if not self.state_file.exists():
            return

        try:
            with open(self.state_file) as f:
                data = json.load(f)

            for run_id, run_data in data.get("runs", {}).items():
                run = SubagentRun.from_dict(run_data)
                # 只恢复未完成的运行
                if run.status in {SubagentStatus.PENDING, SubagentStatus.RUNNING}:
                    self._runs[run_id] = run

        except (json.JSONDecodeError, KeyError):
            pass

    def _persist_to_disk(self):
        """持久化到磁盘"""
        data = {
            "runs": {
                run_id: run.to_dict()
                for run_id, run in self._runs.items()
            }
        }

        with open(self.state_file, "w") as f:
            json.dump(data, f, indent=2)

    def register(self, run: SubagentRun) -> str:
        """
        注册子 Agent
        
        Returns:
            run_id
        """
        self._runs[run.run_id] = run
        self._persist_to_disk()
        return run.run_id

    def get(self, run_id: str) -> Optional[SubagentRun]:
        """获取子 Agent 记录"""
        return self._runs.get(run_id)

    def update(self, run_id: str, **kwargs):
        """更新子 Agent 状态"""
        if run_id not in self._runs:
            return

        run = self._runs[run_id]

        for key, value in kwargs.items():
            if hasattr(run, key):
                setattr(run, key, value)

        self._persist_to_disk()

    def list_for_requester(self, requester_session_key: str) -> list[SubagentRun]:
        """列出某个父 Agent 的所有子 Agent"""
        return [
            run for run in self._runs.values()
            if run.requester_session_key == requester_session_key
        ]

    def list_active(self) -> list[SubagentRun]:
        """列出所有活动的子 Agent"""
        return [
            run for run in self._runs.values()
            if run.status in {SubagentStatus.PENDING, SubagentStatus.RUNNING}
        ]

    def count_active_for_session(self, session_key: str) -> int:
        """统计某个会话的活动子 Agent 数量"""
        return len([
            run for run in self._runs.values()
            if run.requester_session_key == session_key
            and run.status in {SubagentStatus.PENDING, SubagentStatus.RUNNING}
        ])

    def mark_started(self, run_id: str):
        """标记为已启动"""
        self.update(run_id, status=SubagentStatus.RUNNING, started_at=datetime.now())

    def mark_completed(self, run_id: str, result_text: str):
        """标记为已完成"""
        self.update(
            run_id,
            status=SubagentStatus.COMPLETED,
            completed_at=datetime.now(),
            result_text=result_text,
        )

    def mark_failed(self, run_id: str, error: str):
        """标记为失败"""
        self.update(
            run_id,
            status=SubagentStatus.FAILED,
            completed_at=datetime.now(),
            error=error,
        )

    def mark_killed(self, run_id: str):
        """标记为被杀死"""
        self.update(
            run_id,
            status=SubagentStatus.KILLED,
            completed_at=datetime.now(),
        )

    def cleanup_old_runs(self, max_age_hours: int = 24):
        """
        清理旧记录
        
        Args:
            max_age_hours: 最大保留时长（小时）
        """
        cutoff = datetime.now() - timedelta(hours=max_age_hours)

        to_delete = [
            run_id for run_id, run in self._runs.items()
            if run.completed_at and run.completed_at < cutoff
        ]

        for run_id in to_delete:
            del self._runs[run_id]

        if to_delete:
            self._persist_to_disk()
