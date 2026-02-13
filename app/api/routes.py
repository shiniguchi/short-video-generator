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


@router.post("/analyze-trends")
async def trigger_trend_analysis():
    """Trigger trend analysis with Claude API."""
    from app.tasks import analyze_trends_task
    task = analyze_trends_task.delay()
    return {"task_id": str(task.id), "status": "queued", "description": "Analyzing collected trends"}


@router.get("/trend-reports")
async def list_trend_reports(
    limit: int = 10,
    session: AsyncSession = Depends(get_session)
):
    """List trend analysis reports."""
    from app.models import TrendReport

    query = select(TrendReport).order_by(TrendReport.created_at.desc()).limit(limit)
    result = await session.execute(query)
    reports = result.scalars().all()

    return {
        "count": len(reports),
        "reports": [
            {
                "id": r.id,
                "analyzed_count": r.analyzed_count,
                "date_range_start": r.date_range_start.isoformat() if r.date_range_start else None,
                "date_range_end": r.date_range_end.isoformat() if r.date_range_end else None,
                "video_styles": r.video_styles,
                "common_patterns": r.common_patterns,
                "avg_engagement_velocity": r.avg_engagement_velocity,
                "top_hashtags": r.top_hashtags,
                "recommendations": r.recommendations,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in reports
        ]
    }


@router.get("/trend-reports/latest")
async def get_latest_trend_report(session: AsyncSession = Depends(get_session)):
    """Get the most recent trend analysis report."""
    from app.models import TrendReport

    query = select(TrendReport).order_by(TrendReport.created_at.desc()).limit(1)
    result = await session.execute(query)
    report = result.scalars().first()

    if not report:
        raise HTTPException(status_code=404, detail="No trend reports found")

    return {
        "id": report.id,
        "analyzed_count": report.analyzed_count,
        "date_range_start": report.date_range_start.isoformat() if report.date_range_start else None,
        "date_range_end": report.date_range_end.isoformat() if report.date_range_end else None,
        "video_styles": report.video_styles,
        "common_patterns": report.common_patterns,
        "avg_engagement_velocity": report.avg_engagement_velocity,
        "top_hashtags": report.top_hashtags,
        "recommendations": report.recommendations,
        "created_at": report.created_at.isoformat() if report.created_at else None,
    }
