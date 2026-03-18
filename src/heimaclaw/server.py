"""
HeiMaClaw FastAPI 服务模块

提供 webhook 接口，接收飞书和企业微信的回调消息，
并路由到对应的 Agent 进行处理。
"""

from typing import Any

from heimaclaw.agent.runner import AgentRunner
from heimaclaw.agent.session import SessionManager
from heimaclaw.channel.feishu import FeishuAdapter
from heimaclaw.channel.wecom import WeComAdapter
from heimaclaw.config.loader import get_config
from heimaclaw.console import error, info
from heimaclaw.interfaces import AgentConfig, ChannelType

# 全局状态
_agents: dict[str, AgentRunner] = {}
_session_managers: dict[str, SessionManager] = {}
_channel_adapters: dict[str, Any] = {}


async def load_agents() -> None:
    """
    加载所有 Agent 配置

    从 ~/.heimaclaw/agents/ 目录加载所有 Agent
    """
    import json
    from pathlib import Path

    agents_dir = Path.home() / ".heimaclaw" / "agents"

    if not agents_dir.exists():
        info("暂无 Agent 配置")
        return

    for agent_dir in agents_dir.iterdir():
        if not agent_dir.is_dir():
            continue

        config_file = agent_dir / "agent.json"
        if not config_file.exists():
            continue

        try:
            with open(config_file, encoding="utf-8") as f:
                agent_data = json.load(f)

            if not agent_data.get("enabled", True):
                continue

            agent_name = agent_data.get("name", agent_dir.name)

            # 创建 AgentConfig
            config = AgentConfig(
                name=agent_name,
                description=agent_data.get("description", ""),
                channel=ChannelType(agent_data.get("channel", "feishu")),
                model_provider=agent_data.get("llm", {}).get("provider", "openai"),
                model_name=agent_data.get("llm", {}).get("model_name", "gpt-4"),
                sandbox_enabled=agent_data.get("sandbox", {}).get("enabled", False),
            )

            # 创建会话管理器
            session_manager = SessionManager(
                data_dir=f"/tmp/heimaclaw/sessions/{agent_name}"
            )
            _session_managers[agent_name] = session_manager

            # 创建 Agent Runner
            runner = AgentRunner(
                agent_id=agent_name,
                config=config,
                session_manager=session_manager,
                llm_config=agent_data.get("llm", {}),
            )

            _agents[agent_name] = runner

            info(f"加载 Agent: {agent_name} (channel={config.channel.value})")

        except Exception as e:
            error(f"加载 Agent {agent_dir.name} 失败: {e}")


async def start_agents() -> None:
    """启动所有 Agent"""
    for agent_name, runner in _agents.items():
        try:
            await runner.start()
        except Exception as e:
            error(f"启动 Agent {agent_name} 失败: {e}")


async def stop_agents() -> None:
    """停止所有 Agent"""
    for agent_name, runner in _agents.items():
        try:
            await runner.stop()
        except Exception as e:
            error(f"停止 Agent {agent_name} 失败: {e}")


def init_channel_adapters() -> None:
    """初始化渠道适配器"""
    # 从配置加载飞书适配器
    try:
        config = get_config()
        feishu_config = {}
        if hasattr(config, "channels") and hasattr(config.channels, "feishu"):
            feishu = config.channels.feishu
            feishu_config = {
                "app_id": getattr(feishu, "app_id", ""),
                "app_secret": getattr(feishu, "app_secret", ""),
                "encrypt_key": getattr(feishu, "encrypt_key", ""),
            }

        feishu_adapter = FeishuAdapter(feishu_config)
        if feishu_adapter.is_configured():
            _channel_adapters["feishu"] = feishu_adapter
            info("飞书适配器已配置")
    except Exception as e:
        error(f"加载飞书适配器失败: {e}")

    # 从配置加载企业微信适配器
    try:
        config = get_config()
        wecom_config = {}
        if hasattr(config, "channels") and hasattr(config.channels, "wecom"):
            wecom = config.channels.wecom
            wecom_config = {
                "corp_id": getattr(wecom, "corp_id", ""),
                "agent_id": getattr(wecom, "agent_id", ""),
                "secret": getattr(wecom, "secret", ""),
            }

        wecom_adapter = WeComAdapter(wecom_config)
        if wecom_adapter.is_configured():
            _channel_adapters["wecom"] = wecom_adapter
            info("企业微信适配器已配置")
    except Exception as e:
        error(f"加载企业微信适配器失败: {e}")


def run_server(host: str = "0.0.0.0", port: int = 8000, workers: int = 1) -> None:
    """
    启动 HeiMaClaw 服务

    参数:
        host: 监听地址
        port: 监听端口
        workers: 工作进程数
    """
    import uvicorn

    info("启动 HeiMaClaw 服务")
    info(f"监听地址: {host}:{port}")
    info(f"工作进程: {workers}")

    uvicorn.run(
        "heimaclaw.server:app",
        host=host,
        port=port,
        workers=workers,
        reload=False,
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="HeiMaClaw 服务")
    parser.add_argument("--host", default="0.0.0.0", help="监听地址")
    parser.add_argument("--port", type=int, default=8000, help="监听端口")
    parser.add_argument("--workers", type=int, default=1, help="工作进程数")

    args = parser.parse_args()

    run_server(host=args.host, port=args.port, workers=args.workers)
