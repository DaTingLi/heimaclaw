"""
飞书 WebSocket 长连接服务

独立的飞书长连接服务，无需配置 Webhook URL。
"""

import asyncio
import json
from typing import Optional

from heimaclaw.agent.router import AgentRouter
from heimaclaw.agent.runner import AgentRunner
from heimaclaw.agent.session import SessionManager
from heimaclaw.channel.base import InboundMessage
from heimaclaw.channel.feishu_ws import FeishuWebSocketAdapter
from heimaclaw.config.loader import get_config
from heimaclaw.console import error, info
from heimaclaw.interfaces import AgentConfig, ChannelType

# 全局状态
_agents: dict[str, AgentRunner] = {}
_session_managers: dict[str, SessionManager] = {}
_router: Optional[AgentRouter] = None
_adapter: Optional[FeishuWebSocketAdapter] = None


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
                config=AgentConfig(
                    name=agent_name,
                    description=agent_data.get("description", ""),
                    channel=ChannelType.FEISHU,
                    model_provider=agent_data.get("llm", {}).get("provider", "openai"),
                    model_name=agent_data.get("llm", {}).get("model_name", "gpt-4"),
                    sandbox_enabled=False,
                ),
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


async def handle_feishu_message(message: InboundMessage) -> None:
    """处理飞书消息"""
    global _adapter, _router

    try:
        user_id = message.user_id
        chat_id = message.chat_id
        content = message.content

        # 判断是否群聊
        is_group = chat_id.startswith("oc_")

        # 使用路由器选择 Agent
        agent_name = _router.route(user_id, chat_id, is_group)

        info(
            f"收到飞书消息: user={user_id}, chat={chat_id}, "
            f"group={is_group}, agent={agent_name}, content={content[:50]}"
        )

        # 查找对应的 Agent
        runner = _agents.get(agent_name)

        if not runner:
            error(f"Agent 不存在: {agent_name}")
            # 尝试使用默认 Agent
            runner = _agents.get("default")
            if not runner:
                error("默认 Agent 也不存在")
                return

        # 处理消息
        response_text = await runner.process_message(
            user_id=user_id,
            channel=ChannelType.FEISHU,
            content=content,
        )

        # 发送回复
        from heimaclaw.channel.base import OutboundMessage

        # 群聊：发送到群（chat_id）
        # 私聊：发送给用户（chat_id = user_id）
        outbound = OutboundMessage(
            chat_id=chat_id if is_group else user_id,
            content=response_text,
        )

        if _adapter:
            success = await _adapter.send_message(outbound)
            if success:
                info(f"消息回复成功: {response_text[:50]}")
            else:
                error("消息回复失败")
        else:
            error("飞书适配器未初始化")

    except Exception as e:
        error(f"处理飞书消息失败: {e}")
        import traceback

        traceback.print_exc()


async def main() -> None:
    """主函数"""
    global _router, _adapter

    info("HeiMaClaw 飞书长连接服务启动中...")

    # 创建路由器
    _router = AgentRouter()

    # 加载配置
    config = get_config()

    # 获取飞书配置（支持多账号）
    feishu_config = {}
    if hasattr(config, "channels") and hasattr(config.channels, "feishu"):
        feishu = config.channels.feishu
        # 支持新的多账号结构和旧的直接配置
        if hasattr(feishu, "accounts") and feishu.accounts:
            # 新结构：优先使用默认账号
            default_account = feishu.get_default_account()
            if default_account:
                feishu_config = {
                    "app_id": default_account.app_id,
                    "app_secret": default_account.app_secret,
                }
        elif hasattr(feishu, "app_id"):
            # 旧结构：直接配置
            feishu_config = {
                "app_id": feishu.app_id,
                "app_secret": feishu.app_secret,
            }

    if not feishu_config.get("app_id"):
        error(
            "飞书未配置，请先运行: heimaclaw config set channels.feishu...accounts...default...app_id <APP_ID>"
        )
        return

    # 创建飞书长连接适配器
    _adapter = FeishuWebSocketAdapter(feishu_config)

    # 加载 Agent
    await load_agents()

    if not _agents:
        error("没有可用的 Agent，请先创建 Agent: heimaclaw agent create <name>")
        return

    # 启动 Agent
    await start_agents()

    info(f"HeiMaClaw 服务已就绪 ({len(_agents)} Agent)")

    # 显示绑定信息
    bindings = _router.get_bindings()
    if bindings:
        info(f"当前绑定: {bindings}")

    try:
        # 启动长连接
        await _adapter.start_listening(handle_feishu_message)
    except KeyboardInterrupt:
        info("收到停止信号...")
    finally:
        # 停止 Agent
        await stop_agents()
        await _adapter.close()
        info("HeiMaClaw 服务已停止")


if __name__ == "__main__":
    asyncio.run(main())
