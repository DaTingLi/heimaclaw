"""
Container Pool 单元测试

测试容器池的创建、获取、销毁功能。
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock


class TestContainerPoolBasics:
    """容器池基础测试"""

    @pytest.fixture
    def container_pool(self):
        """创建测试用容器池"""
        from heimaclaw.core.dockerimpl import ContainerPool
        
        pool = ContainerPool(
            workspace="/tmp/test_heimaclaw_workspace",
            max_containers=2,
            idle_timeout=60,
        )
        return pool

    def test_initialization(self, container_pool):
        """测试容器池初始化"""
        assert container_pool.max_containers == 2
        assert container_pool.idle_timeout == 60

    def test_workspace_property(self, container_pool):
        """测试工作区属性"""
        assert "test_heimaclaw_workspace" in str(container_pool.workspace)

    def test_get_stats(self, container_pool):
        """测试统计信息"""
        stats = container_pool.get_stats()
        
        assert stats["total"] == 0
        assert stats["max"] == 2
        assert stats["idle_timeout_seconds"] == 60
        assert isinstance(stats["by_status"], dict)
        assert isinstance(stats["containers"], dict)


class TestContainerStatus:
    """容器状态枚举测试"""

    def test_all_statuses_defined(self):
        """测试所有状态都定义"""
        from heimaclaw.core.dockerimpl import ContainerStatus
        
        expected_statuses = [
            "NONE", "CREATING", "RUNNING", "IDLE", 
            "STOPPED", "GRACEFUL", "DESTROYED", "ERROR"
        ]
        
        for status_name in expected_statuses:
            assert hasattr(ContainerStatus, status_name)
            assert ContainerStatus[status_name].value == status_name

    def test_status_count(self):
        """测试状态数量"""
        from heimaclaw.core.dockerimpl import ContainerStatus
        
        statuses = list(ContainerStatus)
        assert len(statuses) == 8


class TestContainerConfig:
    """容器配置测试"""

    def test_default_config(self):
        """测试默认配置"""
        from heimaclaw.core.dockerimpl import ContainerConfig
        
        config = ContainerConfig(project_name="test_project")
        
        assert config.project_name == "test_project"
        assert config.image == "python:3.10-slim"
        assert config.cpu_limit == 1.0
        assert config.memory_limit == "1g"
        assert config.network_mode == "host"

    def test_custom_config(self):
        """测试自定义配置"""
        from heimaclaw.core.dockerimpl import ContainerConfig
        
        config = ContainerConfig(
            project_name="my_project",
            image="python:3.12-slim",
            cpu_limit=2.0,
            memory_limit="2g",
            network_mode="bridge",
            exposed_ports=[5000, 5001],
        )
        
        assert config.project_name == "my_project"
        assert config.image == "python:3.12-slim"
        assert config.cpu_limit == 2.0
        assert config.memory_limit == "2g"
        assert config.network_mode == "bridge"
        assert config.exposed_ports == [5000, 5001]


class TestProjectContainerBasics:
    """项目容器基础测试"""

    def test_project_container_creation(self):
        """测试项目容器创建"""
        from heimaclaw.core.dockerimpl import (
            ProjectContainer, 
            ContainerConfig,
            ContainerStatus,
        )
        
        config = ContainerConfig(project_name="test")
        
        container = ProjectContainer(
            config=config,
            port_pool=Mock(),
            dependency_analyzer=Mock(),
            snapshot_manager=Mock(),
        )
        
        assert container.config == config
        assert container.status == ContainerStatus.NONE
        assert container.container_id is None
        assert isinstance(container.host_ports, dict)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
