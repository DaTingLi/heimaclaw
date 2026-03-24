"""
Graceful Deletion - 软删除机制

提供项目软删除能力，支持 7 天冷静期和恢复。
"""

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional


@dataclass
class GracefulStatus:
    """软删除状态"""
    project_name: str
    marked_at: str
    reason: str
    will_be_deleted_at: str
    recovery_available: bool


class GracefulDeletion:
    """
    软删除管理器
    
    支持项目的软删除、恢复、彻底删除。
    提供 7 天冷静期防止误删。
    """
    
    GRACE_PERIOD_DAYS = 7
    
    def __init__(
        self,
        workspace: str = "/root/heimaclaw_workspace",
        snapshot_manager = None,
    ):
        self.workspace = Path(workspace)
        self.snapshot_manager = snapshot_manager
        
        # 待删除任务调度器
        self._deletion_tasks: dict[str, asyncio.Task] = {}
    
    def mark_for_deletion(
        self,
        project_name: str,
        reason: str = "用户请求删除",
    ) -> GracefulStatus:
        """
        标记项目为待删除（软删除）
        
        Args:
            project_name: 项目名称
            reason: 删除原因
            
        Returns:
            GracefulStatus 对象
        """
        meta = self._load_meta(project_name)
        
        if not meta:
            raise FileNotFoundError(f"项目不存在: {project_name}")
        
        now = datetime.now()
        delete_at = now + timedelta(days=self.GRACE_PERIOD_DAYS)
        
        # 更新元数据
        meta["graceful"] = {
            "markedAt": now.isoformat(),
            "reason": reason,
            "willBeDeletedAt": delete_at.isoformat(),
            "recoveryAvailable": True,
        }
        meta["container"]["status"] = "GRACEFUL"
        
        self._save_meta(project_name, meta)
        
        # 调度彻底删除任务
        self._schedule_deletion(project_name, delete_at)
        
        return GracefulStatus(
            project_name=project_name,
            marked_at=now.isoformat(),
            reason=reason,
            will_be_deleted_at=delete_at.isoformat(),
            recovery_available=True,
        )
    
    def recover(self, project_name: str) -> bool:
        """
        恢复已软删除的项目
        
        Args:
            project_name: 项目名称
            
        Returns:
            是否恢复成功
        """
        meta = self._load_meta(project_name)
        
        if not meta:
            return False
        
        graceful = meta.get("graceful", {})
        
        if not graceful.get("markedAt"):
            # 项目未被标记删除
            return False
        
        if not graceful.get("recoveryAvailable"):
            # 已超过恢复期限
            return False
        
        # 恢复状态
        meta["graceful"] = {
            "markedAt": None,
            "reason": None,
            "willBeDeletedAt": None,
            "recoveryAvailable": True,
        }
        meta["container"]["status"] = "STOPPED"
        
        self._save_meta(project_name, meta)
        
        # 取消删除任务
        self._cancel_deletion(project_name)
        
        return True
    
    def force_delete(self, project_name: str) -> bool:
        """
        立即彻底删除项目（跳过冷静期）
        
        Args:
            project_name: 项目名称
            
        Returns:
            是否删除成功
        """
        # 取消删除任务
        self._cancel_deletion(project_name)
        
        # 执行彻底删除
        return self._hard_delete(project_name)
    
    def get_status(self, project_name: str) -> Optional[GracefulStatus]:
        """
        获取项目的软删除状态
        
        Args:
            project_name: 项目名称
            
        Returns:
            GracefulStatus 或 None
        """
        meta = self._load_meta(project_name)
        
        if not meta:
            return None
        
        graceful = meta.get("graceful", {})
        
        if not graceful.get("markedAt"):
            return None
        
        return GracefulStatus(
            project_name=project_name,
            marked_at=graceful["markedAt"],
            reason=graceful.get("reason", ""),
            will_be_deleted_at=graceful.get("willBeDeletedAt", ""),
            recovery_available=graceful.get("recoveryAvailable", True),
        )
    
    def list_marked_for_deletion(self) -> list[GracefulStatus]:
        """
        列出所有待删除的项目
        
        Returns:
            待删除项目列表
        """
        meta_dir = self.workspace / ".projects"
        
        if not meta_dir.exists():
            return []
        
        marked = []
        
        for meta_path in meta_dir.rglob(".project_meta.json"):
            try:
                meta = json.loads(meta_path.read_text())
                graceful = meta.get("graceful", {})
                
                if graceful.get("markedAt"):
                    marked.append(GracefulStatus(
                        project_name=meta.get("name", ""),
                        marked_at=graceful["markedAt"],
                        reason=graceful.get("reason", ""),
                        will_be_deleted_at=graceful.get("willBeDeletedAt", ""),
                        recovery_available=graceful.get("recoveryAvailable", True),
                    ))
            
            except Exception:
                continue
        
        return marked
    
    def _schedule_deletion(self, project_name: str, delete_at: datetime):
        """调度删除任务"""
        # 取消已有的删除任务
        self._cancel_deletion(project_name)
        
        # 计算延迟（秒）
        delay = (delete_at - datetime.now()).total_seconds()
        
        if delay <= 0:
            # 立即删除
            asyncio.create_task(self._do_hard_delete(project_name))
        else:
            # 延迟删除
            loop = asyncio.get_event_loop()
            task = loop.create_task(self._delayed_delete(project_name, delay))
            self._deletion_tasks[project_name] = task
    
    async def _delayed_delete(self, project_name: str, delay: float):
        """延迟删除任务"""
        try:
            await asyncio.sleep(delay)
            await self._do_hard_delete(project_name)
        except asyncio.CancelledError:
            pass
        finally:
            self._deletion_tasks.pop(project_name, None)
    
    async def _do_hard_delete(self, project_name: str):
        """执行彻底删除"""
        try:
            self._hard_delete(project_name)
        except Exception:
            pass
    
    def _hard_delete(self, project_name: str) -> bool:
        """彻底删除项目"""
        project_dir = self.workspace / project_name
        
        # 1. 删除项目文件
        if project_dir.exists():
            import shutil
            shutil.rmtree(project_dir, ignore_errors=True)
        
        # 2. 删除元数据
        meta_dir = self.workspace / ".projects" / project_name
        if meta_dir.exists():
            import shutil
            shutil.rmtree(meta_dir, ignore_errors=True)
        
        # 3. 删除快照（如果有）
        if self.snapshot_manager:
            snapshots = self.snapshot_manager.list_snapshots(project_name)
            for snapshot in snapshots:
                self.snapshot_manager.delete_snapshot(snapshot.path)
        
        return True
    
    def _cancel_deletion(self, project_name: str):
        """取消删除任务"""
        task = self._deletion_tasks.pop(project_name, None)
        if task:
            task.cancel()
    
    def _load_meta(self, project_name: str) -> Optional[dict]:
        """加载项目元数据"""
        meta_path = self.workspace / ".projects" / project_name / ".project_meta.json"
        
        if not meta_path.exists():
            return None
        
        try:
            return json.loads(meta_path.read_text())
        except Exception:
            return None
    
    def _save_meta(self, project_name: str, meta: dict):
        """保存项目元数据"""
        meta_dir = self.workspace / ".projects" / project_name
        meta_dir.mkdir(parents=True, exist_ok=True)
        
        meta_path = meta_dir / ".project_meta.json"
        meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False))


# 全局实例
_graceful_deletion: Optional[GracefulDeletion] = None


def get_graceful_deletion() -> GracefulDeletion:
    """获取全局软删除管理器实例"""
    global _graceful_deletion
    if _graceful_deletion is None:
        _graceful_deletion = GracefulDeletion()
    return _graceful_deletion
