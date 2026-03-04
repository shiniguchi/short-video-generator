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
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from statemachine.exceptions import TransitionNotAllowed

from app.database import async_session_factory, get_session
from app.models import UGCJob
from app.state_machines.ugc_job import UGCJobStateMachine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ugc", tags=["ugc"])

# Maps review status -> (approve_event, next_task_function_name)
_STAGE_ADVANCE_MAP = {
    "stage_analysis_review":      ("approve_analysis",    "ugc_stage_2_script"),
    "stage_script_review":        ("approve_script",      "ugc_stage_3a_aroll_images"),
    "stage_aroll_image_review":   ("approve_aroll_images", "ugc_stage_3_aroll"),
    "stage_aroll_review":         ("approve_aroll",       "ugc_stage_4a_broll_images"),
    "stage_broll_image_review":   ("approve_broll_images", "ugc_stage_4_broll"),
    "stage_broll_review":         ("approve_broll",       "ugc_stage_5_compose"),
    "stage_composition_review":   ("approve_final",       None),
}

# Maps review status -> celery task to re-run for that stage
_STAGE_REGEN_MAP = {
    "stage_analysis_review":      "ugc_stage_1_analyze",
    "stage_script_review":        "ugc_stage_2_script",
    "stage_aroll_image_review":   "ugc_stage_3a_aroll_images",
    "stage_aroll_review":         "ugc_stage_3_aroll",
    "stage_broll_image_review":   "ugc_stage_4a_broll_images",
    "stage_broll_review":         "ugc_stage_4_broll",
}

# Skip video generation config: image review stage -> how to fast-forward
_STAGE_SKIP_VIDEO_CONFIG = {
    "stage_aroll_image_review": {
        "video_col": "aroll_paths",
        "count_source": "aroll_scenes",
        "complete_event": "complete_aroll",
    },
    "stage_broll_image_review": {
        "video_col": "broll_paths",
        "count_source": "broll_shots",
        "complete_event": "complete_broll",
    },
}

# All valid review states (used to gate the edit endpoint)
_REVIEW_STATES = set(_STAGE_ADVANCE_MAP.keys())


class UGCJobEdit(BaseModel):
    """Editable stage output fields on a UGCJob."""

    master_script: Optional[dict] = None
    aroll_scenes: Optional[list] = None
    broll_shots: Optional[list] = None
    analysis_category: Optional[str] = None
    analysis_ugc_style: Optional[str] = None
    analysis_emotional_tone: Optional[str] = None
    analysis_key_features: Optional[list] = None
    analysis_visual_keywords: Optional[list] = None
    analysis_target_audience: Optional[str] = None


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


# --- POST /ugc/jobs/{job_id}/regenerate ---

@router.post("/jobs/{job_id}/regenerate")
async def regenerate_ugc_stage(
    job_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Re-run the current stage's Celery task from a review state."""
    result = await session.execute(select(UGCJob).where(UGCJob.id == job_id))
    job = result.scalars().first()
    if not job:
        raise HTTPException(status_code=404, detail=f"UGCJob {job_id} not found")

    # Gate: must be a regeneratable review state
    if job.status not in _STAGE_REGEN_MAP:
        if job.status == "stage_composition_review":
            detail = "Composition stage cannot be regenerated — approve or reject only"
        else:
            detail = f"Cannot regenerate from status '{job.status}' — job must be in a review state"
        raise HTTPException(status_code=400, detail=detail)

    task_name = _STAGE_REGEN_MAP[job.status]

    # Use the advance map approve event to transition review -> running
    approve_event, _ = _STAGE_ADVANCE_MAP[job.status]
    try:
        sm = UGCJobStateMachine(model=job, state_field="status", start_value=job.status)
        sm.send(approve_event)
        job.status = sm.current_state.id
    except TransitionNotAllowed as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    await session.commit()
    logger.info(f"UGCJob {job_id} regenerating via '{task_name}', status={job.status}")

    # Lazy import to avoid circular import at module load time
    import app.ugc_tasks as ugc_tasks_module
    task_fn = getattr(ugc_tasks_module, task_name)
    task_fn.delay(job_id)

    return {"job_id": job_id, "status": job.status, "regenerating": task_name}


# Maps populated columns -> Celery task to resume from (bottom-up check)
_RETRY_RESUME_MAP = [
    ("broll_paths",       "ugc_stage_5_compose"),
    ("broll_image_paths", "ugc_stage_4_broll"),
    ("aroll_paths",       "ugc_stage_4a_broll_images"),
    ("aroll_image_paths", "ugc_stage_3_aroll"),
    ("master_script",     "ugc_stage_3a_aroll_images"),
    ("analysis_category", "ugc_stage_2_script"),
]


def _determine_resume_task(job) -> str:
    """Pick the Celery task to resume from based on which columns are populated."""
    for column, task_name in _RETRY_RESUME_MAP:
        if getattr(job, column, None) is not None:
            return task_name
    return "ugc_stage_1_analyze"


# --- POST /ugc/jobs/{job_id}/retry ---

@router.post("/jobs/{job_id}/retry")
async def retry_ugc_job(
    job_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Retry a failed job — resumes from the last successful checkpoint."""
    result = await session.execute(select(UGCJob).where(UGCJob.id == job_id))
    job = result.scalars().first()
    if not job:
        raise HTTPException(status_code=404, detail=f"UGCJob {job_id} not found")

    if job.status != "failed":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot retry from status '{job.status}' — job must be failed",
        )

    task_name = _determine_resume_task(job)

    # Transition failed -> running
    try:
        sm = UGCJobStateMachine(model=job, state_field="status", start_value=job.status)
        sm.send("retry")
        job.status = sm.current_state.id
    except TransitionNotAllowed as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    job.error_message = None
    await session.commit()
    logger.info(f"UGCJob {job_id} retrying via '{task_name}', status={job.status}")

    import app.ugc_tasks as ugc_tasks_module
    getattr(ugc_tasks_module, task_name).delay(job_id)

    return {"job_id": job_id, "status": job.status, "resuming": task_name}


# --- POST /ugc/jobs/{job_id}/reopen ---

@router.post("/jobs/{job_id}/reopen")
async def reopen_ugc_job(
    job_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Reopen an approved job back to composition review for re-editing."""
    result = await session.execute(select(UGCJob).where(UGCJob.id == job_id))
    job = result.scalars().first()
    if not job:
        raise HTTPException(status_code=404, detail=f"UGCJob {job_id} not found")

    if job.status != "approved":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot reopen from status '{job.status}' — job must be approved",
        )

    try:
        sm = UGCJobStateMachine(model=job, state_field="status", start_value=job.status)
        sm.send("reopen")
        job.status = sm.current_state.id
    except TransitionNotAllowed as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    job.approved_at = None
    await session.commit()
    logger.info(f"UGCJob {job_id} reopened, status={job.status}")

    return {"job_id": job_id, "status": job.status}


# --- PATCH /ugc/jobs/{job_id}/edit ---

@router.patch("/jobs/{job_id}/edit")
async def edit_ugc_job(
    job_id: int,
    body: UGCJobEdit,
    session: AsyncSession = Depends(get_session),
):
    """Update stage output columns while in a review state."""
    result = await session.execute(select(UGCJob).where(UGCJob.id == job_id))
    job = result.scalars().first()
    if not job:
        raise HTTPException(status_code=404, detail=f"UGCJob {job_id} not found")

    if job.status not in _REVIEW_STATES:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot edit from status '{job.status}' — job must be in a review state",
        )

    # Apply only non-None fields
    updates = body.model_dump(exclude_none=True)
    for field_name, value in updates.items():
        setattr(job, field_name, value)

    await session.commit()
    logger.info(f"UGCJob {job_id} edited fields={list(updates.keys())}")

    return {"job_id": job_id, "status": job.status, "updated_fields": list(updates.keys())}


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
        # Stage 3a/4a outputs (per-scene images)
        "aroll_image_paths": job.aroll_image_paths,
        "broll_image_paths": job.broll_image_paths,
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
    "stage_aroll_image_review",
    "stage_aroll_review",
    "stage_broll_image_review",
    "stage_broll_review",
    "stage_composition_review",
    "approved",
    "failed",
}


def _derive_stage_progress(job) -> dict:
    """Derive current stage, sub-step detail, and progress % from job data.

    7 stages each ~14% of total. Starts at 0% and ends at 98%.
    """
    num_scenes = len(job.aroll_scenes or [])
    num_shots = len(job.broll_shots or [])

    if job.final_video_path:
        return {"stage": "Composition", "percent": 98, "detail": "Done"}
    if job.broll_paths:
        return {"stage": "Composing final video", "percent": 88, "detail": "Rendering final cut..."}
    if job.broll_image_paths:
        return {"stage": "Generating B-Roll videos", "percent": 74,
                "detail": f"0/{num_shots} clips" if num_shots else "Starting..."}
    if job.aroll_paths:
        return {"stage": "Generating B-Roll images", "percent": 60,
                "detail": f"0/{num_shots} shots" if num_shots else "Starting..."}
    if job.aroll_image_paths:
        return {"stage": "Generating A-Roll videos", "percent": 44,
                "detail": f"0/{num_scenes} clips" if num_scenes else "Starting..."}
    if job.master_script:
        return {"stage": "Generating A-Roll image", "percent": 30, "detail": "Creating creator image..."}
    if job.analysis_category:
        return {"stage": "Writing video script", "percent": 16, "detail": "Drafting hook, proof, CTA..."}
    return {"stage": "Analyzing product", "percent": 0, "detail": "Reading product info..."}


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

            payload = {"status": job.status, "error": job.error_message}
            if job.status == "running":
                payload.update(_derive_stage_progress(job))
            yield f"data: {json.dumps(payload)}\n\n"

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
