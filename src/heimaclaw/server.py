"""
HeiMaClaw FastAPI 服务模块

提供 webhook 接口，接收飞书和企业微信的回调消息。
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

from heimaclaw.console import info, agent_event


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    应用生命周期管理
    
    启动时初始化资源，关闭时清理资源。
    """
    info("HeiMaClaw 服务启动中...")
    
    # TODO: 初始化沙箱池
    # TODO: 初始化渠道客户端
    # TODO: 加载 Agent 配置
    
    info("HeiMaClaw 服务已就绪")
    
    yield
    
    info("HeiMaClaw 服务关闭中...")
    
    # TODO: 清理沙箱实例
    # TODO: 关闭数据库连接
    
    info("HeiMaClaw 服务已停止")


# 创建 FastAPI 应用
app = FastAPI(
    title="HeiMaClaw",
    description="生产级企业 AI Agent 平台",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/")
async def root() -> dict:
    """健康检查端点"""
    return {
        "name": "HeiMaClaw",
        "version": "0.1.0",
        "status": "running",
    }


@app.get("/health")
async def health() -> dict:
    """健康检查端点"""
    return {"status": "healthy"}


# ==================== 飞书 Webhook ====================

@app.post("/webhook/feishu")
async def feishu_webhook(request: Request) -> Response:
    """
    飞书 Webhook 回调端点
    
    接收飞书推送的消息事件。
    """
    body = await request.json()
    
    # URL 验证
    if body.get("type") == "url_verification":
        challenge = body.get("challenge", "")
        agent_event(f"飞书 URL 验证: {challenge[:20]}...")
        return JSONResponse({"challenge": challenge})
    
    # 消息处理
    event = body.get("event", {})
    message_type = event.get("message", {}).get("message_type", "unknown")
    
    agent_event(f"收到飞书消息: type={message_type}")
    
    # TODO: 路由到对应 Agent 的 microVM 执行
    
    return Response(status_code=200)


# ==================== 企业微信 Webhook ====================

@app.post("/webhook/wecom")
async def wecom_webhook(request: Request) -> Response:
    """
    企业微信 Webhook 回调端点
    
    接收企业微信推送的消息事件。
    """
    body = await request.json()
    
    # URL 验证
    if body.get("MsgType") == "event" and body.get("Event") == "change_contact":
        agent_event("企业微信通讯录变更事件")
        return Response(status_code=200)
    
    # 消息处理
    msg_type = body.get("MsgType", "unknown")
    
    agent_event(f"收到企业微信消息: type={msg_type}")
    
    # TODO: 路由到对应 Agent 的 microVM 执行
    
    return Response(status_code=200)


# ==================== Agent 管理 API ====================

@app.get("/api/agents")
async def list_agents() -> dict:
    """列出所有 Agent"""
    # TODO: 实现真实的 Agent 列表
    return {
        "agents": [],
        "total": 0,
    }


@app.get("/api/agents/{agent_id}")
async def get_agent(agent_id: str) -> dict:
    """获取 Agent 详情"""
    # TODO: 实现真实的 Agent 查询
    return {
        "id": agent_id,
        "name": "example-agent",
        "status": "running",
    }


# ==================== 会话管理 API ====================

@app.get("/api/sessions")
async def list_sessions() -> dict:
    """列出活跃会话"""
    # TODO: 实现真实的会话列表
    return {
        "sessions": [],
        "total": 0,
    }


@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str) -> dict:
    """获取会话详情"""
    # TODO: 实现真实的会话查询
    return {
        "id": session_id,
        "status": "active",
        "messages": 0,
    }
