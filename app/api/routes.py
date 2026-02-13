from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
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
