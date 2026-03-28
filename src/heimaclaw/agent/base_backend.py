"""
Base Backend - 基础执行后端接口

定义所有后端必须实现的接口。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class ExecuteResponse:
    """执行结果"""
    output: str
    exit_code: int
    error: str = None


@dataclass
class ServiceInfo:
    """服务信息"""
    project_name: str
    host_port: int
    container_port: int
    status: str
    access_url: str


class BaseBackend(ABC):
    """
    基础执行后端抽象类
    
    所有后端（Docker、Firecracker、Process）必须实现此接口。
    """
    
    @abstractmethod
    async def execute(
        self,
        command: str,
        project_name: str = None,
        timeout: int = None,
        is_background: bool = False,
    ) -> ExecuteResponse:
        """
        执行命令
        
        Args:
            command: 要执行的命令
            project_name: 项目名称
            timeout: 超时时间（秒）
            is_background: 是否后台执行
            
        Returns:
            ExecuteResponse
        """
        ...
    
    @abstractmethod
    async def start_service(
        self,
        project_name: str,
        command: str,
        port: int = 5000,
    ) -> dict:
        """
        启动项目服务
        
        Args:
            project_name: 项目名称
            command: 启动命令
            port: 容器端口
            
        Returns:
            {"success": bool, "host_port": int, "access_url": str}
        """
        ...
    
    @abstractmethod
    async def stop_service(self, project_name: str) -> bool:
        """
        停止项目服务
        
        Args:
            project_name: 项目名称
            
        Returns:
            是否成功
        """
        ...
    
    @abstractmethod
    async def get_service_status(self, project_name: str) -> dict:
        """
        获取服务状态
        
        Args:
            project_name: 项目名称
            
        Returns:
            状态信息
        """
        ...
    
    def get_stats(self) -> dict:
        """
        获取后端统计信息
        
        Returns:
            统计信息字典
        """
        return {}
