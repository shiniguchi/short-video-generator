from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select
from typing import Optional
from app.database import get_session
from app.config import get_settings

router = APIRouter()


@router.get("/health")
async def health_check(session: AsyncSession = Depends(get_session)):
    """Health check endpoint with service status"""
    settings = get_settings()

    # Check database
    db_status = "disconnected"
    try:
        await session.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"

    # Check Redis (skip if not configured)
    redis_status = "not configured"
    if settings.redis_url:
        try:
            import redis.asyncio as aioredis
            r = aioredis.from_url(settings.redis_url)
            await r.ping()
            redis_status = "connected"
            await r.close()
        except Exception as e:
            redis_status = f"error: {str(e)}"

    # Healthy if DB connected and Redis is either connected or not configured
    overall_status = "healthy" if db_status == "connected" and redis_status in ("connected", "not configured") else "unhealthy"

    return {
        "status": overall_status,
        "database": db_status,
        "redis": redis_status,
        "version": "1.0.0"
    }


@router.post("/test-task")
async def trigger_test_task():
    """Trigger a test Celery task"""
    from app.tasks import test_task
    task = test_task.delay()
    return {"task_id": str(task.id), "status": "queued"}


@router.post("/collect-trends")
async def trigger_trend_collection():
    """Trigger trend collection from TikTok and YouTube."""
    from app.tasks import collect_trends_task
    task = collect_trends_task.delay()
    return {"task_id": str(task.id), "status": "queued", "description": "Collecting trends from TikTok and YouTube"}


@router.get("/trends")
async def list_trends(
    platform: Optional[str] = None,
    limit: int = 50,
    session: AsyncSession = Depends(get_session)
):
    """List collected trends, optionally filtered by platform."""
    from app.models import Trend

    query = select(Trend).order_by(Trend.collected_at.desc()).limit(limit)
    if platform:
        query = query.where(Trend.platform == platform)

    result = await session.execute(query)
    trends = result.scalars().all()

    return {
        "count": len(trends),
        "trends": [
            {
                "id": t.id,
                "platform": t.platform,
                "external_id": t.external_id,
                "title": t.title,
                "creator": t.creator,
                "likes": t.likes,
                "comments": t.comments,
                "shares": t.shares,
                "views": t.views,
                "duration": t.duration,
                "engagement_velocity": t.engagement_velocity,
                "collected_at": t.collected_at.isoformat() if t.collected_at else None,
            }
            for t in trends
        ]
    }
