"""
记忆管理工具 v2 - 自然语言 + SQLite 持久化

改进：
1. SQLite 持久化存储
2. 自然语言响应包装
3. 智能记忆检索
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from heimaclaw.memory.sqlite_saver import get_memory_saver


# 自然语言响应模板
NATURE_RESPONSES = {
    "memory_found": [
        "让我想想...我记得你说过{content}",
        "对！你之前告诉过我{content}",
        "我记得你提到过{content}",
    ],
    "memory_not_found": [
        "嗯...我目前还没有记住这方面的信息，下次记得告诉我哦~",
        "这个我还不了解，要不你告诉我一下？",
        "我暂时没有这方面的记忆，你补充一下我会记得更清楚~",
    ],
    "memory_saved": [
        "好的，我记住啦！{content}",
        "收到！这个我记住了：{content}",
        "没问题，我已经在记忆里加上：{content}",
    ],
}


def _get_natural_response(template_key: str, **kwargs) -> str:
    """获取自然语言响应"""
    import random
    templates = NATURE_RESPONSES.get(template_key, [])
    if not templates:
        return "好的。"
    
    template = random.choice(templates)
    try:
        return template.format(**kwargs)
    except KeyError:
        return template


class NaturalLanguageMemory:
    """
    自然语言记忆管理器
    
    提供更友好的记忆交互
    """
    
    def __init__(self, agent_id: str = "default", user_id: str = None):
        self.agent_id = agent_id
        self.user_id = user_id
        self.saver = get_memory_saver()
    
    async def remember(self, preference: str, category: str = "general") -> str:
        """
        记忆偏好 - 带自然语言包装
        """
        # 保存到 SQLite
        success = self.saver.save_memory(
            agent_id=self.agent_id,
            user_id=self.user_id,
            category=category,
            content=preference,
            importance=7,  # 用户偏好优先级较高
        )
        
        if success:
            return _get_natural_response("memory_saved", content=preference)
        else:
            return "抱歉，记忆保存失败了..."
    
    async def recall(self, query: str = None, category: str = None) -> tuple[str, bool]:
        """
        回忆记忆 - 带自然语言包装
        
        Returns:
            (response, found)
        """
        memories = self.saver.search_memories(
            agent_id=self.agent_id,
            user_id=self.user_id,
            query=query,
            category=category,
            limit=5,
        )
        
        if not memories:
            return _get_natural_response("memory_not_found"), False
        
        # 构建自然语言响应
        if len(memories) == 1:
            content = memories[0]["content"]
            return _get_natural_response("memory_found", content=content), True
        else:
            # 多个记忆，用自然语言组合
            items = [m["content"] for m in memories[:3]]
            if len(items) == 2:
                content = f"你说过{items[0]}，还有{items[1]}"
            else:
                content = f"你说过{items[0]}"
            return _get_natural_response("memory_found", content=content), True
    
    async def search_natural(self, query: str) -> str:
        """
        自然语言搜索
        
        用户问"你知道我喜欢什么吗"，返回自然语言
        """
        memories = self.saver.search_memories(
            agent_id=self.agent_id,
            user_id=self.user_id,
            query=query,
            limit=10,
        )
        
        if not memories:
            return _get_natural_response("memory_not_found")
        
        # 按类别分组
        by_category = {}
        for m in memories:
            cat = m.get("category", "other")
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(m["content"])
        
        # 构建自然语言响应
        parts = []
        if "food" in by_category:
            parts.append(f"美食方面，你喜欢{'、'.join(by_category['food'][:3])}")
        if "lifestyle" in by_category or "general" in by_category:
            items = by_category.get("lifestyle", []) + by_category.get("general", [])
            if items:
                parts.append(f"生活习惯上，{'、'.join(items[:3])}")
        
        if parts:
            return f"根据我的记忆，{parts[0]}。"
        else:
            return f"我记得你提到过：{memories[0]['content']}"
    
    def get_all_memories(self) -> list[dict]:
        """获取所有记忆"""
        return self.saver.get_user_memories(self.agent_id, self.user_id, limit=100)


# 便捷函数
_async_memory_cache = {}

def get_natural_memory(agent_id: str = "default", user_id: str = None) -> NaturalLanguageMemory:
    """获取自然语言记忆管理器"""
    key = f"{agent_id}:{user_id}"
    if key not in _async_memory_cache:
        _async_memory_cache[key] = NaturalLanguageMemory(agent_id, user_id)
    return _async_memory_cache[key]
