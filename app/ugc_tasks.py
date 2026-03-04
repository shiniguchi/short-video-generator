"""Per-stage Celery tasks for UGC ad pipeline.

Each stage task: loads UGCJob, runs service logic, transitions state, commits.
On failure, transitions to 'failed' and writes error_message.
"""
import asyncio
import logging

from app.worker import celery_app

logger = logging.getLogger(__name__)


# --- Shared helpers ---

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


def _run_with_job(task_name, job_id, handler, *, fail_on_error=False):
    """Load UGCJob, call handler(session, job), handle errors.

    Args:
        task_name: Celery task name for log messages
        job_id: UGCJob.id
        handler: async fn(session, job) — does the actual work + commits
        fail_on_error: if True, also transition job to 'failed' on exception
    """
    logger.info(f"{task_name}: starting job {job_id}")

    async def _run():
        from app.database import get_task_session_factory
        from app.models import UGCJob
        from sqlalchemy import select

        session_factory = get_task_session_factory()
        async with session_factory() as session:
            result = await session.execute(select(UGCJob).where(UGCJob.id == job_id))
            job = result.scalars().first()
            if not job:
                raise ValueError(f"UGCJob {job_id} not found")
            await handler(session, job)

    try:
        asyncio.run(_run())
    except Exception as exc:
        logger.error(f"{task_name} job {job_id} failed: {exc}")
        if fail_on_error:
            asyncio.run(_fail_job(job_id, str(exc)))
        raise


def _build_analysis(job):
    """Reconstruct ProductAnalysis from stored UGCJob columns."""
    from app.schemas import ProductAnalysis
    return ProductAnalysis(
        category=job.analysis_category,
        key_features=job.analysis_key_features or [],
        target_audience=job.analysis_target_audience or "",
        ugc_style=job.analysis_ugc_style or "",
        emotional_tone=job.analysis_emotional_tone or "",
        visual_keywords=job.analysis_visual_keywords or [],
    )


# --- Stage 1: Analyze product + generate hero image ---

@celery_app.task(bind=True, name='app.ugc_tasks.ugc_stage_1_analyze', max_retries=1, time_limit=600)
def ugc_stage_1_analyze(self, job_id: int):
    """Stage 1: Product analysis + hero image generation."""

    async def _handler(session, job):
        from app.services.ugc_pipeline.product_analyzer import analyze_product
        from app.services.ugc_pipeline.asset_generator import generate_hero_image
        from app.state_machines.ugc_job import UGCJobStateMachine

        sm = UGCJobStateMachine(model=job, state_field="status", start_value=job.status)

        analysis = analyze_product(
            product_name=job.product_name, description=job.description,
            image_count=len(job.product_image_paths or []),
            style_preference=job.style_preference, product_url=job.product_url,
            use_mock=job.use_mock,
        )
        logger.info(f"Job {job_id}: analysis complete — category={analysis.category}")

        hero_image_path = generate_hero_image(
            product_image_path=(job.product_image_paths or [""])[0],
            ugc_style=analysis.ugc_style, emotional_tone=analysis.emotional_tone,
            visual_keywords=analysis.visual_keywords, product_name=job.product_name,
            use_mock=job.use_mock,
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

        sm.send("complete_analysis")
        job.status = sm.current_state.id
        await session.commit()
        logger.info(f"Job {job_id}: status -> {job.status}")

    _run_with_job("ugc_stage_1_analyze", job_id, _handler, fail_on_error=True)


# --- Per-item regeneration during analysis review ---

@celery_app.task(bind=True, name='app.ugc_tasks.ugc_regen_hero_image', max_retries=1)
def ugc_regen_hero_image(self, job_id: int, reference_paths=None, sketch_paths=None):
    """Regenerate only the hero image for a job in stage_analysis_review."""

    async def _handler(session, job):
        from app.services.ugc_pipeline.asset_generator import generate_hero_image

        sketch_path = sketch_paths[-1] if sketch_paths else job.hero_sketch_path

        hero_image_path = generate_hero_image(
            product_image_path=(job.product_image_paths or [""])[0],
            ugc_style=job.analysis_ugc_style or "lifestyle",
            emotional_tone=job.analysis_emotional_tone or "authentic",
            visual_keywords=job.analysis_visual_keywords or [],
            product_name=job.product_name, use_mock=job.use_mock,
            sketch_path=sketch_path, reference_images=reference_paths,
        )

        # Push current image into history before overwriting
        if job.hero_image_path:
            history = list(job.hero_image_history or [])
            history.insert(0, job.hero_image_path)
            job.hero_image_history = history

        job.hero_image_path = hero_image_path
        job.error_message = None
        await session.commit()
        logger.info(f"Job {job_id}: hero image regenerated — {hero_image_path}")

    _run_with_job("ugc_regen_hero_image", job_id, _handler)


@celery_app.task(bind=True, name='app.ugc_tasks.ugc_regen_analysis_field', max_retries=1)
def ugc_regen_analysis_field(self, job_id: int, field: str):
    """Regenerate a single analysis field by re-running analyze_product."""

    async def _handler(session, job):
        from app.services.ugc_pipeline.product_analyzer import analyze_product

        analysis = analyze_product(
            product_name=job.product_name, description=job.description,
            image_count=len(job.product_image_paths or []),
            style_preference=job.style_preference, product_url=job.product_url,
            use_mock=job.use_mock,
        )

        field_map = {
            "analysis_category": "category", "analysis_ugc_style": "ugc_style",
            "analysis_emotional_tone": "emotional_tone", "analysis_target_audience": "target_audience",
            "analysis_key_features": "key_features", "analysis_visual_keywords": "visual_keywords",
        }
        attr = field_map.get(field)
        if attr:
            setattr(job, field, getattr(analysis, attr))
            await session.commit()
            logger.info(f"Job {job_id}: regenerated {field} = {getattr(analysis, attr)}")

    _run_with_job("ugc_regen_analysis_field", job_id, _handler)


# --- Stage 2: Script generation ---

@celery_app.task(bind=True, name='app.ugc_tasks.ugc_stage_2_script', max_retries=1, time_limit=600)
def ugc_stage_2_script(self, job_id: int):
    """Stage 2: UGC script generation."""

    async def _handler(session, job):
        from app.schemas import ProductAnalysis
        from app.services.ugc_pipeline.script_engine import generate_ugc_script
        from app.state_machines.ugc_job import UGCJobStateMachine

        sm = UGCJobStateMachine(model=job, state_field="status", start_value=job.status)
        analysis = _build_analysis(job)

        breakdown = generate_ugc_script(
            product_name=job.product_name, description=job.description,
            analysis=analysis, target_duration=job.target_duration,
            use_mock=job.use_mock,
        )
        logger.info(f"Job {job_id}: script generated — {len(breakdown.aroll_scenes)} scenes")

        job.master_script = breakdown.master_script.model_dump()
        job.aroll_scenes = [s.model_dump() for s in breakdown.aroll_scenes]
        job.broll_shots = [s.model_dump() for s in breakdown.broll_shots]

        sm.send("complete_script")
        job.status = sm.current_state.id
        await session.commit()
        logger.info(f"Job {job_id}: status -> {job.status}")

    _run_with_job("ugc_stage_2_script", job_id, _handler, fail_on_error=True)


# --- Script regeneration (no state transition) ---

@celery_app.task(bind=True, name='app.ugc_tasks.ugc_regen_script', max_retries=1, time_limit=600)
def ugc_regen_script(self, job_id: int):
    """Regenerate the entire script without changing job status."""

    async def _handler(session, job):
        from app.services.ugc_pipeline.script_engine import generate_ugc_script

        breakdown = generate_ugc_script(
            product_name=job.product_name, description=job.description,
            analysis=_build_analysis(job), target_duration=job.target_duration,
            use_mock=job.use_mock,
        )
        logger.info(f"Job {job_id}: script regenerated — {len(breakdown.aroll_scenes)} scenes")

        job.master_script = breakdown.master_script.model_dump()
        job.aroll_scenes = [s.model_dump() for s in breakdown.aroll_scenes]
        job.broll_shots = [s.model_dump() for s in breakdown.broll_shots]
        await session.commit()

    _run_with_job("ugc_regen_script", job_id, _handler)


@celery_app.task(bind=True, name='app.ugc_tasks.ugc_regen_script_field', max_retries=1, time_limit=600)
def ugc_regen_script_field(self, job_id: int, field_type: str, field_index: int = 0):
    """Regenerate a single script field/scene/shot."""

    async def _handler(session, job):
        from app.services.ugc_pipeline.script_engine import generate_ugc_script

        breakdown = generate_ugc_script(
            product_name=job.product_name, description=job.description,
            analysis=_build_analysis(job), target_duration=job.target_duration,
            use_mock=job.use_mock,
        )

        # Update only the targeted field
        if field_type.startswith("master_"):
            attr = field_type.replace("master_", "")
            ms = dict(job.master_script or {})
            ms[attr] = getattr(breakdown.master_script, attr)
            # Recompute full_script when a section field changes
            if attr in ("hook", "problem", "proof", "cta"):
                parts = [ms.get(k, "").strip() for k in ("hook", "problem", "proof", "cta")]
                ms["full_script"] = "\n\n".join(p for p in parts if p)
                from app.services.ugc_pipeline.script_engine import resplit_script_to_scenes
                from sqlalchemy.orm.attributes import flag_modified
                scenes = list(job.aroll_scenes or [])
                if scenes:
                    segments = resplit_script_to_scenes(ms["full_script"], len(scenes), job.use_mock)
                    for i, text in enumerate(segments):
                        if i < len(scenes):
                            scenes[i]["script_text"] = text
                    job.aroll_scenes = scenes
                    flag_modified(job, "aroll_scenes")
            job.master_script = ms
            logger.info(f"Job {job_id}: regenerated master_script.{attr}")
        elif field_type == "aroll_scene":
            scenes = list(job.aroll_scenes or [])
            new_scenes = [s.model_dump() for s in breakdown.aroll_scenes]
            if field_index < len(new_scenes):
                while len(scenes) <= field_index:
                    scenes.append({})
                scenes[field_index] = new_scenes[field_index]
                job.aroll_scenes = scenes
                logger.info(f"Job {job_id}: regenerated aroll_scene[{field_index}]")
        elif field_type == "broll_shot":
            shots = list(job.broll_shots or [])
            new_shots = [s.model_dump() for s in breakdown.broll_shots]
            if field_index < len(new_shots):
                while len(shots) <= field_index:
                    shots.append({})
                shots[field_index] = new_shots[field_index]
                job.broll_shots = shots
                logger.info(f"Job {job_id}: regenerated broll_shot[{field_index}]")

        await session.commit()

    _run_with_job("ugc_regen_script_field", job_id, _handler)


# --- Re-split scene script_text after manual section edit ---

@celery_app.task(bind=True, name="ugc_resplit_scenes", max_retries=1, time_limit=120)
def ugc_resplit_scenes(self, job_id: int):
    """Re-split full_script into scene script_text after manual section edit."""

    async def _handler(session, job):
        from app.services.ugc_pipeline.script_engine import resplit_script_to_scenes
        from sqlalchemy.orm.attributes import flag_modified

        ms = dict(job.master_script or {})
        full_script = ms.get("full_script", "")
        scenes = list(job.aroll_scenes or [])

        if not full_script or not scenes:
            logger.info(f"Job {job_id}: no full_script or scenes to resplit")
            return

        segments = resplit_script_to_scenes(full_script, len(scenes), job.use_mock)
        for i, text in enumerate(segments):
            if i < len(scenes):
                scenes[i]["script_text"] = text

        job.aroll_scenes = scenes
        flag_modified(job, "aroll_scenes")
        await session.commit()
        logger.info(f"Job {job_id}: resplit {len(segments)} scene script_text segments")

    _run_with_job("ugc_resplit_scenes", job_id, _handler)


# --- Stage 3a: A-Roll image generation ---

@celery_app.task(bind=True, name='app.ugc_tasks.ugc_stage_3a_aroll_images', max_retries=1, time_limit=600)
def ugc_stage_3a_aroll_images(self, job_id: int):
    """Stage 3a: Generate per-scene A-Roll images for review."""

    async def _handler(session, job):
        from app.services.ugc_pipeline.asset_generator import generate_aroll_images
        from app.state_machines.ugc_job import UGCJobStateMachine

        sm = UGCJobStateMachine(model=job, state_field="status", start_value=job.status)
        persona = (job.master_script or {}).get("creator_persona", "")

        image_paths = generate_aroll_images(
            aroll_scenes=job.aroll_scenes or [], hero_image_path=job.hero_image_path or "",
            use_mock=job.use_mock, creator_persona=persona,
            product_image_paths=job.product_image_paths or [],
        )
        logger.info(f"Job {job_id}: {len(image_paths)} A-Roll images generated")

        job.aroll_image_paths = image_paths
        sm.send("complete_aroll_images")
        job.status = sm.current_state.id
        await session.commit()
        logger.info(f"Job {job_id}: status -> {job.status}")

    _run_with_job("ugc_stage_3a_aroll_images", job_id, _handler, fail_on_error=True)


# --- Stage 3: A-Roll video generation (from reviewed images) ---

@celery_app.task(bind=True, name='app.ugc_tasks.ugc_stage_3_aroll', max_retries=1, time_limit=600)
def ugc_stage_3_aroll(self, job_id: int):
    """Stage 3: A-Roll video clip generation from reviewed images."""

    async def _handler(session, job):
        from app.services.ugc_pipeline.asset_generator import generate_aroll_assets
        from app.state_machines.ugc_job import UGCJobStateMachine

        sm = UGCJobStateMachine(model=job, state_field="status", start_value=job.status)
        persona = (job.master_script or {}).get("creator_persona", "")

        aroll_paths = generate_aroll_assets(
            aroll_scenes=job.aroll_scenes or [], aroll_image_paths=job.aroll_image_paths or [],
            use_mock=job.use_mock, creator_persona=persona, existing_paths=job.aroll_paths,
        )
        logger.info(f"Job {job_id}: {len(aroll_paths)} A-Roll clips generated")

        job.aroll_paths = aroll_paths
        sm.send("complete_aroll")
        job.status = sm.current_state.id
        await session.commit()
        logger.info(f"Job {job_id}: status -> {job.status}")

    _run_with_job("ugc_stage_3_aroll", job_id, _handler, fail_on_error=True)


# --- Stage 4a: B-Roll image generation ---

@celery_app.task(bind=True, name='app.ugc_tasks.ugc_stage_4a_broll_images', max_retries=1, time_limit=600)
def ugc_stage_4a_broll_images(self, job_id: int):
    """Stage 4a: Generate per-shot B-Roll images for review."""

    async def _handler(session, job):
        from app.services.ugc_pipeline.asset_generator import generate_broll_images
        from app.state_machines.ugc_job import UGCJobStateMachine

        sm = UGCJobStateMachine(model=job, state_field="status", start_value=job.status)

        image_paths = generate_broll_images(
            broll_shots=job.broll_shots or [], product_images=job.product_image_paths or [],
            use_mock=job.use_mock,
        )
        logger.info(f"Job {job_id}: {len(image_paths)} B-Roll images generated")

        job.broll_image_paths = image_paths
        sm.send("complete_broll_images")
        job.status = sm.current_state.id
        await session.commit()
        logger.info(f"Job {job_id}: status -> {job.status}")

    _run_with_job("ugc_stage_4a_broll_images", job_id, _handler, fail_on_error=True)


# --- Stage 4: B-Roll video generation (from reviewed images) ---

@celery_app.task(bind=True, name='app.ugc_tasks.ugc_stage_4_broll', max_retries=1, time_limit=600)
def ugc_stage_4_broll(self, job_id: int):
    """Stage 4: B-Roll video clip generation from reviewed images."""

    async def _handler(session, job):
        from app.services.ugc_pipeline.asset_generator import generate_broll_assets
        from app.state_machines.ugc_job import UGCJobStateMachine

        sm = UGCJobStateMachine(model=job, state_field="status", start_value=job.status)

        broll_paths = generate_broll_assets(
            broll_shots=job.broll_shots or [], broll_image_paths=job.broll_image_paths or [],
            use_mock=job.use_mock, existing_paths=job.broll_paths,
        )
        logger.info(f"Job {job_id}: {len(broll_paths)} B-Roll clips generated")

        job.broll_paths = broll_paths
        sm.send("complete_broll")
        job.status = sm.current_state.id
        await session.commit()
        logger.info(f"Job {job_id}: status -> {job.status}")

    _run_with_job("ugc_stage_4_broll", job_id, _handler, fail_on_error=True)


# --- Per-scene image regeneration ---

@celery_app.task(
    bind=True,
    name='app.ugc_tasks.ugc_regen_aroll_scene_image',
    max_retries=1,
)
def ugc_regen_aroll_scene_image(self, job_id: int, scene_index: int):
    """Regenerate a single A-Roll scene image."""
    logger.info(f"ugc_regen_aroll_scene_image: job {job_id}, scene {scene_index}")

    async def _run():
        from app.database import get_task_session_factory
        from app.models import UGCJob
        from app.services.ugc_pipeline.asset_generator import _get_image_provider
        from sqlalchemy import select
        from sqlalchemy.orm.attributes import flag_modified
        import os

        session_factory = get_task_session_factory()
        async with session_factory() as session:
            result = await session.execute(select(UGCJob).where(UGCJob.id == job_id))
            job = result.scalars().first()
            if not job:
                raise ValueError(f"UGCJob {job_id} not found")

            # Single-image model: scene_index kept for backward compat, always regen the one creator image
            from app.services.ugc_pipeline.asset_generator import _sanitize_veo_prompt

            persona = (job.master_script or {}).get("creator_persona", "")
            product_desc = job.product_name or "the product"
            persona_prefix = f"{persona}. " if persona else ""
            safe_visual = _sanitize_veo_prompt(
                f"{persona_prefix}Looking at camera, natural confident pose. "
                f"Product: {product_desc} held naturally in frame.",
                preserve_terms=[product_desc],
            )
            prompt = (
                f"{safe_visual} "
                f"IMPORTANT: The exact product from the reference image MUST be prominently visible "
                f"in the person's hands or clearly in frame. Keep the product identical to the reference — "
                f"same shape, color, material, and size. "
                f"Professional UGC style, vertical 9:16, soft natural lighting."
            )

            # Use hero image as product reference
            hero = job.hero_image_path or ""
            ref_images = [hero] if hero and os.path.exists(hero) else None

            image_provider = _get_image_provider(use_mock=job.use_mock)
            paths = image_provider.generate_image(
                prompt=prompt, width=720, height=1280, num_images=1,
                reference_images=ref_images, subject_type="product",
                subject_description=product_desc,
            )

            # Save old image to history[0] before overwriting
            image_paths = list(job.aroll_image_paths or [])
            history = list(job.aroll_image_history or [])
            if not history:
                history.append([])
            if image_paths and image_paths[0]:
                history[0] = [image_paths[0]] + history[0]
                job.aroll_image_history = history
                flag_modified(job, "aroll_image_history")

            # Always write to index 0 (single creator image)
            job.aroll_image_paths = [paths[0]]
            flag_modified(job, "aroll_image_paths")
            job.error_message = None
            await session.commit()
            logger.info(f"Job {job_id}: A-Roll creator image regenerated -> {paths[0]}")

    try:
        asyncio.run(_run())
    except Exception as exc:
        logger.error(f"ugc_regen_aroll_scene_image job {job_id} scene {scene_index} failed: {exc}")
        raise


@celery_app.task(
    bind=True,
    name='app.ugc_tasks.ugc_regen_all_aroll_images',
    max_retries=1,
    time_limit=600,
)
def ugc_regen_all_aroll_images(self, job_id: int):
    """Regenerate all A-Roll scene images together for character consistency."""
    logger.info(f"ugc_regen_all_aroll_images: starting job {job_id}")

    async def _run():
        from app.database import get_task_session_factory
        from app.models import UGCJob
        from app.services.ugc_pipeline.asset_generator import generate_aroll_images
        from sqlalchemy import select
        from sqlalchemy.orm.attributes import flag_modified

        session_factory = get_task_session_factory()
        async with session_factory() as session:
            result = await session.execute(select(UGCJob).where(UGCJob.id == job_id))
            job = result.scalars().first()
            if not job:
                raise ValueError(f"UGCJob {job_id} not found")

            # Save old images to per-scene history before overwriting
            old_paths = list(job.aroll_image_paths or [])
            if any(old_paths):
                history = list(job.aroll_image_history or [])
                while len(history) < len(old_paths):
                    history.append([])
                for i, old_p in enumerate(old_paths):
                    if old_p:
                        history[i] = [old_p] + history[i]
                job.aroll_image_history = history
                flag_modified(job, "aroll_image_history")

            persona = (job.master_script or {}).get("creator_persona", "")
            image_paths = generate_aroll_images(
                aroll_scenes=job.aroll_scenes or [],
                hero_image_path=job.hero_image_path or "",
                use_mock=job.use_mock,
                creator_persona=persona,
                product_image_paths=job.product_image_paths or [],
            )
            logger.info(f"Job {job_id}: {len(image_paths)} A-Roll images regenerated (all scenes)")

            job.aroll_image_paths = image_paths
            flag_modified(job, "aroll_image_paths")
            job.error_message = None
            await session.commit()

    try:
        asyncio.run(_run())
    except Exception as exc:
        logger.error(f"ugc_regen_all_aroll_images job {job_id} failed: {exc}")
        raise


@celery_app.task(
    bind=True,
    name='app.ugc_tasks.ugc_regen_broll_shot_image',
    max_retries=1,
)
def ugc_regen_broll_shot_image(self, job_id: int, shot_index: int):
    """Regenerate a single B-Roll shot image."""
    logger.info(f"ugc_regen_broll_shot_image: job {job_id}, shot {shot_index}")

    async def _run():
        from app.database import get_task_session_factory
        from app.models import UGCJob
        from app.services.ugc_pipeline.asset_generator import _get_image_provider
        from sqlalchemy import select
        from sqlalchemy.orm.attributes import flag_modified

        session_factory = get_task_session_factory()
        async with session_factory() as session:
            result = await session.execute(select(UGCJob).where(UGCJob.id == job_id))
            job = result.scalars().first()
            if not job:
                raise ValueError(f"UGCJob {job_id} not found")

            shots = job.broll_shots or []
            if shot_index < 0 or shot_index >= len(shots):
                raise ValueError(f"Invalid shot_index {shot_index}")

            shot = shots[shot_index]
            image_prompt = shot.get("image_prompt", "")
            ref_index = shot.get("reference_image_index", 0)
            product_images = job.product_image_paths or []
            ref_index = max(0, min(ref_index, len(product_images) - 1))
            reference_image = product_images[ref_index] if product_images else ""

            image_provider = _get_image_provider(use_mock=job.use_mock)
            ref_list = [reference_image] if reference_image else None
            paths = image_provider.generate_image(
                prompt=image_prompt, width=720, height=1280, num_images=1,
                reference_images=ref_list,
            )

            # Save old image to per-scene history before overwriting
            image_paths = list(job.broll_image_paths or [])
            history = list(job.broll_image_history or [])
            while len(history) <= shot_index:
                history.append([])
            if shot_index < len(image_paths) and image_paths[shot_index]:
                history[shot_index] = [image_paths[shot_index]] + history[shot_index]
                job.broll_image_history = history
                flag_modified(job, "broll_image_history")

            # Update single index in broll_image_paths
            while len(image_paths) <= shot_index:
                image_paths.append("")
            image_paths[shot_index] = paths[0]
            job.broll_image_paths = image_paths
            flag_modified(job, "broll_image_paths")
            job.error_message = None
            await session.commit()
            logger.info(f"Job {job_id}: B-Roll shot {shot_index} image regenerated -> {paths[0]}")

    try:
        asyncio.run(_run())
    except Exception as exc:
        logger.error(f"ugc_regen_broll_shot_image job {job_id} shot {shot_index} failed: {exc}")
        raise


# --- Regenerate all B-Roll images ---

@celery_app.task(
    bind=True,
    name='app.ugc_tasks.ugc_regen_all_broll_images',
    max_retries=1,
    time_limit=600,
)
def ugc_regen_all_broll_images(self, job_id: int):
    """Regenerate all B-Roll shot images."""
    logger.info(f"ugc_regen_all_broll_images: starting job {job_id}")

    async def _run():
        from app.database import get_task_session_factory
        from app.models import UGCJob
        from app.services.ugc_pipeline.asset_generator import generate_broll_images
        from sqlalchemy import select
        from sqlalchemy.orm.attributes import flag_modified

        session_factory = get_task_session_factory()
        async with session_factory() as session:
            result = await session.execute(select(UGCJob).where(UGCJob.id == job_id))
            job = result.scalars().first()
            if not job:
                raise ValueError(f"UGCJob {job_id} not found")

            # Save old images to per-scene history before overwriting
            old_paths = list(job.broll_image_paths or [])
            if any(old_paths):
                history = list(job.broll_image_history or [])
                while len(history) < len(old_paths):
                    history.append([])
                for i, old_p in enumerate(old_paths):
                    if old_p:
                        history[i] = [old_p] + history[i]
                job.broll_image_history = history
                flag_modified(job, "broll_image_history")

            image_paths = generate_broll_images(
                broll_shots=job.broll_shots or [],
                product_images=job.product_image_paths or [],
                use_mock=job.use_mock,
            )
            logger.info(f"Job {job_id}: {len(image_paths)} B-Roll images regenerated (all shots)")

            job.broll_image_paths = image_paths
            flag_modified(job, "broll_image_paths")
            job.error_message = None
            await session.commit()

    try:
        asyncio.run(_run())
    except Exception as exc:
        logger.error(f"ugc_regen_all_broll_images job {job_id} failed: {exc}")
        raise


# --- Regenerate all B-Roll videos ---

@celery_app.task(
    bind=True,
    name='app.ugc_tasks.ugc_regen_all_broll_videos',
    max_retries=1,
    time_limit=900,
)
def ugc_regen_all_broll_videos(self, job_id: int):
    """Regenerate all B-Roll video clips from their shot images."""
    logger.info(f"ugc_regen_all_broll_videos: starting job {job_id}")

    async def _run():
        from app.database import get_task_session_factory
        from app.models import UGCJob
        from app.services.ugc_pipeline.asset_generator import generate_broll_assets
        from sqlalchemy import select

        session_factory = get_task_session_factory()
        async with session_factory() as session:
            result = await session.execute(select(UGCJob).where(UGCJob.id == job_id))
            job = result.scalars().first()
            if not job:
                raise ValueError(f"UGCJob {job_id} not found")

            broll_paths = generate_broll_assets(
                broll_shots=job.broll_shots or [],
                broll_image_paths=job.broll_image_paths or [],
                use_mock=job.use_mock,
            )
            logger.info(f"Job {job_id}: {len(broll_paths)} B-Roll videos regenerated (all shots)")

            job.broll_paths = broll_paths
            job.error_message = None
            await session.commit()

    try:
        asyncio.run(_run())
    except Exception as exc:
        logger.error(f"ugc_regen_all_broll_videos job {job_id} failed: {exc}")
        raise


# --- Per-clip video regeneration ---

@celery_app.task(
    bind=True,
    name='app.ugc_tasks.ugc_regen_aroll_scene_video',
    max_retries=1,
    time_limit=300,
)
def ugc_regen_aroll_scene_video(self, job_id: int, scene_index: int):
    """Regenerate a single A-Roll video clip from its scene image."""
    logger.info(f"ugc_regen_aroll_scene_video: job {job_id}, scene {scene_index}")

    async def _run():
        from app.database import get_task_session_factory
        from app.models import UGCJob
        from app.services.ugc_pipeline.asset_generator import _get_veo_or_mock
        from sqlalchemy import select

        session_factory = get_task_session_factory()
        async with session_factory() as session:
            result = await session.execute(select(UGCJob).where(UGCJob.id == job_id))
            job = result.scalars().first()
            if not job:
                raise ValueError(f"UGCJob {job_id} not found")

            scenes = job.aroll_scenes or []
            if scene_index < 0 or scene_index >= len(scenes):
                raise ValueError(f"Invalid scene_index {scene_index}")

            scene = scenes[scene_index]
            visual_prompt = scene.get("visual_prompt", "")
            camera_angle = scene.get("camera_angle", "medium close-up")
            script_text = scene.get("script_text", "")
            duration_seconds = 8  # Always max — Veo snaps to [4,6,8], shorter clips truncate voiceover
            persona = (job.master_script or {}).get("creator_persona", "")
            persona_prefix = f"[Creator: {persona}] " if persona else ""
            # Include script_text so Veo 3 generates matching speech audio
            dialogue = f' The person says: "{script_text}"' if script_text else ""
            full_prompt = f"{persona_prefix}{visual_prompt} Camera: {camera_angle}.{dialogue}"

            # All clips use the single creator image
            image_paths = job.aroll_image_paths or []
            image_path = image_paths[0] if image_paths else ""
            if not image_path:
                raise ValueError(f"No source image for scene {scene_index}")

            veo = _get_veo_or_mock(use_mock=job.use_mock)
            clip_path = veo.generate_clip_from_image(
                prompt=full_prompt,
                image_path=image_path,
                duration_seconds=duration_seconds,
                width=720,
                height=1280,
            )

            # Save old video to history before overwriting
            from sqlalchemy.orm.attributes import flag_modified
            aroll_paths = list(job.aroll_paths or [])
            history = list(job.aroll_video_history or [])
            while len(history) <= scene_index:
                history.append([])
            if scene_index < len(aroll_paths) and aroll_paths[scene_index]:
                history[scene_index].insert(0, aroll_paths[scene_index])
            job.aroll_video_history = history
            flag_modified(job, "aroll_video_history")

            while len(aroll_paths) <= scene_index:
                aroll_paths.append("")
            aroll_paths[scene_index] = clip_path
            job.aroll_paths = aroll_paths
            job.error_message = None
            await session.commit()
            logger.info(f"Job {job_id}: A-Roll scene {scene_index} video regenerated -> {clip_path}")

    try:
        asyncio.run(_run())
    except Exception as exc:
        logger.error(f"ugc_regen_aroll_scene_video job {job_id} scene {scene_index} failed: {exc}")
        raise


@celery_app.task(
    bind=True,
    name='app.ugc_tasks.ugc_regen_broll_shot_video',
    max_retries=1,
    time_limit=300,
)
def ugc_regen_broll_shot_video(self, job_id: int, shot_index: int):
    """Regenerate a single B-Roll video clip from its shot image."""
    logger.info(f"ugc_regen_broll_shot_video: job {job_id}, shot {shot_index}")

    async def _run():
        from app.database import get_task_session_factory
        from app.models import UGCJob
        from app.services.ugc_pipeline.asset_generator import _get_veo_or_mock
        from sqlalchemy import select

        session_factory = get_task_session_factory()
        async with session_factory() as session:
            result = await session.execute(select(UGCJob).where(UGCJob.id == job_id))
            job = result.scalars().first()
            if not job:
                raise ValueError(f"UGCJob {job_id} not found")

            shots = job.broll_shots or []
            if shot_index < 0 or shot_index >= len(shots):
                raise ValueError(f"Invalid shot_index {shot_index}")

            shot = shots[shot_index]
            animation_prompt = shot.get("animation_prompt", "")
            duration_seconds = shot.get("duration_seconds", 5)

            image_paths = job.broll_image_paths or []
            image_path = image_paths[shot_index] if shot_index < len(image_paths) else ""
            if not image_path:
                raise ValueError(f"No source image for B-Roll shot {shot_index}")

            veo = _get_veo_or_mock(use_mock=job.use_mock)
            clip_path = veo.generate_clip_from_image(
                prompt=animation_prompt,
                image_path=image_path,
                duration_seconds=duration_seconds,
                width=720,
                height=1280,
            )

            # Save old video to history before overwriting
            from sqlalchemy.orm.attributes import flag_modified
            broll_paths = list(job.broll_paths or [])
            history = list(job.broll_video_history or [])
            while len(history) <= shot_index:
                history.append([])
            if shot_index < len(broll_paths) and broll_paths[shot_index]:
                history[shot_index].insert(0, broll_paths[shot_index])
            job.broll_video_history = history
            flag_modified(job, "broll_video_history")

            while len(broll_paths) <= shot_index:
                broll_paths.append("")
            broll_paths[shot_index] = clip_path
            job.broll_paths = broll_paths
            job.error_message = None
            await session.commit()
            logger.info(f"Job {job_id}: B-Roll shot {shot_index} video regenerated -> {clip_path}")

    try:
        asyncio.run(_run())
    except Exception as exc:
        logger.error(f"ugc_regen_broll_shot_video job {job_id} shot {shot_index} failed: {exc}")
        raise


@celery_app.task(
    bind=True,
    name='app.ugc_tasks.ugc_regen_all_aroll_videos',
    max_retries=1,
    time_limit=900,  # 15 min — all clips sequentially
)
def ugc_regen_all_aroll_videos(self, job_id: int):
    """Regenerate all A-Roll video clips from their scene images."""
    logger.info(f"ugc_regen_all_aroll_videos: starting job {job_id}")

    async def _run():
        from app.database import get_task_session_factory
        from app.models import UGCJob
        from app.services.ugc_pipeline.asset_generator import generate_aroll_assets
        from sqlalchemy import select

        session_factory = get_task_session_factory()
        async with session_factory() as session:
            result = await session.execute(select(UGCJob).where(UGCJob.id == job_id))
            job = result.scalars().first()
            if not job:
                raise ValueError(f"UGCJob {job_id} not found")

            persona = (job.master_script or {}).get("creator_persona", "")
            aroll_paths = generate_aroll_assets(
                aroll_scenes=job.aroll_scenes or [],
                aroll_image_paths=job.aroll_image_paths or [],
                use_mock=job.use_mock,
                creator_persona=persona,
            )
            logger.info(f"Job {job_id}: {len(aroll_paths)} A-Roll videos regenerated (all scenes)")

            job.aroll_paths = aroll_paths
            job.error_message = None
            await session.commit()

    try:
        asyncio.run(_run())
    except Exception as exc:
        logger.error(f"ugc_regen_all_aroll_videos job {job_id} failed: {exc}")
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
            # Recalculate overlay_start dynamically so uploaded clips
            # with different durations don't overlap each other
            from moviepy import VideoFileClip as _VFC
            broll_shots = job.broll_shots or []
            broll_paths = job.broll_paths or []
            broll_metadata = []
            cursor = None  # tracks end of previous B-Roll
            for i, shot in enumerate(broll_shots):
                if i >= len(broll_paths) or not broll_paths[i]:
                    continue
                path = broll_paths[i]
                # Normalize VFR / non-mp4 files (iPhone .MOV fix)
                from app.services.ugc_pipeline.ugc_compositor import normalize_video
                path = normalize_video(path)
                # Update stored path so future recompositions skip re-encoding
                if path != broll_paths[i]:
                    broll_paths[i] = path
                    job.broll_paths = broll_paths
                    from sqlalchemy.orm.attributes import flag_modified
                    flag_modified(job, "broll_paths")
                scripted_start = shot.get("overlay_start", 0.0)
                # If previous clip would overlap, push this one forward
                if cursor is not None and scripted_start < cursor:
                    overlay_start = cursor
                else:
                    overlay_start = scripted_start
                # Probe actual duration to set cursor for next clip
                try:
                    probe = _VFC(path)
                    actual_dur = probe.duration
                    probe.close()
                except Exception:
                    actual_dur = shot.get("duration_seconds", 5)
                cursor = overlay_start + actual_dur
                broll_metadata.append({
                    "path": path,
                    "overlay_start": overlay_start,
                })

            # Build output path
            settings = get_settings()
            comp_dir = os.path.join(settings.output_dir, "review")
            os.makedirs(comp_dir, exist_ok=True)
            output_path = os.path.join(
                comp_dir,
                f"ugc_ad_{job_id}_{uuid4().hex[:8]}.mp4"
            )

            # Run composition
            final_path = compose_ugc_ad(
                aroll_paths=job.aroll_paths or [],
                broll_metadata=broll_metadata,
                output_path=output_path,
                pip_mode=bool(job.broll_include_creator),
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


# --- LP Section-Specific Image Generation ---

# Sections whose items get unique AI images.
# key = section name, value = field name in lp_copy dict
IMAGEABLE_SECTIONS = {
    "benefits": "benefits",
    "how_it_works": "how_it_works",
}


@celery_app.task(
    bind=True,
    name='app.ugc_tasks.lp_generate_section_images',
    max_retries=1,
    time_limit=600,
)
def lp_generate_section_images(self, lp_id: int):
    """Generate unique AI images for each LP section item (benefits, how_it_works)."""
    logger.info(f"lp_generate_section_images: starting for LP {lp_id}")

    async def _run():
        from app.database import get_task_session_factory
        from app.models import LandingPage, UGCJob
        from app.services.image_provider import get_image_provider
        from sqlalchemy import select
        from sqlalchemy.orm.attributes import flag_modified

        session_factory = get_task_session_factory()
        async with session_factory() as session:
            result = await session.execute(
                select(LandingPage).where(LandingPage.id == lp_id)
            )
            lp = result.scalar_one_or_none()
            if not lp:
                raise ValueError(f"LandingPage {lp_id} not found")

            lp_copy = lp.lp_copy or {}
            if not lp_copy:
                raise ValueError(f"LP {lp_id} has no copy data")

            # Get product reference image from linked UGC job
            product_ref = None
            if lp.ugc_job_id:
                ugc_result = await session.execute(
                    select(UGCJob).where(UGCJob.id == lp.ugc_job_id)
                )
                ugc_job = ugc_result.scalar_one_or_none()
                if ugc_job and ugc_job.product_image_paths:
                    import os
                    for p in ugc_job.product_image_paths:
                        if os.path.exists(p):
                            product_ref = p
                            break

            provider = get_image_provider()
            section_images = {}

            for section_name, copy_field in IMAGEABLE_SECTIONS.items():
                items = lp_copy.get(copy_field) or []
                paths = []
                for item in items:
                    title = item.get("title", "")
                    desc = item.get("description", "")
                    if not title:
                        continue
                    prompt = (
                        f"Product lifestyle photo: {title} — {desc}. "
                        "Clean commercial photography, bright natural lighting, 16:9 landscape."
                    )
                    try:
                        ref_images = [product_ref] if product_ref else None
                        generated = provider.generate_image(
                            prompt=prompt,
                            width=1024,
                            height=576,
                            reference_images=ref_images,
                        )
                        paths.append(generated[0])
                        logger.info(f"LP {lp_id} [{section_name}] item '{title}': {generated[0]}")
                    except Exception as e:
                        logger.warning(f"LP {lp_id} [{section_name}] item '{title}' failed: {e}")
                        # Skip failed items — section still gets partial images
                        continue

                if paths:
                    section_images[section_name] = paths

            lp.lp_section_images = section_images
            flag_modified(lp, "lp_section_images")
            await session.commit()
            counts = {k: len(v) for k, v in section_images.items()}
            logger.info(f"LP {lp_id}: section images generated — {counts}")

    try:
        asyncio.run(_run())
    except Exception as exc:
        logger.error(f"lp_generate_section_images LP {lp_id} failed: {exc}")
        raise


@celery_app.task(
    bind=True,
    name='app.ugc_tasks.lp_regen_section_image',
    max_retries=1,
    time_limit=120,
)
def lp_regen_section_image(self, lp_id: int, section: str, index: int):
    """Regenerate a single section image (e.g. benefits[2])."""
    logger.info(f"lp_regen_section_image: LP {lp_id} section={section} index={index}")

    async def _run():
        from app.database import get_task_session_factory
        from app.models import LandingPage, UGCJob
        from app.services.image_provider import get_image_provider
        from sqlalchemy import select
        from sqlalchemy.orm.attributes import flag_modified

        session_factory = get_task_session_factory()
        async with session_factory() as session:
            result = await session.execute(
                select(LandingPage).where(LandingPage.id == lp_id)
            )
            lp = result.scalar_one_or_none()
            if not lp:
                raise ValueError(f"LandingPage {lp_id} not found")

            if section not in IMAGEABLE_SECTIONS:
                raise ValueError(f"Invalid section: {section}")

            lp_copy = lp.lp_copy or {}
            copy_field = IMAGEABLE_SECTIONS[section]
            items = lp_copy.get(copy_field) or []
            if index < 0 or index >= len(items):
                raise ValueError(f"Index {index} out of range for {section} ({len(items)} items)")

            item = items[index]
            title = item.get("title", "")
            desc = item.get("description", "")
            prompt = (
                f"Product lifestyle photo: {title} — {desc}. "
                "Clean commercial photography, bright natural lighting, 16:9 landscape."
            )

            # Product reference image from linked UGC job
            product_ref = None
            if lp.ugc_job_id:
                import os
                ugc_result = await session.execute(
                    select(UGCJob).where(UGCJob.id == lp.ugc_job_id)
                )
                ugc_job = ugc_result.scalar_one_or_none()
                if ugc_job and ugc_job.product_image_paths:
                    for p in ugc_job.product_image_paths:
                        if os.path.exists(p):
                            product_ref = p
                            break

            provider = get_image_provider()
            ref_images = [product_ref] if product_ref else None
            generated = provider.generate_image(
                prompt=prompt, width=1024, height=576,
                reference_images=ref_images,
            )
            new_path = generated[0]

            # Update the specific index in section_images
            section_images = lp.lp_section_images or {}
            if section not in section_images:
                section_images[section] = []
            # Extend list if needed (shouldn't happen, but be safe)
            while len(section_images[section]) <= index:
                section_images[section].append(None)
            section_images[section][index] = new_path
            lp.lp_section_images = section_images
            flag_modified(lp, "lp_section_images")
            await session.commit()
            logger.info(f"LP {lp_id} [{section}][{index}] regenerated: {new_path}")

    try:
        asyncio.run(_run())
    except Exception as exc:
        logger.error(f"lp_regen_section_image LP {lp_id} {section}[{index}] failed: {exc}")
        raise
