"""
Docker Backend 单元测试

使用 importlib 直接加载模块，避免 deepagents 依赖问题。
"""

import pytest
import sys
import importlib.util
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock


# 动态加载模块
def load_docker_backend_module():
    """动态加载 docker_backend 和 base_backend 模块"""
    src_path = Path("/root/dt/ai_coding/heimaclaw/src")
    
    # 加载 base_backend
    base_backend_spec = importlib.util.spec_from_file_location(
        "base_backend", 
        src_path / "heimaclaw/agent/base_backend.py"
    )
    base_backend_module = importlib.util.module_from_spec(base_backend_spec)
    sys.modules["heimaclaw.agent.base_backend"] = base_backend_module
    base_backend_spec.loader.exec_module(base_backend_module)
    
    # 加载 docker_backend
    docker_backend_spec = importlib.util.spec_from_file_location(
        "docker_backend",
        src_path / "heimaclaw/agent/docker_backend.py"
    )
    docker_backend_module = importlib.util.module_from_spec(docker_backend_spec)
    sys.modules["heimaclaw.agent.docker_backend"] = docker_backend_module
    docker_backend_spec.loader.exec_module(docker_backend_module)
    
    return base_backend_module, docker_backend_module


# 加载模块
base_backend, docker_backend = load_docker_backend_module()
ExecuteResponse = base_backend.ExecuteResponse
DockerBackend = docker_backend.DockerBackend


class TestExecuteResponse:
    """执行结果测试"""

    def test_execute_response_creation(self):
        """测试 ExecuteResponse 创建"""
        response = ExecuteResponse(
            output="Hello World",
            exit_code=0,
        )
        
        assert response.output == "Hello World"
        assert response.exit_code == 0
        assert response.error is None

    def test_execute_response_with_error(self):
        """测试带错误的 ExecuteResponse"""
        response = ExecuteResponse(
            output="",
            exit_code=1,
            error="Something went wrong",
        )
        
        assert response.output == ""
        assert response.exit_code == 1
        assert response.error == "Something went wrong"


class TestDockerBackendBasics:
    """DockerBackend 基础测试"""

    def test_backend_initialization(self):
        """测试后端初始化"""
        backend = DockerBackend(
            workspace="/tmp/test_workspace",
            max_containers=4,
        )
        
        assert backend.workspace.name == "test_workspace"
        assert backend._max_containers == 4
        assert backend._container_pool is None  # 延迟加载

    def test_backend_default_initialization(self):
        """测试后端默认初始化"""
        backend = DockerBackend()
        
        assert backend._max_containers == 4
        assert backend.workspace.name == "heimaclaw_workspace"


class TestExtractProjectName:
    """项目名提取测试"""

    def test_extract_from_cd_command(self):
        """测试从 cd 命令提取"""
        backend = DockerBackend()
        
        assert backend._extract_project_name("cd my_project && pip install flask") == "my_project"
        assert backend._extract_project_name("cd /root/heimaclaw_workspace/project-x") == "project-x"

    def test_extract_from_python_command(self):
        """测试从 python 命令提取"""
        backend = DockerBackend()
        
        # 包含项目路径的命令应该提取项目名
        result = backend._extract_project_name("python /root/heimaclaw_workspace/test/app.py")
        assert result == "test/app.py"

    def test_extract_ignores_scripts(self):
        """测试忽略常见脚本名"""
        backend = DockerBackend()
        
        # server, app, main, run 不应该被识别为项目名
        assert backend._extract_project_name("python server.py") is None
        assert backend._extract_project_name("python app.py") is None
        assert backend._extract_project_name("python main.py") is None
        assert backend._extract_project_name("python run.py") is None

    def test_extract_from_nohup_command(self):
        """测试从 nohup 命令提取"""
        backend = DockerBackend()
        
        result = backend._extract_project_name("nohup python myproject/server.py &")
        assert result is not None

    def test_extract_simple_path(self):
        """测试简单路径提取"""
        backend = DockerBackend()
        
        result = backend._extract_project_name("cd myproject && ls")
        assert result == "myproject"


class TestDockerBackendExecute:
    """DockerBackend 执行测试"""

    @pytest.mark.asyncio
    async def test_execute_without_project_name(self):
        """测试无项目名时返回错误"""
        backend = DockerBackend()
        
        response = await backend.execute("echo hello")
        
        assert response.exit_code == 1
        assert "无法提取项目名称" in response.error

    @pytest.mark.asyncio
    async def test_execute_with_project_name(self):
        """测试带项目名时正常执行"""
        backend = DockerBackend()
        
        # 模拟 _container_pool
        mock_container = AsyncMock()
        mock_container.execute.return_value = {
            "output": "Hello",
            "exit_code": 0,
        }
        backend._container_pool = Mock()
        backend._container_pool.get_container = AsyncMock(return_value=mock_container)
        
        response = await backend.execute(
            "echo hello",
            project_name="test_project",
        )
        
        assert response.exit_code == 0
        assert "Hello" in response.output


class TestDockerBackendService:
    """DockerBackend 服务管理测试"""

    @pytest.mark.asyncio
    async def test_start_service(self):
        """测试启动服务"""
        backend = DockerBackend()
        
        mock_container = AsyncMock()
        mock_container.host_ports = {5000: 5700}
        backend._container_pool = Mock()
        backend._container_pool.get_container = AsyncMock(return_value=mock_container)
        
        result = await backend.start_service(
            project_name="test_project",
            command="python server.py",
            port=5000,
        )
        
        assert result["success"] == True
        assert result["host_port"] == 5700
        assert "localhost:5700" in result["access_url"]

    @pytest.mark.asyncio
    async def test_stop_service(self):
        """测试停止服务"""
        backend = DockerBackend()
        
        backend._container_pool = Mock()
        backend._container_pool.destroy_container = AsyncMock(return_value=True)
        
        result = await backend.stop_service("test_project")
        
        assert result == True


class TestDockerBackendIntegration:
    """DockerBackend 集成测试（使用真实 container_pool）"""

    def test_backend_with_real_container_pool(self):
        """测试使用真实 container_pool 的后端"""
        backend = DockerBackend()
        
        # 访问 container_pool property 应该能正常工作
        pool = backend.container_pool
        
        # 应该返回一个 ContainerPool 实例
        assert pool is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
