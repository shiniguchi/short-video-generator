"""Per-stage Celery tasks for UGC ad pipeline.

Five tasks, one per pipeline stage. Each task:
1. Loads UGCJob from DB (NullPool session)
2. Validates state via UGCJobStateMachine
3. Runs one service function with use_mock=job.use_mock
4. Writes output to UGCJob columns
5. Transitions status to stage review state
6. Commits

On failure, transitions to 'failed' and writes error_message.
"""
import asyncio
import logging

from app.worker import celery_app

logger = logging.getLogger(__name__)


# --- Shared failure helper ---

async def _fail_job(job_id: int, error_msg: str) -> None:
    """Load UGCJob, transition to failed, write error_message, commit."""
    from app.database import get_task_session_factory
    from app.models import UGCJob
    from app.state_machines.ugc_job import UGCJobStateMachine
    from sqlalchemy import select

    session_factory = get_task_session_factory()
    async with session_factory() as session:
        result = await session.execute(select(UGCJob).where(UGCJob.id == job_id))
        job = result.scalars().first()
        if not job:
            logger.error(f"UGCJob {job_id} not found — cannot mark as failed")
            return
        sm = UGCJobStateMachine(model=job, state_field="status", start_value=job.status)
        sm.send("fail")
        job.status = sm.current_state.id
        job.error_message = error_msg
        await session.commit()


# --- Stage 1: Analyze product + generate hero image ---

@celery_app.task(
    bind=True,
    name='app.ugc_tasks.ugc_stage_1_analyze',
    max_retries=1,
    time_limit=600,
)
def ugc_stage_1_analyze(self, job_id: int):
    """Stage 1: Product analysis + hero image generation.

    Runs analyze_product() and generate_hero_image(), writes all analysis_*
    columns and hero_image_path, transitions running -> stage_analysis_review.
    """
    logger.info(f"ugc_stage_1_analyze: starting job {job_id}")

    async def _run():
        from app.database import get_task_session_factory
        from app.models import UGCJob
        from app.schemas import ProductAnalysis
        from app.services.ugc_pipeline.product_analyzer import analyze_product
        from app.services.ugc_pipeline.asset_generator import generate_hero_image
        from app.state_machines.ugc_job import UGCJobStateMachine
        from sqlalchemy import select

        session_factory = get_task_session_factory()
        async with session_factory() as session:
            # Load job
            result = await session.execute(select(UGCJob).where(UGCJob.id == job_id))
            job = result.scalars().first()
            if not job:
                raise ValueError(f"UGCJob {job_id} not found")

            # Validate state transition
            sm = UGCJobStateMachine(model=job, state_field="status", start_value=job.status)

            # Run product analysis
            analysis = analyze_product(
                product_name=job.product_name,
                description=job.description,
                image_count=len(job.product_image_paths or []),
                style_preference=job.style_preference,
                product_url=job.product_url,
                use_mock=job.use_mock
            )
            logger.info(f"Job {job_id}: analysis complete — category={analysis.category}")

            # Run hero image generation
            hero_image_path = generate_hero_image(
                product_image_path=(job.product_image_paths or [""])[0],
                ugc_style=analysis.ugc_style,
                emotional_tone=analysis.emotional_tone,
                visual_keywords=analysis.visual_keywords,
                use_mock=job.use_mock
            )
            logger.info(f"Job {job_id}: hero image generated — {hero_image_path}")

            # Write analysis columns + hero image
            job.analysis_category = analysis.category
            job.analysis_ugc_style = analysis.ugc_style
            job.analysis_emotional_tone = analysis.emotional_tone
            job.analysis_key_features = analysis.key_features
            job.analysis_visual_keywords = analysis.visual_keywords
            job.analysis_target_audience = analysis.target_audience
            job.hero_image_path = hero_image_path

            # Transition: running -> stage_analysis_review
            sm.send("complete_analysis")
            job.status = sm.current_state.id
            await session.commit()
            logger.info(f"Job {job_id}: status -> {job.status}")

    try:
        asyncio.run(_run())
    except Exception as exc:
        logger.error(f"ugc_stage_1_analyze job {job_id} failed: {exc}")
        asyncio.run(_fail_job(job_id, str(exc)))
        raise


# --- Stage 2: Script generation ---

@celery_app.task(
    bind=True,
    name='app.ugc_tasks.ugc_stage_2_script',
    max_retries=1,
    time_limit=600,
)
def ugc_stage_2_script(self, job_id: int):
    """Stage 2: UGC script generation.

    Reconstructs ProductAnalysis from job columns, runs generate_ugc_script(),
    writes master_script, aroll_scenes, broll_shots, transitions running -> stage_script_review.
    """
    logger.info(f"ugc_stage_2_script: starting job {job_id}")

    async def _run():
        from app.database import get_task_session_factory
        from app.models import UGCJob
        from app.schemas import ProductAnalysis
        from app.services.ugc_pipeline.script_engine import generate_ugc_script
        from app.state_machines.ugc_job import UGCJobStateMachine
        from sqlalchemy import select

        session_factory = get_task_session_factory()
        async with session_factory() as session:
            # Load job
            result = await session.execute(select(UGCJob).where(UGCJob.id == job_id))
            job = result.scalars().first()
            if not job:
                raise ValueError(f"UGCJob {job_id} not found")

            # Validate state transition
            sm = UGCJobStateMachine(model=job, state_field="status", start_value=job.status)

            # Reconstruct ProductAnalysis from stored columns
            analysis = ProductAnalysis(
                category=job.analysis_category,
                key_features=job.analysis_key_features or [],
                target_audience=job.analysis_target_audience or "",
                ugc_style=job.analysis_ugc_style or "",
                emotional_tone=job.analysis_emotional_tone or "",
                visual_keywords=job.analysis_visual_keywords or []
            )

            # Run script generation
            breakdown = generate_ugc_script(
                product_name=job.product_name,
                description=job.description,
                analysis=analysis,
                target_duration=job.target_duration,
                use_mock=job.use_mock
            )
            logger.info(f"Job {job_id}: script generated — {len(breakdown.aroll_scenes)} scenes")

            # Write script columns
            job.master_script = breakdown.master_script.model_dump()
            job.aroll_scenes = [s.model_dump() for s in breakdown.aroll_scenes]
            job.broll_shots = [s.model_dump() for s in breakdown.broll_shots]

            # Transition: running -> stage_script_review
            sm.send("complete_script")
            job.status = sm.current_state.id
            await session.commit()
            logger.info(f"Job {job_id}: status -> {job.status}")

    try:
        asyncio.run(_run())
    except Exception as exc:
        logger.error(f"ugc_stage_2_script job {job_id} failed: {exc}")
        asyncio.run(_fail_job(job_id, str(exc)))
        raise


# --- Stage 3: A-Roll asset generation ---

@celery_app.task(
    bind=True,
    name='app.ugc_tasks.ugc_stage_3_aroll',
    max_retries=1,
    time_limit=600,
)
def ugc_stage_3_aroll(self, job_id: int):
    """Stage 3: A-Roll video clip generation.

    Runs generate_aroll_assets(), writes aroll_paths,
    transitions running -> stage_aroll_review.
    """
    logger.info(f"ugc_stage_3_aroll: starting job {job_id}")

    async def _run():
        from app.database import get_task_session_factory
        from app.models import UGCJob
        from app.services.ugc_pipeline.asset_generator import generate_aroll_assets
        from app.state_machines.ugc_job import UGCJobStateMachine
        from sqlalchemy import select

        session_factory = get_task_session_factory()
        async with session_factory() as session:
            # Load job
            result = await session.execute(select(UGCJob).where(UGCJob.id == job_id))
            job = result.scalars().first()
            if not job:
                raise ValueError(f"UGCJob {job_id} not found")

            # Validate state transition
            sm = UGCJobStateMachine(model=job, state_field="status", start_value=job.status)

            # Run A-Roll generation
            aroll_paths = generate_aroll_assets(
                aroll_scenes=job.aroll_scenes or [],
                hero_image_path=job.hero_image_path or "",
                use_mock=job.use_mock
            )
            logger.info(f"Job {job_id}: {len(aroll_paths)} A-Roll clips generated")

            # Write A-Roll paths
            job.aroll_paths = aroll_paths

            # Transition: running -> stage_aroll_review
            sm.send("complete_aroll")
            job.status = sm.current_state.id
            await session.commit()
            logger.info(f"Job {job_id}: status -> {job.status}")

    try:
        asyncio.run(_run())
    except Exception as exc:
        logger.error(f"ugc_stage_3_aroll job {job_id} failed: {exc}")
        asyncio.run(_fail_job(job_id, str(exc)))
        raise


# --- Stage 4: B-Roll asset generation ---

@celery_app.task(
    bind=True,
    name='app.ugc_tasks.ugc_stage_4_broll',
    max_retries=1,
    time_limit=600,
)
def ugc_stage_4_broll(self, job_id: int):
    """Stage 4: B-Roll product shot generation.

    Runs generate_broll_assets(), writes broll_paths,
    transitions running -> stage_broll_review.
    """
    logger.info(f"ugc_stage_4_broll: starting job {job_id}")

    async def _run():
        from app.database import get_task_session_factory
        from app.models import UGCJob
        from app.services.ugc_pipeline.asset_generator import generate_broll_assets
        from app.state_machines.ugc_job import UGCJobStateMachine
        from sqlalchemy import select

        session_factory = get_task_session_factory()
        async with session_factory() as session:
            # Load job
            result = await session.execute(select(UGCJob).where(UGCJob.id == job_id))
            job = result.scalars().first()
            if not job:
                raise ValueError(f"UGCJob {job_id} not found")

            # Validate state transition
            sm = UGCJobStateMachine(model=job, state_field="status", start_value=job.status)

            # Run B-Roll generation
            broll_paths = generate_broll_assets(
                broll_shots=job.broll_shots or [],
                product_images=job.product_image_paths or [],
                use_mock=job.use_mock
            )
            logger.info(f"Job {job_id}: {len(broll_paths)} B-Roll clips generated")

            # Write B-Roll paths
            job.broll_paths = broll_paths

            # Transition: running -> stage_broll_review
            sm.send("complete_broll")
            job.status = sm.current_state.id
            await session.commit()
            logger.info(f"Job {job_id}: status -> {job.status}")

    try:
        asyncio.run(_run())
    except Exception as exc:
        logger.error(f"ugc_stage_4_broll job {job_id} failed: {exc}")
        asyncio.run(_fail_job(job_id, str(exc)))
        raise


# --- Stage 5: Final composition ---

@celery_app.task(
    bind=True,
    name='app.ugc_tasks.ugc_stage_5_compose',
    max_retries=1,
    time_limit=1200,  # 20 min — composition is slower
)
def ugc_stage_5_compose(self, job_id: int):
    """Stage 5: Final UGC ad composition.

    Builds broll_metadata from stored shots and paths, runs compose_ugc_ad(),
    writes final_video_path and cost_usd, transitions running -> stage_composition_review.
    """
    logger.info(f"ugc_stage_5_compose: starting job {job_id}")

    async def _run():
        import os
        from uuid import uuid4
        from app.database import get_task_session_factory
        from app.models import UGCJob
        from app.services.ugc_pipeline.ugc_compositor import compose_ugc_ad
        from app.state_machines.ugc_job import UGCJobStateMachine
        from app.config import get_settings
        from sqlalchemy import select

        session_factory = get_task_session_factory()
        async with session_factory() as session:
            # Load job
            result = await session.execute(select(UGCJob).where(UGCJob.id == job_id))
            job = result.scalars().first()
            if not job:
                raise ValueError(f"UGCJob {job_id} not found")

            # Validate state transition
            sm = UGCJobStateMachine(model=job, state_field="status", start_value=job.status)

            # Build broll_metadata from stored shots and paths
            broll_shots = job.broll_shots or []
            broll_paths = job.broll_paths or []
            broll_metadata = [
                {
                    "path": broll_paths[i],
                    "overlay_start": shot.get("overlay_start", 0.0)
                }
                for i, shot in enumerate(broll_shots)
                if i < len(broll_paths)
            ]

            # Build output path
            settings = get_settings()
            os.makedirs(settings.composition_output_dir, exist_ok=True)
            output_path = os.path.join(
                settings.composition_output_dir,
                f"ugc_ad_{job_id}_{uuid4().hex[:8]}.mp4"
            )

            # Run composition
            final_path = compose_ugc_ad(
                aroll_paths=job.aroll_paths or [],
                broll_metadata=broll_metadata,
                output_path=output_path
            )
            logger.info(f"Job {job_id}: composition complete — {final_path}")

            # Write output columns
            job.final_video_path = final_path
            job.cost_usd = 0.0  # Mock cost; real tracking is future work

            # Transition: running -> stage_composition_review
            sm.send("complete_composition")
            job.status = sm.current_state.id
            await session.commit()
            logger.info(f"Job {job_id}: status -> {job.status}")

    try:
        asyncio.run(_run())
    except Exception as exc:
        logger.error(f"ugc_stage_5_compose job {job_id} failed: {exc}")
        asyncio.run(_fail_job(job_id, str(exc)))
        raise


# --- LP Hero Image Regeneration ---

@celery_app.task(
    bind=True,
    name='app.ugc_tasks.lp_hero_regen',
    max_retries=1,
    time_limit=300,
)
def lp_hero_regen(self, lp_id: int):
    """Regenerate LP hero image. Stores result as candidate (never overwrites approved hero)."""
    logger.info(f"lp_hero_regen: starting for LP {lp_id}")

    async def _run():
        from app.database import get_task_session_factory
        from app.models import LandingPage, UGCJob
        from sqlalchemy import select

        session_factory = get_task_session_factory()
        async with session_factory() as session:
            result = await session.execute(
                select(LandingPage).where(LandingPage.id == lp_id)
            )
            lp = result.scalar_one_or_none()
            if not lp:
                raise ValueError(f"LandingPage {lp_id} not found")

            # Determine use_mock from linked UGCJob
            use_mock = False
            if lp.ugc_job_id:
                ugc_result = await session.execute(
                    select(UGCJob).where(UGCJob.id == lp.ugc_job_id)
                )
                ugc_job = ugc_result.scalar_one_or_none()
                if ugc_job:
                    use_mock = ugc_job.use_mock

            # Generate new hero image — stores as candidate per "regeneration produces candidates" decision
            from app.services.ugc_pipeline.asset_generator import generate_hero_image
            candidate_path = generate_hero_image(
                product_image_path=lp.lp_hero_image_path or "",
                ugc_style="product-hero",
                emotional_tone="professional",
                visual_keywords=["product", "hero", "landing page"],
                use_mock=use_mock
            )

            # Store as candidate — never mutate approved content in place
            lp.lp_hero_candidate_path = candidate_path
            await session.commit()
            logger.info(f"LP {lp_id}: hero candidate generated — {candidate_path}")

    try:
        asyncio.run(_run())
    except Exception as exc:
        logger.error(f"lp_hero_regen LP {lp_id} failed: {exc}")
        raise
