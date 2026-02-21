import asyncio
import csv
import io
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Optional, Tuple
from uuid import uuid4

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from statemachine.exceptions import TransitionNotAllowed

from app.database import async_session_factory, get_session
from app.models import LandingPage, UGCJob, WaitlistEntry
from app.ugc_router import _STAGE_ADVANCE_MAP, _STAGE_REGEN_MAP
from app.state_machines.ugc_job import UGCJobStateMachine
# NOTE: landing_page service imports are deferred to _run_generation to avoid
# google.genai module-level import error at server startup in Docker.

# Router for all web UI HTML pages
router = APIRouter(prefix="/ui", tags=["web-ui"])
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


def _media_url(path: str) -> str:
    """Convert stored relative path 'output/foo/bar.mp4' to URL '/output/foo/bar.mp4'."""
    if not path:
        return ""
    return "/" + path.lstrip("/")


templates.env.filters["media_url"] = _media_url

# In-memory job store: job_id -> status dict
_jobs: Dict[str, dict] = {}

# Stage order for stepper rendering
STAGE_ORDER = [
    ("stage_analysis_review", "Analysis"),
    ("stage_script_review", "Script"),
    ("stage_aroll_review", "A-Roll"),
    ("stage_broll_review", "B-Roll"),
    ("stage_composition_review", "Composition"),
]
_REVIEW_STATES = {s for s, _ in STAGE_ORDER}

# LP module names — single source of truth for review and approve endpoint
LP_MODULES = ["headline", "hero", "cta", "benefits"]


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, session: AsyncSession = Depends(get_session)):
    """Dashboard — lists all landing pages ordered by newest first."""
    result = await session.execute(select(LandingPage).order_by(LandingPage.created_at.desc()))
    lps = result.scalars().all()
    return templates.TemplateResponse(request=request, name="index.html", context={"lps": lps})


@router.get("/generate", response_class=HTMLResponse)
async def generate_form(request: Request):
    """Serve the LP generation form."""
    return templates.TemplateResponse(request=request, name="generate.html", context={})


@router.post("/generate", response_class=HTMLResponse)
async def start_generate(
    request: Request,
    product_idea: str = Form(...),
    target_audience: str = Form(...),
    color_preference: str = Form("research"),
    mock: bool = Form(False),
):
    """Accept form submission, start background generation, redirect to progress page."""
    job_id = uuid4().hex[:8]
    _jobs[job_id] = {
        "status": "running",
        "progress": 0,
        "message": "Starting generation...",
        "run_id": None,
        "html_path": None,
        "error": None,
    }
    asyncio.create_task(_run_generation(job_id, product_idea, target_audience, color_preference, mock))
    return RedirectResponse(url=f"/ui/generate/{job_id}/progress", status_code=303)


@router.get("/generate/{job_id}/progress", response_class=HTMLResponse)
async def generation_progress(request: Request, job_id: str):
    """Serve the progress page for a running generation job."""
    return templates.TemplateResponse(request=request, name="progress.html", context={"job_id": job_id})


@router.get("/generate/{job_id}/events")
async def generation_events(job_id: str):
    """SSE endpoint — streams job status updates until done or error."""
    async def event_stream():
        for _ in range(120):  # max 2 min (120 x 1s)
            job = _jobs.get(job_id, {"status": "not_found"})
            yield f"data: {json.dumps(job)}\n\n"
            if job["status"] in ("done", "error", "not_found"):
                break
            await asyncio.sleep(1)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/preview/{run_id}", response_class=HTMLResponse)
async def preview_lp(request: Request, run_id: str, session: AsyncSession = Depends(get_session)):
    """Preview a landing page in an inline iframe."""
    result = await session.execute(select(LandingPage).where(LandingPage.run_id == run_id))
    lp = result.scalar_one_or_none()
    if not lp:
        raise HTTPException(status_code=404, detail=f"LP {run_id} not found")
    return templates.TemplateResponse(request=request, name="preview.html", context={"lp": lp, "run_id": run_id})


@router.post("/deploy/{run_id}")
async def deploy_lp(run_id: str, session: AsyncSession = Depends(get_session)):
    """Deploy LP to Cloudflare Pages. Updates status to 'deployed' on success."""
    from app.services.landing_page.deployer import deploy_to_cloudflare_pages
    from app.config import get_settings

    result = await session.execute(select(LandingPage).where(LandingPage.run_id == run_id))
    lp = result.scalar_one_or_none()
    if not lp:
        raise HTTPException(status_code=404, detail=f"LP {run_id} not found")

    settings = get_settings()

    try:
        url = await deploy_to_cloudflare_pages(lp.html_path, lp.run_id, settings)
    except RuntimeError as e:
        return {"status": "error", "message": str(e)}

    # Update DB — allow re-deploy (update URL and timestamp)
    lp.status = "deployed"
    lp.deployed_at = datetime.now(timezone.utc)
    lp.deployed_url = url
    await session.commit()

    return {"status": "deployed", "url": url}


@router.get("/lp/{run_id}/review", response_class=HTMLResponse)
async def lp_review(request: Request, run_id: str, session: AsyncSession = Depends(get_session)):
    """LP module review page — shows each copy module as a card with approve button."""
    result = await session.execute(select(LandingPage).where(LandingPage.run_id == run_id))
    lp = result.scalar_one_or_none()
    if not lp:
        raise HTTPException(status_code=404, detail=f"LP {run_id} not found")

    # Check video approval status via ugc_job_id FK
    if lp.ugc_job_id is not None:
        ugc_result = await session.execute(select(UGCJob).where(UGCJob.id == lp.ugc_job_id))
        ugc_job = ugc_result.scalar_one_or_none()
        video_approved = ugc_job is not None and ugc_job.status == "approved"
    else:
        video_approved = True  # standalone LP — no stage gate

    # Build per-module content from stored lp_copy
    lp_copy = lp.lp_copy or {}
    benefits = lp_copy.get("benefits") or []
    benefits_text = "\n".join(
        f"- {b.get('title', '')}: {b.get('description', '')}" if isinstance(b, dict) else str(b)
        for b in benefits
    )
    lp_module_content = {
        "headline": "\n".join(filter(None, [lp_copy.get("headline", ""), lp_copy.get("subheadline", "")])),
        "hero": lp.lp_hero_image_path or "No hero image",
        "cta": "\n".join(filter(None, [lp_copy.get("cta_text", ""), lp_copy.get("urgency_text") or ""])),
        "benefits": benefits_text or "No benefits data",
    }

    return templates.TemplateResponse(
        request=request,
        name="lp_review.html",
        context={
            "lp": lp,
            "video_approved": video_approved,
            "modules": LP_MODULES,
            "lp_module_content": lp_module_content,
        },
    )


@router.post("/lp/{run_id}/module/{module}/approve", response_class=HTMLResponse)
async def lp_module_approve(request: Request, run_id: str, module: str, session: AsyncSession = Depends(get_session)):
    """HTMX: approve one LP module, return updated lp-stage-controls partial."""
    if module not in LP_MODULES:
        raise HTTPException(status_code=400, detail=f"Unknown module '{module}'")

    result = await session.execute(select(LandingPage).where(LandingPage.run_id == run_id))
    lp = result.scalar_one_or_none()
    if not lp:
        raise HTTPException(status_code=404, detail=f"LP {run_id} not found")

    if lp.lp_review_locked:
        raise HTTPException(status_code=400, detail="LP review is locked — approve the linked video first")

    # Update approvals dict — reassign to trigger SQLAlchemy dirty detection
    approvals = dict(lp.lp_module_approvals or {})
    approvals[module] = "approved"
    lp.lp_module_approvals = approvals
    await session.commit()

    return templates.TemplateResponse(
        request=request,
        name="partials/lp_stage_controls.html",
        context={"lp": lp, "modules": LP_MODULES},
    )


def _parse_date_range(start_str: Optional[str], end_str: Optional[str]) -> Tuple[Optional[datetime], Optional[datetime]]:
    """Parse optional YYYY-MM-DD strings into UTC datetimes. End date is inclusive (adds 1 day)."""
    start_dt = datetime(*(date.fromisoformat(start_str).timetuple()[:3]), tzinfo=timezone.utc) if start_str else None
    end_dt = (
        datetime(*(date.fromisoformat(end_str).timetuple()[:3]), tzinfo=timezone.utc) + timedelta(days=1)
        if end_str
        else None
    )
    return start_dt, end_dt


@router.get("/dashboard", response_class=HTMLResponse)
async def analytics_dashboard(
    request: Request,
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_session),
):
    """Analytics dashboard — per-LP traffic, signups, and CVR with optional date filter."""
    start_dt, end_dt = _parse_date_range(start, end)

    # Build signup count per LP source with optional date filter
    signup_q = select(WaitlistEntry.lp_source, func.count(WaitlistEntry.id).label("count")).group_by(
        WaitlistEntry.lp_source
    )
    if start_dt:
        signup_q = signup_q.where(WaitlistEntry.signed_up_at >= start_dt)
    if end_dt:
        signup_q = signup_q.where(WaitlistEntry.signed_up_at < end_dt)
    signup_result = await session.execute(signup_q)
    signups_by_lp = {row.lp_source: row.count for row in signup_result}

    # Fetch all LPs ordered newest first
    lp_result = await session.execute(select(LandingPage).order_by(LandingPage.created_at.desc()))
    lps = lp_result.scalars().all()

    # Fetch analytics concurrently from Cloudflare Worker (lazy import)
    from app.services.analytics.client import CloudflareAnalyticsClient  # noqa: PLC0415
    client = CloudflareAnalyticsClient()
    analytics_list = await asyncio.gather(*[client.get_lp_analytics(lp.run_id) for lp in lps])
    analytics = {lp.run_id: data for lp, data in zip(lps, analytics_list)}

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={"lps": lps, "signups_by_lp": signups_by_lp, "analytics": analytics, "start": start or "", "end": end or ""},
    )


@router.get("/waitlist", response_class=HTMLResponse)
async def waitlist_view(
    request: Request,
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_session),
):
    """Waitlist signups table with optional date filter."""
    start_dt, end_dt = _parse_date_range(start, end)

    q = select(WaitlistEntry).order_by(WaitlistEntry.signed_up_at.desc())
    if start_dt:
        q = q.where(WaitlistEntry.signed_up_at >= start_dt)
    if end_dt:
        q = q.where(WaitlistEntry.signed_up_at < end_dt)
    result = await session.execute(q)
    entries = result.scalars().all()

    return templates.TemplateResponse(
        request=request,
        name="waitlist.html",
        context={"entries": entries, "start": start or "", "end": end or ""},
    )


@router.get("/waitlist/export.csv")
async def export_waitlist_csv(
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_session),
):
    """Stream waitlist signups as a CSV download with optional date filter."""
    start_dt, end_dt = _parse_date_range(start, end)

    q = select(WaitlistEntry).order_by(WaitlistEntry.signed_up_at.desc())
    if start_dt:
        q = q.where(WaitlistEntry.signed_up_at >= start_dt)
    if end_dt:
        q = q.where(WaitlistEntry.signed_up_at < end_dt)
    result = await session.execute(q)
    entries = result.scalars().all()

    def generate():
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["email", "signed_up_at", "lp_source"])
        yield buf.getvalue()
        for e in entries:
            buf.seek(0)
            buf.truncate()
            writer.writerow([
                e.email,
                e.signed_up_at.isoformat() if e.signed_up_at else "",
                e.lp_source or "",
            ])
            yield buf.getvalue()

    return StreamingResponse(
        generate(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="waitlist.csv"'},
    )


@router.get("/ugc", response_class=HTMLResponse)
async def ugc_list(request: Request, session: AsyncSession = Depends(get_session)):
    """List all UGC jobs."""
    result = await session.execute(select(UGCJob).order_by(UGCJob.created_at.desc()))
    ugc_jobs = result.scalars().all()
    return templates.TemplateResponse(request=request, name="ugc_list.html", context={"ugc_jobs": ugc_jobs})


@router.get("/ugc/new", response_class=HTMLResponse)
async def ugc_new(request: Request):
    """Serve UGC job creation form."""
    return templates.TemplateResponse(request=request, name="ugc_new.html", context={})


@router.get("/ugc/{job_id}/review", response_class=HTMLResponse)
async def ugc_review(request: Request, job_id: int, session: AsyncSession = Depends(get_session)):
    """Stage stepper + item grids for a UGC job."""
    result = await session.execute(select(UGCJob).where(UGCJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail=f"UGCJob {job_id} not found")

    # Derive stepper state
    stage_keys = [s for s, _ in STAGE_ORDER]
    if job.status in stage_keys:
        current_idx = stage_keys.index(job.status)
        completed_stages = set(stage_keys[:current_idx])
    elif job.status == "approved":
        completed_stages = set(stage_keys)
    else:
        completed_stages = set()

    # When running, derive which stage is "in progress" by checking populated data columns
    running_toward = None
    if job.status == "running":
        if job.final_video_path is not None or job.broll_paths is not None:
            running_toward = "stage_composition_review"
            completed_stages = set(stage_keys[:4])
        elif job.aroll_paths is not None:
            running_toward = "stage_broll_review"
            completed_stages = set(stage_keys[:3])
        elif job.aroll_scenes is not None:
            running_toward = "stage_aroll_review"
            completed_stages = set(stage_keys[:2])
        elif job.master_script is not None:
            running_toward = "stage_script_review"
            completed_stages = set(stage_keys[:1])
        else:
            running_toward = "stage_analysis_review"

    return templates.TemplateResponse(
        request=request,
        name="ugc_review.html",
        context={
            "job": job,
            "stage_order": STAGE_ORDER,
            "completed_stages": completed_stages,
            "review_states": _REVIEW_STATES,
            "running_toward": running_toward,
        },
    )


@router.post("/ugc/{job_id}/advance", response_class=HTMLResponse)
async def ugc_ui_advance(request: Request, job_id: int, session: AsyncSession = Depends(get_session)):
    """HTMX: approve current stage, return updated stage-controls partial."""
    result = await session.execute(select(UGCJob).where(UGCJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail=f"UGCJob {job_id} not found")

    if job.status not in _STAGE_ADVANCE_MAP:
        raise HTTPException(status_code=400, detail=f"Cannot advance from '{job.status}'")

    approve_event, next_task_name = _STAGE_ADVANCE_MAP[job.status]

    try:
        sm = UGCJobStateMachine(model=job, state_field="status", start_value=job.status)
        sm.send(approve_event)
        job.status = sm.current_state.id
    except TransitionNotAllowed as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # Set approved_at on final approval (uses module-level datetime import)
    if approve_event == "approve_final":
        job.approved_at = datetime.now(timezone.utc)

    await session.commit()

    # Enqueue next stage task
    if next_task_name:
        import app.ugc_tasks as ugc_tasks_module
        getattr(ugc_tasks_module, next_task_name).delay(job_id)

    return templates.TemplateResponse(
        request=request,
        name="partials/ugc_stage_controls.html",
        context={"job": job, "review_states": _REVIEW_STATES},
    )


@router.post("/ugc/{job_id}/regenerate", response_class=HTMLResponse)
async def ugc_ui_regenerate(request: Request, job_id: int, session: AsyncSession = Depends(get_session)):
    """HTMX: regenerate current stage, return updated stage-controls partial."""
    result = await session.execute(select(UGCJob).where(UGCJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail=f"UGCJob {job_id} not found")

    if job.status not in _STAGE_REGEN_MAP:
        detail = ("Composition stage cannot be regenerated"
                  if job.status == "stage_composition_review"
                  else f"Cannot regenerate from '{job.status}'")
        raise HTTPException(status_code=400, detail=detail)

    task_name = _STAGE_REGEN_MAP[job.status]
    approve_event, _ = _STAGE_ADVANCE_MAP[job.status]

    try:
        sm = UGCJobStateMachine(model=job, state_field="status", start_value=job.status)
        sm.send(approve_event)
        job.status = sm.current_state.id
    except TransitionNotAllowed as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    await session.commit()

    import app.ugc_tasks as ugc_tasks_module
    getattr(ugc_tasks_module, task_name).delay(job_id)

    return templates.TemplateResponse(
        request=request,
        name="partials/ugc_stage_controls.html",
        context={"job": job, "review_states": _REVIEW_STATES},
    )


async def _run_generation(job_id: str, product_idea: str, target_audience: str, color_preference: str, use_mock: bool):
    """Background task: run LP generation pipeline and save result to DB."""
    try:
        # Lazy import — avoids google.genai module-level import at server startup
        from app.services.landing_page import LandingPageRequest, generate_landing_page  # noqa: PLC0415

        _jobs[job_id]["progress"] = 10
        _jobs[job_id]["message"] = "Preparing generation request..."

        lp_request = LandingPageRequest(
            product_idea=product_idea,
            target_audience=target_audience,
            color_preference=color_preference,
        )

        _jobs[job_id]["progress"] = 20
        _jobs[job_id]["message"] = "Running LP generation pipeline..."

        result = await generate_landing_page(lp_request, use_mock=use_mock)

        # Extract run_id from the output directory name
        run_id = Path(result.html_path).parent.name

        # Save to database
        _jobs[job_id]["progress"] = 90
        _jobs[job_id]["message"] = "Saving to database..."

        async with async_session_factory() as session:
            lp_record = LandingPage(
                run_id=run_id,
                product_idea=product_idea,
                target_audience=target_audience,
                html_path=result.html_path,
                status="generated",
                color_scheme_source=color_preference,
                sections=result.sections,
                lp_copy=result.lp_copy,
            )
            session.add(lp_record)
            await session.commit()

        _jobs[job_id]["status"] = "done"
        _jobs[job_id]["progress"] = 100
        _jobs[job_id]["message"] = "Complete!"
        _jobs[job_id]["run_id"] = run_id
        _jobs[job_id]["html_path"] = result.html_path

    except Exception as e:
        import traceback
        traceback.print_exc()
        _jobs[job_id]["status"] = "error"
        _jobs[job_id]["error"] = str(e)
