"""
Agent 策略配置模块

定义 Agent 的响应策略：
- mode: mention（@才响应）/ open（所有人）/ disabled（禁用）
- scope: private（私聊）/ group（群聊）/ both（都支持）
"""

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional


class PolicyMode(str, Enum):
    """响应模式"""

    MENTION = "mention"  # 只响应 @提及
    OPEN = "open"  # 响应所有人
    DISABLED = "disabled"  # 禁用


class PolicyScope(str, Enum):
    """作用范围"""

    PRIVATE = "private"  # 只私聊
    GROUP = "group"  # 只群聊
    BOTH = "both"  # 两者都支持


@dataclass
class AgentPolicy:
    """Agent 策略配置"""

    mode: PolicyMode = PolicyMode.MENTION
    scope: PolicyScope = PolicyScope.BOTH
    allow_all_users: bool = True  # 允许所有用户
    allow_all_groups: bool = True  # 允许所有群
    whitelist_users: list[str] = field(default_factory=list)  # 用户白名单
    whitelist_groups: list[str] = field(default_factory=list)  # 群白名单

    def should_respond(
        self,
        is_group: bool,
        user_id: Optional[str] = None,
        group_id: Optional[str] = None,
        has_mention: bool = False,
    ) -> bool:
        """
        判断是否应该响应

        参数:
            is_group: 是否群聊
            user_id: 用户 ID
            group_id: 群 ID
            has_mention: 是否有 @提及

        返回:
            True = 应该响应，False = 不响应
        """
        # 1. 检查范围
        if is_group and self.scope == PolicyScope.PRIVATE:
            return False
        if not is_group and self.scope == PolicyScope.GROUP:
            return False

        # 2. 禁用模式
        if self.mode == PolicyMode.DISABLED:
            return False

        # 3. 开放模式
        if self.mode == PolicyMode.OPEN:
            return self._check_whitelist(is_group, user_id, group_id)

        # 4. @提及模式
        if self.mode == PolicyMode.MENTION:
            # 群聊必须有 @提及
            if is_group and not has_mention:
                return False
            # 私聊直接响应
            return self._check_whitelist(is_group, user_id, group_id)

        return False

    def _check_whitelist(
        self,
        is_group: bool,
        user_id: Optional[str],
        group_id: Optional[str],
    ) -> bool:
        """检查白名单"""
        # 全局允许
        if not is_group and self.allow_all_users:
            return True
        if is_group and self.allow_all_groups:
            return True

        # 检查白名单
        if user_id and user_id in self.whitelist_users:
            return True
        if group_id and group_id in self.whitelist_groups:
            return True

        return False

    def to_dict(self) -> dict:
        """序列化为字典"""
        return {
            "mode": self.mode.value,
            "scope": self.scope.value,
            "allow_all_users": self.allow_all_users,
            "allow_all_groups": self.allow_all_groups,
            "whitelist_users": self.whitelist_users,
            "whitelist_groups": self.whitelist_groups,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AgentPolicy":
        """从字典反序列化"""
        if not data:
            return cls()

        return cls(
            mode=PolicyMode(data.get("mode", PolicyMode.MENTION.value)),
            scope=PolicyScope(data.get("scope", PolicyScope.BOTH.value)),
            allow_all_users=data.get("allow_all_users", True),
            allow_all_groups=data.get("allow_all_groups", True),
            whitelist_users=data.get("whitelist_users", []),
            whitelist_groups=data.get("whitelist_groups", []),
        )


class PolicyManager:
    """
    策略管理器

    负责加载和管理所有 Agent 的策略配置。
    支持从 agent.json 自动加载，无需单独配置群组。
    """

    def __init__(self):
        self._policies: dict[str, AgentPolicy] = {}
        self._load_all_policies()

    def _load_all_policies(self) -> None:
        """加载所有 Agent 的策略配置"""
        agents_dir = Path.home() / ".heimaclaw" / "agents"
        if not agents_dir.exists():
            return

        for agent_dir in agents_dir.iterdir():
            if not agent_dir.is_dir():
                continue

            config_file = agent_dir / "agent.json"
            if not config_file.exists():
                continue

            try:
                with open(config_file, encoding="utf-8") as f:
                    config = json.load(f)

                agent_name = config.get("name", agent_dir.name)
                policy_data = config.get("policy", {})

                self._policies[agent_name] = AgentPolicy.from_dict(policy_data)

            except (json.JSONDecodeError, IOError):
                # 使用默认策略
                self._policies[agent_dir.name] = AgentPolicy()

    def reload(self) -> None:
        """重新加载所有策略"""
        self._policies.clear()
        self._load_all_policies()

    def get_policy(self, agent_name: str) -> AgentPolicy:
        """获取 Agent 的策略"""
        if agent_name not in self._policies:
            self._policies[agent_name] = AgentPolicy()
        return self._policies[agent_name]

    def set_policy(self, agent_name: str, policy: AgentPolicy) -> None:
        """设置 Agent 的策略"""
        self._policies[agent_name] = policy
        self._save_policy_to_agent(agent_name, policy)

    def _save_policy_to_agent(self, agent_name: str, policy: AgentPolicy) -> None:
        """保存策略到 agent.json"""
        agents_dir = Path.home() / ".heimaclaw" / "agents"
        config_file = agents_dir / agent_name / "agent.json"

        if not config_file.exists():
            return

        try:
            with open(config_file, encoding="utf-8") as f:
                config = json.load(f)

            config["policy"] = policy.to_dict()

            with open(config_file, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2, ensure_ascii=False)

        except (json.JSONDecodeError, IOError):
            pass

    def should_respond(
        self,
        agent_name: str,
        is_group: bool,
        user_id: Optional[str] = None,
        group_id: Optional[str] = None,
        has_mention: bool = False,
    ) -> bool:
        """判断 Agent 是否应该响应"""
        policy = self.get_policy(agent_name)
        return policy.should_respond(is_group, user_id, group_id, has_mention)

    def get_all_policies(self) -> dict[str, AgentPolicy]:
        """获取所有策略"""
        return self._policies.copy()
