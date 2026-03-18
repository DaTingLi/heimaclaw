"""
配置编译器

将 Markdown 配置编译为高性能的 JSON 配置
"""

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from heimaclaw.config.markdown_parser import MarkdownParser
from heimaclaw.console import error, info, success, warning


class ConfigCompiler:
    """配置编译器"""

    def __init__(self, agents_dir: Path):
        """
        初始化编译器

        参数:
            agents_dir: agents 目录路径
        """
        self.agents_dir = agents_dir
        self.compiled_dir_name = ".compiled"

    async def compile_agent(self, agent_name: str, force: bool = False) -> bool:
        """
        编译单个 agent 的配置

        参数:
            agent_name: Agent 名称
            force: 是否强制重新编译

        返回:
            是否编译成功
        """
        agent_dir = self.agents_dir / agent_name
        if not agent_dir.exists():
            error(f"Agent 目录不存在: {agent_dir}")
            return False

        # 检查是否需要重新编译
        if not force and not self._needs_recompile(agent_dir):
            info(f"Agent {agent_name} 配置未变化，跳过编译")
            return True

        info(f"开始编译 Agent: {agent_name}")

        # 加载基础配置（agent.json）
        base_config = self._load_base_config(agent_dir)
        if not base_config:
            error(f"加载基础配置失败: {agent_dir / 'agent.json'}")
            return False

        # 解析 Markdown 配置
        parser = MarkdownParser(agent_dir)
        markdown_config = await self._parse_markdown_configs(parser)

        # 合并配置
        compiled_config = self._merge_configs(base_config, markdown_config)

        # 保存编译后的配置
        if not self._save_compiled_config(agent_dir, compiled_config):
            error(f"保存编译配置失败: {agent_dir}")
            return False

        # 保存哈希
        self._save_hashes(agent_dir)

        success(f"Agent {agent_name} 编译完成")
        return True

    async def compile_all(self, force: bool = False) -> dict[str, bool]:
        """
        编译所有 agent

        参数:
            force: 是否强制重新编译

        返回:
            Agent 名称到编译结果的映射
        """
        results = {}

        for agent_dir in self.agents_dir.iterdir():
            if not agent_dir.is_dir():
                continue

            # 跳过隐藏目录
            if agent_dir.name.startswith("."):
                continue

            # 跳过编译目录
            if agent_dir.name == self.compiled_dir_name:
                continue

            agent_name = agent_dir.name
            results[agent_name] = await self.compile_agent(agent_name, force)

        return results

    async def _parse_markdown_configs(self, parser: MarkdownParser) -> dict[str, Any]:
        """解析所有 Markdown 配置"""
        config = {}

        # 解析 SOUL.md
        soul_config = parser.parse_soul()
        if soul_config:
            config["soul"] = soul_config.to_dict()

        # 解析 TOOLS.md
        tools_config = parser.parse_tools()
        if tools_config:
            config["tools"] = tools_config.to_dict()

        # 解析 IDENTITY.md
        identity_config = parser.parse_identity()
        if identity_config:
            config["identity"] = identity_config.to_dict()

        # 解析 USER.md
        user_config = parser.parse_user()
        if user_config:
            config["user"] = user_config.to_dict()

        return config

    def _load_base_config(self, agent_dir: Path) -> Optional[dict[str, Any]]:
        """加载基础配置（agent.json）"""
        config_file = agent_dir / "agent.json"
        if not config_file.exists():
            return None

        try:
            return json.loads(config_file.read_text(encoding="utf-8"))
        except Exception as e:
            error(f"解析 agent.json 失败: {e}")
            return None

    def _merge_configs(self, base_config: dict[str, Any], markdown_config: dict[str, Any]) -> dict[str, Any]:
        """合并基础配置和 Markdown 配置"""
        merged = {
            "metadata": base_config,
            "compiled_at": datetime.now().isoformat(),
            "version": "1.0",
        }

        # 添加 Markdown 配置
        merged.update(markdown_config)

        # 生成系统提示（基于 Markdown 配置）
        merged["system_prompt"] = self._generate_system_prompt(markdown_config)

        return merged

    def _generate_system_prompt(self, markdown_config: dict[str, Any]) -> str:
        """生成系统提示"""
        prompts = []

        # 身份信息
        if "identity" in markdown_config:
            identity = markdown_config["identity"]
            prompts.append(f"你是 {identity.get('name', 'HeiMaClaw Agent')}")
            if identity.get("creature"):
                prompts.append(f"身份: {identity['creature']}")
            if identity.get("atmosphere"):
                prompts.append(f"氛围: {identity['atmosphere']}")
            if identity.get("introduction"):
                prompts.append(identity["introduction"])

        # 核心定位
        if "soul" in markdown_config:
            soul = markdown_config["soul"]
            if soul.get("core_positioning"):
                prompts.append(f"\n核心定位:\n{soul['core_positioning']}")

            if soul.get("core_capabilities"):
                prompts.append("\n核心能力:")
                for cap in soul["core_capabilities"]:
                    prompts.append(f"- {cap['category']}: {cap['description']}")

        # 工具使用规范
        if "tools" in markdown_config:
            tools = markdown_config["tools"]
            if tools.get("usage_principles"):
                prompts.append("\n工具使用原则:")
                for principle in tools["usage_principles"]:
                    prompts.append(f"- {principle}")

        # 用户信息
        if "user" in markdown_config:
            user = markdown_config["user"]
            if user.get("name"):
                prompts.append(f"\n用户: {user['name']}")
            if user.get("preferences"):
                prompts.append("用户偏好:")
                for key, value in user["preferences"].items():
                    prompts.append(f"- {key}: {value}")

        return "\n".join(prompts)

    def _needs_recompile(self, agent_dir: Path) -> bool:
        """检查是否需要重新编译"""
        # 如果没有编译过，需要编译
        compiled_dir = agent_dir / self.compiled_dir_name
        if not compiled_dir.exists():
            return True

        # 加载保存的哈希
        hashes_file = compiled_dir / "hashes.json"
        if not hashes_file.exists():
            return True

        try:
            saved_hashes = json.loads(hashes_file.read_text(encoding="utf-8"))
        except Exception:
            return True

        # 计算当前文件的哈希
        current_hashes = self._calculate_hashes(agent_dir)

        # 比较哈希
        return saved_hashes != current_hashes

    def _calculate_hashes(self, agent_dir: Path) -> dict[str, str]:
        """计算配置文件的哈希"""
        hashes = {}

        # agent.json
        agent_json = agent_dir / "agent.json"
        if agent_json.exists():
            hashes["agent.json"] = self._file_hash(agent_json)

        # Markdown 文件
        for md_file in ["SOUL.md", "TOOLS.md", "IDENTITY.md", "USER.md", "MEMORY.md"]:
            file_path = agent_dir / md_file
            if file_path.exists():
                hashes[md_file] = self._file_hash(file_path)

        return hashes

    def _file_hash(self, file_path: Path) -> str:
        """计算文件哈希"""
        content = file_path.read_bytes()
        return hashlib.md5(content).hexdigest()

    def _save_compiled_config(self, agent_dir: Path, config: dict[str, Any]) -> bool:
        """保存编译后的配置"""
        compiled_dir = agent_dir / self.compiled_dir_name
        compiled_dir.mkdir(exist_ok=True)

        config_file = compiled_dir / "agent.compiled.json"

        try:
            config_file.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
            return True
        except Exception as e:
            error(f"保存编译配置失败: {e}")
            return False

    def _save_hashes(self, agent_dir: Path) -> None:
        """保存文件哈希"""
        compiled_dir = agent_dir / self.compiled_dir_name
        compiled_dir.mkdir(exist_ok=True)

        hashes = self._calculate_hashes(agent_dir)
        hashes_file = compiled_dir / "hashes.json"

        try:
            hashes_file.write_text(json.dumps(hashes, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as e:
            warning(f"保存哈希失败: {e}")
