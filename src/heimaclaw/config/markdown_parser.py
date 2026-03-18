"""
Markdown 配置解析器

解析 Agent 的 Markdown 配置文件（SOUL.md、TOOLS.md、IDENTITY.md 等）
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass
class SoulConfig:
    """SOUL.md 配置"""

    core_positioning: str = ""
    core_capabilities: list[dict[str, str]] = field(default_factory=list)
    collaboration: dict[str, str] = field(default_factory=dict)
    boundaries: list[str] = field(default_factory=list)
    atmosphere: str = ""
    continuity: str = ""

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "core_positioning": self.core_positioning,
            "core_capabilities": self.core_capabilities,
            "collaboration": self.collaboration,
            "boundaries": self.boundaries,
            "atmosphere": self.atmosphere,
            "continuity": self.continuity,
        }


@dataclass
class ToolsConfig:
    """TOOLS.md 配置"""

    core_tools: list[dict[str, Any]] = field(default_factory=list)
    usage_principles: list[str] = field(default_factory=list)
    tool_restrictions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "core_tools": self.core_tools,
            "usage_principles": self.usage_principles,
            "tool_restrictions": self.tool_restrictions,
        }


@dataclass
class IdentityConfig:
    """IDENTITY.md 配置"""

    name: str = ""
    creature: str = ""
    atmosphere: str = ""
    emoji: str = ""
    avatar: str = ""
    introduction: str = ""

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "creature": self.creature,
            "atmosphere": self.atmosphere,
            "emoji": self.emoji,
            "avatar": self.avatar,
            "introduction": self.introduction,
        }


@dataclass
class UserConfig:
    """USER.md 配置"""

    name: str = ""
    nickname: str = ""
    timezone: str = ""
    language: str = ""
    work_scenarios: list[str] = field(default_factory=list)
    preferences: dict[str, str] = field(default_factory=dict)
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "nickname": self.nickname,
            "timezone": self.timezone,
            "language": self.language,
            "work_scenarios": self.work_scenarios,
            "preferences": self.preferences,
            "notes": self.notes,
        }


@dataclass
class MemoryConfig:
    """MEMORY.md 配置"""

    core_positioning: str = ""
    important_events: list[dict[str, str]] = field(default_factory=list)
    learned_lessons: list[str] = field(default_factory=list)
    user_profile: dict[str, Any] = field(default_factory=dict)
    project_memory: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "core_positioning": self.core_positioning,
            "important_events": self.important_events,
            "learned_lessons": self.learned_lessons,
            "user_profile": self.user_profile,
            "project_memory": self.project_memory,
        }


class MarkdownParser:
    """Markdown 配置解析器"""

    def __init__(self, agent_dir: Path):
        """
        初始化解析器

        参数:
            agent_dir: Agent 配置目录
        """
        self.agent_dir = agent_dir

    def parse_soul(self) -> Optional[SoulConfig]:
        """解析 SOUL.md"""
        soul_file = self.agent_dir / "SOUL.md"
        if not soul_file.exists():
            return None

        content = soul_file.read_text(encoding="utf-8")
        config = SoulConfig()

        # 解析核心定位
        config.core_positioning = self._extract_section(content, "核心定位")

        # 解析核心能力
        capabilities_text = self._extract_section(content, "核心能力")
        config.core_capabilities = self._parse_capabilities(capabilities_text)

        # 解析协作关系
        collaboration_text = self._extract_section(content, "协作关系")
        config.collaboration = self._parse_collaboration(collaboration_text)

        # 解析边界
        boundaries_text = self._extract_section(content, "边界")
        config.boundaries = self._parse_list(boundaries_text)

        # 解析氛围
        config.atmosphere = self._extract_section(content, "氛围")

        # 解析连续性
        config.continuity = self._extract_section(content, "连续性")

        return config

    def parse_tools(self) -> Optional[ToolsConfig]:
        """解析 TOOLS.md"""
        tools_file = self.agent_dir / "TOOLS.md"
        if not tools_file.exists():
            return None

        content = tools_file.read_text(encoding="utf-8")
        config = ToolsConfig()

        # 解析核心工具
        core_tools_text = self._extract_section(content, "核心工具")
        config.core_tools = self._parse_tools_list(core_tools_text)

        # 解析使用原则
        principles_text = self._extract_section(content, "使用原则")
        config.usage_principles = self._parse_list(principles_text)

        # 解析工具限制
        restrictions_text = self._extract_section(content, "工具限制")
        config.tool_restrictions = self._parse_list(restrictions_text)

        return config

    def parse_identity(self) -> Optional[IdentityConfig]:
        """解析 IDENTITY.md"""
        identity_file = self.agent_dir / "IDENTITY.md"
        if not identity_file.exists():
            return None

        content = identity_file.read_text(encoding="utf-8")
        config = IdentityConfig()

        # 解析基本信息
        config.name = self._extract_field(content, "姓名")
        config.creature = self._extract_field(content, "生物")
        config.atmosphere = self._extract_field(content, "氛围")
        config.emoji = self._extract_field(content, "表情符号")
        config.avatar = self._extract_field(content, "头像")

        # 解析自我介绍
        config.introduction = self._extract_section(content, "自我介绍")

        return config

    def parse_user(self) -> Optional[UserConfig]:
        """解析 USER.md"""
        user_file = self.agent_dir / "USER.md"
        if not user_file.exists():
            return None

        content = user_file.read_text(encoding="utf-8")
        config = UserConfig()

        # 解析基本信息
        config.name = self._extract_field(content, "姓名")
        config.nickname = self._extract_field(content, "称呼")
        config.timezone = self._extract_field(content, "时区")
        config.language = self._extract_field(content, "语言偏好")

        # 解析工作场景
        work_text = self._extract_section(content, "工作场景")
        config.work_scenarios = self._parse_list(work_text)

        # 解析核心定位
        config.core_positioning = self._extract_section(content, "核心定位")

        # 解析重要事件
        events_text = self._extract_section(content, "重要事件记录")
        config.important_events = self._parse_events(events_text)

        # 解析学到的经验
        lessons_text = self._extract_section(content, "学到的经验")
        config.learned_lessons = self._parse_list(lessons_text)

        # 解析用户画像
        profile_text = self._extract_section(content, "用户画像")
        config.user_profile = self._parse_user_profile(profile_text)

        # 解析项目记忆
        project_text = self._extract_section(content, "项目记忆")
        config.project_memory = self._parse_project_memory(project_text)

        return config

    def _extract_section(self, content: str, section_name: str) -> str:
        """提取章节内容"""
        import re

        lines = content.split("\n")
        in_section = False
        section_lines = []

        for line in lines:
            # 检查是否是章节标题
            if re.match(r"^#+\s*" + re.escape(section_name), line, re.IGNORECASE):
                in_section = True
                continue

            if in_section:
                # 遇到下一个章节标题，停止
                if re.match(r"^#+\s+", line):
                    break
                section_lines.append(line)

        return "\n".join(section_lines).strip()

    def _extract_field(self, content: str, field_name: str) -> str:
        """提取字段值"""
        # 匹配 **字段名**：值 或 - **字段名**：值
        pattern = rf"\*\*{field_name}\*\*[：:]\s*(.+?)(?:\n|$)"
        match = re.search(pattern, content)
        return match.group(1).strip() if match else ""

    def _parse_list(self, text: str) -> list[str]:
        """解析列表"""
        items = []
        for line in text.split("\n"):
            # 匹配 - 项目 或 * 项目 或 数字. 项目
            match = re.match(r"^\s*[-*]\s+(.+)|^\s*\d+\.\s+(.+)", line)
            if match:
                item = match.group(1) or match.group(2)
                items.append(item.strip())
        return items

    def _parse_capabilities(self, text: str) -> list[dict[str, str]]:
        """解析核心能力"""
        capabilities = []
        current_category = ""

        for line in text.split("\n"):
            # 匹配分类（### 或 **）
            category_match = re.match(r"^###\s+(.+)|\*\*(.+?)\*\*", line)
            if category_match:
                current_category = category_match.group(1) or category_match.group(2)
                continue

            # 匹配能力项
            item_match = re.match(r"^\s*[-*]\s+(.+)", line)
            if item_match and current_category:
                capabilities.append(
                    {
                        "category": current_category,
                        "description": item_match.group(1).strip(),
                    }
                )

        return capabilities

    def _parse_collaboration(self, text: str) -> dict[str, str]:
        """解析协作关系"""
        collaboration = {}
        for line in text.split("\n"):
            match = re.match(r"^\s*[-*]\s+(.+?)[：:]\s*(.+)", line)
            if match:
                collaboration[match.group(1).strip()] = match.group(2).strip()
        return collaboration

    def _parse_tools_list(self, text: str) -> list[dict[str, Any]]:
        """解析工具列表"""
        tools = []
        current_tool = None
        in_code_block = False

        for line in text.split("\n"):
            # 检测代码块
            if "```" in line:
                in_code_block = not in_code_block
                continue

            if in_code_block:
                continue

            # 匹配工具名（### 数字. 工具名）
            tool_match = re.match(r"^###\s+(\d+\.)?\s*(.+)", line)
            if tool_match:
                if current_tool:
                    tools.append(current_tool)
                tool_name = tool_match.group(2).strip()
                current_tool = {
                    "name": tool_name,
                    "description": "",
                    "usage": "",
                    "examples": [],
                }
                continue

            # 匹配工具描述
            if current_tool and line.strip().startswith("用途"):
                desc_match = re.match(r"用途[：:]\s*(.+)", line.strip())
                if desc_match:
                    current_tool["description"] = desc_match.group(1).strip()

        if current_tool:
            tools.append(current_tool)

        return tools

    def _parse_preferences(self, text: str) -> dict[str, str]:
        """解析偏好设置"""
        preferences = {}
        for line in text.split("\n"):
            match = re.match(r"^\s*[-*]\s+\*\*(.+?)\*\*[：:]\s*(.+)", line)
            if match:
                preferences[match.group(1).strip()] = match.group(2).strip()
        return preferences

    def _parse_events(self, text: str) -> list[dict[str, str]]:
        """解析重要事件"""
        events = []
        current_date = ""

        for line in text.split("\n"):
            # 匹配日期
            date_match = re.match(r"^###\s+(\d{4}-\d{2}-\d{2})", line)
            if date_match:
                current_date = date_match.group(1)
                continue

            # 匹配事件
            event_match = re.match(r"^\s*[-*]\s+(.+)", line)
            if event_match and current_date:
                events.append(
                    {"date": current_date, "event": event_match.group(1).strip()}
                )

        return events

    def _parse_user_profile(self, text: str) -> dict[str, Any]:
        """解析用户画像"""
        profile = {}
        current_key = ""

        for line in text.split("\n"):
            # 匹配键
            key_match = re.match(r"^###\s+(.+)|\*\*(.+?)\*\*[：:]", line)
            if key_match:
                current_key = key_match.group(1) or key_match.group(2)
                continue

            # 匹配值
            if current_key:
                value_match = re.match(r"^\s*[-*]\s+(.+)", line)
                if value_match:
                    if current_key not in profile:
                        profile[current_key] = []
                    profile[current_key].append(value_match.group(1).strip())

        return profile

    def _parse_project_memory(self, text: str) -> dict[str, Any]:
        """解析项目记忆"""
        # 简化处理，返回字典
        return {"content": text}

    def _parse_list(self, text: str) -> list[str]:
        """解析列表"""
        items = []
        for line in text.split("\n"):
            # 匹配 - 项目 或 * 项目 或 数字. 项目
            match = re.match(r"^\s*[-*]\s+(.+)|^\s*\d+\.\s+(.+)", line)
            if match:
                item = match.group(1) or match.group(2)
                items.append(item.strip())
        return items
