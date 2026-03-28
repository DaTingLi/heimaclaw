"""
Tool Policy - 工具策略引擎

定义:
    - 是什么: 三层执行控制机制
    - 为什么: 保证安全隔离 + 最小权限 + 可控执行
    - 何时触发: Agent 执行任意命令时自动检查
"""

import re
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional


class ExecutionLayer(Enum):
    """执行层级"""
    L1_SANDBOX = "L1"  # 沙箱内执行 (默认)
    L2_ELEVATED = "L2"  # 宿主机执行 (需要权限)
    L3_INTERACTIVE = "L3"  # 用户交互执行


class PolicyAction(Enum):
    """策略动作"""
    ALLOW = "allow"      # ✅ 直接允许
    DENY = "deny"        # ❌ 直接拒绝
    ASK = "ask"          # ❓ 询问用户
    ELEVATED = "elevated"  # 🔓 需要宿主机权限


@dataclass
class ToolPolicyConfig:
    """工具策略配置"""
    mode: str = "allowlist"  # allowlist(白名单) / denylist(黑名单)
    default_action: PolicyAction = PolicyAction.ASK  # 默认动作
    
    # ✅ 白名单 - 允许的工具
    allowlist: list[str] = field(default_factory=lambda: [
        # 开发工具
        "python", "python3", "pip", "pip3",
        "node", "npm", "npx", "yarn",
        "go", "golang",
        "rustc", "cargo",
        "java", "javac", "mvn", "gradle",
        "git", "curl", "wget",
        "claude", "gemini",
        # 文件操作
        "cat", "ls", "cd", "pwd", "mkdir", "touch", "cp", "mv", "rm",
        "tar", "zip", "unzip",
        # 文本处理
        "grep", "sed", "awk", "head", "tail", "sort", "uniq", "wc",
        "find", "xargs",
        # 网络
        "ping", "netstat", "ss",
        # 其他
        "apt-get", "apt", "yum", "dnf",
        "echo", "printf", "sleep", "date",
        "mysql", "mysqld", "mariadb",
    ])
    
    # ❌ 黑名单 - 禁止的工具
    denylist: list[str] = field(default_factory=list)
    
    # 🔓 Elevated 工具 - 需要宿主机权限
    elevated_tools: list[str] = field(default_factory=lambda: [
        "docker", "podman",
        
        
        "pip install --user",
        "chmod +x",
    ])
    
    # ☠️ 危险命令模式 (正则)
    dangerous_patterns: list[str] = field(default_factory=lambda: [
        r"rm\s+-rf\s+/\*?",
        r"mkfs",
        r":\(\)\s*\{\s*:\|\:&\s*\}\s*;:",  # fork bomb
        r"chmod.*\s0{3}",
        r"iptables\s+-F",
        r">\s*/dev/sd[a-z]",
    ])
    
    # 📁 受保护的系统目录
    protected_dirs: list[str] = field(default_factory=lambda: [
        "/etc", "/var", "/bin", "/sbin", "/usr", "/boot", "/sys",
        "/proc", "/dev", "/run", "/root",
    ])


class ToolPolicy:
    """
    工具策略引擎
    
    决策流程:
        Step 1: 危险模式检查 → 直接 DENY
        Step 2: Elevated 检查 → 需要宿主机权限
        Step 3: 白名单/黑名单检查 → ALLOW / ASK
    """
    
    def __init__(self, config: ToolPolicyConfig = None):
        self.config = config or ToolPolicyConfig()
        self._compile_patterns()
    
    def _compile_patterns(self):
        """编译正则模式"""
        self._dangerous_regex = [
            re.compile(p, re.IGNORECASE) 
            for p in self.config.dangerous_patterns
        ]
        self._elevated_regex = [
            re.compile(p, re.IGNORECASE) 
            for p in self.config.elevated_tools
        ]
    
    def check(self, command: str) -> "PolicyResult":
        """
        检查命令是否允许执行
        
        Returns:
            PolicyResult: 包含决策结果
        """
        command = command.strip()
        tool = self._extract_tool(command)
        
        # ========== Step 1: 危险命令 ==========
        if self._match_dangerous(command):
            return PolicyResult(
                action=PolicyAction.DENY,
                layer=ExecutionLayer.L1_SANDBOX,
                tool=tool,
                command=command,
                reason="危险命令，已拦截",
            )
        
        # ========== Step 2: Elevated 检查 ==========
        if self._is_elevated(command):
            return PolicyResult(
                action=PolicyAction.ELEVATED,
                layer=ExecutionLayer.L2_ELEVATED,
                tool=tool,
                command=command,
                reason=f"工具 '{tool}' 需要宿主机权限",
                require_confirm=True,
            )
        
        # ========== Step 3: 名单检查 ==========
        if self.config.mode == "allowlist":
            if tool in self.config.allowlist:
                return PolicyResult(
                    action=PolicyAction.ALLOW,
                    layer=ExecutionLayer.L1_SANDBOX,
                    tool=tool,
                    command=command,
                    reason=f"工具 '{tool}' 在允许列表中",
                )
            else:
                return PolicyResult(
                    action=PolicyAction.ASK,
                    layer=ExecutionLayer.L3_INTERACTIVE,
                    tool=tool,
                    command=command,
                    reason=f"工具 '{tool}' 不在白名单中",
                    require_confirm=True,
                )
        else:
            # 黑名单模式
            if tool in self.config.denylist:
                return PolicyResult(
                    action=PolicyAction.DENY,
                    layer=ExecutionLayer.L1_SANDBOX,
                    tool=tool,
                    command=command,
                    reason=f"工具 '{tool}' 在黑名单中",
                )
            else:
                return PolicyResult(
                    action=PolicyAction.ALLOW,
                    layer=ExecutionLayer.L1_SANDBOX,
                    tool=tool,
                    command=command,
                    reason=f"工具 '{tool}' 不在黑名单中",
                )
    
    def _match_dangerous(self, command: str) -> bool:
        """检查是否匹配危险模式"""
        for regex in self._dangerous_regex:
            if regex.search(command):
                return True
        return False
    
    def _is_elevated(self, command: str) -> bool:
        """检查是否需要 Elevated 权限"""
        for regex in self._elevated_regex:
            if regex.search(command):
                return True
        return False
    
    def _extract_tool(self, command: str) -> str:
        """从命令中提取工具名"""
        parts = command.split()
        return parts[0] if parts else ""
    
    def should_block_path(self, path: str) -> bool:
        """检查路径是否受保护"""
        for protected in self.config.protected_dirs:
            if path.startswith(protected):
                return True
        return False


@dataclass
class PolicyResult:
    """策略检查结果"""
    action: PolicyAction
    layer: ExecutionLayer
    tool: str
    command: str
    reason: str
    require_confirm: bool = False
    
    @property
    def is_allowed(self) -> bool:
        """是否允许执行"""
        return self.action == PolicyAction.ALLOW
    
    @property
    def needs_elevated(self) -> bool:
        """是否需要 Elevated"""
        return self.action == PolicyAction.ELEVATED
    
    @property
    def needs_user_confirm(self) -> bool:
        """是否需要用户确认"""
        return self.action in (PolicyAction.ASK, PolicyAction.ELEVATED)
    
    def __str__(self) -> str:
        icons = {
            PolicyAction.ALLOW: "✅",
            PolicyAction.DENY: "❌",
            PolicyAction.ASK: "❓",
            PolicyAction.ELEVATED: "🔓",
        }
        icon = icons.get(self.action, "❓")
        return f"{icon} [{self.layer.value}] {self.reason}"


# ============ 便捷函数 ============

_default_policy: ToolPolicy = None


def get_default_policy() -> ToolPolicy:
    """获取默认策略实例"""
    global _default_policy
    if _default_policy is None:
        _default_policy = ToolPolicy()
    return _default_policy


def check_command(command: str) -> PolicyResult:
    """快速检查命令"""
    return get_default_policy().check(command)
