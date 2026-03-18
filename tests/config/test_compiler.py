"""
配置编译器测试
"""

import json
import tempfile
from pathlib import Path

import pytest

from heimaclaw.config.compiler import ConfigCompiler


@pytest.fixture
def sample_agents_dir():
    """创建示例 agents 目录"""
    with tempfile.TemporaryDirectory() as tmpdir:
        agents_dir = Path(tmpdir)
        agent_dir = agents_dir / "test-agent"
        agent_dir.mkdir()

        # 创建 agent.json
        base_config = {
            "name": "test-agent",
            "description": "测试 Agent",
            "channel": "feishu",
            "enabled": True,
            "llm": {"provider": "glm", "model_name": "glm-4-flash"},
        }

        (agent_dir / "agent.json").write_text(
            json.dumps(base_config, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        # 创建 SOUL.md
        soul_content = """# SOUL.md

## 🎯 核心定位

测试 Agent 核心定位
"""
        (agent_dir / "SOUL.md").write_text(soul_content, encoding="utf-8")

        # 创建 IDENTITY.md
        identity_content = """# IDENTITY.md

- **姓名**：Test Agent
"""
        (agent_dir / "IDENTITY.md").write_text(identity_content, encoding="utf-8")

        yield agents_dir


@pytest.mark.asyncio
async def test_compile_agent(sample_agents_dir):
    """测试编译单个 agent"""
    compiler = ConfigCompiler(sample_agents_dir)
    success = await compiler.compile_agent("test-agent")

    assert success

    # 检查编译后的文件是否存在
    compiled_file = (
        sample_agents_dir / "test-agent" / ".compiled" / "agent.compiled.json"
    )
    assert compiled_file.exists()

    # 检查内容
    compiled_config = json.loads(compiled_file.read_text(encoding="utf-8"))
    assert "metadata" in compiled_config
    assert "soul" in compiled_config
    assert "identity" in compiled_config
    assert "system_prompt" in compiled_config


@pytest.mark.asyncio
async def test_compile_all(sample_agents_dir):
    """测试编译所有 agent"""
    compiler = ConfigCompiler(sample_agents_dir)
    results = await compiler.compile_all()

    assert "test-agent" in results
    assert results["test-agent"]


@pytest.mark.asyncio
async def test_needs_recompile(sample_agents_dir):
    """测试重新编译检测"""
    compiler = ConfigCompiler(sample_agents_dir)

    # 第一次应该需要编译
    assert compiler._needs_recompile(sample_agents_dir / "test-agent")

    # 编译后
    await compiler.compile_agent("test-agent")

    # 第二次不需要（哈希未变）
    assert not compiler._needs_recompile(sample_agents_dir / "test-agent")

    # 修改文件后需要重新编译
    soul_file = sample_agents_dir / "test-agent" / "SOUL.md"
    soul_file.write_text("# Modified", encoding="utf-8")
    assert compiler._needs_recompile(sample_agents_dir / "test-agent")


def test_generate_system_prompt(sample_agents_dir):
    """测试系统提示生成"""
    compiler = ConfigCompiler(sample_agents_dir)

    markdown_config = {
        "identity": {"name": "Test Agent", "creature": "AI", "atmosphere": "友好"},
        "soul": {
            "core_positioning": "测试定位",
            "core_capabilities": [{"category": "对话", "description": "回答问题"}],
        },
    }

    prompt = compiler._generate_system_prompt(markdown_config)

    assert "Test Agent" in prompt
    assert "测试定位" in prompt
    assert "AI" in prompt


def test_file_hash(sample_agents_dir):
    """测试文件哈希计算"""
    compiler = ConfigCompiler(sample_agents_dir)
    agent_dir = sample_agents_dir / "test-agent"

    hashes1 = compiler._calculate_hashes(agent_dir)
    assert "agent.json" in hashes1
    assert "SOUL.md" in hashes1

    # 修改文件后哈希应该改变
    soul_file = agent_dir / "SOUL.md"
    soul_file.write_text("# Modified", encoding="utf-8")

    hashes2 = compiler._calculate_hashes(agent_dir)
    assert hashes1["SOUL.md"] != hashes2["SOUL.md"]
