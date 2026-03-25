# HeiMaClaw 沙箱规范 v1.0

> 参考 OpenClaw 沙箱机制，实现与 OpenClaw 一致的沙箱架构

---

## 一、OpenClaw 沙箱核心功能

| 功能 | OpenClaw | HeiMaClaw (当前) | 目标 |
|------|-----------|-------------------|------|
| **沙箱模式** | off / non-main / all | 无 | ✅ 实现 |
| **沙箱范围** | session / agent / shared | agent (固定) | ✅ 扩展 |
| **工作区访问** | none / ro / rw | rw (固定) | ✅ 扩展 |
| **网络隔离** | none (默认) / bridge | host | 🔴 修复 |
| **Root 只读** | readOnlyRoot | ❌ 无 | ✅ 实现 |
| **用户权限** | user: 1000:1000 | root | 🔴 修复 |
| **能力限制** | capDrop: ALL | ❌ 无 | ✅ 实现 |
| **PID 限制** | pidsLimit: 256 | ❌ 无 | ✅ 实现 |
| **内存限制** | memory + memorySwap | 只有 memory | ✅ 扩展 |
| **临时文件系统** | tmpfs: [/tmp, /var/tmp] | ❌ 无 | ✅ 实现 |
| **工具策略** | allow/deny list | ❌ 无 | ✅ 实现 |
| **Setup 命令** | setupCommand | ❌ 无 | ✅ 实现 |
| **容器清理** | prune (idle/maxAge) | ❌ 无 | ✅ 实现 |
| **Seccomp** | seccompProfile | ❌ 无 | ✅ 实现 |
| **AppArmor** | apparmorProfile | ❌ 无 | ✅ 实现 |
| **DNS 配置** | dns: [] | ❌ 无 | ✅ 实现 |
| **额外 hosts** | extraHosts: [] | ❌ 无 | ✅ 实现 |
| **沙箱浏览器** | noVNC + CDP 隔离 | ❌ 无 | 🔜 未来 |

---

## 二、目标配置结构

### 2.1 Agent 配置中的沙箱选项

```json
{
  "name": "coder_heima",
  "display_name": "heima_coder",
  "sandbox": {
    "enabled": true,
    "mode": "all",           // off | non-main | all
    "scope": "agent",         // session | agent | shared
    "workspace_access": "rw", // none | ro | rw
    
    "docker": {
      "image": "heimaclaw-sandbox:bookworm-slim",
      "container_prefix": "heimaclaw-sbx-",
      "workdir": "/workspace",
      "read_only_root": true,
      
      "tmpfs": ["/tmp", "/var/tmp", "/run"],
      "network": "none",       // none | bridge | host (host 被禁止)
      "user": "1000:1000",
      "cap_drop": ["ALL"],
      
      "memory": "1g",
      "memory_swap": "2g",
      "cpus": 1,
      
      "pids_limit": 256,
      "ulimits": {
        "nofile": { "soft": 1024, "hard": 2048 },
        "nproc": { "soft": 256, "hard": 512 }
      },
      
      "dns": ["1.1.1.1", "8.8.8.8"],
      "extra_hosts": [],
      
      "seccomp_profile": "/etc/heima/seccomp.json",
      "apparmor_profile": "heimaclaw-sandbox",
      
      "env": {
        "LANG": "C.UTF-8"
      },
      
      "setup_command": "apt-get update && apt-get install -y git curl jq"
    },
    
    "prune": {
      "idle_hours": 24,
      "max_age_days": 7
    }
  }
}
```

### 2.2 工具策略配置

```json
{
  "tools": {
    "sandbox": {
      "tools": {
        "allow": [
          "exec",
          "read_file",
          "write_file", 
          "docker_project",
          "expose",
          "write_todos"
        ],
        "deny": [
          "systemctl",
          "service",
          "reboot",
          "shutdown",
          "mount",
          "umount"
        ]
      }
    }
  }
}
```

---

## 三、网络安全（关键修复）

### 3.1 当前问题

```python
# 当前: --net=host (危险!)
docker run -d --net=host ...
```

**问题**：
- 容器完全共享宿主机网络栈
- 容器内可以访问宿主机任意端口
- 违反最小权限原则

### 3.2 OpenClaw 方式

```python
# 默认: 无网络
docker run -d --network=none ...

# 可选: bridge (需要时)
docker run -d --network=bridge ...

# 禁止: host (除非 break-glass)
if network == "host":
    raise SecurityError("host network is forbidden")
```

### 3.3 修复方案

```python
SECURITY_BLOCKED_NETWORKS = ["host"]

def validate_network_mode(network: str) -> str:
    if network == "host":
        raise SecurityError("host network is forbidden by security policy")
    if network == "container:*":
        raise SecurityError("container namespace join is forbidden")
    return network
```

---

## 四、安全加固

### 4.1 必须的安全参数

| 参数 | 推荐值 | 说明 |
|------|--------|------|
| `--read-only-root-filesystem` | true | 根文件系统只读 |
| `--cap-drop=ALL` | 必须 | 移除所有 Linux capabilities |
| `--user=1000:1000` | 必须 | 非 root 用户运行 |
| `--pids-limit=256` | 必须 | 限制进程数 |
| `--memory=1g --memory-swap=2g` | 必须 | 内存限制 + swap |
| `--ulimit` | 推荐 | 文件描述符/进程数限制 |
| `--tmpfs /tmp` | 推荐 | 临时文件在内存中 |

### 4.2 Seccomp 配置

```json
// /etc/heima/seccomp.json
{
  "defaultAction": "SCMP_ACT_ERRNO",
  "syscalls": [
    { "names": ["read", "write", "open", "close"], "action": "SCMP_ACT_ALLOW" },
    { "names": ["exit", "exit_group"], "action": "SCMP_ACT_ALLOW" },
    // ... 白名单外的 syscall 都会被阻止
  ]
}
```

### 4.3 危险命令拦截（保持）

```python
DANGEROUS_PATTERNS = [
    r"\brm\s+-[rf]{1,2}\s+/",      # rm -rf /
    r"\bmkfs\b",
    r"\bdd\s+if=",
    r"\bfdisk\b",
    r"\bparted\b",
    r"\bchroot\b",
    r"\bmknod\b",
    r"\bswapoff\b",
    r"\bifconfig\b.*down",
    r"\broute\s+del\s+default",
]
```

---

## 五、沙箱镜像

### 5.1 推荐镜像

```dockerfile
# 基于 Debian Bookworm Slim
FROM debian:bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV LANG=C.UTF-8

# 安装常用工具
RUN apt-get update && apt-get install -y \
    git curl wget jq \
    python3 python3-pip python3-venv \
    nodejs npm \
    file tree zip unzip \
    && rm -rf /var/lib/apt/lists/*

# 安全加固
RUN useradd -m -s /bin/bash sandbox && \
    mkdir -p /workspace && \
    chown -R sandbox:sandbox /workspace

USER sandbox
WORKDIR /workspace

CMD ["sleep", "infinity"]
```

### 5.2 构建命令

```bash
docker build -t heimaclaw-sandbox:bookworm-slim -f Dockerfile.bookworm .
docker build -t heimaclaw-sandbox-common:bookworm-slim -f Dockerfile.common .
```

---

## 六、实现计划

### Phase 1: 核心安全修复（最高优先级）

| 任务 | 文件 | 说明 |
|------|------|------|
| 移除 `--net=host` | `sandbox/docker.py` | 改为 `network=none` |
| 添加用户权限 | `sandbox/docker.py` | `--user=1000:1000` |
| 添加 `cap-drop=ALL` | `sandbox/docker.py` | 移除所有 capabilities |
| 添加 `read-only-root` | `sandbox/docker.py` | 根文件系统只读 |
| 添加 `pids-limit` | `sandbox/docker.py` | 限制进程数 |
| 添加 `tmpfs` | `sandbox/docker.py` | /tmp 在内存中 |
| 添加内存限制 | `sandbox/docker.py` | memory + memorySwap |

### Phase 2: 配置结构

| 任务 | 文件 | 说明 |
|------|------|------|
| 定义 SandboxConfig | `sandbox/config.py` | 配置模型 |
| 添加沙箱配置到 Agent | `agent/manager.py` | sandbox 字段 |
| 实现配置验证 | `sandbox/config.py` | 安全验证 |

### Phase 3: 工具策略

| 任务 | 文件 | 说明 |
|------|------|------|
| 定义工具策略 | `tools/policy.py` | allow/deny 列表 |
| 工具执行前检查 | `tools/registry.py` | 执行前验证 |
| 添加 system 工具到 deny | - | systemctl 等 |

### Phase 4: 生命周期管理

| 任务 | 文件 | 说明 |
|------|------|------|
| 实现 setupCommand | `sandbox/executor.py` | 容器创建后一次性命令 |
| 实现 prune 策略 | `sandbox/manager.py` | 空闲/过期容器清理 |

### Phase 5: 工具策略

- [ ] 实现工具 allow/deny 策略
- [ ] 添加 systemctl/service 到危险命令

---

## 七、安全检查清单

```
✅ 网络模式不是 host
✅ 不是 root 用户运行
✅ cap_drop = ALL
✅ read_only_root = true
✅ pids_limit 设置
✅ memory_limit 设置
✅ tmpfs /tmp 设置
✅ 工具 deny 列表包含危险命令
✅ Seccomp 配置
```

---

*本文档为 HeiMaClaw 内部标准，参考 OpenClaw 沙箱文档实现。*
*参考: OpenClaw docs/gateway/sandboxing.md*
