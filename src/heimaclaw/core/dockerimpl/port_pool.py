"""
Port Pool - 端口池管理器

负责 Docker 容器端口到宿主机端口的动态映射管理。
"""

import asyncio
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class PortMapping:
    """端口映射"""
    container_port: int
    host_port: int
    protocol: str = "tcp"


class PortPool:
    """
    端口池管理器
    
    负责端口的分配、释放、冲突检测。
    一个项目可以有多个端口映射。
    """
    
    def __init__(
        self,
        workspace: str = "/root/heimaclaw_workspace",
        port_range: tuple[int, int] = (5000, 6000),
    ):
        self.workspace = Path(workspace)
        self.port_range = range(port_range[0], port_range[1])
        
        # 项目端口分配记录: project_name -> {container_port: host_port}
        self._allocations: dict[str, dict[int, int]] = {}
        
        # 已预留的宿主机端口
        self._reserved: set[int] = set()
        
        # 加载已有分配
        self._load_allocations()
    
    def _load_allocations(self):
        """从元数据目录加载已有端口分配"""
        meta_dir = self.workspace / ".projects"
        
        if not meta_dir.exists():
            return
        
        for meta_path in meta_dir.rglob(".project_meta.json"):
            try:
                import json
                meta = json.loads(meta_path.read_text())
                
                project_name = meta.get("name")
                if not project_name:
                    continue
                
                host_ports = meta.get("container", {}).get("hostPorts", {})
                
                allocations = {}
                for container_port_str, host_port in host_ports.items():
                    container_port = int(container_port_str)
                    allocations[container_port] = host_port
                    self._reserved.add(host_port)
                
                if allocations:
                    self._allocations[project_name] = allocations
            
            except Exception:
                continue
    
    def _is_port_in_use(self, port: int) -> bool:
        """检测宿主机端口是否被占用"""
        # 检查我们记录的
        if port in self._reserved:
            return True
        
        # 检查系统端口
        result = subprocess.run(
            f"ss -tlnp | grep ':{port}'",
            shell=True,
            capture_output=True,
            text=True,
        )
        return result.returncode == 0
    
    def _find_available_port(self, preferred: int = None) -> int:
        """查找可用端口"""
        # 如果有首选端口且可用，直接使用
        if preferred and preferred not in self._reserved:
            if not self._is_port_in_use(preferred):
                return preferred
        
        # 扫描可用端口
        for port in self.port_range:
            if port in self._reserved:
                continue
            if self._is_port_in_use(port):
                self._reserved.add(port)  # 标记为已占用
                continue
            return port
        
        raise RuntimeError(f"无可用端口 (range: {self.port_range.start}-{self.port_range.stop-1})")
    
    def allocate(
        self,
        project_name: str,
        container_port: int = 5000,
        preferred_port: int = None,
    ) -> int:
        """
        为项目分配宿主机端口
        
        Args:
            project_name: 项目名称
            container_port: 容器内部端口
            preferred_port: 优先使用的宿主机端口（用户指定）
            
        Returns:
            分配的宿主机端口
        """
        # 如果项目已有此容器端口的映射，直接返回
        if project_name in self._allocations:
            if container_port in self._allocations[project_name]:
                return self._allocations[project_name][container_port]
        
        # 如果指定了优先端口，尝试使用
        if preferred_port:
            if preferred_port in self._reserved:
                raise RuntimeError(f"端口 {preferred_port} 已被占用，请选择其他端口")
            if self._is_port_in_use(preferred_port):
                raise RuntimeError(f"端口 {preferred_port} 已被系统占用，请选择其他端口")
            host_port = preferred_port
        else:
            # 分配新端口
            host_port = self._find_available_port(container_port)
        
        # 记录分配
        if project_name not in self._allocations:
            self._allocations[project_name] = {}
        
        self._allocations[project_name][container_port] = host_port
        self._reserved.add(host_port)
        
        # 持久化
        self._save_project_ports(project_name)
        
        return host_port
    
    def release(self, project_name: str):
        """
        释放项目的所有端口
        
        Args:
            project_name: 项目名称
        """
        if project_name not in self._allocations:
            return
        
        for host_port in self._allocations[project_name].values():
            self._reserved.discard(host_port)
        
        del self._allocations[project_name]
    
    def get_mapping(self, project_name: str) -> dict[int, int]:
        """
        获取项目的所有端口映射
        
        Returns:
            {container_port: host_port}
        """
        return self._allocations.get(project_name, {}).copy()
    
    def get_allocation(self, project_name: str, container_port: int = 5000) -> Optional[int]:
        """
        获取项目的指定端口映射
        
        Args:
            project_name: 项目名称
            container_port: 容器内部端口
            
        Returns:
            宿主机端口，如果不存在则返回 None
        """
        return self._allocations.get(project_name, {}).get(container_port)
    
    def _save_project_ports(self, project_name: str):
        """保存项目端口到元数据"""
        meta_dir = self.workspace / ".projects" / project_name
        meta_path = meta_dir / ".project_meta.json"
        
        if not meta_path.exists():
            return
        
        try:
            import json
            meta = json.loads(meta_path.read_text())
            
            host_ports = {
                str(cp): hp
                for cp, hp in self._allocations.get(project_name, {}).items()
            }
            
            if "container" not in meta:
                meta["container"] = {}
            meta["container"]["hostPorts"] = host_ports
            
            meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False))
        except Exception:
            pass
    
    def get_stats(self) -> dict:
        """获取端口池统计"""
        total_allocated = sum(
            len(ports) for ports in self._allocations.values()
        )
        
        return {
            "total_allocated": total_allocated,
            "total_reserved": len(self._reserved),
            "available": len(self.port_range) - len(self._reserved),
            "range": f"{self.port_range.start}-{self.port_range.stop - 1}",
            "projects": {
                name: {str(cp): hp for cp, hp in ports.items()}
                for name, ports in self._allocations.items()
            }
        }


# 全局单例
_port_pool: Optional[PortPool] = None


def get_port_pool() -> PortPool:
    """获取全局端口池实例"""
    global _port_pool
    if _port_pool is None:
        _port_pool = PortPool()
    return _port_pool
