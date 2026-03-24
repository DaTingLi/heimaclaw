# HeiMaClaw Docker 沙箱架构 v1.0

> **版本**: v1.0  
> **创建**: 2026-03-24  
> **状态**: 待实现

---

## 一、设计背景

### 1.1 Firecracker 的局限性

| 维度 | Firecracker | Docker |
|------|-------------|--------|
| **环境完整性** | ❌ Alpine Linux，基础工具 | ✅ 完整 Linux 环境 |
| **Python 依赖** | ❌ 需手动安装 | ✅ 可预装或 Dockerfile |
| **Web 服务** | ❌ 端口隔离，无法外部访问 | ✅ 端口映射 |
| **持久运行** | ⚠️ 超时限制 | ✅ 可以一直运行 |
| **资源隔离** | ✅ 轻量级 | ✅ 适中 |
| **镜像构建** | ❌ 每次全新 | ✅ 复用镜像层 |

### 1.2 设计目标

```
每个 Agent 项目 = 独立 Docker 容器
         ↓
容器内有完整的 Python 环境
         ↓
服务运行在容器内，端口映射到 Host
         ↓
既有隔离，又有完整功能
```

---

## 二、架构设计

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                    HeiMaClaw Docker 架构                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐     ┌──────────────────────────────────────┐  │
│  │  Host       │     │  Docker Container                    │  │
│  │  (Ubuntu)   │     │  (项目级隔离)                        │  │
│  │              │     │                                      │  │
│  │  ┌────────┐ │     │  ┌────────────────────────────────┐  │  │
│  │  │ Agent  │ │────►│  │ Python + Flask + SQLite        │  │  │
│  │  │推理进程 │ │     │  │ /root/heimaclaw_workspace/     │  │  │
│  │  └────────┘ │     │  │ <project_name>/                 │  │  │
│  │      │        │     │  └────────────────────────────────┘  │  │
│  │      │        │     │           ▲                          │  │
│  │      │        │     │           │                          │  │
│  │      ▼        │     │  ┌───────┴────────┐                │  │
│  │  ┌────────┐  │     │  │ Project Volume │                │  │
│  │  │ 端口   │◄─┼────►│  │ /workspace    │                │  │
│  │  │ 映射   │  │     │  └───────────────┘                │  │
│  │  └────────┘  │     │                                      │  │
│  └──────────────┘     └──────────────────────────────────────┘  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 组件职责

| 组件 | 职责 |
|------|------|
| **HostExecutor** | 在宿主机执行部署命令，容器管理 |
| **DockerBackend** | Docker 容器生命周期管理 |
| **ContainerManager** | 容器创建/启动/停止/删除 |
| **PortMapper** | 容器端口到宿主机端口的映射 |
| **VolumeManager** | 项目目录与容器卷的挂载 |

---

## 三、核心组件设计

### 3.1 DockerBackend

```python
class DockerBackend:
    """
    Docker 沙箱后端
    
    为每个项目创建独立的 Docker 容器，
    容器内有完整的 Python 环境和依赖。
    """
    
    def __init__(
        self,
        image: str = "python:3.10-slim",
        workspace: str = "/root/heimaclaw_workspace",
    ):
        self.image = image
        self.workspace = Path(workspace)
        self.dockerfile_path = Path("/root/dt/ai_coding/heimaclaw/docker")
        
        # 每个项目的容器
        self._containers: dict[str, str] = {}  # project_name -> container_id
    
    async def execute(
        self,
        command: str,
        project_name: str,
        timeout: int = None,
    ) -> ExecuteResponse:
        """
        在项目的 Docker 容器中执行命令
        """
        # 1. 确保容器运行
        container_id = await self._ensure_container(project_name)
        
        # 2. 在容器中执行命令
        result = await self._exec_in_container(container_id, command, timeout)
        
        return ExecuteResponse(
            output=result["output"],
            exit_code=result["exit_code"],
        )
    
    async def _ensure_container(self, project_name: str) -> str:
        """
        确保项目容器存在并运行
        """
        if project_name not in self._containers:
            # 创建新容器
            container_id = await self._create_container(project_name)
            self._containers[project_name] = container_id
        
        container_id = self._containers[project_name]
        
        # 检查容器状态
        if not await self._is_running(container_id):
            # 重启容器
            await self._start_container(container_id)
        
        return container_id
    
    async def _create_container(self, project_name: str) -> str:
        """
        为项目创建新容器
        """
        # 项目工作目录
        project_dir = self.workspace / project_name
        
        # 容器配置
        config = {
            "Image": self.image,
            "Cmd": ["sleep", "infinity"],  # 保持容器运行
            "Volumes": {
                f"{project_dir}": {"bind": "/root/workspace", "mode": "rw"},
            },
            "WorkingDir": "/root/workspace",
            "ExposedPorts": {
                "5000/tcp": {},  # Flask 默认端口
                "8080/tcp": {},  # 常用端口
            },
            "Env": [
                f"PROJECT_NAME={project_name}",
                "PYTHONUNBUFFERED=1",
            ],
            "HostConfig": {
                "PortBindings": {
                    "5000/tcp": [{"HostPort": "5000"}],
                },
                "Binds": [f"{project_dir}:/root/workspace:rw"],
                "AutoRemove": False,
            },
        }
        
        # 创建并启动容器
        container = await self.docker.containers.run(**config)
        return container.id
    
    async def _exec_in_container(
        self,
        container_id: str,
        command: str,
        timeout: int = None,
    ) -> dict:
        """
        在容器中执行命令
        """
        container = self.docker.containers.get(container_id)
        
        # 使用 exec_run 执行命令
        result = container.exec_run(
            f"bash -c '{command}'",
            workdir="/root/workspace",
            demux=True,
        )
        
        return {
            "output": result.output.decode("utf-8", errors="ignore"),
            "exit_code": result.exit_code,
        }
```

### 3.2 Dockerfile 模板

```dockerfile
# /root/dt/ai_coding/heimaclaw/docker/Dockerfile

FROM python:3.10-slim

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    git \
    curl \
    wget \
    vim \
    && rm -rf /var/lib/apt/lists/*

# 设置工作目录
WORKDIR /root/workspace

# 设置环境变量
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive

# 默认命令
CMD ["sleep", "infinity"]
```

### 3.3 requirements.txt 支持

```dockerfile
# 在 _create_container 中，如果项目有 requirements.txt
# 则安装依赖

if (project_dir / "requirements.txt").exists():
    # 复制 requirements.txt 到容器
    # 安装依赖
    exec_commands.append("COPY requirements.txt /root/workspace/")
    exec_commands.append("RUN pip install -r requirements.txt")
```

---

## 四、端口管理

### 4.1 动态端口分配

```python
class PortManager:
    """
    动态端口管理器
    
    为每个项目分配唯一的主机端口。
    """
    
    # 可用端口范围
    PORT_RANGE = range(5000, 6000)
    
    def __init__(self):
        self._allocated: dict[str, int] = {}  # project_name -> host_port
        self._used_ports: set[int] = set()
    
    def allocate(self, project_name: str) -> int:
        """为项目分配端口"""
        if project_name in self._allocated:
            return self._allocated[project_name]
        
        # 查找可用端口
        for port in self.PORT_RANGE:
            if port not in self._used_ports:
                self._allocated[project_name] = port
                self._used_ports.add(port)
                return port
        
        raise RuntimeError("无可用端口")
    
    def release(self, project_name: str):
        """释放项目端口"""
        if project_name in self._allocated:
            port = self._allocated.pop(project_name)
            self._used_ports.discard(port)
    
    def get_mapping(self, project_name: str) -> tuple[int, int]:
        """获取项目端口映射 (host_port, container_port)"""
        host_port = self.allocate(project_name)
        return host_port, 5000  # 容器内默认 5000
```

### 4.2 端口映射示例

| 项目 | 容器端口 | 主机端口 | 访问地址 |
|------|---------|---------|---------|
| flask_demo | 5000 | 5000 | http://localhost:5000 |
| api_server | 5000 | 5001 | http://localhost:5001 |
| blog | 5000 | 5002 | http://localhost:5002 |

---

## 五、与现有架构的集成

### 5.1 替换 FirecrackerBackend

```python
# src/heimaclaw/agent/docker_deepagents_backend.py

from heimaclaw.agent.base_backend import BaseBackend

class DockerDeepAgentsBackend(BaseBackend):
    """
    Docker 沙箱后端
    
    替换 FirecrackerDeepAgentsBackend，
    提供完整的项目级隔离。
    """
    
    def __init__(self, root_dir, docker_backend, instance_id, env):
        self.root_dir = root_dir
        self.docker_backend = docker_backend
        self.instance_id = instance_id
        self.env = env
    
    async def execute(self, command: str, timeout: int = None) -> ExecuteResponse:
        # 提取项目名
        project_name = extract_project_name(command)
        
        # 在 Docker 容器中执行
        return await self.docker_backend.execute(
            command=command,
            project_name=project_name,
            timeout=timeout,
        )
```

### 5.2 配置切换

```yaml
# config.yaml

sandbox:
  type: docker  # firecracker | docker | subprocess
  
docker:
  image: python:3.10-slim
  workspace: /root/heimaclaw_workspace
  port_range:
    start: 5000
    end: 6000
```

---

## 六、实施计划

### 6.1 第一阶段：基础设施

- [ ] 创建 `docker/` 目录和 Dockerfile
- [ ] 实现 `DockerBackend` 类
- [ ] 实现 `PortManager` 类
- [ ] 实现 `VolumeManager` 类

### 6.2 第二阶段：核心功能

- [ ] 容器生命周期管理（创建/启动/停止/删除）
- [ ] 命令执行（同步/异步）
- [ ] 端口映射
- [ ] 卷挂载

### 6.3 第三阶段：集成测试

- [ ] 与现有 Agent Runner 集成
- [ ] 与 HostExecutor 集成
- [ ] 部署任务测试
- [ ] 性能测试

### 6.4 第四阶段：生产就绪

- [ ] 日志收集
- [ ] 资源限制（CPU/内存）
- [ ] 自动清理
- [ ] 监控告警

---

## 七、文件结构

```
/root/dt/ai_coding/heimaclaw/
├── src/heimaclaw/agent/
│   ├── docker_deepagents_backend.py   # 🆕 Docker 后端
│   └── firecracker_deepagents_backend.py  # 保留（可切换）
├── docker/
│   ├── Dockerfile                    # 🆕 基础镜像
│   ├── Dockerfile.flask               # 🆕 Flask 专用镜像
│   └── requirements.txt              # 🆕 基础依赖
├── standards/
│   └── DOCKER-SANDBOX-ARCHITECTURE-v1.0.md  # 🆕 本文档
└── config.yaml
```

---

## 八、风险与缓解

| 风险 | 缓解措施 |
|------|---------|
| Docker 未安装 | 检查并提示安装 |
| 端口冲突 | 动态端口分配 + 冲突检测 |
| 容器无法启动 | 错误日志 + 重试机制 |
| 镜像拉取失败 | 本地镜像缓存 + 超时设置 |
| 资源耗尽 | 容器资源限制（CPU/内存）|

---

_文档版本: v1.0 | 创建: 2026-03-24_
