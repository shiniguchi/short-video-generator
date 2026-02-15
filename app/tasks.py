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
def generate_content_task(self, job_id: int, theme_config_path: Optional[str] = None):
    """Generate content: config -> script -> video -> voiceover.

    Orchestrates the full content generation pipeline using mock or real providers.
    Returns separate video_path and audio_path (compositing is Phase 4).
    """
    from typing import Optional as Opt

    logger.info(f"Starting content generation for job {job_id} (attempt {self.request.retries + 1})")

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
        trend_report_id=trend_report_id,
        job_id=job_id
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

    # Step 6b: Generate avatar video if avatar provider is configured
    # Avatar video replaces both video + voiceover (talking-head includes speech audio)
    from app.config import get_settings
    settings = get_settings()
    if settings.avatar_provider_type in ("heygen",):
        from app.services.avatar_generator.generator import get_avatar_generator
        avatar_gen = get_avatar_generator()
        avatar_path = avatar_gen.generate_avatar_video(
            script_text=plan['voiceover_script']
        )
        logger.info(f"Avatar video generated: {avatar_path}")
        # Avatar replaces both video and audio (it includes the presenter speaking)
        video_path = avatar_path
        audio_path = avatar_path  # Avatar video has embedded audio

    # Step 7: Build cost data (REVIEW-05)
    # For mock providers, costs are 0.0. For real providers, costs will be populated when swapped in.
    cost_data = {
        "claude_cost": 0.0,  # Will be populated by real Claude provider
        "tts_cost": 0.0,  # Will be populated by real TTS provider
        "video_gen_cost": 0.0  # Will be populated by real video provider
    }

    # Step 8: Chain into compose_video_task for end-to-end pipeline
    compose_result = compose_video_task.delay(job_id, script_id, video_path, audio_path, cost_data)
    logger.info(f"Composition task queued: {compose_result.id}")

    result = {
        "status": "success",
        "script_id": script_id,
        "video_path": video_path,
        "audio_path": audio_path,
        "compose_task_id": str(compose_result.id),
        "title": plan.get('title', ''),
        "duration_target": plan.get('duration_target', 0),
        "scenes_count": len(plan.get('scenes', []))
    }
    logger.info(f"Content generation complete: {result}")
    return result


@celery_app.task(
    bind=True,
    name='app.tasks.compose_video_task',
    max_retries=2,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
)
def compose_video_task(self, job_id: int, script_id: int, video_path: str, audio_path: str, cost_data: dict = None):
    """Compose final video with text overlays, audio mixing, and thumbnail generation.

    Args:
        job_id: Database ID of the Job record
        script_id: Database ID of the Script record containing text_overlays
        video_path: Path to generated video file
        audio_path: Path to generated voiceover audio file
        cost_data: Dict with claude_cost, tts_cost, video_gen_cost (REVIEW-05)

    Returns:
        dict with video_id, video_path, thumbnail_path, duration
    """
    logger.info(f"Starting video composition for job {job_id}, script {script_id} (attempt {self.request.retries + 1})")

    # Initialize cost_data if not provided
    if cost_data is None:
        cost_data = {"claude_cost": 0.0, "tts_cost": 0.0, "video_gen_cost": 0.0}

    try:
        # Import inside task to avoid circular imports
        from app.services.video_compositor import VideoCompositor
        from app.schemas import TextOverlaySchema
        from app.config import get_settings

        # Step 1: Load Script from database
        async def _load_script(script_id: int):
            from app.database import get_task_session_factory
            from app.models import Script
            from sqlalchemy import select

            async with get_task_session_factory()() as session:
                query = select(Script).where(Script.id == script_id)
                result = await session.execute(query)
                script = result.scalars().first()
                if not script:
                    raise ValueError(f"Script {script_id} not found")
                return script

        script = asyncio.run(_load_script(script_id))
        logger.info(f"Loaded script: {script.title}")

        # Step 2: Extract text_overlays from Script.text_overlays JSON field
        text_overlays_raw = script.text_overlays or []
        text_overlays = [TextOverlaySchema(**t) for t in text_overlays_raw]
        logger.info(f"Extracted {len(text_overlays)} text overlays")

        # Step 3: Get composition settings
        settings = get_settings()
        background_music = settings.background_music_path or None

        # Step 4: Create VideoCompositor and compose
        compositor = VideoCompositor(output_dir=settings.composition_output_dir)
        result = compositor.compose(
            video_path=video_path,
            audio_path=audio_path,
            text_overlays=text_overlays,
            background_music_path=background_music,
            music_volume=settings.music_volume,
            thumbnail_timestamp=settings.thumbnail_timestamp
        )
        logger.info(f"Composition complete: {result['video_path']}")

        # Step 5: Calculate total cost and build generation metadata (REVIEW-02, REVIEW-05)
        total_cost = sum([
            cost_data.get("claude_cost", 0.0),
            cost_data.get("tts_cost", 0.0),
            cost_data.get("video_gen_cost", 0.0)
        ])

        # Build generation metadata
        from uuid import uuid4
        from datetime import datetime, timezone
        generation_metadata = {
            "gen_id": uuid4().hex,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "theme": script.theme_config.get("theme") if script.theme_config else None,
            "trend_pattern": script.trend_report_id,
            "prompts": {
                "video_prompt": script.video_prompt,
                "voiceover_script": script.voiceover_script
            },
            "model": {
                "script_model": "claude",
                "video_model": settings.video_provider_type,
                "tts_model": settings.tts_provider_type
            },
            "cost_usd": total_cost,
            "output_path": result["video_path"],
            "status": "generated"
        }

        # Step 6: Save Video record to database with cost and metadata
        async def _save_video_record(job_id: int, script_id: int, file_path: str, thumbnail_path: str,
                                      duration: float, cost_usd: float, generation_metadata: dict):
            from app.database import get_task_session_factory
            from app.models import Video

            async with get_task_session_factory()() as session:
                video = Video(
                    job_id=job_id,
                    script_id=script_id,
                    file_path=file_path,
                    thumbnail_path=thumbnail_path,
                    duration_seconds=duration,
                    status="generated",
                    cost_usd=cost_usd,
                    extra_data=generation_metadata
                )
                session.add(video)
                await session.commit()
                await session.refresh(video)
                return video.id

        video_id = asyncio.run(_save_video_record(
            job_id=job_id,
            script_id=script_id,
            file_path=result["video_path"],
            thumbnail_path=result["thumbnail_path"],
            duration=result["duration"],
            cost_usd=total_cost,
            generation_metadata=generation_metadata
        ))
        logger.info(f"Video record saved to DB: ID {video_id}, cost: ${total_cost:.4f}")

        # Step 7: Return success result
        return {
            "status": "success",
            "video_id": video_id,
            "video_path": result["video_path"],
            "thumbnail_path": result["thumbnail_path"],
            "duration": result["duration"],
            "cost_usd": total_cost
        }

    except Exception as exc:
        logger.error(f"Video composition failed: {exc}")
        raise


@celery_app.task(
    bind=True,
    name='app.tasks.generate_ugc_ad_task',
    max_retries=1,
    time_limit=1800,  # 30 minutes for full pipeline
)
def generate_ugc_ad_task(self, job_id, product_name, description, product_images, product_url=None, target_duration=30, style_preference=None):
    """Generate UGC product ad through full pipeline.

    Orchestrates: product analysis -> hero image -> script -> A-Roll -> B-Roll -> composition.
    Uses mock providers when USE_MOCK_DATA=true (default).

    Args:
        job_id: Database ID of the Job record
        product_name: Name of the product
        description: Product description
        product_images: List of paths to uploaded product images
        product_url: Optional product URL
        target_duration: Target video duration in seconds (default 30)
        style_preference: Optional UGC style preference

    Returns:
        dict with status, video_id, video_path, product_name, category, scene counts
    """
    from typing import List, Optional
    from uuid import uuid4
    import os

    logger.info(f"Starting UGC ad generation for job {job_id}, product '{product_name}' (attempt {self.request.retries + 1})")

    try:
        # Import helpers (lazy to avoid circular imports)
        from app.pipeline import _update_job_status, _mark_job_failed, _mark_job_complete

        # Step 1: Update Job status to running
        asyncio.run(_update_job_status(job_id, "ugc_product_analysis", "running"))

        # Step 2: Product Analysis
        from app.services.ugc_pipeline.product_analyzer import analyze_product
        analysis = analyze_product(
            product_name=product_name,
            description=description,
            image_count=len(product_images),
            style_preference=style_preference
        )
        logger.info(f"Product analysis: category={analysis.category}, style={analysis.ugc_style}")

        # Step 3: Hero Image Generation
        from app.services.ugc_pipeline.asset_generator import generate_hero_image
        hero_image_path = generate_hero_image(
            product_image_path=product_images[0],  # Use first uploaded image
            ugc_style=analysis.ugc_style,
            emotional_tone=analysis.emotional_tone,
            visual_keywords=analysis.visual_keywords
        )
        logger.info(f"Hero image: {hero_image_path}")

        # Step 4: Script Generation
        from app.services.ugc_pipeline.script_engine import generate_ugc_script
        breakdown = generate_ugc_script(
            product_name=product_name,
            description=description,
            analysis=analysis,
            target_duration=target_duration
        )
        logger.info(f"Script: {len(breakdown.aroll_scenes)} A-Roll scenes, {len(breakdown.broll_shots)} B-Roll shots")

        # Step 5: A-Roll Asset Generation
        from app.services.ugc_pipeline.asset_generator import generate_aroll_assets
        aroll_scenes_dicts = [s.model_dump() if hasattr(s, 'model_dump') else s for s in breakdown.aroll_scenes]
        aroll_paths = generate_aroll_assets(
            aroll_scenes=aroll_scenes_dicts,
            hero_image_path=hero_image_path
        )
        logger.info(f"A-Roll clips: {len(aroll_paths)}")

        # Step 6: B-Roll Asset Generation
        from app.services.ugc_pipeline.asset_generator import generate_broll_assets
        broll_shots_dicts = [s.model_dump() if hasattr(s, 'model_dump') else s for s in breakdown.broll_shots]
        broll_paths = generate_broll_assets(
            broll_shots=broll_shots_dicts,
            product_image_path=product_images[0]
        )
        logger.info(f"B-Roll clips: {len(broll_paths)}")

        # Step 7: Final Composition
        from app.services.ugc_pipeline.ugc_compositor import compose_ugc_ad
        from app.config import get_settings

        settings = get_settings()
        output_path = os.path.join(settings.composition_output_dir, f"ugc_ad_{uuid4().hex[:8]}.mp4")
        os.makedirs(settings.composition_output_dir, exist_ok=True)

        # Build broll_metadata with paths and overlay_start from breakdown
        broll_metadata = []
        for i, shot_dict in enumerate(broll_shots_dicts):
            broll_metadata.append({
                "path": broll_paths[i],
                "overlay_start": shot_dict.get("overlay_start", 0.0)
            })

        final_path = compose_ugc_ad(
            aroll_paths=aroll_paths,
            broll_metadata=broll_metadata,
            output_path=output_path
        )
        logger.info(f"Final video: {final_path}")

        # Step 8: Save Video Record to DB
        async def _save_ugc_video(job_id, file_path, product_name, analysis_category):
            from app.database import get_task_session_factory
            from app.models import Video
            from datetime import datetime, timezone

            async with get_task_session_factory()() as session:
                video = Video(
                    job_id=job_id,
                    file_path=file_path,
                    status="generated",
                    cost_usd=0.0,  # Mock providers have zero cost
                    extra_data={
                        "gen_id": uuid4().hex,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "pipeline": "ugc_product_ad",
                        "product_name": product_name,
                        "category": analysis_category,
                        "status": "generated"
                    }
                )
                session.add(video)
                await session.commit()
                await session.refresh(video)
                return video.id

        video_id = asyncio.run(_save_ugc_video(job_id, final_path, product_name, analysis.category))

        # Step 9: Mark Job Complete
        asyncio.run(_mark_job_complete(job_id))

        # Step 10: Return result
        return {
            "status": "completed",
            "job_id": job_id,
            "video_id": video_id,
            "video_path": final_path,
            "product_name": product_name,
            "category": analysis.category,
            "aroll_scenes": len(breakdown.aroll_scenes),
            "broll_shots": len(breakdown.broll_shots)
        }

    except Exception as exc:
        logger.error(f"UGC ad generation failed: {exc}")
        asyncio.run(_mark_job_failed(job_id, "ugc_pipeline", str(exc)))
        raise
