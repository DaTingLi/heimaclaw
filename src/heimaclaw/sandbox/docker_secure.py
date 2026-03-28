"""
HeiMaClaw 安全沙箱配置

符合 OpenClaw 沙箱安全标准：
- 网络隔离: none (默认)
- 用户权限: 非 root
- 能力限制: cap_drop=ALL
- 根文件系统只读
- PID/内存限制
- 临时文件系统隔离
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SandboxDockerConfig:
    """
    Docker 沙箱安全配置
    
    参考 OpenClaw agents.defaults.sandbox.docker
    """
    
    # 镜像
    image: str = "python:3.10-slim"
    container_prefix: str = "heimaclaw-sbx-"
    
    # 工作目录
    workdir: str = "/workspace"
    
    # 安全: 根文件系统只读
    read_only_root: bool = True
    
    # 安全: 非 root 用户
    user: str = "1000:1000"
    
    # 安全: 移除所有 capabilities
    cap_drop: list = field(default_factory=lambda: ["ALL"])
    
    # 网络隔离
    network: str = "none"  # none | bridge | "host" 被禁止
    
    # 临时文件系统
    tmpfs: list = field(default_factory=lambda: ["/tmp", "/var/tmp", "/run"])
    
    # 内存限制
    memory: str = "1g"
    memory_swap: str = "2g"
    
    # CPU 限制
    cpus: int = 1
    
    # PID 限制
    pids_limit: int = 256
    
    # Ulimits
    ulimits: dict = field(default_factory=lambda: {
        "nofile": {"soft": 1024, "hard": 2048},
        "nproc": {"soft": 256, "hard": 512},
    })
    
    # DNS
    dns: list = field(default_factory=lambda: ["1.1.1.1", "8.8.8.8"])
    
    # 额外 hosts
    extra_hosts: list = field(default_factory=list)
    
    # 环境变量
    env: dict = field(default_factory=lambda: {"LANG": "C.UTF-8"})
    
    # 一次性初始化命令
    setup_command: str = ""
    
    # === 验证方法 ===
    
    def validate(self) -> list[str]:
        """
        验证配置安全性，返回错误列表
        
        Returns:
            错误消息列表，空列表表示验证通过
        """
        errors = []
        
        # 网络安全检查
        if self.network == "host":
            errors.append("网络模式 'host' 被安全策略禁止，请使用 'none' 或 'bridge'")
        if self.network.startswith("container:"):
            errors.append("网络模式 'container:<id>' 被安全策略禁止")
        
        # 镜像安全检查
        if not self.image or not self.image.strip():
            errors.append("镜像不能为空")
        
        # 用户格式检查
        if self.user:
            parts = self.user.split(":")
            if len(parts) != 2 or not all(p.isdigit() for p in parts):
                errors.append(f"用户格式错误: {self.user} (应为 UID:GID)")
        
        # 内存限制检查
        if self.memory:
            if not self._is_valid_memory(self.memory):
                errors.append(f"内存限制格式错误: {self.memory}")
        
        return errors
    
    @staticmethod
    def _is_valid_memory(s: str) -> bool:
        """检查内存格式是否有效 (如 '1g', '512m')"""
        import re
        return bool(re.match(r'^\d+[kmgKMG]$', s))
    
    def build_docker_run_args(self, container_name: str, volumes: dict = None) -> list[str]:
        """
        构建安全的 docker run 参数
        
        Returns:
            docker run 参数列表
        """
        args = ["docker", "run", "-d"]
        
        # 容器名称
        args.extend(["--name", container_name])
        
        # 网络隔离
        if self.network == "none":
            args.extend(["--network", "none"])
        elif self.network:
            args.extend(["--network", self.network])
        
        # 主机名
        args.extend(["--hostname", container_name.replace("heimaclaw-sbx-", "")])
        
        # 安全: 用户权限
        if self.user:
            args.extend(["--user", self.user])
        
        # 安全: 限制 capabilities
        for cap in self.cap_drop:
            args.extend(["--cap-drop", cap])
        
        # 安全: 根文件系统只读
        if self.read_only_root:
            args.append("--read-only")
        
        # 安全: PID 限制
        args.extend(["--pids-limit", str(self.pids_limit)])
        
        # 内存限制
        args.extend(["--memory", self.memory])
        if self.memory_swap:
            args.extend(["--memory-swap", self.memory_swap])
        
        # CPU 限制
        args.extend(["--cpus", str(self.cpus)])
        
        # Ulimits
        for name, limits in self.ulimits.items():
            args.extend([
                "--ulimit", f"{name}={limits['soft']}:{limits['hard']}"
            ])
        
        # 临时文件系统
        for mount in self.tmpfs:
            args.extend(["--tmpfs", f"{mount}:rw,noexec,nosuid,size=64m"])
        
        # DNS
        for d in self.dns:
            args.extend(["--dns", d])
        
        # 额外 hosts
        for h in self.extra_hosts:
            args.extend(["--add-host", h])
        
        # 环境变量
        for k, v in self.env.items():
            args.extend(["-e", f"{k}={v}"])
        
        # 卷挂载
        if volumes:
            for host_path, container_path in volumes.items():
                args.extend(["-v", f"{host_path}:{container_path}:rw"])
        
        # 工作目录
        args.extend(["-w", self.workdir])
        
        # 镜像
        args.append(self.image)
        
        # 命令
        args.extend(["sleep", "infinity"])
        
        return args
    
    def get_security_opt(self) -> list[str]:
        """获取安全选项"""
        opts = []
        if self.apparmor_profile:
            opts.append(f"apparmor:{self.apparmor_profile}")
        if self.seccomp_profile:
            opts.append(f"seccomp:{self.seccomp_profile}")
        return ["--security-opt", opt] if opts else []


@dataclass  
class SandboxConfig:
    """
    完整沙箱配置
    
    参考 OpenClaw agents.defaults.sandbox
    """
    
    # 是否启用沙箱
    enabled: bool = True
    
    # 模式: off | non-main | all
    mode: str = "all"
    
    # 范围: session | agent | shared
    scope: str = "agent"
    
    # 工作区访问: none | ro | rw
    workspace_access: str = "rw"
    
    # Docker 配置
    docker: SandboxDockerConfig = field(default_factory=SandboxDockerConfig)
    
    # 清理策略
    prune_idle_hours: int = 24
    prune_max_age_days: int = 7
    
    def validate(self) -> list[str]:
        """验证完整配置"""
        errors = []
        
        if self.mode not in ["off", "non-main", "all"]:
            errors.append(f"沙箱模式无效: {self.mode}")
        
        if self.scope not in ["session", "agent", "shared"]:
            errors.append(f"沙箱范围无效: {self.scope}")
        
        if self.workspace_access not in ["none", "ro", "rw"]:
            errors.append(f"工作区访问模式无效: {self.workspace_access}")
        
        errors.extend(self.docker.validate())
        
        return errors


# 默认安全配置
DEFAULT_SANDBOX_CONFIG = SandboxConfig(
    enabled=True,
    mode="all",
    scope="agent", 
    workspace_access="rw",
    docker=SandboxDockerConfig(
        image="python:3.10-slim",
        network="none",  # 默认无网络（安全）
        read_only_root=True,
        user="1000:1000",
        cap_drop=["ALL"],
        pids_limit=256,
        memory="1g",
        memory_swap="2g",
        tmpfs=["/tmp", "/var/tmp", "/run"],
    )
)
