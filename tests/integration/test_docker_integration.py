"""
Docker 集成测试

测试真实的 Docker 容器创建、执行、销毁流程。
需要 Docker 运行环境。
"""

import pytest
import asyncio
import tempfile
import time
from pathlib import Path


class TestDockerIntegration:
    """Docker 集成测试"""

    @pytest.fixture
    def workspace(self):
        """创建临时工作空间"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def container_pool(self, workspace):
        """创建容器池"""
        from heimaclaw.core.dockerimpl import ContainerPool
        
        pool = ContainerPool(
            workspace=str(workspace / ".projects"),
            max_containers=2,
            idle_timeout=60,
        )
        yield pool
        
        # 清理
        import subprocess
        stats = pool.get_stats()
        containers = stats.get("containers", {})
        for name in containers.keys():
            try:
                subprocess.run(
                    ["docker", "rm", "-f", f"heimaclaw-{name}"],
                    capture_output=True, timeout=10
                )
            except:
                pass

    @pytest.mark.asyncio
    async def test_create_and_execute(self, container_pool):
        """测试创建容器并执行命令"""
        container = await container_pool.get_container("test_simple")
        
        # 初始化容器（确保存在）
        await container.ensure()
        
        # 执行命令
        result = await container.execute("echo 'Hello from container'", timeout=60)
        
        assert result["exit_code"] == 0
        assert "Hello from container" in result["output"]

    @pytest.mark.asyncio
    async def test_python_execution(self, container_pool):
        """测试 Python 代码执行"""
        container = await container_pool.get_container("test_python")
        await container.ensure()
        
        result = await container.execute(
            "python3 -c 'print(1 + 2)'",
            timeout=60,
        )
        
        assert result["exit_code"] == 0
        assert "3" in result["output"]

    @pytest.mark.asyncio
    async def test_multiple_commands(self, container_pool):
        """测试多个命令顺序执行"""
        container = await container_pool.get_container("test_multi")
        await container.ensure()
        
        # 执行多个命令
        result1 = await container.execute("echo 'first'", timeout=30)
        result2 = await container.execute("echo 'second'", timeout=30)
        
        assert result1["exit_code"] == 0
        assert result2["exit_code"] == 0
        assert "first" in result1["output"]
        assert "second" in result2["output"]


class TestPortPoolIntegration:
    """端口池集成测试"""

    @pytest.fixture
    def port_pool(self):
        """创建端口池"""
        from heimaclaw.core.dockerimpl import PortPool
        
        with tempfile.TemporaryDirectory() as tmpdir:
            pool = PortPool(
                workspace=tmpdir,
                port_range=(5800, 5900),
            )
            yield pool

    def test_allocate_ports(self, port_pool):
        """测试端口分配"""
        # 分配两个不同容器端口
        port1 = port_pool.allocate("project1", container_port=5000)
        port2 = port_pool.allocate("project1", container_port=5001)
        
        # 同一项目的不同容器端口应该分配不同的宿主机端口
        assert port1 != port2

    def test_allocate_with_preferred_port(self, port_pool):
        """测试指定优先端口"""
        port = port_pool.allocate(
            "project1", 
            container_port=5000, 
            preferred_port=5850
        )
        
        # 应该使用指定的优先端口
        assert port == 5850

    def test_port_conflict_prevention(self, port_pool):
        """测试端口冲突预防"""
        port_pool.allocate("project1", container_port=5000, preferred_port=5850)
        
        # 同一宿主机端口再次分配应该失败
        with pytest.raises(RuntimeError):
            port_pool.allocate("project2", container_port=5001, preferred_port=5850)


class TestDependencyAnalyzer:
    """依赖分析器测试"""

    def test_analyze_requirements(self):
        """测试 requirements.txt 分析"""
        from heimaclaw.core.dockerimpl import DependencyAnalyzer
        
        analyzer = DependencyAnalyzer()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            req_file = Path(tmpdir) / "requirements.txt"
            req_file.write_text("flask==2.0.0\nrequests\n")
            
            deps = analyzer.analyze(str(req_file))
            
            assert deps is not None

    def test_analyze_no_requirements(self):
        """测试无 requirements.txt"""
        from heimaclaw.core.dockerimpl import DependencyAnalyzer
        
        analyzer = DependencyAnalyzer()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            deps = analyzer.analyze(str(Path(tmpdir) / "nonexistent.txt"))
            assert deps.has_requirements == False


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
