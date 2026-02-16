from fastapi import APIRouter, Depends, HTTPException, Form, File, UploadFile
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select
from typing import Optional, List
from datetime import datetime, timezone
from pathlib import Path
import shutil
from app.database import get_session
from app.config import get_settings

router = APIRouter()
_security = HTTPBearer()


async def require_api_key(
    credentials: HTTPAuthorizationCredentials = Depends(_security),
) -> str:
    """Validate Bearer token against API_SECRET_KEY. Returns the key on success."""
    settings = get_settings()
    if credentials.credentials != settings.api_secret_key:
        raise HTTPException(status_code=403, detail="Invalid API key")
    return credentials.credentials


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
async def trigger_test_task(_: str = Depends(require_api_key)):
    """Trigger a test Celery task"""
    from app.tasks import test_task
    task = test_task.delay()
    return {"task_id": str(task.id), "status": "queued"}


@router.post("/collect-trends")
async def trigger_trend_collection(_: str = Depends(require_api_key)):
    """Trigger trend collection from TikTok and YouTube."""
    from app.tasks import collect_trends_task
    task = collect_trends_task.delay()
    return {"task_id": str(task.id), "status": "queued", "description": "Collecting trends from TikTok and YouTube"}


@router.get("/trends")
async def list_trends(
    platform: Optional[str] = None,
    limit: int = 50,
    session: AsyncSession = Depends(get_session),
    _: str = Depends(require_api_key),
):
    """List collected trends, optionally filtered by platform."""
    from app.models import Trend

    query = select(Trend).order_by(Trend.collected_at.desc()).limit(limit)
    if platform:
        query = query.where(Trend.platform == platform)

    result = await session.execute(query)
    trends = result.scalars().all()

    return {
        "count": len(trends),
        "trends": [
            {
                "id": t.id,
                "platform": t.platform,
                "external_id": t.external_id,
                "title": t.title,
                "creator": t.creator,
                "likes": t.likes,
                "comments": t.comments,
                "shares": t.shares,
                "views": t.views,
                "duration": t.duration,
                "engagement_velocity": t.engagement_velocity,
                "collected_at": t.collected_at.isoformat() if t.collected_at else None,
            }
            for t in trends
        ]
    }


@router.post("/analyze-trends")
async def trigger_trend_analysis(_: str = Depends(require_api_key)):
    """Trigger trend analysis with Claude API."""
    from app.tasks import analyze_trends_task
    task = analyze_trends_task.delay()
    return {"task_id": str(task.id), "status": "queued", "description": "Analyzing collected trends"}


@router.get("/trend-reports")
async def list_trend_reports(
    limit: int = 10,
    session: AsyncSession = Depends(get_session),
    _: str = Depends(require_api_key),
):
    """List trend analysis reports."""
    from app.models import TrendReport

    query = select(TrendReport).order_by(TrendReport.created_at.desc()).limit(limit)
    result = await session.execute(query)
    reports = result.scalars().all()

    return {
        "count": len(reports),
        "reports": [
            {
                "id": r.id,
                "analyzed_count": r.analyzed_count,
                "date_range_start": r.date_range_start.isoformat() if r.date_range_start else None,
                "date_range_end": r.date_range_end.isoformat() if r.date_range_end else None,
                "video_styles": r.video_styles,
                "common_patterns": r.common_patterns,
                "avg_engagement_velocity": r.avg_engagement_velocity,
                "top_hashtags": r.top_hashtags,
                "recommendations": r.recommendations,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in reports
        ]
    }


@router.get("/trend-reports/latest")
async def get_latest_trend_report(
    session: AsyncSession = Depends(get_session),
    _: str = Depends(require_api_key),
):
    """Get the most recent trend analysis report."""
    from app.models import TrendReport

    query = select(TrendReport).order_by(TrendReport.created_at.desc()).limit(1)
    result = await session.execute(query)
    report = result.scalars().first()

    if not report:
        raise HTTPException(status_code=404, detail="No trend reports found")

    return {
        "id": report.id,
        "analyzed_count": report.analyzed_count,
        "date_range_start": report.date_range_start.isoformat() if report.date_range_start else None,
        "date_range_end": report.date_range_end.isoformat() if report.date_range_end else None,
        "video_styles": report.video_styles,
        "common_patterns": report.common_patterns,
        "avg_engagement_velocity": report.avg_engagement_velocity,
        "top_hashtags": report.top_hashtags,
        "recommendations": report.recommendations,
        "created_at": report.created_at.isoformat() if report.created_at else None,
    }


# --- Phase 3: Content Generation ---

@router.post("/generate-content")
async def trigger_content_generation(
    job_id: Optional[int] = None,
    theme_config_path: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
    _: str = Depends(require_api_key),
):
    """Trigger full content generation pipeline (config -> script -> video -> voiceover)."""
    from app.tasks import generate_content_task
    from app.models import Job

    # Create Job if not provided
    if job_id is None:
        job = Job(
            status="pending",
            stage="content_generation",
            theme="manual",
            extra_data={"completed_stages": []}
        )
        session.add(job)
        await session.commit()
        await session.refresh(job)
        job_id = job.id

    task = generate_content_task.delay(job_id, theme_config_path)
    return {
        "task_id": str(task.id),
        "job_id": job_id,
        "status": "queued",
        "description": "Generating content: script, video, and voiceover"
    }


@router.get("/scripts")
async def list_scripts(
    limit: int = 10,
    session: AsyncSession = Depends(get_session),
    _: str = Depends(require_api_key),
):
    """List generated video production plans (scripts)."""
    from app.models import Script

    query = select(Script).order_by(Script.created_at.desc()).limit(limit)
    result = await session.execute(query)
    scripts = result.scalars().all()

    return {
        "count": len(scripts),
        "scripts": [
            {
                "id": s.id,
                "title": s.title,
                "duration_target": s.duration_target,
                "aspect_ratio": s.aspect_ratio,
                "scenes_count": len(s.scenes) if s.scenes else 0,
                "created_at": s.created_at.isoformat() if s.created_at else None,
            }
            for s in scripts
        ]
    }


@router.get("/scripts/{script_id}")
async def get_script(
    script_id: int,
    session: AsyncSession = Depends(get_session),
    _: str = Depends(require_api_key),
):
    """Get full details of a generated script."""
    from app.models import Script

    query = select(Script).where(Script.id == script_id)
    result = await session.execute(query)
    script = result.scalars().first()

    if not script:
        raise HTTPException(status_code=404, detail=f"Script {script_id} not found")

    return {
        "id": script.id,
        "video_prompt": script.video_prompt,
        "duration_target": script.duration_target,
        "aspect_ratio": script.aspect_ratio,
        "scenes": script.scenes,
        "voiceover_script": script.voiceover_script,
        "hook_text": script.hook_text,
        "cta_text": script.cta_text,
        "text_overlays": script.text_overlays,
        "hashtags": script.hashtags,
        "title": script.title,
        "description": script.description,
        "theme_config": script.theme_config,
        "trend_report_id": script.trend_report_id,
        "created_at": script.created_at.isoformat() if script.created_at else None,
    }


# --- Phase 4: Video Composition ---

@router.post("/compose-video")
async def trigger_video_composition(
    script_id: int,
    video_path: str,
    audio_path: str,
    job_id: Optional[int] = None,
    cost_data: Optional[dict] = None,
    session: AsyncSession = Depends(get_session),
    _: str = Depends(require_api_key),
):
    """Trigger video composition task with text overlays and audio mixing."""
    from app.tasks import compose_video_task
    from app.models import Job

    # Validate paths stay within the output directory
    output_base = Path("output").resolve()
    for p, label in [(video_path, "video_path"), (audio_path, "audio_path")]:
        if not Path(p).resolve().is_relative_to(output_base):
            raise HTTPException(400, f"{label} must be inside the output directory")

    # Create Job if not provided
    if job_id is None:
        job = Job(
            status="pending",
            stage="composition",
            theme="manual",
            extra_data={"completed_stages": ["content_generation"]}
        )
        session.add(job)
        await session.commit()
        await session.refresh(job)
        job_id = job.id

    task = compose_video_task.delay(job_id, script_id, video_path, audio_path, cost_data)
    return {
        "task_id": str(task.id),
        "job_id": job_id,
        "status": "queued",
        "description": "Composing final video..."
    }


@router.get("/videos")
async def list_videos(
    limit: int = 10,
    status: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
    _: str = Depends(require_api_key),
):
    """List composed videos with optional status filter."""
    from app.models import Video

    query = select(Video).order_by(Video.created_at.desc()).limit(limit)
    if status:
        query = query.where(Video.status == status)

    result = await session.execute(query)
    videos = result.scalars().all()

    return {
        "count": len(videos),
        "videos": [
            {
                "id": v.id,
                "script_id": v.script_id,
                "file_path": v.file_path,
                "thumbnail_path": v.thumbnail_path,
                "duration_seconds": v.duration_seconds,
                "status": v.status,
                "cost_usd": v.cost_usd,
                "created_at": v.created_at.isoformat() if v.created_at else None,
            }
            for v in videos
        ]
    }


@router.get("/videos/{video_id}")
async def get_video(
    video_id: int,
    session: AsyncSession = Depends(get_session),
    _: str = Depends(require_api_key),
):
    """Get full details of a composed video."""
    from app.models import Video

    query = select(Video).where(Video.id == video_id)
    result = await session.execute(query)
    video = result.scalars().first()

    if not video:
        raise HTTPException(status_code=404, detail=f"Video {video_id} not found")

    return {
        "id": video.id,
        "job_id": video.job_id,
        "script_id": video.script_id,
        "status": video.status,
        "file_path": video.file_path,
        "thumbnail_path": video.thumbnail_path,
        "duration_seconds": video.duration_seconds,
        "cost_usd": video.cost_usd,
        "created_at": video.created_at.isoformat() if video.created_at else None,
        "approved_at": video.approved_at.isoformat() if video.approved_at else None,
        "published_at": video.published_at.isoformat() if video.published_at else None,
        "published_url": video.published_url,
        "extra_data": video.extra_data,
    }


# --- Phase 5: Review & Output ---

@router.post("/videos/{video_id}/approve")
async def approve_video(
    video_id: int,
    session: AsyncSession = Depends(get_session),
    _: str = Depends(require_api_key),
):
    """Approve a generated video and move it to approved directory (REVIEW-03)."""
    from app.models import Video

    # Query video by ID
    query = select(Video).where(Video.id == video_id)
    result = await session.execute(query)
    video = result.scalars().first()

    if not video:
        raise HTTPException(status_code=404, detail=f"Video {video_id} not found")

    # Validate status
    if video.status != "generated":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot approve video with status '{video.status}'. Only 'generated' videos can be approved."
        )

    # Get settings
    settings = get_settings()

    # Ensure approved directory exists
    approved_dir = Path(settings.approved_output_dir)
    approved_dir.mkdir(parents=True, exist_ok=True)

    # Move video file
    file_moved = False
    thumbnail_moved = False
    warnings = []

    try:
        if video.file_path:
            source_path = Path(video.file_path)
            if source_path.exists():
                new_video_path = approved_dir / source_path.name
                shutil.move(str(source_path), str(new_video_path))
                video.file_path = str(new_video_path)
                file_moved = True
            else:
                warnings.append(f"Video file not found: {video.file_path}")
    except Exception as e:
        warnings.append(f"Error moving video file: {str(e)}")

    # Move thumbnail file if exists
    try:
        if video.thumbnail_path:
            thumb_source_path = Path(video.thumbnail_path)
            if thumb_source_path.exists():
                new_thumb_path = approved_dir / thumb_source_path.name
                shutil.move(str(thumb_source_path), str(new_thumb_path))
                video.thumbnail_path = str(new_thumb_path)
                thumbnail_moved = True
            else:
                warnings.append(f"Thumbnail file not found: {video.thumbnail_path}")
    except Exception as e:
        warnings.append(f"Error moving thumbnail file: {str(e)}")

    # Update video record
    video.status = "approved"
    video.approved_at = datetime.now(timezone.utc)

    # Update extra_data status if exists
    if video.extra_data:
        video.extra_data["status"] = "approved"

    await session.commit()
    await session.refresh(video)

    response = {
        "id": video.id,
        "status": video.status,
        "file_path": video.file_path,
        "thumbnail_path": video.thumbnail_path,
        "cost_usd": video.cost_usd,
        "approved_at": video.approved_at.isoformat() if video.approved_at else None,
        "message": "Video approved and moved to output/approved/"
    }

    if warnings:
        response["warnings"] = warnings

    return response


@router.post("/videos/{video_id}/reject")
async def reject_video(
    video_id: int,
    session: AsyncSession = Depends(get_session),
    _: str = Depends(require_api_key),
):
    """Reject a generated video and move it to rejected directory (REVIEW-04)."""
    from app.models import Video

    # Query video by ID
    query = select(Video).where(Video.id == video_id)
    result = await session.execute(query)
    video = result.scalars().first()

    if not video:
        raise HTTPException(status_code=404, detail=f"Video {video_id} not found")

    # Validate status
    if video.status != "generated":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot reject video with status '{video.status}'. Only 'generated' videos can be rejected."
        )

    # Get settings
    settings = get_settings()

    # Ensure rejected directory exists
    rejected_dir = Path(settings.rejected_output_dir)
    rejected_dir.mkdir(parents=True, exist_ok=True)

    # Move video file
    file_moved = False
    thumbnail_moved = False
    warnings = []

    try:
        if video.file_path:
            source_path = Path(video.file_path)
            if source_path.exists():
                new_video_path = rejected_dir / source_path.name
                shutil.move(str(source_path), str(new_video_path))
                video.file_path = str(new_video_path)
                file_moved = True
            else:
                warnings.append(f"Video file not found: {video.file_path}")
    except Exception as e:
        warnings.append(f"Error moving video file: {str(e)}")

    # Move thumbnail file if exists
    try:
        if video.thumbnail_path:
            thumb_source_path = Path(video.thumbnail_path)
            if thumb_source_path.exists():
                new_thumb_path = rejected_dir / thumb_source_path.name
                shutil.move(str(thumb_source_path), str(new_thumb_path))
                video.thumbnail_path = str(new_thumb_path)
                thumbnail_moved = True
            else:
                warnings.append(f"Thumbnail file not found: {video.thumbnail_path}")
    except Exception as e:
        warnings.append(f"Error moving thumbnail file: {str(e)}")

    # Update video record
    video.status = "rejected"
    # Note: Do NOT set approved_at for rejected videos

    # Update extra_data status if exists
    if video.extra_data:
        video.extra_data["status"] = "rejected"

    await session.commit()
    await session.refresh(video)

    response = {
        "id": video.id,
        "status": video.status,
        "file_path": video.file_path,
        "thumbnail_path": video.thumbnail_path,
        "cost_usd": video.cost_usd,
        "message": "Video rejected and moved to output/rejected/"
    }

    if warnings:
        response["warnings"] = warnings

    return response


# --- Phase 6: Pipeline Integration ---

@router.post("/generate")
async def trigger_pipeline(
    request: "PipelineTriggerRequest" = None,
    session: AsyncSession = Depends(get_session),
    _: str = Depends(require_api_key),
):
    """Trigger full pipeline execution (ORCH-05).

    Creates a Job record and triggers orchestrate_pipeline_task asynchronously.
    """
    # Lazy imports to avoid circular dependencies
    from app.schemas import PipelineTriggerRequest, PipelineTriggerResponse
    from app.models import Job
    from app.pipeline import orchestrate_pipeline_task

    # Use default empty request if None
    if request is None:
        request = PipelineTriggerRequest()

    # Create Job record
    job = Job(
        status="pending",
        stage="initialization",
        theme=request.theme or "default",
        extra_data={
            "completed_stages": [],
            "config_path": request.config_path
        }
    )

    session.add(job)
    await session.commit()
    await session.refresh(job)

    # Trigger pipeline task (non-blocking)
    task = orchestrate_pipeline_task.delay(
        job_id=job.id,
        theme_config_path=request.config_path
    )

    return PipelineTriggerResponse(
        job_id=job.id,
        task_id=str(task.id),
        status="queued",
        poll_url=f"/api/jobs/{job.id}",
        message="Pipeline execution started"
    )


@router.get("/jobs")
async def list_jobs(
    status: Optional[str] = None,
    limit: int = 20,
    session: AsyncSession = Depends(get_session),
    _: str = Depends(require_api_key),
):
    """List pipeline jobs with optional status filter (ORCH-04)."""
    from app.models import Job
    from app.schemas import JobListResponse, JobStatusResponse
    from app.pipeline import PIPELINE_STAGES

    # Build query
    query = select(Job).order_by(Job.created_at.desc()).limit(limit)
    if status:
        query = query.where(Job.status == status)

    result = await session.execute(query)
    jobs = result.scalars().all()

    # Compute progress for each job
    total_stages = len(PIPELINE_STAGES)
    job_responses = []

    for job in jobs:
        completed_stages = job.extra_data.get("completed_stages", []) if job.extra_data else []
        progress_pct = round(len(completed_stages) / total_stages * 100, 1) if total_stages > 0 else 0

        job_responses.append(JobStatusResponse(
            id=job.id,
            status=job.status,
            stage=job.stage,
            theme=job.theme,
            created_at=job.created_at.isoformat() if job.created_at else None,
            updated_at=job.updated_at.isoformat() if job.updated_at else None,
            error_message=job.error_message,
            completed_stages=completed_stages,
            total_stages=total_stages,
            progress_pct=progress_pct
        ))

    return JobListResponse(
        count=len(job_responses),
        jobs=job_responses
    )


@router.get("/jobs/{job_id}")
async def get_job_status(
    job_id: int,
    session: AsyncSession = Depends(get_session),
    _: str = Depends(require_api_key),
):
    """Get detailed status for a single pipeline job (ORCH-04)."""
    from app.models import Job
    from app.schemas import JobStatusResponse
    from app.pipeline import PIPELINE_STAGES

    query = select(Job).where(Job.id == job_id)
    result = await session.execute(query)
    job = result.scalars().first()

    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    # Compute progress
    completed_stages = job.extra_data.get("completed_stages", []) if job.extra_data else []
    total_stages = len(PIPELINE_STAGES)
    progress_pct = round(len(completed_stages) / total_stages * 100, 1) if total_stages > 0 else 0

    return JobStatusResponse(
        id=job.id,
        status=job.status,
        stage=job.stage,
        theme=job.theme,
        created_at=job.created_at.isoformat() if job.created_at else None,
        updated_at=job.updated_at.isoformat() if job.updated_at else None,
        error_message=job.error_message,
        completed_stages=completed_stages,
        total_stages=total_stages,
        progress_pct=progress_pct
    )


@router.post("/jobs/{job_id}/retry")
async def retry_job(
    job_id: int,
    session: AsyncSession = Depends(get_session),
    _: str = Depends(require_api_key),
):
    """Retry a failed pipeline job from last checkpoint (ORCH-05)."""
    from app.models import Job
    from app.schemas import JobRetryResponse
    from app.pipeline import orchestrate_pipeline_task, PIPELINE_STAGES

    query = select(Job).where(Job.id == job_id)
    result = await session.execute(query)
    job = result.scalars().first()

    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    # Validate status
    if job.status != "failed":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot retry job with status '{job.status}'. Only 'failed' jobs can be retried."
        )

    # Reset job status (keep completed_stages for resume)
    job.status = "pending"
    job.error_message = None
    job.updated_at = datetime.now(timezone.utc)

    await session.commit()

    # Trigger pipeline with resume=True
    config_path = job.extra_data.get("config_path") if job.extra_data else None
    task = orchestrate_pipeline_task.delay(
        job_id=job.id,
        theme_config_path=config_path,
        resume=True
    )

    # Compute resume info
    completed_stages = job.extra_data.get("completed_stages", []) if job.extra_data else []
    resume_from = None
    for stage in PIPELINE_STAGES:
        if stage not in completed_stages:
            resume_from = stage
            break

    return JobRetryResponse(
        job_id=job.id,
        task_id=str(task.id),
        status="queued",
        resume_from=resume_from,
        skipping_stages=completed_stages,
        message=f"Pipeline retry started from {resume_from}" if resume_from else "Pipeline retry started"
    )


# --- Phase 13: UGC Product Ad Pipeline ---

@router.post("/ugc-ad-generate")
async def generate_ugc_ad(
    product_name: str = Form(...),
    description: str = Form(...),
    product_url: Optional[str] = Form(None),
    target_duration: int = Form(30),
    style_preference: Optional[str] = Form(None),
    images: List[UploadFile] = File(..., description="Product photos (1-5 images)"),
    session: AsyncSession = Depends(get_session),
    _: str = Depends(require_api_key),
):
    """Generate UGC product ad video from product images + metadata.

    Accepts multipart form data with product details and up to 5 product images.
    Queues UGC pipeline task and returns job_id for status tracking.

    Args:
        product_name: Name of the product
        description: Product description
        product_url: Optional product URL
        target_duration: Target video duration in seconds (default 30)
        style_preference: Optional UGC style preference
        images: Product photos (1-5 images)

    Returns:
        UGCAdResponse with job_id, task_id, status, poll_url
    """
    import os
    from uuid import uuid4
    from app.models import Job
    from app.schemas import UGCAdResponse
    from app.tasks import generate_ugc_ad_task

    # Validate image count
    if len(images) > 5:
        raise HTTPException(400, "Maximum 5 product images allowed")

    # Validate each image is actually an image
    for image in images:
        if not image.content_type or not image.content_type.startswith("image/"):
            raise HTTPException(400, f"File {image.filename} is not an image")

    # Save uploaded images to output/uploads/
    upload_dir = "output/uploads"
    os.makedirs(upload_dir, exist_ok=True)

    max_image_size = 10 * 1024 * 1024  # 10 MB
    product_image_paths = []
    for image in images:
        content = await image.read()
        if len(content) > max_image_size:
            raise HTTPException(400, f"Image too large (max 10 MB)")
        # Use only UUID + guessed extension — never trust user-supplied filenames
        import mimetypes
        ext = mimetypes.guess_extension(image.content_type or "") or ".png"
        filename = f"{uuid4().hex}{ext}"
        image_path = os.path.join(upload_dir, filename)
        with open(image_path, "wb") as f:
            f.write(content)
        product_image_paths.append(image_path)

    # Create Job record
    job = Job(
        status="pending",
        stage="ugc_product_analysis",
        theme=f"ugc:{product_name}",
        extra_data={
            "completed_stages": [],
            "pipeline": "ugc_product_ad",
            "product_name": product_name
        }
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)

    # Queue Celery task
    task = generate_ugc_ad_task.delay(
        job_id=job.id,
        product_name=product_name,
        description=description,
        product_images=product_image_paths,
        product_url=product_url,
        target_duration=target_duration,
        style_preference=style_preference
    )

    # Return UGCAdResponse
    return UGCAdResponse(
        job_id=job.id,
        task_id=str(task.id),
        status="queued",
        poll_url=f"/jobs/{job.id}",
        message=f"UGC ad generation started for '{product_name}'"
    )
