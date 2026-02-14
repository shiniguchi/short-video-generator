from typing import Optional
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


@celery_app.task(
    bind=True,
    name='app.tasks.generate_content_task',
    max_retries=2,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
)
def generate_content_task(self, theme_config_path: Optional[str] = None):
    """Generate content: config -> script -> video -> voiceover.

    Orchestrates the full content generation pipeline using mock or real providers.
    Returns separate video_path and audio_path (compositing is Phase 4).
    """
    from typing import Optional as Opt

    logger.info(f"Starting content generation (attempt {self.request.retries + 1})")

    # Step 1: Read config
    from app.services.config_reader import read_theme_config, read_content_references
    config = read_theme_config(config_path=theme_config_path)
    refs = read_content_references(config_path=theme_config_path)
    logger.info(f"Config loaded: theme='{config.theme}', product='{config.product_name}'")

    # Step 2: Get latest trend data (optional, may be None)
    trend_report = None
    trend_report_id = None
    try:
        from app.services.trend_reporter import get_latest_report
        trend_report = asyncio.run(get_latest_report())
        if trend_report:
            trend_report_id = trend_report.get('id')
            logger.info(f"Using trend report ID {trend_report_id}")
        else:
            logger.info("No trend reports available, proceeding without trend data")
    except Exception as exc:
        logger.warning(f"Could not fetch trend report: {exc}")

    # Step 3: Generate script (production plan)
    from app.services.script_generator import generate_production_plan, save_production_plan
    plan = generate_production_plan(
        theme_config=config.model_dump(),
        content_refs=[r.model_dump() for r in refs],
        trend_report=trend_report
    )
    logger.info(f"Script generated: '{plan['title']}' with {len(plan['scenes'])} scenes")

    # Step 4: Save script to database
    script_id = asyncio.run(save_production_plan(
        plan_data=plan,
        theme_config=config.model_dump(),
        trend_report_id=trend_report_id
    ))
    logger.info(f"Script saved to DB: ID {script_id}")

    # Step 5: Generate video clips
    from app.services.video_generator.generator import get_video_generator
    video_gen = get_video_generator()
    video_path = video_gen.generate_video(
        scenes=plan['scenes'],
        target_duration=plan['duration_target']
    )
    logger.info(f"Video generated: {video_path}")

    # Step 6: Generate voiceover
    from app.services.voiceover_generator.generator import get_voiceover_generator
    voice_gen = get_voiceover_generator()
    audio_path = voice_gen.generate_voiceover(
        script=plan['voiceover_script']
    )
    logger.info(f"Voiceover generated: {audio_path}")

    result = {
        "status": "success",
        "script_id": script_id,
        "video_path": video_path,
        "audio_path": audio_path,
        "title": plan.get('title', ''),
        "duration_target": plan.get('duration_target', 0),
        "scenes_count": len(plan.get('scenes', []))
    }
    logger.info(f"Content generation complete: {result}")
    return result
