"""
Agent 路由器

根据消息来源（用户/群聊）路由到对应的 Agent。
"""

import json
from pathlib import Path
from typing import Optional


class AgentRouter:
    """
    Agent 路由器

    根据消息来源路由到对应的 Agent：
    1. 私聊：查找该用户的绑定 Agent
    2. 群聊：查找该群的绑定 Agent
    3. 默认：使用默认 Agent
    """

    def __init__(self) -> None:
        """初始化路由器"""
        self._bindings_dir = Path.home() / ".heimaclaw" / "bindings"
        self._bindings_dir.mkdir(parents=True, exist_ok=True)

        # 绑定配置文件
        self._bindings_file = self._bindings_dir / "bindings.json"

        # 加载绑定配置
        self._bindings: dict[str, str] = {}
        self._load_bindings()

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
            print(f"保存绑定配置失败: {e}")

    def route(
        self,
        user_id: str,
        chat_id: Optional[str] = None,
        is_group: bool = False,
    ) -> str:
        """
        路由到对应的 Agent

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

    def bind_user(self, user_id: str, agent_name: str) -> None:
        """
        绑定用户到 Agent

        参数:
            user_id: 用户 ID
            agent_name: Agent 名称
        """
        self._bindings[f"user:{user_id}"] = agent_name
        self._save_bindings()

    def bind_group(self, chat_id: str, agent_name: str) -> None:
        """
        绑定群聊到 Agent

        参数:
            chat_id: 群 ID
            agent_name: Agent 名称
        """
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
