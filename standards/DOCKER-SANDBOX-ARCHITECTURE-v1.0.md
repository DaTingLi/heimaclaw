# HeiMaClaw Docker 沙箱架构 v1.0

> **版本**: v1.0  
> **创建**: 2026-03-24  
> **更新**: 2026-03-24 (按需容器+资源管理)  
> **状态**: 待实现

---

## 一、设计原则（核心）

### 1.1 关键理解

| 原则 | 说明 |
|------|------|
| **按需创建** | 容器不是既定的，是根据项目需求动态创建 |
| **环境自洽** | 每个容器内环境完整，自行管理依赖，不依赖宿主机 |
| **项目隔离** | 一个项目 = 一个容器，容器间完全隔离 |
| **资源可控** | 容器有资源限制，不占用过多宿主机资源 |
| **生命周期管理** | 容器的创建/运行/销毁有完整管理机制 |

### 1.2 与 Firecracker 的区别

```
Firecracker:
  预创建微 VM → 复用 → 环境受限(Alpine)

Docker:
  按需创建容器 → 按项目需求构建镜像 → 完整环境 + 持久运行
```

---

## 二、容器生命周期管理

### 2.1 生命周期状态机

```
┌─────────────────────────────────────────────────────────────────┐
│                    容器生命周期状态机                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────┐                                                  │
│  │  NONE    │ (初始状态，无容器)                                │
│  └────┬─────┘                                                  │
│       │ 创建项目容器                                            │
│       ▼                                                        │
│  ┌──────────┐    首次执行    ┌────────────┐                     │
│  │ CREATING │──────────────►│  RUNNING   │                     │
│  └──────────┘              └──────┬─────┘                     │
│                                    │                            │
│       ┌────────────────────────────┼────────────────────────┐   │
│       │                            │                        │   │
│       ▼                            ▼                        ▼   │
│  ┌──────────┐              ┌────────────┐           ┌──────────┐│
│  │  STOPPED │◄─────────────│   IDLE     │────────►│ DESTROY ││
│  │ (休眠)   │  无活动超时   │  (无任务)   │  资源紧张 │  (销毁)  ││
│  └──────────┘              └────────────┘           └──────────┘│
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 状态转换规则

| 当前状态 | 触发条件 | 下一状态 | 动作 |
|---------|---------|---------|------|
| NONE | 项目首次需要执行命令 | CREATING | 创建容器 + 构建镜像 |
| CREATING | 容器创建成功 | RUNNING | 开始执行命令 |
| RUNNING | 命令执行完成 | IDLE | 启动空闲计时器 |
| IDLE | 空闲超时 (默认 30 分钟) | STOPPED | 停止容器，释放资源 |
| IDLE | 新命令到达 | RUNNING | 启动容器 |
| STOPPED | 需要执行 | RUNNING | 重启容器 |
| STOPPED | 资源紧张 / 项目结束 | DESTROY | 删除容器 |
| ANY | 强制销毁 | DESTROY | 删除容器 + 清理资源 |

### 2.3 容器资源占用

| 资源 | 限制 | 说明 |
|------|------|------|
| **CPU** | 0.5 - 2 核 | 可配置，默认 1 核 |
| **内存** | 512MB - 2GB | 可配置，默认 1GB |
| **磁盘** | 10GB | 基于 Docker 的 volume |
| **端口** | 动态分配 | 5000-6000 范围 |

**资源预留**：
```
宿主机资源 = 4 核 CPU + 8GB 内存
├─ 系统预留 = 1 核 + 2GB
├─ Agent 进程 = 1 核 + 1GB
└─ 容器池 = 最多 4 个容器 × 1核 + 1GB
```

---

## 三、端口映射机制（详细）

### 3.1 端口分配策略

```
宿主机端口资源: 5000-6000 (共 1000 个端口)

分配原则:
1. 项目创建时动态分配
2. 同项目多端口自动递增
3. 容器销毁后端口释放回池
```

### 3.2 端口分配表

| 场景 | 容器端口 | 宿主机端口 | 说明 |
|------|---------|-----------|------|
| Flask 应用 | 5000 | 5001 | 第 1 个 Flask 项目 |
| Flask 应用 | 5000 | 5002 | 第 2 个 Flask 项目 |
| Streamlit | 8501 | 5003 | Streamlit 默认 8501 |
| API 服务 | 8000 | 5004 | REST API 服务 |
| 同一项目多端口 | 5000, 5001 | 5005, 5006 | 项目有两个服务 |

### 3.3 端口冲突检测与处理

```python
class PortPool:
    """
    端口池管理器
    
    负责端口的分配、释放、冲突检测。
    """
    
    def __init__(self, port_range=(5000, 6000)):
        self.port_range = range(port_range[0], port_range[1])
        self._allocated: dict[str, list[int]] = {}  # project -> [ports]
        self._available: set[int] = set(self.port_range)
        self._reserved: set[int] = set()  # 宿主机已占用的端口
    
    def _detect_host_conflict(self, port: int) -> bool:
        """检测宿主机端口是否被占用"""
        result = subprocess.run(
            f"ss -tlnp | grep ':{port}'",
            shell=True,
            capture_output=True,
        )
        return result.returncode == 0
    
    def allocate(self, project_name: str, container_port: int = 5000) -> int:
        """
        为项目分配宿主机端口
        
        1. 尝试分配 requested port
        2. 如果冲突，扫描可用端口
        3. 如果无可用端口，抛出异常
        """
        # 检查请求的端口是否可用
        if port not in self._reserved and not self._detect_host_conflict(port):
            self._allocated[project_name].append(port)
            self._reserved.add(port)
            return port
        
        # 扫描可用端口
        for candidate in self.port_range:
            if candidate in self._reserved:
                continue
            if self._detect_host_conflict(candidate):
                self._reserved.add(candidate)  # 标记为已占用
                continue
            
            # 找到可用端口
            self._allocated[project_name].append(candidate)
            self._reserved.add(candidate)
            return candidate
        
        raise RuntimeError(f"无可用端口 (range: {self.port_range})")
    
    def release(self, project_name: str):
        """释放项目的所有端口"""
        if project_name in self._allocated:
            for port in self._allocated[project_name]:
                self._reserved.discard(port)
            del self._allocated[project_name]
```

### 3.4 多端口项目管理

```python
# 一个项目可能有多个服务需要暴露端口
project_config = {
    "name": "flask_demo",
    "services": [
        {"name": "web", "port": 5000},      # Flask Web
        {"name": "admin", "port": 5001},    # Admin 面板
    ]
}

# 分配结果
# flask_demo_web -> host:5001 -> container:5000
# flask_demo_admin -> host:5002 -> container:5001
```

---

## 四、容器镜像设计（按需构建）

### 4.1 基础镜像

```dockerfile
# docker/Dockerfile.base
FROM python:3.10-slim

# 安装通用工具（不包含项目特定依赖）
RUN apt-get update && apt-get install -y \
    git \
    curl \
    wget \
    vim \
    htop
### 4.2 镜像构建策略（按需）

```
┌─────────────────────────────────────────────────────────────────┐
│                    镜像构建流程 (按需)                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. 分析项目依赖                                                  │
│     │                                                           │
│     ▼                                                           │
│  ┌──────────────────────┐                                      │
│  │  项目有什么依赖？        │                                      │
│  │  - requirements.txt   │                                      │
│  │  - pyproject.toml     │                                      │
│  │  - environment.yml    │                                      │
│  └──────────────────────┘                                      │
│     │                                                           │
│     ▼                                                           │
│  2. 选择基础镜像                                                  │
│     │                                                           │
│     ▼                                                           │
│  ┌──────────────────────────────────┐                           │
│  │  Python 版本 │ 基础镜像              │                           │
│  ├──────────────────────────────────┤                           │
│  │  3.8       │ python:3.8-slim      │                           │
│  │  3.9       │ python:3.9-slim      │                           │
│  │  3.10      │ python:3.10-slim      │                           │
│  │  3.11      │ python:3.11-slim      │                           │
│  │  3.12      │ python:3.12-slim      │                           │
│  └──────────────────────────────────┘                           │
│     │                                                           │
│     ▼                                                           │
│  3. 生成项目专用镜像                                              │
│     │                                                           │
│     ▼                                                           │
│  ┌──────────────────────────────────┐                           │
│  │  FROM python:3.10-slim           │                           │
│  │  COPY requirements.txt /tmp/     │                           │
│  │  RUN pip install -r /tmp/req.txt │                           │
│  │  (其他项目特定安装)                │                           │
│  └──────────────────────────────────┘                           │
│     │                                                           │
│     ▼                                                           │
│  4. 缓存镜像层                                                   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 4.3 依赖分析器

```python
class DependencyAnalyzer:
    """
    项目依赖分析器
    
    分析项目使用的框架/库，自动确定需要预装的依赖。
    """
    
    # 框架特征指纹
    FRAMEWORK_PATTERNS = {
        "flask": ["flask", "werkzeug", "jinja2"],
        "django": ["django", "wsgi", "templates"],
        "fastapi": ["fastapi", "uvicorn", "starlette"],
        "streamlit": ["streamlit", "pandas", "plotly"],
        "gradio": ["gradio", "spaces"],
        "pyqt": ["PyQt", "PySide"],
        "pandas": ["pandas", "numpy"],
        "ml": ["torch", "tensorflow", "transformers"],
    }
    
    def analyze(self, project_dir: Path) -> dict:
        """
        分析项目依赖
        
        返回:
        {
            "frameworks": ["flask"],
            "python_version": "3.10",
            "system_deps": ["libgl1"],  # OpenCV 需要
            "pip_packages": ["flask", "sqlalchemy"],
        }
        """
        result = {
            "frameworks": [],
            "python_version": "3.10",
            "system_deps": [],
            "pip_packages": [],
        }
        
        # 1. 扫描 Python 文件
        for py_file in project_dir.rglob("*.py"):
            content = py_file.read_text(errors="ignore")
            result["frameworks"].extend(
                self._detect_frameworks(content)
            )
        
        # 2. 读取依赖文件
        if (project_dir / "requirements.txt").exists():
            result["pip_packages"].extend(
                self._parse_requirements(project_dir / "requirements.txt")
            )
        
        # 3. 系统依赖检测
        result["system_deps"] = self._detect_system_deps(result["frameworks"])
        
        return result
    
    def _detect_system_deps(self, frameworks: list[str]) -> list[str]:
        """检测需要的系统依赖"""
        deps_map = {
            "pandas": ["libgomp1"],
            "ml": ["libgl1", "libglib2.0-0"],  # OpenCV/PyTorch
            "pyqt": ["libxkbcommon0", "libxcb-icccm4"],
        }
        
        deps = []
        for fw in frameworks:
            deps.extend(deps_map.get(fw, []))
        return list(set(deps))
```

---

## 五、项目容器管理

### 5.1 ProjectContainer（核心类）

```python
@dataclass
class ContainerConfig:
    """容器配置"""
    project_name: str
    image: str = "python:3.10-slim"
    cpu_limit: float = 1.0      # CPU 核数
    memory_limit: str = "1g"    # 内存限制
    workspace_path: Path = None  # 项目工作目录
    exposed_ports: list[int] = None  # 容器内需要暴露的端口


class ProjectContainer:
    """
    项目容器管理器
    
    负责单个项目的容器生命周期管理。
    """
    
    def __init__(self, config: ContainerConfig, port_pool: PortPool):
        self.config = config
        self.port_pool = port_pool
        self.container_id: str = None
        self.status: ContainerStatus = ContainerStatus.NONE
        self.port_mappings: dict[int, int] = {}  # container_port -> host_port
        self.idle_timer: asyncio.Task = None
    
    async def ensure(self) -> str:
        """
        确保容器存在并运行
        
        根据当前状态自动决定需要做什么:
        - NONE -> 创建并启动
        - STOPPED -> 启动
        - RUNNING/IDLE -> 直接使用
        """
        if self.status == ContainerStatus.NONE:
            await self._create()
            await self._start()
        elif self.status == ContainerStatus.STOPPED:
            await self._start()
        
        return self.container_id
    
    async def _create(self):
        """
        创建容器
        
        1. 构建镜像（如果需要）
        2. 创建容器
        3. 分配端口
        """
        # 1. 分析依赖，构建镜像
        image = await self._build_image()
        
        # 2. 分配端口
        for container_port in (self.config.exposed_ports or [5000]):
            host_port = self.port_pool.allocate(
                self.config.project_name, 
                container_port
            )
            self.port_mappings[container_port] = host_port
        
        # 3. 创建容器
        self.container_id = await self._do_create(image)
        self.status = ContainerStatus.CREATING
    
    async def _build_image(self) -> str:
        """
        构建项目专用镜像
        
        如果项目有特殊依赖，构建新镜像；
        否则使用基础镜像。
        """
        deps = self._analyzer.analyze(self.config.workspace_path)
        
        if not deps["pip_packages"] and not deps["system_deps"]:
            # 无特殊依赖，使用基础镜像
            return "python:3.10-slim"
        
        # 构建自定义镜像
        image_name = f"heimaclaw/{self.config.project_name}:latest"
        
        dockerfile_content = self._generate_dockerfile(deps)
        
        # 写入临时 Dockerfile
        dockerfile_path = Path(f"/tmp/heimaclaw/{self.config.project_name}/Dockerfile")
        dockerfile_path.parent.mkdir(parents=True, exist_ok=True)
        dockerfile_path.write_text(dockerfile_content)
        
        # 构建镜像
        await async_run([
            "docker", "build", "-t", image_name,
            "-f", str(dockerfile_path),
            str(self.config.workspace_path)
        ])
        
        return image_name
    
    async def execute(self, command: str, timeout: int = None) -> ExecuteResponse:
        """
        在容器中执行命令
        """
        # 确保容器运行
        await self.ensure()
        
        # 重置空闲计时器
        self._reset_idle_timer()
        
        # 执行命令
        result = await self._exec_in_container(command, timeout)
        
        return ExecuteResponse(
            output=result["output"],
            exit_code=result["exit_code"],
        )
    
    async def destroy(self):
        """销毁容器并释放资源"""
        if self.container_id:
            # 停止容器
            await async_run(["docker", "stop", self.container_id])
            # 删除容器
            await async_run(["docker", "rm", "-v", self.container_id])
        
        # 释放端口
        self.port_pool.release(self.config.project_name)
        
        self.status = ContainerStatus.DESTROYED
        self.container_id = None
```

### 5.2 ContainerPool（容器池管理）

```python
class ContainerPool:
    """
    容器池管理器
    
    管理所有项目容器，控制资源使用。
    """
    
    def __init__(
        self,
        max_containers: int = 4,
        idle_timeout: int = 1800,  # 30 分钟
    ):
        self.max_containers = max_containers
        self.idle_timeout = idle_timeout
        
        self._containers: dict[str, ProjectContainer] = {}
        self._lock = asyncio.Lock()
    
    async def get_container(self, project_name: str) -> ProjectContainer:
        """获取或创建项目容器"""
        async with self._lock:
            if project_name not in self._containers:
                # 检查是否达到上限
                if len(self._containers) >= self.max_containers:
                    # 尝试清理空闲容器
                    await self._cleanup_idle_containers()
                
                # 再次检查
                if len(self._containers) >= self.max_containers:
                    raise RuntimeError(
                        f"容器数量已达上限 ({self.max_containers})，"
                        "请等待其他项目完成"
                    )
                
                # 创建新容器
                config = ContainerConfig(
                    project_name=project_name,
                    workspace_path=Path(f"/root/heimaclaw_workspace/{project_name}"),
                )
                self._containers[project_name] = ProjectContainer(
                    config=config,
                    port_pool=self._port_pool,
                )
            
            return self._containers[project_name]
    
    async def _cleanup_idle_containers(self):
        """清理空闲容器"""
        idle_containers = [
            (name, container)
            for name, container in self._containers.items()
            if container.status == ContainerStatus.IDLE
        ]
        
        # 按空闲时间排序，最老的优先清理
        idle_containers.sort(key=lambda x: x[1].idle_since)
        
        # 清理 1 个容器
        if idle_containers:
            name, container = idle_containers[0]
            await container.destroy()
            del self._containers[name]
    
    async def destroy_project(self, project_name: str):
        """销毁指定项目容器"""
        async with self._lock:
            if project_name in self._containers:
                await self._containers[project_name].destroy()
                del self._containers[project_name]
    
    def get_stats(self) -> dict:
        """获取容器池统计"""
        return {
            "total": len(self._containers),
            "max": self.max_containers,
            "by_status": {
                status.value: sum(
                    1 for c in self._containers.values()
                    if c.status == status
                )
                for status in ContainerStatus
            }
        }
```

---

## 六、命令执行流程

### 6.1 完整执行流程

```
┌─────────────────────────────────────────────────────────────────┐
│                    命令执行流程                                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. 接收命令                                                     │
│     │                                                           │
│     ▼                                                           │
│  2. 判定部署任务？                                                │
│     │                                                           │
│     ├─ YES ───────────────────────────────────────────────┐      │
│     │                                                        │      │
│     ▼                                                        ▼      │
│  ┌──────────────────┐                              ┌────────────┐  │
│  │ 部署任务处理      │                              │ 即时任务处理 │  │
│  │                  │                              │            │  │
│  │ 1. 提取项目名     │                              │ 1. 在现有   │  │
│  │ 2. 获取/创建容器  │                              │    容器执行 │  │
│  │ 3. 启动服务       │                              │ 2. 返回结果 │  │
│  │ 4. 后台运行       │                              └────────────┘  │
│  │ 5. 端口映射检测   │                                        │      │
│  └────────┬─────────┘                                        │      │
│           │                                                   │      │
│           ▼                                                   │      │
│  ┌──────────────────┐                                        │      │
│  │  等待服务就绪      │                                        │      │
│  │  (健康检查)        │                                        │      │
│  └────────┬─────────┘                                        │      │
│           │                                                   │      │
│           ▼                                                   │      │
│  ┌──────────────────┐                                        │      │
│  │  返回访问信息     │                                        │      │
│  │  http://host:port │                                        │      │
│  └──────────────────┘                                        │      │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 6.2 部署任务处理

```python
async def handle_deployment_task(command: str) -> ExecuteResponse:
    """
    处理部署任务
    """
    # 1. 提取项目名
    project_name = extract_project_name(command)
    
    # 2. 获取容器
    container = await container_pool.get_container(project_name)
    
    # 3. 分析服务端口
    ports = detect_service_ports(command)  # 如 [5000, 5001]
    
    # 4. 更新容器配置，添加端口映射
    for port in ports:
        if port not in container.port_mappings:
            host_port = port_pool.allocate(project_name, port)
            container.port_mappings[port] = host_port
    
    # 5. 在容器中执行部署命令（后台）
    await container.execute_in_background(command)
    
    # 6. 等待服务就绪
    await wait_for_service_ready(
        host_port=container.port_mappings[5000],
        timeout=60
    )
    
    # 7. 返回访问信息
    return ExecuteResponse(
        output=f"服务已启动: http://localhost:{container.port_mappings[5000]}",
        exit_code=0,
    )
```

---

## 七、资源限制与安全

### 7.1 Docker 资源限制

```yaml
# docker-compose.yml 风格的配置
services:
  project_container:
    image: ${IMAGE}
    deploy:
      resources:
        limits:
          cpus: '1.0'        # 最多 1 核
          memory: 1G          # 最多 1GB
        reservations:
          cpus: '0.25'       # 最小 0.25 核
          memory: 256M       # 最小 256MB
```

### 7.2 网络隔离

```python
# 容器网络配置
network_config = {
    "NetworkMode": "heimaclaw-net",  # 专用网络
}

# 容器间网络隔离
# 项目容器之间不能直接通信
# 只能通过宿主机端口访问
```

### 7.3 文件系统限制

```python
# 只读根目录，可写项目目录
volume_config = {
    "/root/workspace": {
        "bind": f"/root/heimaclaw_workspace/{project_name}",
        "mode": "rw",  # 可写
    },
    "/": {
        "bind": "/",
        "mode": "ro",  # 只读
    },
}
```

---

## 八、与现有架构集成

### 8.1 Backend 接口统一

```python
# src/heimaclaw/agent/docker_backend.py

from heimaclaw.agent.base_backend import BaseBackend

class DockerBackend(BaseBackend):
    """
    Docker 后端
    
    实现 BaseBackend 接口，替换 FirecrackerBackend。
    """
    
    async def execute(self, command: str, timeout: int = None) -> ExecuteResponse:
        """执行命令"""
        project_name = extract_project_name(command)
        
        if is_deployment_task(command):
            # 部署任务：使用容器池
            container = await self.container_pool.get_container(project_name)
            return await container.execute(command, timeout)
        else:
            # 即时任务：直接执行
            return await self._execute_direct(command, timeout)
```

### 8.2 配置切换

```yaml
# config.yaml

sandbox:
  type: docker  # firecracker | docker | subprocess
  
docker:
  image_base: python:3.10-slim
  max_containers: 4
  idle_timeout_minutes: 30
  port_range:
    start: 5000
    end: 6000
  resources:
    cpu_per_container: 1.0
    memory_per_container: 1g
```

---

## 九、文件结构

```
/root/dt/ai_coding/heimaclaw/
├── src/heimaclaw/
│   ├── agent/
│   │   ├── docker_backend.py           # 🆕 Docker 后端
│   │   ├── base_backend.py            # 后端接口定义
│   │   └── firecracker_backend.py      # 保留（可切换）
│   ├── core/
│   │   ├── container_manager.py        # 🆕 容器生命周期
│   │   ├── port_pool.py                # 🆕 端口池管理
│   │   ├── dependency_analyzer.py     # 🆕 依赖分析
│   │   └── container_pool.py           # 🆕 容器池
│   └── ...
├── docker/
│   ├── Dockerfile.base                 # 🆕 基础镜像
│   └── requirements.txt                # 🆕 基础依赖
├── standards/
│   └── DOCKER-SANDBOX-ARCHITECTURE-v1.0.md  # 🆕 本文档
└── config.yaml
```

---

## 十、关键设计决策

| 决策 | 选择 | 理由 |
|------|------|------|
| 容器生命周期 | 按需创建/销毁 | 节省资源 |
| 空闲超时 | 30 分钟 | 平衡资源与响应速度 |
| 最大容器数 | 4 个 | 宿主机资源限制 |
| 端口分配 | 动态分配 | 避免冲突 |
| 镜像构建 | 按需构建 | 只构建需要的 |
| 资源限制 | CPU 1核 + 内存 1GB | 隔离但不过度占用 |

---

## 十一、风险与缓解

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|---------|
| Docker 未安装 | 低 | 高 | 启动时检查，提示安装 |
| 端口耗尽 | 低 | 中 | 动态分配 + 及时释放 |
| 镜像构建失败 | 中 | 中 | 回退到基础镜像 + 错误提示 |
| 容器无法启动 | 低 | 高 | 错误日志 + 自动重试 |
| 宿主机资源耗尽 | 中 | 高 | 容器数量限制 + 资源预留 |
| 端口冲突 | 低 | 中 | 冲突检测 + 自动切换端口 |

---

## 十二、测试计划

### 12.1 单元测试

| 模块 | 测试内容 |
|------|---------|
| PortPool | 分配、释放、冲突检测 |
| DependencyAnalyzer | 框架检测、版本检测 |
| ContainerPool | 容器创建、销毁、限制 |

### 12.2 集成测试

| 场景 | 预期结果 |
|------|---------|
| 首次部署 Flask 项目 | 创建容器 + 安装依赖 + 启动服务 |
| 再次部署同一项目 | 复用已有容器 |
| 4 个容器同时运行 | 第 5 个项目等待 |
| 30 分钟无活动 | 容器自动停止 |
| 端口 5000 被占用 | 自动使用 5001 |

---

_文档版本: v1.0 | 创建: 2026-03-24 | 更新: 2026-03-24_
