"""
监控 API 端点

提供 token 使用统计、健康检查等监控接口。
"""

from typing import Optional

from fastapi import APIRouter, Query

from heimaclaw.monitoring.metrics import get_token_tracker

router = APIRouter(prefix="/api/monitoring", tags=["monitoring"])


@router.get("/health")
async def health_check():
    """
    健康检查端点

    返回服务健康状态。
    """
    return {
        "status": "healthy",
        "service": "heimaclaw",
        "version": "0.1.0",
    }


@router.get("/ready")
async def readiness_check():
    """
    就绪检查端点

    检查服务是否已准备好接收请求。
    """
    # TODO: 检查数据库连接、LLM 连接等
    return {
        "ready": True,
        "checks": {
            "database": "ok",
            "llm": "ok",
        },
    }


@router.get("/token-stats")
async def get_token_stats(
    agent_id: Optional[str] = Query(None, description="过滤 Agent ID"),
    provider: Optional[str] = Query(None, description="过滤提供商"),
    start_date: Optional[str] = Query(None, description="开始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD"),
):
    """
    获取 token 使用统计

    返回 token 使用情况的统计数据。
    """
    tracker = get_token_tracker()

    stats = tracker.get_stats(
        agent_id=agent_id,
        provider=provider,
        start_date=start_date,
        end_date=end_date,
    )

    return stats


@router.get("/daily-usage")
async def get_daily_usage(
    agent_id: Optional[str] = Query(None, description="过滤 Agent ID"),
    days: int = Query(7, ge=1, le=90, description="查询最近多少天"),
):
    """
    获取每日使用量

    返回每日的 token 使用情况。
    """
    tracker = get_token_tracker()

    usage = tracker.get_daily_usage(agent_id=agent_id, days=days)

    return {
        "days": days,
        "usage": usage,
    }


@router.get("/agent-usage/{agent_id}")
async def get_agent_usage(
    agent_id: str,
    days: int = Query(7, ge=1, le=90, description="查询最近多少天"),
):
    """
    获取指定 Agent 的使用情况

    返回单个 Agent 的 token 使用统计。
    """
    tracker = get_token_tracker()

    stats = tracker.get_stats(agent_id=agent_id)
    daily = tracker.get_daily_usage(agent_id=agent_id, days=days)

    return {
        "agent_id": agent_id,
        "stats": stats,
        "daily": daily,
    }
