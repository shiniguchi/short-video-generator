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


@celery_app.task(
    bind=True,
    name='app.tasks.analyze_trends_task',
    max_retries=3,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
)
def analyze_trends_task(self):
    """Analyze collected trends using Claude API."""
    logger.info(f"Starting trend analysis (attempt {self.request.retries + 1})")
    try:
        from app.services.trend_reporter import get_trends_for_analysis, save_report
        from app.services.trend_analyzer import analyze_trends
        from datetime import datetime, timezone, timedelta

        # Get trends from last 24 hours
        trends = asyncio.run(get_trends_for_analysis(hours=24))

        if not trends:
            logger.warning("No trends found for analysis")
            return {"status": "skipped", "reason": "No trends in last 24 hours"}

        # Analyze with Claude (or mock)
        report_data = analyze_trends(trends)

        # Save report to DB
        now = datetime.now(timezone.utc)
        report_id = asyncio.run(save_report(
            report_data=report_data,
            date_range_start=now - timedelta(hours=24),
            date_range_end=now
        ))

        logger.info(f"Trend analysis complete, report ID: {report_id}")
        return {
            "status": "success",
            "report_id": report_id,
            "analyzed_count": report_data.get("analyzed_count", 0)
        }
    except Exception as exc:
        logger.error(f"Trend analysis failed: {exc}")
        raise
