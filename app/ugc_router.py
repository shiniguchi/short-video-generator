"""FastAPI router for UGC job submission, advancement, and status.

Endpoints:
  GET  /ugc/jobs             — List all UGC jobs (newest first)
  POST /ugc/jobs             — Submit new UGC job (creates job, enqueues stage 1)
  POST /ugc/jobs/{id}/advance — Advance past review gate (enqueues next stage)
  GET  /ugc/jobs/{id}        — Get job status and stage outputs
  GET  /ugc/jobs/{id}/events — SSE stream of job status updates
"""
import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import async_session_factory, get_session
from app.models import UGCJob
from app.state_machines.ugc_job import UGCJobStateMachine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ugc", tags=["ugc"])

# Maps review status -> (approve_event, next_task_function_name)
_STAGE_ADVANCE_MAP = {
    "stage_analysis_review":    ("approve_analysis", "ugc_stage_2_script"),
    "stage_script_review":      ("approve_script",   "ugc_stage_3_aroll"),
    "stage_aroll_review":       ("approve_aroll",    "ugc_stage_4_broll"),
    "stage_broll_review":       ("approve_broll",    "ugc_stage_5_compose"),
    "stage_composition_review": ("approve_final",    None),
}


# --- GET /ugc/jobs ---

@router.get("/jobs")
async def list_ugc_jobs(session: AsyncSession = Depends(get_session)):
    """Return all UGCJobs ordered newest first."""
    result = await session.execute(select(UGCJob).order_by(UGCJob.created_at.desc()))
    jobs = result.scalars().all()
    return [
        {
            "id": job.id,
            "product_name": job.product_name,
            "status": job.status,
            "use_mock": job.use_mock,
            "created_at": job.created_at,
            "error_message": job.error_message,
        }
        for job in jobs
    ]


# --- POST /ugc/jobs ---

@router.post("/jobs")
async def submit_ugc_job(
    product_name: str = Form(...),
    description: str = Form(...),
    use_mock: bool = Form(True),
    product_url: Optional[str] = Form(None),
    target_duration: int = Form(30),
    style_preference: Optional[str] = Form(None),
    images: List[UploadFile] = File(default=[]),
    session: AsyncSession = Depends(get_session),
):
    """Create a UGCJob, upload product images, and enqueue stage 1 analysis task."""
    # Create job row
    job = UGCJob(
        product_name=product_name,
        description=description,
        use_mock=use_mock,
        product_url=product_url,
        target_duration=target_duration,
        style_preference=style_preference,
        status="pending",
    )
    session.add(job)
    await session.flush()  # Get job.id before saving images

    # Save uploaded images
    image_paths: List[str] = []
    if images:
        upload_dir = Path("output") / "ugc_uploads" / str(job.id)
        upload_dir.mkdir(parents=True, exist_ok=True)
        for img in images:
            dest = upload_dir / (img.filename or f"image_{len(image_paths)}")
            content = await img.read()
            dest.write_bytes(content)
            image_paths.append(str(dest))
    job.product_image_paths = image_paths or None

    # Transition pending -> running
    sm = UGCJobStateMachine(model=job, state_field="status", start_value=job.status)
    sm.send("start")
    job.status = sm.current_state.id

    await session.commit()
    logger.info(f"UGCJob {job.id} created, status={job.status}")

    # Enqueue stage 1 task
    import app.ugc_tasks  # noqa: F401 — ensures tasks are registered
    app.ugc_tasks.ugc_stage_1_analyze.delay(job.id)

    return {"job_id": job.id, "status": job.status}


# --- POST /ugc/jobs/{job_id}/advance ---

@router.post("/jobs/{job_id}/advance")
async def advance_ugc_job(
    job_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Approve current review state, optionally enqueue next stage task."""
    # Load job
    result = await session.execute(select(UGCJob).where(UGCJob.id == job_id))
    job = result.scalars().first()
    if not job:
        raise HTTPException(status_code=404, detail=f"UGCJob {job_id} not found")

    # Check current status is a review state
    if job.status not in _STAGE_ADVANCE_MAP:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot advance from status '{job.status}' — not a review state",
        )

    approve_event, next_task_name = _STAGE_ADVANCE_MAP[job.status]

    # Transition via state machine
    from statemachine.exceptions import TransitionNotAllowed
    try:
        sm = UGCJobStateMachine(model=job, state_field="status", start_value=job.status)
        sm.send(approve_event)
        job.status = sm.current_state.id
    except TransitionNotAllowed as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # Set approved_at timestamp on final approval
    if approve_event == "approve_final":
        job.approved_at = datetime.now(timezone.utc)

    await session.commit()
    logger.info(f"UGCJob {job_id} advanced via '{approve_event}', status={job.status}")

    # Enqueue next stage task if applicable
    if next_task_name:
        import app.ugc_tasks as ugc_tasks_module  # noqa: F401
        task_fn = getattr(ugc_tasks_module, next_task_name)
        task_fn.delay(job_id)

    return {"job_id": job.id, "status": job.status, "next_stage": next_task_name}


# --- GET /ugc/jobs/{job_id} ---

@router.get("/jobs/{job_id}")
async def get_ugc_job(
    job_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Return job status and all stage output columns."""
    result = await session.execute(select(UGCJob).where(UGCJob.id == job_id))
    job = result.scalars().first()
    if not job:
        raise HTTPException(status_code=404, detail=f"UGCJob {job_id} not found")

    return jsonable_encoder({
        "id": job.id,
        "product_name": job.product_name,
        "status": job.status,
        "use_mock": job.use_mock,
        "created_at": job.created_at,
        "error_message": job.error_message,
        # Stage 1 outputs
        "analysis_category": job.analysis_category,
        "analysis_ugc_style": job.analysis_ugc_style,
        "analysis_emotional_tone": job.analysis_emotional_tone,
        "analysis_key_features": job.analysis_key_features,
        "analysis_visual_keywords": job.analysis_visual_keywords,
        "analysis_target_audience": job.analysis_target_audience,
        "hero_image_path": job.hero_image_path,
        # Stage 2 outputs
        "master_script": job.master_script,
        "aroll_scenes": job.aroll_scenes,
        "broll_shots": job.broll_shots,
        # Stage 3 outputs
        "aroll_paths": job.aroll_paths,
        # Stage 4 outputs
        "broll_paths": job.broll_paths,
        # Stage 5 outputs
        "final_video_path": job.final_video_path,
        "cost_usd": job.cost_usd,
        "approved_at": job.approved_at,
    })


# --- GET /ugc/jobs/{job_id}/events ---

# Status values where the job will not change further
_TERMINAL_STATES = {
    "stage_analysis_review",
    "stage_script_review",
    "stage_aroll_review",
    "stage_broll_review",
    "stage_composition_review",
    "approved",
    "failed",
}


@router.get("/jobs/{job_id}/events")
async def ugc_job_events(job_id: int, request: Request):
    """SSE stream of job status updates at 1-second intervals.

    Uses a fresh DB session per iteration so the connection is never
    held open across the full stream duration.
    Closes automatically on terminal state or client disconnect.
    """
    async def event_stream():
        # Poll for up to 10 minutes (600 × 1s)
        for _ in range(600):
            # Check client disconnect before querying DB
            if await request.is_disconnected():
                break

            async with async_session_factory() as s:
                result = await s.execute(select(UGCJob).where(UGCJob.id == job_id))
                job = result.scalars().first()

            if job is None:
                yield f"data: {json.dumps({'status': 'not_found'})}\n\n"
                break

            yield f"data: {json.dumps({'status': job.status, 'error': job.error_message})}\n\n"

            if job.status in _TERMINAL_STATES:
                break

            await asyncio.sleep(1)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
