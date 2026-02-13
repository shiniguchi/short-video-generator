from app.worker import celery_app
import time
import asyncio
import logging

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3)
def test_task(self):
    """Simple test task to verify Celery is working"""
    try:
        print("Test task started")
        time.sleep(2)  # Simulate work
        print("Test task completed")
        return {"status": "success", "message": "Test task executed successfully"}
    except Exception as exc:
        print(f"Test task failed: {exc}")
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(
    bind=True,
    name='app.tasks.collect_trends_task',
    max_retries=3,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
)
def collect_trends_task(self):
    """Collect trending videos from TikTok and YouTube."""
    logger.info(f"Starting trend collection (attempt {self.request.retries + 1})")
    try:
        from app.services.trend_collector import collect_all_trends
        result = asyncio.run(collect_all_trends())
        logger.info(f"Trend collection complete: {result}")
        return {"status": "success", "collected": result}
    except Exception as exc:
        logger.error(f"Trend collection failed: {exc}")
        raise
