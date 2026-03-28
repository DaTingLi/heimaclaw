"""
Agent 路由器 v2.0

支持：
1. 私聊路由
2. 群聊单 Agent 路由
3. 群聊 @提及多 Agent 路由（v0.2）
4. 关键词路由（预留）
"""

import json
from heimaclaw.console import error
import re
from pathlib import Path
from typing import Optional


class AgentRouter:
    """
    Agent 路由器 v2.0

    支持多种路由模式：
    - 私聊：用户绑定 > 默认
    - 群聊单 Agent：群绑定 > 默认
    - 群聊多 Agent：@提及路由 + 群绑定 + 默认
    """

    def __init__(self) -> None:
        """初始化路由器"""
        self._bindings_dir = Path.home() / ".heimaclaw" / "bindings"
        self._bindings_dir.mkdir(parents=True, exist_ok=True)

        # 绑定配置文件
        self._bindings_file = self._bindings_dir / "bindings.json"

        # 群组多 Agent 配置
        self._groups_config_file = self._bindings_dir / "groups.json"

        # 加载绑定配置
        self._bindings: dict[str, str] = {}
        self._group_configs: dict[str, dict] = {}
        self._load_bindings()
        self._load_group_configs()

    def _load_bindings(self) -> None:
        """加载绑定配置"""
        if self._bindings_file.exists():
            try:
                with open(self._bindings_file, encoding="utf-8") as f:
                    self._bindings = json.load(f)
            except Exception:
                self._bindings = {}

    def _save_bindings(self) -> None:
        """保存绑定配置"""
        try:
            with open(self._bindings_file, "w", encoding="utf-8") as f:
                json.dump(self._bindings, f, indent=2, ensure_ascii=False)
        except Exception as e:
            error(f"保存绑定配置失败: {e}")

    def _load_group_configs(self) -> None:
        """加载群组多 Agent 配置"""
        if self._groups_config_file.exists():
            try:
                with open(self._groups_config_file, encoding="utf-8") as f:
                    self._group_configs = json.load(f)
            except Exception:
                self._group_configs = {}

    def _save_group_configs(self) -> None:
        """保存群组多 Agent 配置"""
        try:
            with open(self._groups_config_file, "w", encoding="utf-8") as f:
                json.dump(self._group_configs, f, indent=2, ensure_ascii=False)
        except Exception as e:
            error(f"保存群组配置失败: {e}")

    def parse_mentions(self, content: str) -> list[str]:
        """
        解析消息中的 @提及

        参数:
            content: 消息内容

        返回:
            被 @ 的 Agent 名称列表
        """
        # 匹配 @名字 的模式
        pattern = r"@([\w\u4e00-\u9fff]+)"
        mentions = re.findall(pattern, content)
        return mentions

    def route(
        self,
        user_id: str,
        chat_id: Optional[str] = None,
        is_group: bool = False,
    ) -> str:
        """
        路由到对应的 Agent（单 Agent 模式）

        参数:
            user_id: 用户 ID
            chat_id: 会话 ID（群聊时为群 ID）
            is_group: 是否群聊

        返回:
            Agent 名称
        """
        # 群聊优先级：群绑定 > 默认
        if is_group and chat_id:
            group_key = f"group:{chat_id}"
            if group_key in self._bindings:
                return self._bindings[group_key]

        # 私聊优先级：用户绑定 > 默认
        user_key = f"user:{user_id}"
        if user_key in self._bindings:
            return self._bindings[user_key]

        # 返回默认 Agent
        return self._bindings.get("default", "default")

    def route_with_mentions(
        self,
        content: str,
        user_id: str,
        chat_id: Optional[str] = None,
        is_group: bool = False,
    ) -> list[str]:
        """
        路由到对应的 Agent（@提及多 Agent 模式）

        参数:
            content: 消息内容
            user_id: 用户 ID
            chat_id: 会话 ID（群聊时为群 ID）
            is_group: 是否群聊

        返回:
            Agent 名称列表（按优先级排序）
        """
        agents: list[str] = []
        seen: set[str] = set()

        # 1. 解析 @提及
        mentions = self.parse_mentions(content)
        for mention in mentions:
            agent = self._find_agent_by_name(mention)
            if agent and agent not in seen:
                agents.append(agent)
                seen.add(agent)

        # 2. 如果有 @提及，返回被 @ 的 Agents
        if agents:
            return agents

        # 3. 没有 @提及，使用默认路由
        default_agent = self.route(user_id, chat_id, is_group)
        if default_agent not in seen:
            agents.append(default_agent)

        return agents

    def _find_agent_by_name(self, name: str) -> Optional[str]:
        """
        根据名称查找 Agent（模糊匹配）

        参数:
            name: Agent 名称或 @后的名字

        返回:
            Agent 名称，未找到返回 None
        """
        # 清理名称（移除 @ 和空格）
        name = name.strip().lstrip("@")

        # 检查是否是完整的 Agent 名称
        agent_dir = Path.home() / ".heimaclaw" / "agents" / name
        if agent_dir.exists():
            return name

        # 模糊匹配：查找名称中包含关键词的 Agent
        agents_dir = Path.home() / ".heimaclaw" / "agents"
        if not agents_dir.exists():
            return None

        name_lower = name.lower()
        for agent_path in agents_dir.iterdir():
            if agent_path.is_dir():
                agent_name = agent_path.name.lower()
                if name_lower in agent_name or agent_name in name_lower:
                    return agent_path.name

        return None

    def route_by_keywords(
        self,
        content: str,
        user_id: str,
        chat_id: Optional[str] = None,
        is_group: bool = False,
    ) -> list[str]:
        """
        根据关键词路由（预留功能）

        参数:
            content: 消息内容
            user_id: 用户 ID
            chat_id: 会话 ID
            is_group: 是否群聊

        返回:
            Agent 名称列表
        """
        # 预留：关键词路由功能
        # 从群组配置中读取关键词配置
        if is_group and chat_id:
            group_config = self._group_configs.get(chat_id, {})
            keyword_routing = group_config.get("keyword_routing", {})

            content_lower = content.lower()
            matched_agents: list[str] = []
            seen: set[str] = set()

            for agent_name, keywords in keyword_routing.items():
                for keyword in keywords:
                    if keyword.lower() in content_lower:
                        if agent_name not in seen:
                            matched_agents.append(agent_name)
                            seen.add(agent_name)
                        break

            if matched_agents:
                return matched_agents

        # 回退到默认路由
        default_agent = self.route(user_id, chat_id, is_group)
        return [default_agent]

    # ==================== 绑定管理 ====================

    def bind_user(self, user_id: str, agent_name: str) -> None:
        """绑定用户到 Agent"""
        self._bindings[f"user:{user_id}"] = agent_name
        self._save_bindings()

    def bind_group(self, chat_id: str, agent_name: str) -> None:
        """绑定群聊到 Agent（单 Agent 模式）"""
        self._bindings[f"group:{chat_id}"] = agent_name
        self._save_bindings()

    def unbind_user(self, user_id: str) -> None:
        """解绑用户"""
        self._bindings.pop(f"user:{user_id}", None)
        self._save_bindings()

    def unbind_group(self, chat_id: str) -> None:
        """解绑群聊"""
        self._bindings.pop(f"group:{chat_id}", None)
        self._save_bindings()

    def set_default(self, agent_name: str) -> None:
        """设置默认 Agent"""
        self._bindings["default"] = agent_name
        self._save_bindings()

    def get_bindings(self) -> dict[str, str]:
        """获取所有绑定"""
        return self._bindings.copy()

    def clear_bindings(self) -> None:
        """清空所有绑定"""
        self._bindings.clear()
        self._save_bindings()

    # ==================== 群组多 Agent 配置 ====================

    def configure_group_multi_agent(
        self,
        chat_id: str,
        mode: str = "mention",
        agents: list[str] = None,
        default: str = None,
        keyword_routing: dict[str, list[str]] = None,
    ) -> None:
        """
        配置群组多 Agent

        参数:
            chat_id: 群 ID
            mode: 路由模式 ("mention" | "keyword" | "both")
            agents: 可用的 Agent 列表
            default: 默认 Agent
            keyword_routing: 关键词路由配置
        """
        self._group_configs[chat_id] = {
            "mode": mode,
            "agents": agents or [],
            "default": default,
            "keyword_routing": keyword_routing or {},
        }
        self._save_group_configs()

    def get_group_config(self, chat_id: str) -> Optional[dict]:
        """获取群组配置"""
        return self._group_configs.get(chat_id)

    def remove_group_config(self, chat_id: str) -> None:
        """移除群组配置"""
        self._group_configs.pop(chat_id, None)
        self._save_group_configs()

    def get_all_group_configs(self) -> dict[str, dict]:
        """获取所有群组配置"""
        return self._group_configs.copy()
