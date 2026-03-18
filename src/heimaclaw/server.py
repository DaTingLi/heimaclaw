"""
HeiMaClaw FastAPI 服务模块

提供 webhook 接口，接收飞书和企业微信的回调消息，
并路由到对应的 Agent 进行处理。
"""

from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

from heimaclaw.agent.runner import AgentRunner
from heimaclaw.agent.session import SessionManager
from heimaclaw.channel.feishu import FeishuAdapter
from heimaclaw.channel.wecom import WeComAdapter
from heimaclaw.config.loader import get_config
from heimaclaw.console import agent_event, error, info
from heimaclaw.interfaces import AgentConfig, ChannelType
from heimaclaw.server_monitoring import router as monitoring_router

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


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    应用生命周期管理

    启动时初始化资源，关闭时清理资源。
    """
    info("HeiMaClaw 服务启动中...")

    # 初始化渠道适配器
    init_channel_adapters()

    # 加载 Agent
    await load_agents()

    # 启动 Agent
    await start_agents()

    info(f"HeiMaClaw 服务已就绪 ({len(_agents)} Agent)")

    yield

    info("HeiMaClaw 服务关闭中...")

    # 停止 Agent
    await stop_agents()

    info("HeiMaClaw 服务已停止")


# 创建 FastAPI 应用
app = FastAPI(
    title="HeiMaClaw",
    description="生产级企业 AI Agent 平台",
    version="0.1.0",
    lifespan=lifespan,
)

# 注册监控路由
app.include_router(monitoring_router)


@app.get("/")
async def root() -> dict[str, Any]:
    """健康检查端点"""
    return {
        "name": "HeiMaClaw",
        "version": "0.1.0",
        "status": "running",
        "agents": len(_agents),
    }


@app.get("/health")
async def health() -> dict[str, Any]:
    """健康检查端点"""
    return {"status": "healthy"}


# ==================== 飞书 Webhook ====================


@app.post("/webhook/feishu")
async def feishu_webhook(request: Request) -> Response:
    """
    飞书 Webhook 回调端点

    接收飞书推送的消息事件，路由到对应 Agent 处理。
    """
    # 获取适配器
    adapter = _channel_adapters.get("feishu")

    if not adapter:
        return JSONResponse(
            {"error": "飞书未配置"},
            status_code=503,
        )

    # 验证请求
    if not await adapter.verify_webhook(request):
        return JSONResponse(
            {"error": "验证失败"},
            status_code=401,
        )

    # 解析消息
    try:
        inbound_msg = await adapter.parse_message(request)
    except Exception as e:
        error(f"解析飞书消息失败: {e}")
        return Response(status_code=400)

    # URL 验证
    if inbound_msg.message_type == "url_verification":
        return JSONResponse({"challenge": inbound_msg.content})

    # 查找对应的 Agent
    agent_name = "default"  # TODO: 根据消息路由到不同 Agent
    runner = _agents.get(agent_name)

    if not runner:
        agent_event(f"未找到 Agent: {agent_name}")
        return Response(status_code=200)  # 返回 200 避免重试

    # 处理消息
    try:
        response = await runner.process_message(
            user_id=inbound_msg.user_id,
            channel=ChannelType.FEISHU,
            content=inbound_msg.content,
        )

        # 发送响应

        sessions = await runner.session_manager.list_active()
        user_sessions = [s for s in sessions if s.user_id == inbound_msg.user_id]

        if user_sessions:
            session = user_sessions[-1]
            await adapter.send_message(
                session.to_context(),
                response,
            )

        return Response(status_code=200)

    except Exception as e:
        error(f"处理飞书消息失败: {e}")
        return Response(status_code=500)


async def _get_last_session_id(runner: AgentRunner, user_id: str) -> str:
    """获取用户最近的会话 ID"""
    sessions = await runner.session_manager.list_active()
    for session in sessions:
        if session.user_id == user_id:
            return session.session_id
    return ""


# ==================== 企业微信 Webhook ====================


@app.post("/webhook/wecom")
async def wecom_webhook(request: Request) -> Response:
    """
    企业微信 Webhook 回调端点

    接收企业微信推送的消息事件。
    """
    adapter = _channel_adapters.get("wecom")

    if not adapter:
        return JSONResponse(
            {"error": "企业微信未配置"},
            status_code=503,
        )

    # 验证请求
    if not await adapter.verify_webhook(request):
        return JSONResponse(
            {"error": "验证失败"},
            status_code=401,
        )

    # 解析消息
    try:
        inbound_msg = await adapter.parse_message(request)
    except Exception as e:
        error(f"解析企业微信消息失败: {e}")
        return Response(status_code=400)

    # URL 验证
    if inbound_msg.message_type == "url_verification":
        return Response(content=inbound_msg.content, media_type="text/plain")

    # 查找对应的 Agent
    agent_name = "default"
    runner = _agents.get(agent_name)

    if not runner:
        return Response(status_code=200)

    # 处理消息
    try:
        response = await runner.process_message(
            user_id=inbound_msg.user_id,
            channel=ChannelType.WECOM,
            content=inbound_msg.content,
        )

        # 发送响应

        sessions = await runner.session_manager.list_active()
        user_sessions = [s for s in sessions if s.user_id == inbound_msg.user_id]

        if user_sessions:
            session = user_sessions[-1]
            await adapter.send_message(
                session.to_context(),
                response,
            )

        return Response(status_code=200)

    except Exception as e:
        error(f"处理企业微信消息失败: {e}")
        return Response(status_code=500)


# ==================== Agent 管理 API ====================


@app.get("/api/agents")
async def list_agents() -> dict[str, Any]:
    """列出所有 Agent"""
    agents = []
    for name, runner in _agents.items():
        agents.append(
            {
                "name": name,
                "status": runner.status.value,
                "channel": runner.config.channel.value,
            }
        )

    return {
        "agents": agents,
        "total": len(agents),
    }


@app.get("/api/agents/{agent_name}")
async def get_agent(agent_name: str) -> dict[str, Any]:
    """获取 Agent 详情"""
    runner = _agents.get(agent_name)

    if not runner:
        return JSONResponse(
            {"error": f"Agent 不存在: {agent_name}"},
            status_code=404,
        )

    return {
        "name": agent_name,
        "status": runner.status.value,
        "channel": runner.config.channel.value,
        "model": f"{runner.config.model_provider}/{runner.config.model_name}",
    }


# ==================== 会话管理 API ====================


@app.get("/api/sessions")
async def list_sessions(agent_name: str = "") -> dict[str, Any]:
    """列出活跃会话"""
    sessions = []

    for name, manager in _session_managers.items():
        if agent_name and name != agent_name:
            continue

        active = await manager.list_active()
        for session in active:
            sessions.append(
                {
                    "session_id": session.session_id,
                    "agent_id": session.agent_id,
                    "user_id": session.user_id,
                    "status": session.status.value,
                }
            )

    return {
        "sessions": sessions,
        "total": len(sessions),
    }


# ==================== 服务启动入口 ====================


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
