import asyncio
import json
from pathlib import Path
from typing import Dict
from uuid import uuid4

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory, get_session
from app.models import LandingPage
# NOTE: landing_page service imports are deferred to _run_generation to avoid
# google.genai module-level import error at server startup in Docker.

# Router for all web UI HTML pages
router = APIRouter(prefix="/ui", tags=["web-ui"])
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

# In-memory job store: job_id -> status dict
_jobs: Dict[str, dict] = {}


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
async def deploy_lp(run_id: str):
    """Stub — actual Cloudflare deployment in Phase 19."""
    return {"status": "not_implemented", "message": "Cloudflare deployment coming in Phase 19"}


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
