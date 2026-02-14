"""Pipeline orchestration module for ViralForge.

Sequences all pipeline stages with database-backed checkpointing,
resume-from-checkpoint capability, and per-stage retry logic.
"""

import asyncio
import logging
from typing import Optional, List, Dict, Any
from celery import Celery
from datetime import datetime, timezone

from app.worker import celery_app
from app.database import get_task_session_factory
from app.models import Job
from sqlalchemy import select

logger = logging.getLogger(__name__)

# Stage constants - single source of truth for stage names
STAGE_TREND_COLLECTION = "trend_collection"
STAGE_TREND_ANALYSIS = "trend_analysis"
STAGE_CONTENT_GENERATION = "content_generation"
STAGE_COMPOSITION = "composition"
STAGE_REVIEW = "review"

PIPELINE_STAGES = [
    STAGE_TREND_COLLECTION,
    STAGE_TREND_ANALYSIS,
    STAGE_CONTENT_GENERATION,
    STAGE_COMPOSITION,
    STAGE_REVIEW,
]


# Async Job helper functions (called via asyncio.run() from sync Celery context)

async def _load_job(job_id: int) -> Dict[str, Any]:
    """Load job from database.

    Returns:
        dict with id, status, stage, theme, extra_data, error_message
    """
    async with get_task_session_factory()() as session:
        query = select(Job).where(Job.id == job_id)
        result = await session.execute(query)
        job = result.scalars().first()

        if not job:
            raise ValueError(f"Job {job_id} not found")

        return {
            "id": job.id,
            "status": job.status,
            "stage": job.stage,
            "theme": job.theme,
            "extra_data": job.extra_data or {},
            "error_message": job.error_message
        }


async def _update_job_status(job_id: int, stage: str, status: str, error_msg: Optional[str] = None) -> None:
    """Update Job status and stage.

    Args:
        job_id: Database ID of Job
        stage: Current pipeline stage
        status: Job status (pending, running, completed, failed)
        error_msg: Optional error message
    """
    async with get_task_session_factory()() as session:
        query = select(Job).where(Job.id == job_id)
        result = await session.execute(query)
        job = result.scalars().first()

        if not job:
            raise ValueError(f"Job {job_id} not found")

        job.status = status
        job.stage = stage
        job.updated_at = datetime.now(timezone.utc)

        if error_msg:
            job.error_message = error_msg

        await session.commit()


async def _mark_stage_complete(job_id: int, stage: str) -> None:
    """Mark a pipeline stage as complete.

    Appends stage to extra_data["completed_stages"] list and updates status to "running".

    Args:
        job_id: Database ID of Job
        stage: Stage name to mark complete
    """
    async with get_task_session_factory()() as session:
        query = select(Job).where(Job.id == job_id)
        result = await session.execute(query)
        job = result.scalars().first()

        if not job:
            raise ValueError(f"Job {job_id} not found")

        # Get existing extra_data or initialize
        extra_data = job.extra_data or {}
        completed_stages = extra_data.get("completed_stages", [])

        # Add stage if not already present
        if stage not in completed_stages:
            completed_stages.append(stage)

        # Reassign dict to trigger SQLAlchemy dirty detection
        job.extra_data = {**extra_data, "completed_stages": completed_stages}
        job.status = "running"
        job.updated_at = datetime.now(timezone.utc)

        await session.commit()


async def _mark_job_complete(job_id: int) -> None:
    """Mark job as completed.

    Sets status="completed", stage to last stage.

    Args:
        job_id: Database ID of Job
    """
    async with get_task_session_factory()() as session:
        query = select(Job).where(Job.id == job_id)
        result = await session.execute(query)
        job = result.scalars().first()

        if not job:
            raise ValueError(f"Job {job_id} not found")

        job.status = "completed"
        job.stage = PIPELINE_STAGES[-1]  # Last stage
        job.updated_at = datetime.now(timezone.utc)

        await session.commit()


async def _mark_job_failed(job_id: int, stage: str, error_msg: str) -> None:
    """Mark job as failed.

    Sets status="failed", stores error_message.

    Args:
        job_id: Database ID of Job
        stage: Stage where failure occurred
        error_msg: Error message
    """
    async with get_task_session_factory()() as session:
        query = select(Job).where(Job.id == job_id)
        result = await session.execute(query)
        job = result.scalars().first()

        if not job:
            raise ValueError(f"Job {job_id} not found")

        job.status = "failed"
        job.stage = stage
        job.error_message = error_msg
        job.updated_at = datetime.now(timezone.utc)

        await session.commit()


@celery_app.task(bind=True, name='app.tasks.orchestrate_pipeline_task', max_retries=0)
def orchestrate_pipeline_task(self, job_id: int, theme_config_path: Optional[str] = None, resume: bool = False):
    """Orchestrate the full video generation pipeline.

    Executes all 5 pipeline stages in sequence:
    1. Trend Collection
    2. Trend Analysis
    3. Content Generation (script + video + voiceover)
    4. Composition (chained from Content Generation)
    5. Review

    Features:
    - Database-backed checkpointing (completed_stages in Job.extra_data)
    - Resume-from-checkpoint capability
    - Per-stage retry logic (individual tasks have autoretry_for configured)
    - Logging for Docker container visibility

    Args:
        job_id: Database ID of Job to orchestrate
        theme_config_path: Optional path to theme config YAML
        resume: Whether to resume from last completed stage

    Returns:
        dict with status, job_id, completed_stages
    """
    # Import stage tasks inside function to avoid circular imports
    from app.tasks import collect_trends_task, analyze_trends_task, generate_content_task

    logger.info(f"Starting pipeline orchestration for job {job_id}")

    try:
        # Load job
        job = asyncio.run(_load_job(job_id))
        logger.info(f"Loaded job {job_id}: status={job['status']}, stage={job['stage']}")

        # Get completed stages
        completed_stages = job["extra_data"].get("completed_stages", []) if job["extra_data"] else []
        logger.info(f"Previously completed stages: {completed_stages}")

        # Update job status to running
        asyncio.run(_update_job_status(job_id, PIPELINE_STAGES[0], "running"))

        # Define stage-to-task mapping
        stage_tasks = [
            (STAGE_TREND_COLLECTION, collect_trends_task, []),
            (STAGE_TREND_ANALYSIS, analyze_trends_task, []),
            (STAGE_CONTENT_GENERATION, generate_content_task, [job_id, theme_config_path]),
        ]

        # Execute each stage
        for stage_name, task_func, args in stage_tasks:
            # Skip if already completed
            if stage_name in completed_stages:
                logger.info(f"Skipping stage {stage_name} (already completed)")
                continue

            # Start stage
            logger.info(f"Starting stage: {stage_name}")
            asyncio.run(_update_job_status(job_id, stage_name, "running"))

            # Execute task synchronously — disable_sync_subtasks=False allows
            # calling .get() from within a parent task (safe with threads pool)
            result = task_func.apply_async(args=args)
            task_result = result.get(disable_sync_subtasks=False, timeout=1800)

            logger.info(f"Stage {stage_name} completed: {task_result}")

            # Mark stage complete
            asyncio.run(_mark_stage_complete(job_id, stage_name))

            # Special handling for content generation: wait for composition
            if stage_name == STAGE_CONTENT_GENERATION:
                compose_task_id = task_result.get("compose_task_id")
                if compose_task_id:
                    logger.info(f"Waiting for composition task {compose_task_id}")
                    compose_result = celery_app.AsyncResult(compose_task_id)
                    compose_output = compose_result.get(disable_sync_subtasks=False, timeout=1800)
                    logger.info(f"Composition completed: {compose_output}")

                    # Mark composition stage complete
                    asyncio.run(_mark_stage_complete(job_id, STAGE_COMPOSITION))

        # Mark review stage complete (manual review happens outside this task)
        asyncio.run(_mark_stage_complete(job_id, STAGE_REVIEW))

        # Mark job complete
        asyncio.run(_mark_job_complete(job_id))

        logger.info(f"Pipeline orchestration complete for job {job_id}")
        return {
            "status": "completed",
            "job_id": job_id,
            "completed_stages": PIPELINE_STAGES
        }

    except Exception as exc:
        # Get current stage from job or default to first stage
        try:
            job = asyncio.run(_load_job(job_id))
            current_stage = job.get("stage", PIPELINE_STAGES[0])
        except Exception:
            current_stage = PIPELINE_STAGES[0]

        logger.error(f"Pipeline orchestration failed at stage {current_stage}: {exc}")
        asyncio.run(_mark_job_failed(job_id, current_stage, str(exc)))
        raise
