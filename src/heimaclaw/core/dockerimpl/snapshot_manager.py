"""
Snapshot Manager - 快照管理器

支持项目备份和恢复，防止数据丢失。
"""

import asyncio
import json
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class Snapshot:
    """快照信息"""
    project_name: str
    snapshot_id: str
    path: str
    size: int
    created_at: str
    description: str = ""


class SnapshotManager:
    """
    快照管理器
    
    支持创建项目快照、从快照恢复、列出快照。
    """
    
    def __init__(
        self,
        workspace: str = "/root/heimaclaw_workspace",
        keep_snapshots: int = 3,
    ):
        self.workspace = Path(workspace)
        self.snapshot_dir = self.workspace / ".projects" / ".snapshots"
        self.keep_snapshots = keep_snapshots
        
        # 确保快照目录存在
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)
    
    def create_snapshot(
        self,
        project_name: str,
        description: str = "",
    ) -> Snapshot:
        """
        创建项目快照
        
        Args:
            project_name: 项目名称
            description: 快照描述
            
        Returns:
            Snapshot 对象
        """
        project_dir = self.workspace / project_name
        
        if not project_dir.exists():
            raise FileNotFoundError(f"项目目录不存在: {project_dir}")
        
        # 创建快照目录
        project_snapshot_dir = self.snapshot_dir / project_name
        project_snapshot_dir.mkdir(parents=True, exist_ok=True)
        
        # 生成快照 ID 和文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        snapshot_id = f"{project_name}_{timestamp}"
        snapshot_path = project_snapshot_dir / f"{snapshot_id}.tar.gz"
        
        # 创建 tar.gz 快照
        result = subprocess.run(
            [
                "tar", "-czf", str(snapshot_path),
                "-C", str(project_dir.parent),
                project_name,
            ],
            capture_output=True,
            text=True,
        )
        
        if result.returncode != 0:
            raise RuntimeError(f"创建快照失败: {result.stderr}")
        
        # 获取快照大小
        size = snapshot_path.stat().st_size
        
        # 创建快照元数据
        snapshot = Snapshot(
            project_name=project_name,
            snapshot_id=snapshot_id,
            path=str(snapshot_path),
            size=size,
            created_at=datetime.now().isoformat(),
            description=description,
        )
        
        # 保存快照元数据
        self._save_snapshot_meta(snapshot)
        
        # 清理旧快照
        self._cleanup_old_snapshots(project_name)
        
        return snapshot
    
    def restore_snapshot(
        self,
        project_name: str,
        snapshot_path: str,
        force: bool = False,
    ) -> bool:
        """
        从快照恢复项目
        
        Args:
            project_name: 项目名称
            snapshot_path: 快照文件路径
            force: 是否强制覆盖现有项目
            
        Returns:
            是否恢复成功
        """
        snapshot_path = Path(snapshot_path)
        
        if not snapshot_path.exists():
            raise FileNotFoundError(f"快照文件不存在: {snapshot_path}")
        
        project_dir = self.workspace / project_name
        
        # 检查目标目录
        if project_dir.exists() and not force:
            raise RuntimeError(
                f"项目 {project_name} 已存在，"
                "请先删除或使用 force=True"
            )
        
        # 解压到临时目录
        temp_dir = Path(f"/tmp/restore_{project_name}_{asyncio.get_event_loop().time()}")
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            # 解压快照
            result = subprocess.run(
                ["tar", "-xzf", str(snapshot_path), "-C", str(temp_dir)],
                capture_output=True,
                text=True,
            )
            
            if result.returncode != 0:
                raise RuntimeError(f"解压快照失败: {result.stderr}")
            
            # 检查解压结果
            extracted_dir = temp_dir / project_name
            if not extracted_dir.exists():
                raise RuntimeError("快照内容结构不正确")
            
            # 备份现有项目（如果存在）
            backup_dir = None
            if project_dir.exists():
                backup_dir = Path(f"/tmp/backup_{project_name}_{asyncio.get_event_loop().time()}")
                shutil.move(str(project_dir), str(backup_dir))
            
            try:
                # 移动到目标位置
                shutil.move(str(extracted_dir), str(project_dir))
            except Exception as e:
                # 恢复备份
                if backup_dir and backup_dir.exists():
                    shutil.move(str(backup_dir), str(project_dir))
                raise RuntimeError(f"恢复项目失败: {e}")
            finally:
                # 清理备份
                if backup_dir and backup_dir.exists():
                    shutil.rmtree(backup_dir, ignore_errors=True)
            
            return True
        
        finally:
            # 清理临时目录
            shutil.rmtree(temp_dir, ignore_errors=True)
    
    def list_snapshots(self, project_name: str) -> list[Snapshot]:
        """
        列出项目的所有快照
        
        Args:
            project_name: 项目名称
            
        Returns:
            快照列表（按时间倒序）
        """
        project_snapshot_dir = self.snapshot_dir / project_name
        
        if not project_snapshot_dir.exists():
            return []
        
        snapshots = []
        meta_dir = project_snapshot_dir / ".meta"
        
        if meta_dir.exists():
            for meta_file in meta_dir.glob("*.json"):
                try:
                    meta = json.loads(meta_file.read_text())
                    snapshots.append(Snapshot(**meta))
                except Exception:
                    continue
        
        # 如果没有元数据，根据文件生成
        if not snapshots:
            for snapshot_file in project_snapshot_dir.glob("*.tar.gz"):
                stat = snapshot_file.stat()
                snapshot_id = snapshot_file.stem
                
                snapshots.append(Snapshot(
                    project_name=project_name,
                    snapshot_id=snapshot_id,
                    path=str(snapshot_file),
                    size=stat.st_size,
                    created_at=datetime.fromtimestamp(stat.st_mtime).isoformat(),
                ))
        
        # 按时间倒序
        snapshots.sort(key=lambda s: s.created_at, reverse=True)
        
        return snapshots
    
    def delete_snapshot(self, snapshot_path: str) -> bool:
        """
        删除指定快照
        
        Args:
            snapshot_path: 快照文件路径
            
        Returns:
            是否删除成功
        """
        path = Path(snapshot_path)
        
        if not path.exists():
            return False
        
        try:
            path.unlink()
            
            # 删除元数据
            meta_file = Path(str(path) + ".meta.json")
            if meta_file.exists():
                meta_file.unlink()
            
            return True
        
        except Exception:
            return False
    
    def _save_snapshot_meta(self, snapshot: Snapshot):
        """保存快照元数据"""
        project_snapshot_dir = self.snapshot_dir / snapshot.project_name
        meta_dir = project_snapshot_dir / ".meta"
        meta_dir.mkdir(parents=True, exist_ok=True)
        
        meta_file = meta_dir / f"{snapshot.snapshot_id}.json"
        meta_file.write_text(json.dumps({
            "project_name": snapshot.project_name,
            "snapshot_id": snapshot.snapshot_id,
            "path": snapshot.path,
            "size": snapshot.size,
            "created_at": snapshot.created_at,
            "description": snapshot.description,
        }, indent=2))
    
    def _cleanup_old_snapshots(self, project_name: str):
        """清理旧快照（保留最近的 N 个）"""
        snapshots = self.list_snapshots(project_name)
        
        if len(snapshots) <= self.keep_snapshots:
            return
        
        # 删除多余的快照
        for snapshot in snapshots[self.keep_snapshots:]:
            self.delete_snapshot(snapshot.path)
    
    def get_snapshot_stats(self) -> dict:
        """获取快照统计"""
        total_size = 0
        project_count = 0
        
        if self.snapshot_dir.exists():
            for project_dir in self.snapshot_dir.iterdir():
                if project_dir.is_dir() and project_dir.name != ".meta":
                    project_count += 1
                    
                    for snapshot_file in project_dir.glob("*.tar.gz"):
                        total_size += snapshot_file.stat().st_size
        
        return {
            "total_projects": project_count,
            "total_size": total_size,
            "total_size_mb": round(total_size / 1024 / 1024, 2),
            "snapshot_dir": str(self.snapshot_dir),
        }


# 全局实例
_snapshot_manager: Optional[SnapshotManager] = None


def get_snapshot_manager() -> SnapshotManager:
    """获取全局快照管理器实例"""
    global _snapshot_manager
    if _snapshot_manager is None:
        _snapshot_manager = SnapshotManager()
    return _snapshot_manager
