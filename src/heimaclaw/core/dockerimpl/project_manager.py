"""
Project Manager - 项目管理器

统一的查询和管理接口。
"""

import asyncio
import json
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from .container_pool import ContainerPool, ContainerStatus
from .graceful_deletion import GracefulDeletion, GracefulStatus
from .snapshot_manager import SnapshotManager, Snapshot


@dataclass
class ProjectInfo:
    """项目信息"""
    name: str
    status: str
    created_at: Optional[str] = None
    last_accessed: Optional[str] = None
    container_id: Optional[str] = None
    image: Optional[str] = None
    ports: dict = None
    frameworks: list = None
    graceful: dict = None


@dataclass
class OperationLog:
    """操作日志"""
    action: str
    timestamp: str
    details: str = ""


class ProjectManager:
    """
    项目管理器
    
    统一的查询和管理接口。
    """
    
    def __init__(
        self,
        workspace: str = "/root/heimaclaw_workspace",
        container_pool: ContainerPool = None,
    ):
        self.workspace = Path(workspace)
        self.meta_dir = self.workspace / ".projects"
        
        # 初始化容器池
        if container_pool is None:
            from .container_pool import get_container_pool
            container_pool = get_container_pool()
        self.container_pool = container_pool
        
        # 初始化其他管理器
        from .graceful_deletion import get_graceful_deletion
        from .snapshot_manager import get_snapshot_manager
        
        self.graceful_deletion = get_graceful_deletion()
        self.snapshot_manager = get_snapshot_manager()
        
        # 确保元数据目录存在
        self.meta_dir.mkdir(parents=True, exist_ok=True)
    
    # ==================== 查询接口 ====================
    
    def list_projects(
        self,
        status: str = None,
        include_graceful: bool = True,
    ) -> list[ProjectInfo]:
        """
        列出所有项目（可按状态过滤）
        
        Args:
            status: 状态过滤（RUNNING|IDLE|STOPPED|GRACEFUL|DESTROYED）
            include_graceful: 是否包含软删除项目
            
        Returns:
            项目列表
        """
        projects = []
        
        if not self.meta_dir.exists():
            return projects
        
        for meta_path in self.meta_dir.rglob(".project_meta.json"):
            try:
                meta = json.loads(meta_path.read_text())
                
                project_status = meta.get("container", {}).get("status", "UNKNOWN")
                
                # 状态过滤
                if status and project_status != status:
                    continue
                
                # 跳过已删除
                if not include_graceful and project_status == "GRACEFUL":
                    continue
                
                projects.append(ProjectInfo(
                    name=meta.get("name", ""),
                    status=project_status,
                    created_at=meta.get("created_at"),
                    last_accessed=meta.get("lastAccessed"),
                    container_id=meta.get("container", {}).get("containerId"),
                    image=meta.get("container", {}).get("image"),
                    ports=meta.get("container", {}).get("hostPorts", {}),
                    frameworks=meta.get("dependencies", {}).get("frameworks", []),
                    graceful=meta.get("graceful"),
                ))
            
            except Exception:
                continue
        
        # 按最后访问时间排序
        projects.sort(
            key=lambda p: p.last_accessed or "",
            reverse=True,
        )
        
        return projects
    
    def get_project(self, project_name: str) -> Optional[ProjectInfo]:
        """
        获取项目详细信息
        
        Args:
            project_name: 项目名称
            
        Returns:
            ProjectInfo 或 None
        """
        meta = self._load_meta(project_name)
        
        if not meta:
            return None
        
        return ProjectInfo(
            name=meta.get("name", ""),
            status=meta.get("container", {}).get("status", "UNKNOWN"),
            created_at=meta.get("created_at"),
            last_accessed=meta.get("lastAccessed"),
            container_id=meta.get("container", {}).get("containerId"),
            image=meta.get("container", {}).get("image"),
            ports=meta.get("container", {}).get("hostPorts", {}),
            frameworks=meta.get("dependencies", {}).get("frameworks", []),
            graceful=meta.get("graceful"),
        )
    
    def get_project_status(self, project_name: str) -> str:
        """
        获取项目状态（快速查询）
        
        Args:
            project_name: 项目名称
            
        Returns:
            状态字符串
        """
        meta = self._load_meta(project_name)
        
        if not meta:
            return "NOT_FOUND"
        
        return meta.get("container", {}).get("status", "UNKNOWN")
    
    def get_container_logs(
        self,
        project_name: str,
        lines: int = 100,
    ) -> str:
        """
        获取容器日志
        
        Args:
            project_name: 项目名称
            lines: 日志行数
            
        Returns:
            日志内容
        """
        meta = self._load_meta(project_name)
        
        if not meta:
            return "项目不存在"
        
        container_id = meta.get("container", {}).get("containerId")
        
        if not container_id:
            return "容器不存在或未创建"
        
        result = subprocess.run(
            ["docker", "logs", "--tail", str(lines), container_id],
            capture_output=True,
            text=True,
        )
        
        return result.stdout + result.stderr
    
    def get_project_files(self, project_name: str) -> Optional[str]:
        """
        获取项目文件结构
        
        Args:
            project_name: 项目名称
            
        Returns:
            文件树字符串
        """
        project_dir = self.workspace / project_name
        
        if not project_dir.exists():
            return None
        
        result = subprocess.run(
            ["tree", "-L", "3", "--noreport", str(project_dir)],
            capture_output=True,
            text=True,
        )
        
        if result.returncode != 0:
            # tree 命令不可用，使用 ls
            result = subprocess.run(
                ["find", str(project_dir), "-maxdepth", "3", "-type", "f"],
                capture_output=True,
                text=True,
            )
            return result.stdout
        
        return result.stdout
    
    def get_operation_logs(self, project_name: str) -> list[OperationLog]:
        """
        获取项目操作日志
        
        Args:
            project_name: 项目名称
            
        Returns:
            操作日志列表
        """
        meta = self._load_meta(project_name)
        
        if not meta:
            return []
        
        return [
            OperationLog(**op)
            for op in meta.get("operations", [])
        ]
    
    # ==================== 管理接口 ====================
    
    def create_project(
        self,
        project_name: str,
        description: str = "",
    ) -> ProjectInfo:
        """
        创建项目记录
        
        Args:
            project_name: 项目名称
            description: 项目描述
            
        Returns:
            ProjectInfo
        """
        meta = {
            "name": project_name,
            "created_at": datetime.now().isoformat(),
            "lastAccessed": datetime.now().isoformat(),
            "container": {
                "status": "NONE",
                "hostPorts": {},
            },
            "dependencies": {
                "frameworks": [],
                "requirements": [],
            },
            "operations": [
                {
                    "action": "create",
                    "timestamp": datetime.now().isoformat(),
                    "details": description,
                }
            ],
            "graceful": {
                "markedAt": None,
                "reason": None,
                "recoveryAvailable": True,
            },
        }
        
        self._save_meta(project_name, meta)
        
        return ProjectInfo(
            name=project_name,
            status="NONE",
            created_at=meta["created_at"],
            last_accessed=meta["lastAccessed"],
        )
    
    async def start_project(self, project_name: str) -> bool:
        """
        启动项目
        
        Args:
            project_name: 项目名称
            
        Returns:
            是否成功
        """
        # 检查软删除状态
        graceful_status = self.graceful_deletion.get_status(project_name)
        
        if graceful_status:
            # 从软删除恢复
            await self.recover_project(project_name)
        
        # 获取或创建容器
        container = await self.container_pool.get_container(project_name)
        await container.ensure()
        
        # 更新元数据
        meta = self._load_meta(project_name)
        meta["container"]["status"] = "RUNNING"
        meta["lastAccessed"] = datetime.now().isoformat()
        meta["operations"].append({
            "action": "start",
            "timestamp": datetime.now().isoformat(),
            "details": "项目启动",
        })
        self._save_meta(project_name, meta)
        
        return True
    
    async def stop_project(self, project_name: str) -> bool:
        """
        停止项目
        
        Args:
            project_name: 项目名称
            
        Returns:
            是否成功
        """
        if project_name in self.container_pool._containers:
            container = self.container_pool._containers[project_name]
            await container._stop()
        
        # 更新元数据
        meta = self._load_meta(project_name)
        meta["container"]["status"] = "STOPPED"
        meta["operations"].append({
            "action": "stop",
            "timestamp": datetime.now().isoformat(),
            "details": "项目停止",
        })
        self._save_meta(project_name, meta)
        
        return True
    
    def delete_project(
        self,
        project_name: str,
        force: bool = False,
        reason: str = "用户请求删除",
    ) -> dict:
        """
        删除项目（软删除或硬删除）
        
        Args:
            project_name: 项目名称
            force: 是否强制删除（跳过冷静期）
            reason: 删除原因
            
        Returns:
            {"success": bool, "message": str, "graceful_status": GracefulStatus}
        """
        meta = self._load_meta(project_name)
        
        if not meta:
            return {"success": False, "message": "项目不存在"}
        
        if force:
            # 硬删除
            self.graceful_deletion.force_delete(project_name)
            return {"success": True, "message": "项目已彻底删除"}
        
        # 软删除
        status = self.graceful_deletion.mark_for_deletion(project_name, reason)
        
        return {
            "success": True,
            "message": f"项目已标记为待删除，将于 7 天后自动彻底删除",
            "graceful_status": status,
        }
    
    async def recover_project(self, project_name: str) -> bool:
        """
        恢复已删除项目
        
        Args:
            project_name: 项目名称
            
        Returns:
            是否成功
        """
        success = self.graceful_deletion.recover(project_name)
        
        if success:
            # 更新元数据
            meta = self._load_meta(project_name)
            meta["operations"].append({
                "action": "recover",
                "timestamp": datetime.now().isoformat(),
                "details": "从软删除恢复",
            })
            self._save_meta(project_name, meta)
        
        return success
    
    async def rebuild_project(
        self,
        project_name: str,
    ) -> bool:
        """
        重建项目（重新构建镜像）
        
        Args:
            project_name: 项目名称
            
        Returns:
            是否成功
        """
        # 1. 停止现有容器
        await self.stop_project(project_name)
        
        # 2. 删除旧容器
        await self.container_pool.destroy_container(project_name)
        
        # 3. 重新获取容器（会重新创建）
        container = await self.container_pool.get_container(project_name)
        
        # 4. 更新元数据
        meta = self._load_meta(project_name)
        meta["operations"].append({
            "action": "rebuild",
            "timestamp": datetime.now().isoformat(),
            "details": "重建容器镜像",
        })
        self._save_meta(project_name, meta)
        
        return True
    
    # ==================== 辅助方法 ====================
    
    def _load_meta(self, project_name: str) -> Optional[dict]:
        """加载项目元数据"""
        meta_path = self.meta_dir / project_name / ".project_meta.json"
        
        if not meta_path.exists():
            return None
        
        try:
            return json.loads(meta_path.read_text())
        except Exception:
            return None
    
    def _save_meta(self, project_name: str, meta: dict):
        """保存项目元数据"""
        meta_dir = self.meta_dir / project_name
        meta_dir.mkdir(parents=True, exist_ok=True)
        
        meta_path = meta_dir / ".project_meta.json"
        meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False))


# 全局实例
_project_manager: Optional[ProjectManager] = None


def get_project_manager() -> ProjectManager:
    """获取全局项目管理器实例"""
    global _project_manager
    if _project_manager is None:
        _project_manager = ProjectManager()
    return _project_manager
