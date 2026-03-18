"""
长期记忆模块

存储重要事件、用户画像、项目信息等永久记忆。
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Optional


class LongTermMemory:
    """
    长期记忆管理器
    
    职责：
    - 永久存储重要信息
    - 用户画像管理
    - 项目信息记录
    - 自动容量管理（100KB）
    
    存储格式：
    ~/.heimaclaw/agents/{agent}/MEMORY.md
    """
    
    MAX_SIZE_KB = 100  # 最大容量 100KB
    
    def __init__(
        self,
        agent_id: str,
        memory_file: Optional[Path] = None,
    ):
        """
        初始化长期记忆
        
        参数:
            agent_id: Agent ID
            memory_file: 记忆文件路径（默认 ~/.heimaclaw/agents/{agent}/MEMORY.md）
        """
        self.agent_id = agent_id
        
        # 记忆文件
        if memory_file is None:
            memory_dir = Path.home() / ".heimaclaw" / "agents" / agent_id
            memory_file = memory_dir / "MEMORY.md"
        
        self.memory_file = Path(memory_file)
        self.memory_file.parent.mkdir(parents=True, exist_ok=True)
        
        # 如果文件不存在，创建模板
        if not self.memory_file.exists():
            self._create_template()
    
    def _create_template(self) -> None:
        """创建记忆模板"""
        template = f"""# MEMORY.md - 长期记忆

_{self.agent_id} 的长期知识库，记录重要事件、决策和经验_

## 📝 记忆原则

- **只记录有价值的信息**：重要决策、关键学习、用户偏好、项目里程碑
- **定期整理**：从日常记忆中提炼精华，更新到这里
- **保持简洁**：这是精华，不是流水账

---

## 🎯 核心定位

_待初始化时填写_

---

## 📅 重要事件记录

### {datetime.now().strftime("%Y-%m-%d")}
- 长期记忆系统初始化

---

## 💡 学到的经验

_持续积累中..._

---

## 👤 用户画像

- **主要用户**：_待观察_
- **偏好**：_待观察_
- **工作场景**：_待观察_

---

## 🚀 项目记忆

_记录重要项目信息..._

---

_此文件会随着交互不断丰富，成为 agent 的长期知识库_
"""
        self.memory_file.write_text(template, encoding="utf-8")
    
    def add_important_event(
        self,
        event: str,
        event_type: str = "milestone",
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        """
        添加重要事件
        
        参数:
            event: 事件描述
            event_type: 事件类型（milestone/decision/learning/preference）
            metadata: 元数据
        """
        content = self.memory_file.read_text(encoding="utf-8")
        
        # 查找"重要事件记录"章节
        section_marker = "## 📅 重要事件记录"
        if section_marker not in content:
            # 如果没有章节，添加到文件末尾
            section_start = len(content)
        else:
            section_start = content.find(section_marker)
        
        # 构建事件条目
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        event_entry = f"\n### {timestamp} - {event_type}\n{event}\n"
        
        if metadata:
            event_entry += "\n**详情：**\n"
            for key, value in metadata.items():
                event_entry += f"- {key}: {value}\n"
        
        # 插入事件（在章节后第一个 ### 之前）
        insert_pos = content.find("\n###", section_start + len(section_marker))
        if insert_pos == -1:
            # 没有 ###，插入到文件末尾
            insert_pos = len(content)
        
        new_content = content[:insert_pos] + event_entry + content[insert_pos:]
        
        # 检查容量
        if len(new_content.encode("utf-8")) > self.MAX_SIZE_KB * 1024:
            # 容量超限，压缩旧事件
            new_content = self._compress_content(new_content)
        
        # 保存
        self.memory_file.write_text(new_content, encoding="utf-8")
    
    def add_learning(self, lesson: str, category: str = "general") -> None:
        """
        添加学到的经验
        
        参数:
            lesson: 经验描述
            category: 分类（general/technical/workflow）
        """
        content = self.memory_file.read_text(encoding="utf-8")
        
        # 查找"学到的经验"章节
        section_marker = "## 💡 学到的经验"
        if section_marker not in content:
            # 如果没有章节，添加到文件末尾
            section_start = len(content)
        else:
            section_start = content.find(section_marker)
        
        # 构建经验条目
        timestamp = datetime.now().strftime("%Y-%m-%d")
        lesson_entry = f"\n- **{timestamp}** ({category}): {lesson}\n"
        
        # 插入经验（在章节后下一个 ## 之前）
        insert_pos = content.find("\n##", section_start + len(section_marker))
        if insert_pos == -1:
            # 没有 ##，插入到文件末尾
            insert_pos = len(content)
        
        new_content = content[:insert_pos] + lesson_entry + content[insert_pos:]
        
        # 保存
        self.memory_file.write_text(new_content, encoding="utf-8")
    
    def update_user_profile(
        self,
        key: str,
        value: str,
    ) -> None:
        """
        更新用户画像
        
        参数:
            key: 字段名（如"主要用户"、"偏好"）
            value: 字段值
        """
        content = self.memory_file.read_text(encoding="utf-8")
        
        # 查找字段
        pattern = f"- **{key}**："
        start_pos = content.find(pattern)
        
        if start_pos != -1:
            # 找到字段，更新值
            end_pos = content.find("\n", start_pos)
            old_line = content[start_pos:end_pos]
            new_line = f"- **{key}**：{value}"
            
            new_content = content[:start_pos] + new_line + content[end_pos:]
        else:
            # 没找到字段，添加到用户画像章节
            section_marker = "## 👤 用户画像"
            section_start = content.find(section_marker)
            
            if section_start != -1:
                # 在用户画像章节后插入
                insert_pos = content.find("\n##", section_start + len(section_marker))
                if insert_pos == -1:
                    insert_pos = len(content)
                
                new_entry = f"\n- **{key}**：{value}\n"
                new_content = content[:insert_pos] + new_entry + content[insert_pos:]
            else:
                # 没有用户画像章节，添加到文件末尾
                new_entry = f"\n## 👤 用户画像\n\n- **{key}**：{value}\n"
                new_content = content + new_entry
        
        # 保存
        self.memory_file.write_text(new_content, encoding="utf-8")
    
    def get_content(self) -> str:
        """获取完整内容"""
        return self.memory_file.read_text(encoding="utf-8")
    
    def get_section(self, section_name: str) -> str:
        """
        获取某个章节的内容
        
        参数:
            section_name: 章节名（如"用户画像"、"重要事件记录"）
        
        返回:
            章节内容
        """
        content = self.get_content()
        
        # 查找章节
        pattern = f"## {section_name}"
        start = content.find(pattern)
        
        if start == -1:
            return ""
        
        # 查找章节结束（下一个 ##）
        end = content.find("\n##", start + len(pattern))
        
        if end == -1:
            return content[start:]
        
        return content[start:end]
    
    def search(self, keyword: str) -> list[str]:
        """
        搜索关键词
        
        参数:
            keyword: 关键词
        
        返回:
            匹配的行列表
        """
        content = self.get_content()
        lines = content.split("\n")
        
        # 查找包含关键词的行及其上下文
        matches = []
        for i, line in enumerate(lines):
            if keyword.lower() in line.lower():
                # 添加上下文（前后各2行）
                context_start = max(0, i - 2)
                context_end = min(len(lines), i + 3)
                context = "\n".join(lines[context_start:context_end])
                matches.append(context)
        
        return matches
    
    def _compress_content(self, content: str) -> str:
        """
        压缩内容（当超过 100KB 时）
        
        策略：
        1. 保留用户画像、核心定位
        2. 压缩重要事件（只保留最近30天）
        3. 保留学到的经验
        4. 删除项目记忆（可从其他地方恢复）
        """
        # 简化实现：保留最近的事件
        lines = content.split("\n")
        compressed_lines = []
        
        in_events_section = False
        event_count = 0
        max_events = 50  # 最多保留50个事件
        
        for i, line in enumerate(lines):
            # 检测进入事件章节
            if "## 📅 重要事件记录" in line:
                in_events_section = True
                compressed_lines.append(line)
                continue
            
            # 检测离开事件章节
            if in_events_section and line.startswith("## "):
                in_events_section = False
            
            # 在事件章节中，限制数量
            if in_events_section:
                if line.startswith("### "):
                    event_count += 1
                
                if event_count <= max_events:
                    compressed_lines.append(line)
            else:
                # 其他章节全部保留
                compressed_lines.append(line)
        
        return "\n".join(compressed_lines)
