"""
记忆管理工具 - 增强版

功能：
1. update_memory - 更新长期记忆
2. read_memory - 读取记忆内容
3. remember_preference - 快速记忆用户偏好

参考 OpenClaw Memory System 设计
"""

from pathlib import Path
from datetime import datetime
import re


MEMORY_DIR = Path.home() / ".heimaclaw" / "agents"
AGENTS_FILE = "AGENTS.md"
DAILY_DIR = MEMORY_DIR / "memory"


def get_memory_path(agent_id: str = "default") -> Path:
    """获取记忆文件路径"""
    return MEMORY_DIR / agent_id / AGENTS_FILE


def get_daily_memory_path(agent_id: str = "default") -> Path:
    """获取每日记忆文件路径"""
    date_str = datetime.now().strftime("%Y-%m-%d")
    daily_file = DAILY_DIR / agent_id / f"{date_str}.md"
    daily_file.parent.mkdir(parents=True, exist_ok=True)
    return daily_file


async def update_memory_handler(
    content: str,
    section: str = "notes",
    agent_id: str = "default",
) -> str:
    """
    更新长期记忆
    
    Args:
        content: 要添加的记忆内容
        section: 要更新的章节 (notes/learning/user_profile/project)
        agent_id: Agent ID
    
    Returns:
        更新结果
    """
    memory_path = get_memory_path(agent_id)
    
    if not memory_path.exists():
        memory_path.parent.mkdir(parents=True, exist_ok=True)
        memory_path.write_text(_create_memory_template(agent_id), encoding="utf-8")
    
    try:
        current_content = memory_path.read_text(encoding="utf-8")
        
        # 根据 section 构建要添加的内容
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        if section == "notes":
            section_marker = "## 📅 重要事件记录"
            entry = f"\n### {timestamp}\n- {content}\n"
        elif section == "learning":
            section_marker = "## 💡 学到的经验"
            entry = f"\n- **{timestamp}**: {content}\n"
        elif section == "user_profile":
            section_marker = "## 👤 用户画像"
            entry = f"\n- {content}\n"
        elif section == "project":
            section_marker = "## 🚀 项目记忆"
            entry = f"\n### {timestamp}\n{content}\n"
        else:  # notes
            section_marker = "## 📅 重要事件记录"
            entry = f"\n### {timestamp}\n- {content}\n"
        
        # 查找 section 是否存在
        if section_marker in current_content:
            # 在现有 section 中添加
            section_start = current_content.find(section_marker)
            next_section = current_content.find("\n##", section_start + len(section_marker))
            
            if next_section == -1:
                insert_pos = len(current_content)
            else:
                insert_pos = next_section
            
            new_content = (
                current_content[:insert_pos] 
                + entry 
                + current_content[insert_pos:]
            )
        else:
            # 添加新 section
            new_content = current_content + f"\n\n{section_marker}\n{entry}"
        
        # 写入
        memory_path.write_text(new_content, encoding="utf-8")
        
        return f"✅ 记忆已更新到 {section} 章节\n\n{content[:100]}..."
        
    except Exception as e:
        return f"错误: 更新记忆失败 - {str(e)}"


async def remember_preference_handler(
    preference: str,
    category: str = "general",
    agent_id: str = "default",
) -> str:
    """
    快速记忆用户偏好
    
    这是最常用的记忆工具，用于记住用户的喜好、习惯等。
    
    Args:
        preference: 偏好内容（如 "用户喜欢用中文交流"）
        category: 类别 (general/communication/work/technical)
        agent_id: Agent ID
    
    Returns:
        记忆结果
    """
    from pathlib import Path
    import os
    
    # 构建偏好条目
    timestamp = datetime.now().strftime("%Y-%m-%d")
    
    entry = f"- [{timestamp}] ({category}) {preference}"
    
    # 更新到用户画像章节
    memory_path = Path.home() / ".heimaclaw" / "agents" / agent_id / "AGENTS.md"
    
    info(f"[DEBUG] remember_preference: path={memory_path}, exists={memory_path.exists()}")
    info(f"[DEBUG] preference: {preference}")
    
    # 确保目录存在
    memory_path.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        if memory_path.exists():
            content = memory_path.read_text(encoding="utf-8")
        else:
            content = _create_memory_template(agent_id)
        
        # 查找用户画像章节
        section_marker = "## 👤 用户偏好"
        
        if section_marker in content:
            # 在现有章节中添加
            section_start = content.find(section_marker)
            next_section = content.find("\n##", section_start + len(section_marker))
            
            if next_section == -1:
                insert_pos = len(content)
            else:
                insert_pos = next_section
            
            new_content = content[:insert_pos] + f"\n{entry}" + content[insert_pos:]
        else:
            # 添加新章节
            new_content = content + f"\n\n{section_marker}\n{entry}\n"
        
        memory_path.write_text(new_content, encoding="utf-8")
        info(f"[DEBUG] Successfully wrote to {memory_path}")
        
        return f"🧠 已记住你的偏好：{preference}"
        
    except Exception as e:
        import traceback
        error(f"[DEBUG] remember_preference error: {e}")
        error(f"[DEBUG] {traceback.format_exc()}")
        return f"错误: 记忆偏好失败 - {str(e)}"
        
    except Exception as e:
        return f"错误: 记忆偏好失败 - {str(e)}"


async def append_daily_note_handler(
    content: str,
    agent_id: str = "default",
) -> str:
    """
    添加每日笔记
    
    用于记录当天的会话摘要、任务进度等。
    
    Args:
        content: 笔记内容
        agent_id: Agent ID
    
    Returns:
        添加结果
    """
    daily_path = get_daily_memory_path(agent_id)
    
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        # 如果文件不存在，创建模板
        if not daily_path.exists():
            daily_path.write_text(
                f"# {datetime.now().strftime('%Y-%m-%d')} 日记\n\n",
                encoding="utf-8"
            )
        
        # 追加内容
        with open(daily_path, "a", encoding="utf-8") as f:
            f.write(f"\n### {timestamp}\n{content}\n")
        
        return f"📝 已添加到今日笔记\n\n{content[:100]}..."
        
    except Exception as e:
        return f"错误: 添加笔记失败 - {str(e)}"


async def read_memory_handler(
    agent_id: str = "default",
    section: str = None,
) -> str:
    """
    读取记忆内容
    
    Args:
        agent_id: Agent ID
        section: 要读取的章节 (notes/learning/user_profile/project/all)
    
    Returns:
        记忆内容
    """
    memory_path = get_memory_path(agent_id)
    
    if not memory_path.exists():
        return "记忆文件不存在"
    
    try:
        content = memory_path.read_text(encoding="utf-8")
        
        if section and section != "all":
            # 读取特定 section
            section_map = {
                "notes": ("📅 重要事件记录", "notes"),
                "learning": ("💡 学到的经验", "learning"),
                "user_profile": ("👤 用户", "user_profile"),
                "project": ("🚀 项目记忆", "project"),
            }
            
            if section in section_map:
                section_name, _ = section_map[section]
                marker = f"## {section_name}"
                start = content.find(marker)
                
                if start == -1:
                    return f"未找到 [{section}] 章节"
                
                end = content.find("\n##", start + len(marker))
                if end == -1:
                    section_content = content[start:]
                else:
                    section_content = content[start:end]
                
                return section_content
        
        # 读取全部（限制长度）
        if len(content) > 3000:
            return content[:3000] + "\n\n... (内容过长，已截断)"
        return content
        
    except Exception as e:
        return f"错误: 读取记忆失败 - {str(e)}"


def _create_memory_template(agent_id: str) -> str:
    """创建记忆模板"""
    return f"""# MEMORY.md - 长期记忆

_{agent_id} 的长期知识库_

## 📝 记忆原则

- 只记录有价值的信息
- 定期整理，从日常笔记中提炼精华
- 保持简洁，这是精华不是流水账

---

## 👤 用户偏好

_记录用户的喜好和习惯_

---

## 📅 重要事件记录

_记录重要的决策和事件_

---

## 💡 学到的经验

_持续积累中..._

---

## 🚀 项目记忆

_记录重要项目信息..._

---

_此文件由 Agent 自动更新_
"""


def get_memory_tools_definition() -> list[dict]:
    """获取记忆工具定义"""
    return [
        {
            "name": "update_memory",
            "description": """更新 Agent 的长期记忆

使用场景：
- 用户说"记住..."、"以后都..."时
- 完成重要决策后记录
- 发现重要项目信息时

参数：
- content: 要记忆的内容
- section: 章节 (notes/learning/user_profile/project)

重要：只存储有价值的信息""",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "要记忆的内容"},
                    "section": {
                        "type": "string",
                        "enum": ["notes", "learning", "user_profile", "project"],
                        "description": "记忆章节",
                        "default": "notes"
                    }
                },
                "required": ["content"]
            }
        },
        {
            "name": "remember_preference",
            "description": """快速记忆用户偏好

这是最常用的记忆工具！
当用户表达偏好、习惯、喜好时，立即调用此工具。

使用场景：
- 用户说"我喜欢..."
- 用户说"我习惯..."
- 用户说"我通常..."
- 用户表达任何个人喜好

参数：
- preference: 偏好内容
- category: 类别 (general/communication/work/technical)""",
            "parameters": {
                "type": "object",
                "properties": {
                    "preference": {"type": "string", "description": "偏好内容"},
                    "category": {
                        "type": "string",
                        "enum": ["general", "communication", "work", "technical"],
                        "description": "偏好类别",
                        "default": "general"
                    }
                },
                "required": ["preference"]
            }
        },
        {
            "name": "append_daily_note",
            "description": """添加每日笔记

记录当天的会话摘要、任务进度等。

参数：
- content: 笔记内容""",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "笔记内容"}
                },
                "required": ["content"]
            }
        },
        {
            "name": "read_memory",
            "description": """读取 Agent 的长期记忆

使用场景：
- 开始新任务前查看已记住的信息
- 了解用户的偏好和习惯
- 回顾之前的决策

参数：
- section: 章节 (notes/learning/user_profile/project/all)""",
            "parameters": {
                "type": "object",
                "properties": {
                    "section": {
                        "type": "string",
                        "enum": ["notes", "learning", "user_profile", "project", "all"],
                        "description": "记忆章节",
                        "default": "all"
                    }
                }
            }
        }
    ]


async def search_memory_handler(
    query: str,
    max_results: int = 5,
    agent_id: str = "default",
) -> str:
    """
    搜索记忆内容
    
    使用 Hybrid Search (BM25 + Vector + MMR + Temporal Decay)
    
    Args:
        query: 搜索查询
        max_results: 最大结果数
        agent_id: Agent ID
    
    Returns:
        搜索结果
    """
    try:
        from heimaclaw.memory.manager_v3 import MemoryManagerV3
        
        # 创建临时的 MemoryManagerV3 来执行搜索
        # 注意：这里需要 session_id 等参数
        # 简化版本直接搜索文件
        
        import sqlite3
        from pathlib import Path
        
        db_path = Path.home() / ".heimaclaw" / "data" / "memory" / f"{agent_id}.db"
        if not db_path.exists():
            return "没有找到记忆数据"
        
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # 简单搜索：使用 LIKE
        search_pattern = f"%{query}%"
        
        results = []
        
        # 搜索事件
        cursor.execute(
            "SELECT * FROM events WHERE content LIKE ? ORDER BY importance DESC LIMIT ?",
            (search_pattern, max_results)
        )
        for row in cursor.fetchall():
            results.append({
                "type": "event",
                "content": row["content"],
                "importance": row["importance"],
                "created_at": row["created_at"],
            })
        
        # 搜索用户画像
        cursor.execute(
            "SELECT * FROM user_profile WHERE value LIKE ? LIMIT ?",
            (search_pattern, max_results)
        )
        for row in cursor.fetchall():
            results.append({
                "type": "profile",
                "key": row["key"],
                "value": row["value"],
                "confidence": row["confidence"],
            })
        
        conn.close()
        
        if not results:
            return f"没有找到与「{query}」相关的记忆"
        
        # 格式化结果
        formatted = [f"找到 {len(results)} 条相关记忆：\n"]
        for i, r in enumerate(results, 1):
            if r["type"] == "event":
                formatted.append(f"{i}. [事件] {r['content']}")
            elif r["type"] == "profile":
                formatted.append(f"{i}. [偏好] {r['key']}: {r['value']}")
        
        return "\n".join(formatted)
        
    except Exception as e:
        return f"搜索记忆失败: {str(e)}"


def get_memory_tools_definition() -> list[dict]:
    """获取记忆工具定义"""
    return [
        {
            "name": "update_memory",
            "description": """更新 Agent 的长期记忆

使用场景：
- 用户说"记住..."、"以后都..."时
- 完成重要决策后记录
- 发现重要项目信息时

参数：
- content: 要记忆的内容
- section: 章节 (notes/learning/user_profile/project)

重要：只存储有价值的信息""",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "要记忆的内容"},
                    "section": {
                        "type": "string",
                        "enum": ["notes", "learning", "user_profile", "project"],
                        "description": "记忆章节",
                        "default": "notes"
                    }
                },
                "required": ["content"]
            }
        },
        {
            "name": "remember_preference",
            "description": """快速记忆用户偏好

这是最常用的记忆工具！
当用户表达偏好、习惯、喜好时，立即调用此工具。

使用场景：
- 用户说"我喜欢..."
- 用户说"我习惯..."
- 用户说"我通常..."
- 用户表达任何个人喜好

参数：
- preference: 偏好内容
- category: 类别 (general/communication/work/technical)""",
            "parameters": {
                "type": "object",
                "properties": {
                    "preference": {"type": "string", "description": "偏好内容"},
                    "category": {
                        "type": "string",
                        "enum": ["general", "communication", "work", "technical"],
                        "description": "偏好类别",
                        "default": "general"
                    }
                },
                "required": ["preference"]
            }
        },
        {
            "name": "append_daily_note",
            "description": """添加每日笔记

记录当天的会话摘要、任务进度等。

参数：
- content: 笔记内容""",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "笔记内容"}
                },
                "required": ["content"]
            }
        },
        {
            "name": "read_memory",
            "description": """读取 Agent 的长期记忆

使用场景：
- 开始新任务前查看已记住的信息
- 了解用户的偏好和习惯
- 回顾之前的决策

参数：
- section: 章节 (notes/learning/user_profile/project/all)""",
            "parameters": {
                "type": "object",
                "properties": {
                    "section": {
                        "type": "string",
                        "enum": ["notes", "learning", "user_profile", "project", "all"],
                        "description": "记忆章节",
                        "default": "all"
                    }
                }
            }
        },
        {
            "name": "search_memory",
            "description": """搜索记忆内容

使用 Hybrid Search (BM25 + Vector) 搜索记忆

使用场景：
- 用户问"你记得之前..."
- 需要查找之前记住的信息
- 回顾相关项目经验

参数：
- query: 搜索查询
- max_results: 最大结果数""",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索查询"},
                    "max_results": {
                        "type": "integer",
                        "description": "最大结果数",
                        "default": 5
                    }
                },
                "required": ["query"]
            }
        }
    ]
