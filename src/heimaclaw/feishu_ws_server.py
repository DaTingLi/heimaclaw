"""
飞书 WebSocket 长连接服务

独立的飞书长连接服务，无需配置 Webhook URL。
"""

import asyncio
import json
from typing import Any

from heimaclaw.agent.runner import AgentRunner
from heimaclaw.agent.session import SessionManager
from heimaclaw.channel.feishu_ws import FeishuWebSocketAdapter
from heimaclaw.config.loader import get_config
from heimaclaw.console import error, info
from heimaclaw.interfaces import ChannelType

# 全局状态
_agents: dict[str, AgentRunner] = {}
_session_managers: dict[str, SessionManager] = {}


async def load_agents() -> None:
    """加载所有 Agent 配置"""
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

            # 创建会话管理器
            session_manager = SessionManager(
                data_dir=f"/tmp/heimaclaw/sessions/{agent_name}"
            )
            _session_managers[agent_name] = session_manager

            # 创建 Agent Runner
            runner = AgentRunner(
                agent_id=agent_name,
                config=type(
                    "AgentConfig",
                    (),
                    {
                        "name": agent_name,
                        "description": agent_data.get("description", ""),
                        "channel": ChannelType.FEISHU,
                        "sandbox_enabled": False,
                    },
                )(),
                session_manager=session_manager,
                llm_config=agent_data.get("llm", {}),
            )

            _agents[agent_name] = runner

            info(f"加载 Agent: {agent_name}")

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


async def handle_feishu_message(message: Any) -> None:
    """处理飞书消息"""
    try:
        user_id = message.user_id
        content = message.content

        info(f"收到飞书消息: user={user_id}, content={content[:50]}")

        # 查找对应的 Agent
        runner = _agents.get("default")

        if not runner:
            error("Agent 不存在: default")
            return

        # 处理消息
        response_text = await runner.process_message(
            user_id=user_id,
            channel=ChannelType.FEISHU,
            content=content,
        )

        # 发送回复
        from heimaclaw.channel.base import OutboundMessage

        outbound = OutboundMessage(
            user_id=user_id,
            content=response_text,
        )

        # 获取飞书适配器并发送消息
        # TODO: 需要保存 adapter 引用

        info(f"消息处理完成，回复: {response_text[:50]}")

    except Exception as e:
        error(f"处理飞书消息失败: {e}")


async def main() -> None:
    """主函数"""
    info("HeiMaClaw 飞书长连接服务启动中...")

    # 加载配置
    config = get_config()

    # 获取飞书配置
    feishu_config = {}
    if hasattr(config, "channels") and hasattr(config.channels, "feishu"):
        feishu = config.channels.feishu
        feishu_config = {
            "app_id": getattr(feishu, "app_id", ""),
            "app_secret": getattr(feishu, "app_secret", ""),
        }

    if not feishu_config.get("app_id"):
        error(
            "飞书未配置，请先运行: heimaclaw config set channels.feishu.app_id <APP_ID>"
        )
        return

    # 创建飞书长连接适配器
    adapter = FeishuWebSocketAdapter(feishu_config)

    # 加载 Agent
    await load_agents()

    # 启动 Agent
    await start_agents()

    info(f"HeiMaClaw 服务已就绪 ({len(_agents)} Agent)")

    try:
        # 启动长连接
        await adapter.start_listening(handle_feishu_message)
    except KeyboardInterrupt:
        info("收到停止信号...")
    finally:
        # 停止 Agent
        await stop_agents()
        await adapter.close()
        info("HeiMaClaw 服务已停止")


if __name__ == "__main__":
    asyncio.run(main())
