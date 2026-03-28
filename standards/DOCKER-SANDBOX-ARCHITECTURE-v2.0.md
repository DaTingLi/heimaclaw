# HeiMaClaw Docker 沙箱架构 v2.0

> **版本**: v2.0  
> **创建**: 2026-03-24  
> **更新**: 2026-03-24 (结合 OpenClaw Delegate 架构)  
> **状态**: 待实现

---

## 一、设计理念（参考 OpenClaw Delegate）

### 1.1 OpenClaw Delegate 核心原则

```
OpenClaw Delegate 模型 = 执行代理 + 生命周期管理 + 审计追踪

我们的 Docker 容器 = 项目执行代理 + 持久化存储 + 状态追踪
```

| OpenClaw Delegate | 我们的 Docker 容器 |
|-------------------|-------------------|
| 有自己的身份 | 有唯一的容器 ID |
| 代表用户执行 | 代表项目执行 |
| 有权限边界 | 有资源限制 |
| 操作可审计 | 操作可追溯 |
| 生命周期管理 | 项目状态追踪 |

### 1.2 核心设计原则

```
┌─────────────────────────────────────────────────────────────────┐
│                    五大核心原则                                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. 项目代码永远不丢失                                            │
│     └── 容器销毁 ≠ 代码丢失（代码在宿主机 volume）                 │
│                                                                  │
│  2. 容器按需创建，按策略销毁                                       │
│     └── 不是预创建，而是需要时创建                                 │
│                                                                  │
│  3. 销毁有冷却期，给用户反悔机会                                   │
│     └── soft delete（标记删除）→ 冷静期 → hard delete（真正删除） │
│                                                                  │
│  4. 所有操作可查询、可追溯、可恢复                                 │
│     └── 项目状态机 + 操作日志 + 快照机制                           │
│                                                                  │
│  5. 容器内环境完整，不污染宿主机                                   │
│     └── 依赖隔离 + 版本隔离                                        │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 二、项目生命周期管理

### 2.1 项目状态机（核心）

```
┌─────────────────────────────────────────────────────────────────┐
│                    项目完整生命周期                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────┐                                                   │
│  │ CREATED  │ (首次创建项目目录)                                  │
│  └────┬─────┘                                                   │
│       │ 首次部署命令                                              │
│       ▼                                                          │
│  ┌──────────┐                                                   │
│  │ BUILDING │ 构建镜像中                                          │
│  └────┬─────┘                                                   │
│       │ 镜像构建成功                                              │
│       ▼                                                          │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐                   │
│  │ RUNNING  │───►│  IDLE    │───►│ STOPPED  │                   │
│  │ (运行中)  │    │ (空闲)   │    │ (已停止)  │                   │
│  └────┬─────┘    └────┬─────┘    └────┬─────┘                   │
│       │              │              │                            │
│       │              │ 超时 30min   │ 强制停止                   │
│       │              │              │                            │
│       │              ▼              ▼                            │
│       │         ┌──────────────────────┐                        │
│       │         │     GRACEFUL         │                        │
│       │         │     (软删除/待删除)    │                        │
│       │         └──────────────────────┘                        │
│       │                   │                                      │
│       │                   │ 7天冷静期                             │
│       │                   │ 或 用户恢复                           │
│       │                   ▼                                      │
│       │         ┌──────────────────────┐                        │
│       └────────►│     DESTROYED        │                        │
│                 │     (彻底删除)        │                        │
│                 └──────────────────────┘                        │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 项目元数据（持久化存储）

```python
# 项目元数据文件: /root/heimaclaw_workspace/.projects/<project_name>/.project_meta.json

{
    "name": "flask_demo",
    "created_at": "2026-03-24T10:00:00Z",
    "lastAccessed": "2026-03-24T15:30:00Z",
    
    # 容器状态
    "container": {
        "containerId": "abc123def456",
        "image": "heimaclaw/flask_demo:latest",
        "status": "RUNNING",  # CREATED|BUILDING|RUNNING|IDLE|STOPPED|GRACEFUL|DESTROYED
        "hostPorts": {
            "5000": 5001,
            "5001": 5003
        },
        "createdAt": "2026-03-24T10:00:00Z",
        "lastStarted": "2026-03-24T15:00:00Z",
    },
    
    # 依赖信息
    "dependencies": {
        "pythonVersion": "3.10",
        "frameworks": ["flask", "sqlalchemy"],
        "requirements": ["flask", "sqlalchemy", "redis"],
        "systemDeps": ["libgl1"]
    },
    
    # 操作日志
    "operations": [
        {"action": "create", "timestamp": "2026-03-24T10:00:00Z"},
        {"action": "deploy", "timestamp": "2026-03-24T10:00:05Z"},
        {"action": "stop", "timestamp": "2026-03-24T15:30:00Z"},
    ],
    
    # 软删除标记
    "graceful": {
        "markedAt": null,
        "reason": null,
        "recoveryAvailable": true
    }
}
```

### 2.3 软删除机制（关键！）

```python
class GracefulDeletion:
    """
    软删除机制 - 给用户反悔机会
    """
    
    GRACE_PERIOD = 7 * 24 * 3600  # 7 天冷静期
    
    async def mark_for_deletion(self, project_name: str, reason: str):
        """
        标记项目为待删除（软删除）
        
        1. 停止容器
        2. 保留项目文件
        3. 保留元数据
        4. 启动 7 天倒计时
        """
        meta = self._load_meta(project_name)
        
        # 停止容器（不删除）
        if meta["container"]["containerId"]:
            await self._stop_container(meta["container"]["containerId"])
        
        # 标记为软删除
        meta["graceful"] = {
            "markedAt": datetime.now().isoformat(),
            "reason": reason,
            "recoveryAvailable": True
        }
        meta["container"]["status"] = "GRACEFUL"
        
        self._save_meta(project_name, meta)
        
        # 创建备份快照
        await self._create_snapshot(project_name)
        
        # 调度彻底删除任务
        self._schedule_destruction(project_name, self.GRACE_PERIOD)
    
    async def recover(self, project_name: str):
        """
        恢复项目（反悔）
        """
        meta = self._load_meta(project_name)
        
        if not meta["graceful"]["recoveryAvailable"]:
            raise RuntimeError("项目已超过恢复期限")
        
        # 恢复状态
        meta["graceful"] = {"markedAt": None, "reason": None, "recoveryAvailable": True}
        meta["container"]["status"] = "STOPPED"
        
        self._save_meta(project_name, meta)
        
        # 取消删除任务
        self._cancel_destruction(project_name)
    
    async def hard_delete(self, project_name: str):
        """
        彻底删除（硬删除）
        
        冷静期结束后执行
        """
        # 1. 删除项目文件
        await self._delete_project_files(project_name)
        
        # 2. 删除镜像
        await self._delete_image(project_name)
        
        # 3. 删除快照
        await self._delete_snapshot(project_name)
        
        # 4. 删除元数据
        self._delete_meta(project_name)
```

---

## 三、查询与管理机制

### 3.1 项目管理器（ProjectManager）

```python
class ProjectManager:
    """
    项目管理器 - 统一的查询和管理接口
    """
    
    def __init__(self, workspace: Path, container_pool):
        self.workspace = workspace
        self.container_pool = container_pool
        self.meta_dir = workspace / ".projects"
    
    # ==================== 查询接口 ====================
    
    def list_projects(self, status: str = None) -> list[dict]:
        """
        列出所有项目（可按状态过滤）
        """
        projects = []
        
        for meta_path in self.meta_dir.rglob(".project_meta.json"):
            meta = json.loads(meta_path.read_text())
            
            if status is None or meta["container"]["status"] == status:
                projects.append({
                    "name": meta["name"],
                    "status": meta["container"]["status"],
                    "lastAccessed": meta["lastAccessed"],
                    "createdAt": meta["created_at"],
                })
        
        return projects
    
    def get_project(self, project_name: str) -> dict:
        """
        获取项目详细信息
        """
        meta = self._load_meta(project_name)
        
        return {
            "name": meta["name"],
            "status": meta["container"]["status"],
            "container": {
                "id": meta["container"]["containerId"],
                "image": meta["container"]["image"],
                "ports": meta["container"]["hostPorts"],
                "createdAt": meta["container"]["createdAt"],
                "lastStarted": meta["container"]["lastStarted"],
            },
            "dependencies": meta["dependencies"],
            "operations": meta["operations"],
            "graceful": meta["graceful"],
        }
    
    def get_project_status(self, project_name: str) -> str:
        """
        获取项目状态（快速查询）
        """
        meta = self._load_meta(project_name)
        return meta["container"]["status"]
    
    def get_container_logs(self, project_name: str, lines: int = 100) -> str:
        """
        获取容器日志
        """
        meta = self._load_meta(project_name)
        container_id = meta["container"]["containerId"]
        
        if not container_id:
            return "容器不存在"
        
        result = subprocess.run(
            ["docker", "logs", "--tail", str(lines), container_id],
            capture_output=True,
            text=True,
        )
        
        return result.stdout + result.stderr
    
    def get_project_files(self, project_name: str) -> tree:
        """
        获取项目文件结构
        """
        project_dir = self.workspace / project_name
        
        if not project_dir.exists():
            return None
        
        return self._build_tree(project_dir)
    
    # ==================== 管理接口 ====================
    
    async def start_project(self, project_name: str):
        """
        启动项目
        """
        meta = self._load_meta(project_name)
        
        if meta["graceful"]["markedAt"]:
            # 从软删除恢复
            await self.recover_project(project_name)
            return
        
        container = await self.container_pool.get_container(project_name)
        await container.start()
        
        meta["container"]["status"] = "RUNNING"
        meta["lastAccessed"] = datetime.now().isoformat()
        self._save_meta(project_name, meta)
    
    async def stop_project(self, project_name: str):
        """
        停止项目
        """
        container = await self.container_pool.get_container(project_name)
        await container.stop()
        
        meta = self._load_meta(project_name)
        meta["container"]["status"] = "STOPPED"
        self._save_meta(project_name, meta)
    
    async def delete_project(self, project_name: str, force: bool = False):
        """
        删除项目
        
        Args:
            project_name: 项目名
            force: 是否强制删除（跳过冷静期）
        """
        meta = self._load_meta(project_name)
        
        if not force and meta["container"]["status"] != "GRACEFUL":
            # 软删除
            await self._graceful_delete(project_name, reason="用户请求删除")
        else:
            # 硬删除
            await self._hard_delete(project_name)
    
    async def rebuild_project(self, project_name: str):
        """
        重建项目（重新构建镜像）
        """
        # 1. 停止现有容器
        await self.stop_project(project_name)
        
        # 2. 删除旧镜像
        meta = self._load_meta(project_name)
        if meta["container"]["image"]:
            await self._delete_image(meta["container"]["image"])
        
        # 3. 重新构建
        meta["container"]["status"] = "BUILDING"
        self._save_meta(project_name, meta)
        
        container = await self.container_pool.get_container(project_name)
        await container.rebuild()
        
        meta["container"]["status"] = "STOPPED"
        self._save_meta(project_name, meta)
```

### 3.2 用户交互接口

```python
# 用户可以通过以下方式管理项目：

# 1. 查看所有项目
await pm.list_projects()
# [
#   {"name": "flask_demo", "status": "RUNNING", "lastAccessed": "2026-03-24T15:30:00Z"},
#   {"name": "api_server", "status": "GRACEFUL", "lastAccessed": "2026-03-20T10:00:00Z"},
# ]

# 2. 查看项目详情
await pm.get_project("flask_demo")
# {
#   "name": "flask_demo",
#   "status": "RUNNING",
#   "container": {"id": "abc123", "ports": {"5000": 5001}},
#   "dependencies": {"frameworks": ["flask"]},
# }

# 3. 获取访问地址
ports = meta["container"]["hostPorts"]
access_url = f"http://localhost:{ports[5000]}"

# 4. 查看容器日志
await pm.get_container_logs("flask_demo", lines=50)

# 5. 启动/停止/删除
await pm.start_project("flask_demo")
await pm.stop_project("flask_demo")
await pm.delete_project("flask_demo")  # 软删除
await pm.delete_project("flask_demo", force=True)  # 硬删除

# 6. 恢复已删除项目
await pm.recover_project("flask_demo")

# 7. 重建项目
await pm.rebuild_project("flask_demo")
```

---

## 四、销毁后恢复机制（核心！）

### 4.1 数据永不丢失原则

```
┌─────────────────────────────────────────────────────────────────┐
│                    数据存储架构                                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  宿主机文件系统                                                    │
│  /root/heimaclaw_workspace/                                     │
│  │                                                               │
│  ├── flask_demo/               ← 项目代码（持久化）              │
│  │   ├── app.py                                                  │
│  │   ├── requirements.txt                                        │
│  │   └── ...                                                      │
│  │                                                               │
│  ├── api_server/              ← 项目代码（持久化）                │
│  │   └── ...                                                      │
│  │                                                               │
│  └── .projects/                ← 元数据目录（隐藏）                │
│      ├── flask_demo/                                            │
│      │   └── .project_meta.json  ← 项目状态+配置                 │
│      │                                                               │
│      ├── api_server/                                              │
│      │   └── .project_meta.json                                  │
│      │                                                               │
│      └── .snapshots/           ← 备份快照                         │
│          └── flask_demo/                                          │
│              └── (tar.gz 快照)                                    │
│                                                                  │
│  Docker 镜像（容器销毁后保留 7 天）                                │
│  heimaclaw/flask_demo:latest                                     │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 4.2 恢复场景与方式

| 场景 | 容器状态 | 项目文件 | 恢复方式 |
|------|---------|---------|---------|
| 容器意外停止 | STOPPED | ✅ 保留 | 直接启动 |
| 宿主机重启 | STOPPED | ✅ 保留 | 直接启动 |
| 软删除后 | GRACEFUL | ✅ 保留 | 调用 recover() |
| 硬删除后 7 天内 | DESTROYED | ✅ 有快照 | 从快照恢复 |
| 硬删除后 7 天后 | GONE | ❌ 无 | **无法恢复** |

### 4.3 快照机制

```python
class SnapshotManager:
    """
    快照管理器 - 支持恢复
    """
    
    SNAPSHOT_DIR = "/root/heimaclaw_workspace/.projects/.snapshots"
    KEEP_SNAPSHOTS = 3  # 保留最近 3 个快照
    
    async def create_snapshot(self, project_name: str) -> str:
        """
        创建项目快照
        """
        project_dir = Path(f"/root/heimaclaw_workspace/{project_name}")
        snapshot_dir = Path(self.SNAPSHOT_DIR) / project_name
        
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        
        # 快照文件名：project_v3_20260324_103000.tar.gz
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        snapshot_path = snapshot_dir / f"{project_name}_{timestamp}.tar.gz"
        
        # 创建 tar.gz 快照
        result = await async_run([
            "tar", "-czf", str(snapshot_path),
            "-C", str(project_dir.parent),
            project_name
        ])
        
        # 清理旧快照
        await self._cleanup_old_snapshots(project_name)
        
        return str(snapshot_path)
    
    async def restore_snapshot(self, project_name: str, snapshot_path: str):
        """
        从快照恢复项目
        """
        project_dir = Path(f"/root/heimaclaw_workspace/{project_name}")
        
        # 解压到临时目录
        temp_dir = Path(f"/tmp/restore_{project_name}_{os.getpid()}")
        temp_dir.mkdir(parents=True)
        
        await async_run([
            "tar", "-xzf", snapshot_path,
            "-C", str(temp_dir)
        ])
        
        # 移动到目标位置
        if project_dir.exists():
            shutil.rmtree(project_dir)
        
        shutil.move(str(temp_dir / project_name), str(project_dir))
        
        # 清理临时目录
        shutil.rmtree(temp_dir)
        
        # 更新元数据
        meta = self._load_meta(project_name)
        meta["container"]["status"] = "STOPPED"
        meta["graceful"] = {"markedAt": None, "reason": None, "recoveryAvailable": True}
        self._save_meta(project_name, meta)
    
    async def list_snapshots(self, project_name: str) -> list[dict]:
        """
        列出项目的所有快照
        """
        snapshot_dir = Path(self.SNAPSHOT_DIR) / project_name
        
        if not snapshot_dir.exists():
            return []
        
        snapshots = []
        for f in snapshot_dir.glob("*.tar.gz"):
            stat = f.stat()
            snapshots.append({
                "path": str(f),
                "size": stat.st_size,
                "created": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            })
        
        return sorted(snapshots, key=lambda x: x["created"], reverse=True)
```

---

## 五、命令执行流程（完整）

### 5.1 部署任务执行

```
┌─────────────────────────────────────────────────────────────────┐
│                    部署任务完整流程                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. 接收部署命令                                                  │
│     │ python server.py                                           │
│     ▼                                                            │
│  2. 提取项目名                                                    │
│     │ server.py → 项目目录名                                      │
│     ▼                                                            │
│  3. 检查项目状态                                                  │
│     │                                                            │
│     ├─ 状态=GRACEFUL ──────────────────────────────────────┐    │
│     │  恢复项目 + 重新构建镜像                                  │    │
│     └─ 其他状态 ────────────────────────────────────────────┘    │
│     │                                                            │
│     ▼                                                            │
│  4. 获取/创建容器                                                 │
│     │                                                            │
│     ├─ 容器已存在 ───────────────────────────────────────────┐    │
│     │  启动容器（如已停止）                                      │    │
│     └─ 容器不存在 ───────────────────────────────────────────┘    │
│     │  分析依赖 → 构建镜像 → 创建容器                            │
│     ▼                                                            │
│  5. 执行部署命令                                                  │
│     │ nohup python server.py > /tmp/flask_demo.log 2>&1 &       │
│     ▼                                                            │
│  6. 健康检查                                                      │
│     │ curl http://localhost:5001/health                         │
│     ▼                                                            │
│  7. 返回结果                                                      │
│     │ http://localhost:5001                                      │
│     ▼                                                            │
│  8. 更新元数据                                                    │
│     │ lastAccessed, status=RUNNING                              │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 5.2 容器复用逻辑

```python
async def execute_in_container(command: str, project_name: str):
    """
    在项目中执行命令（容器复用）
    """
    # 1. 获取项目元数据
    meta = project_manager._load_meta(project_name)
    
    # 2. 检查项目状态
    status = meta["container"]["status"]
    
    if status == "GRACEFUL":
        # 项目被标记删除，先恢复
        await project_manager.recover_project(project_name)
        await project_manager.rebuild_project(project_name)
    
    elif status == "DESTROYED":
        # 项目已删除，从快照恢复
        snapshots = snapshot_manager.list_snapshots(project_name)
        if snapshots:
            await snapshot_manager.restore_snapshot(project_name, snapshots[0]["path"])
            await project_manager.rebuild_project(project_name)
        else:
            raise RuntimeError(f"项目 {project_name} 已无法恢复")
    
    elif status == "STOPPED" or status == "IDLE":
        # 启动容器
        await project_manager.start_project(project_name)
    
    elif status == "NONE" or status == "CREATED":
        # 首次创建
        await project_manager.create_project(project_name)
    
    # 3. 在容器中执行命令
    container = await container_pool.get_container(project_name)
    result = await container.execute(command)
    
    # 4. 更新访问时间
    meta["lastAccessed"] = datetime.now().isoformat()
    project_manager._save_meta(project_name, meta)
    
    return result
```

---

## 六、端口管理（完整）

### 6.1 端口池状态

```python
class PortPool:
    """
    端口池 - 全局唯一
    """
    
    def __init__(self, start: int = 5000, end: int = 6000):
        self.port_range = range(start, end)
        self._allocated: dict[str, int] = {}  # project -> host_port
        self._container_ports: dict[str, int] = {}  # project -> container_port
        self._reserved: set[int] = set()  # 被占用的宿主机端口
    
    def allocate(self, project_name: str, container_port: int = 5000) -> int:
        """
        分配端口
        """
        # 1. 检查项目是否已有端口
        if project_name in self._allocated:
            return self._allocated[project_name]
        
        # 2. 尝试分配请求的端口
        if not self._is_port_used(container_port):
            host_port = container_port
        else:
            # 3. 扫描可用端口
            host_port = self._find_available_port()
        
        # 4. 记录分配
        self._allocated[project_name] = host_port
        self._container_ports[project_name] = container_port
        self._reserved.add(host_port)
        
        # 5. 持久化到元数据
        meta = self._load_meta(project_name)
        meta["container"]["hostPorts"][str(container_port)] = host_port
        self._save_meta(project_name, meta)
        
        return host_port
    
    def release(self, project_name: str):
        """
        释放端口（容器销毁时）
        """
        if project_name in self._allocated:
            port = self._allocated.pop(project_name)
            self._reserved.discard(port)
            self._container_ports.pop(project_name, None)
    
    def _is_port_used(self, port: int) -> bool:
        """检查端口是否被占用"""
        # 1. 检查我们记录的
        if port in self._reserved:
            return True
        
        # 2. 检查系统
        result = subprocess.run(
            f"ss -tlnp | grep ':{port}'",
            shell=True, capture_output=True
        )
        return result.returncode == 0
    
    def get_mapping(self, project_name: str) -> dict[int, int]:
        """获取项目的所有端口映射"""
        meta = self._load_meta(project_name)
        return meta["container"]["hostPorts"]
```

---

## 七、与 OpenClaw 架构对比

### 7.1 OpenClaw vs HeiMaClaw

| 维度 | OpenClaw | HeiMaClaw |
|------|----------|-----------|
| **执行代理** | Agent (LLM) | Docker Container |
| **工作空间** | `~/.openclaw/workspace` | `/root/heimaclaw_workspace/<project>` |
| **身份** | Agent ID + display_name | Container ID + project_name |
| **生命周期** | Session → Agent lifecycle | Project lifecycle |
| **隔离** | Sandbox (PTX/Docker) | Docker Container |
| **持久化** | Session transcripts | Project files + Meta |
| **权限控制** | Tool policy + standing orders | Resource limits + project status |
| **查询** | `sessions_list`, `sessions_history` | `ProjectManager.list/get` |

### 7.2 借鉴 OpenClaw 的设计

```python
# 参考 OpenClaw 的 agent 配置，设计容器配置

container_config = {
    "id": "flask_demo",  # 项目名
    "workspace": "/root/heimaclaw_workspace/flask_demo",
    "sandbox": {
        "mode": "docker",  # docker | firecracker | subprocess
        "image": "heimaclaw/flask_demo:latest",
        "resources": {
            "cpu": 1.0,
            "memory": "1g",
        },
    },
    "tools": {
        "allow": ["read", "exec", "pip"],
        "deny": ["browser", "canvas"],
    },
}
```

---

## 八、文件结构

```
/root/dt/ai_coding/heimaclaw/
├── src/heimaclaw/
│   ├── core/
│   │   ├── project_manager.py        # 🆕 项目管理器（查询+管理）
│   │   ├── container_pool.py         # 🆕 容器池
│   │   ├── port_pool.py              # 🆕 端口池
│   │   ├── snapshot_manager.py       # 🆕 快照管理
│   │   ├── graceful_deletion.py      # 🆕 软删除机制
│   │   └── dependency_analyzer.py    # 🆕 依赖分析
│   ├── agent/
│   │   └── docker_backend.py         # 🆕 Docker 后端
│   └── ...
├── docker/
│   └── Dockerfile.base                # 🆕 基础镜像
├── standards/
│   └── DOCKER-SANDBOX-ARCHITECTURE-v2.0.md  # 🆕 本文档
└── config.yaml
```

---

## 九、操作命令汇总

### 9.1 用户可执行的操作

| 操作 | 命令 | 说明 |
|------|------|------|
| 列出项目 | `pm.list_projects()` | 查看所有项目及状态 |
| 查看项目 | `pm.get_project(name)` | 查看项目详情 |
| 查看日志 | `pm.get_container_logs(name)` | 查看容器日志 |
| 查看文件 | `pm.get_project_files(name)` | 查看项目文件结构 |
| 启动项目 | `pm.start_project(name)` | 启动容器 |
| 停止项目 | `pm.stop_project(name)` | 停止容器 |
| 删除项目 | `pm.delete_project(name)` | 软删除（7天冷静期）|
| 强制删除 | `pm.delete_project(name, force=True)` | 硬删除 |
| 恢复项目 | `pm.recover_project(name)` | 恢复软删除的项目 |
| 重建项目 | `pm.rebuild_project(name)` | 重新构建镜像 |
| 查看快照 | `SnapshotManager.list_snapshots(name)` | 查看可用快照 |
| 从快照恢复 | `SnapshotManager.restore(name, path)` | 从快照恢复 |

---

## 十、关键设计决策

| 决策 | 选择 | 理由 |
|------|------|------|
| 软删除 | ✅ 支持 | 防止误删，给用户反悔机会 |
| 冷静期 | 7 天 | 足够用户发现并恢复 |
| 快照保留 | 3 个 | 平衡存储空间与恢复能力 |
| 端口范围 | 5000-6000 | 避免与系统端口冲突 |
| 空闲超时 | 30 分钟 | 平衡资源与响应速度 |
| 最大容器 | 4 个 | 宿主机资源限制 |

---

## 十一、风险与缓解

| 风险 | 缓解措施 |
|------|---------|
| 误删项目 | 软删除 + 7天冷静期 |
| 容器无法启动 | 错误日志 + 自动重试 + 快照恢复 |
| 端口耗尽 | 动态分配 + 及时释放 |
| 磁盘空间不足 | 快照数量限制 + 定期清理 |
| 宿主机重启 | 容器自动重启 + 状态恢复 |

---

_文档版本: v2.0 | 创建: 2026-03-24 | 参考: OpenClaw Delegate Architecture_

---

## 十三、测试报告（2026-03-24）

### 13.1 单元测试结果

| 模块 | 测试内容 | 结果 |
|------|---------|------|
| port_pool | 端口分配/释放 | ✅ 通过 |
| dependency_analyzer | 框架检测 | ✅ 通过 |
| snapshot_manager | 快照创建 | ✅ 通过 |
| graceful_deletion | 软删除/恢复 | ✅ 通过 |
| container_pool | 容器池管理 | ✅ 通过 |
| project_manager | 项目查询/管理 | ✅ 通过 |

### 13.2 集成测试结果

| 测试场景 | 结果 | 说明 |
|---------|------|------|
| 端口池分配 | ✅ | test_project_1:5000 → 5000, test_project_2:5000 → 5001 |
| 依赖分析 | ✅ | 检测到 flask, fastapi, elasticsearch, gradio, streamlit |
| Docker 容器创建 | ✅ | 容器 c975d235472c 运行中 |
| 容器内命令执行 | ✅ | `echo 'Hello from Docker!'` + `python3 --version` 正常 |
| 资源清理 | ⚠️ | 容器停止有 10 秒超时（可接受）|

### 13.3 已知问题

| 问题 | 影响 | 解决方案 |
|------|------|---------|
| 容器停止超时 | 低 | 调整 stop timeout 或使用 docker kill |
| 镜像构建失败回退 | 低 | 自动回退到基础镜像 |

---

_文档版本: v2.0 | 更新: 2026-03-24 | 测试: 通过_

---

## 📋 实现进度 (2026-03-26)

### ✅ 已完成

| 模块 | 文件 | 行数 | 状态 |
|------|------|------|------|
| 基础镜像 | `docker/Dockerfile.base` | 54 | ✅ 已创建 |
| 端口池 | `core/dockerimpl/port_pool.py` | 244 | ✅ 已测试 |
| 依赖分析 | `core/dockerimpl/dependency_analyzer.py` | 323 | ✅ 已测试 |
| 容器池 | `core/dockerimpl/container_pool.py` | 550 | ✅ 已测试 |
| 项目管理 | `core/dockerimpl/project_manager.py` | 498 | ✅ 已测试 |
| 快照管理 | `core/dockerimpl/snapshot_manager.py` | 317 | ✅ 已测试 |
| 优雅删除 | `core/dockerimpl/graceful_deletion.py` | 302 | ✅ 已测试 |
| BaseBackend | `agent/base_backend.py` | 72 | ✅ 新建 |
| DockerBackend | `agent/docker_backend.py` | - | ✅ 修复导入 |
| CLI docker | `cli.py` | +150 | ✅ 5个子命令 |

**代码量统计**: ~2360 行核心代码

### CLI 命令

```bash
heimaclaw docker list     # 列出所有容器
heimaclaw docker stats    # 容器统计
heimaclaw docker cleanup  # 清理空闲容器
heimaclaw docker logs     # 查看日志
heimaclaw docker inspect  # 详细信息
```

### 🔄 进行中

1. **单元测试** - `tests/test_docker_*.py`
2. **集成测试** - 创建真实容器验证

### 📋 待完成

| 优先级 | 任务 | 说明 |
|--------|------|------|
| P1 | 容器创建集成测试 | 验证真实容器创建流程 |
| P1 | 日志功能完善 | 实现容器日志查看 |
| P2 | 快照恢复 | 从快照恢复项目 |
| P2 | 监控告警 | 容器资源监控 |
| P3 | API 服务化 | 提供 HTTP API |

---

## 🧪 单元测试 (2026-03-26)

### 测试文件

| 文件 | 测试数 | 状态 |
|------|--------|------|
| `tests/core/test_port_pool.py` | 12 | ✅ 通过 |
| `tests/core/test_container_pool.py` | 8 | ✅ 通过 |
| `tests/agent/test_docker_backend.py` | 14 | ✅ 通过 |
| **总计** | **34** | **✅ 100%** |

### 运行测试

```bash
cd /root/dt/ai_coding/heimaclaw
PYTHONPATH=/root/dt/ai_coding/heimaclaw/src python3 -m pytest tests/core/test_port_pool.py tests/core/test_container_pool.py tests/agent/test_docker_backend.py -v
```

### 覆盖范围

- **PortPool**: 初始化、分配、释放、统计、边界情况
- **ContainerPool**: 初始化、配置、状态枚举
- **DockerBackend**: 基础操作、项目名提取、服务启停、Mock 执行

### 测试技术

- 使用 `importlib.util` 动态加载模块，避免 `deepagents` 依赖问题
- 使用 `unittest.mock` Mock 对象进行隔离测试
- 使用 `@pytest.mark.asyncio` 测试异步方法

---

## ✅ 集成测试完成 (2026-03-26)

### 测试结果

```
104 passed, 1 skipped, 3 warnings in 2.24s
```

### 集成测试覆盖

| 测试类 | 测试内容 | 状态 |
|--------|----------|------|
| `TestDockerIntegration` | 创建容器、Python执行、多命令 | ✅ 3个 |
| `TestPortPoolIntegration` | 端口分配、优先端口、冲突检测 | ✅ 3个 |
| `TestDependencyAnalyzer` | requirements.txt分析 | ✅ 2个 |

### 真实容器测试验证

```python
# 测试1: 创建容器并执行命令
container = await container_pool.get_container("test_simple")
await container.ensure()
result = await container.execute("echo 'Hello from container'", timeout=60)
# ✅ exit_code=0, "Hello from container" in output

# 测试2: Python执行
result = await container.execute("python3 -c 'print(1 + 2)'", timeout=60)
# ✅ exit_code=0, "3" in output

# 测试3: 多次命令顺序执行（验证容器持久化）
result1 = await container.execute("echo 'first'", timeout=30)
result2 = await container.execute("echo 'second'", timeout=30)
# ✅ 两个命令都成功，容器状态保持
```

### 资源清理

集成测试包含自动清理机制：
- `container_pool` fixture 在测试后清理所有创建的容器
- 使用 `docker rm -f` 确保容器被销毁

---

## 🔧 Agent 工具封装 (2026-03-26)

### 用户说话就能用的工具

现在用户可以通过自然语言调用 Docker 沙箱功能了！

#### 1. docker_snapshot - 快照工具

```python
SNAPSHOT_TOOL_DEFINITION = {
    "name": "docker_snapshot",
    "description": "Docker 项目快照工具 - 保存和恢复项目代码快照"
}
```

**支持的操作：**
- `save` - 保存快照
- `list` - 列出快照
- `restore` - 恢复快照
- `delete` - 删除快照

**用户说话示例：**
```
用户: "帮我保存一下快照"
用户: "看看有哪些快照"
用户: "恢复到之前的版本"
用户: "删除那个快照"
```

#### 2. docker_monitor - 监控工具

```python
MONITOR_TOOL_DEFINITION = {
    "name": "docker_monitor",
    "description": "Docker 容器监控工具 - 查看容器资源使用情况和告警"
}
```

**支持的操作：**
- `status` - 容器状态
- `stats` - 资源统计（CPU、内存）
- `inspect` - 单个容器详情
- `alert` - 资源告警检查

**用户说话示例：**
```
用户: "现在容器状态怎么样？"
用户: "帮我看看内存使用"
用户: "哪个容器用的资源最多？"
```

### 工具注册

工具已注册到 `AgentRunner._register_all_tools()`:
- `docker_project` - 项目管理（已有）
- `docker_snapshot` - 快照管理（新增）
- `docker_monitor` - 监控告警（新增）

### 使用流程

```
用户（飞书消息）
    ↓
Agent 理解意图
    ↓
调用工具: docker_snapshot / docker_monitor / docker_project
    ↓
返回结果给用户
```
