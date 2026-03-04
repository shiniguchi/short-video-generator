import asyncio
import csv
import io
import json
import logging
import shutil
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Optional, Tuple
from uuid import uuid4

from PIL import Image

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from statemachine.exceptions import TransitionNotAllowed

from app.database import async_session_factory, get_session
from app.models import LandingPage, UGCJob, WaitlistEntry
from app.ugc_router import _STAGE_ADVANCE_MAP, _STAGE_REGEN_MAP, _STAGE_SKIP_VIDEO_CONFIG, _determine_resume_task
from app.state_machines.ugc_job import UGCJobStateMachine
# NOTE: landing_page service imports are deferred to _run_generation to avoid
# google.genai module-level import error at server startup in Docker.

logger = logging.getLogger(__name__)

# Router for all web UI HTML pages
router = APIRouter(prefix="/ui", tags=["web-ui"])
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


def _media_url(path: str) -> str:
    """Convert stored relative path 'output/foo/bar.mp4' to URL '/output/foo/bar.mp4'."""
    if not path:
        return ""
    return "/" + path.lstrip("/")


templates.env.filters["media_url"] = _media_url


def _delete_files_safe(paths: list[str]):
    """Delete files from disk, skip missing."""
    for p in paths:
        try:
            path = Path(p)
            if path.exists():
                path.unlink()
        except Exception:
            pass


# In-memory job store: job_id -> status dict
_jobs: Dict[str, dict] = {}

# Stage order for stepper rendering
STAGE_ORDER = [
    ("stage_analysis_review",     "Overview"),
    ("stage_script_review",       "Script"),
    ("stage_aroll_image_review",  "A-Roll Images"),
    ("stage_aroll_review",        "A-Roll Videos"),
    ("stage_broll_image_review",  "B-Roll Images"),
    ("stage_broll_review",        "B-Roll Videos"),
    ("stage_composition_review",  "Composition"),
]
_REVIEW_STATES = {s for s, _ in STAGE_ORDER}

# Columns to clear when rewinding to a given stage (everything generated AFTER it)
_DOWNSTREAM_COLUMNS = {
    "stage_analysis_review": [
        "master_script", "aroll_scenes", "broll_shots",
        "aroll_image_paths", "aroll_paths",
        "broll_image_paths", "broll_paths", "final_video_path",
    ],
    "stage_script_review": [
        "aroll_image_paths", "aroll_paths",
        "broll_image_paths", "broll_paths", "final_video_path",
    ],
    "stage_aroll_image_review": [
        "aroll_paths", "broll_image_paths", "broll_paths", "final_video_path",
    ],
    "stage_aroll_review": [
        "broll_image_paths", "broll_paths", "final_video_path",
    ],
    "stage_broll_image_review": [
        "broll_paths", "final_video_path",
    ],
    "stage_broll_review": [
        "final_video_path",
    ],
}

# LP module names — single source of truth for review and approve endpoint
LP_MODULES = ["headline", "hero", "cta", "benefits"]

# Workflow definitions — template loops over these, no per-workflow HTML needed
WORKFLOWS = [
    {
        "id": "video_lp",
        "icon": "video_lp",
        "title": "Video + Landing Page",
        "desc": "Create a short-form video, then generate a matching landing page.",
        "href": "/ui/ugc/new",
    },
    {
        "id": "video",
        "icon": "video",
        "title": "Video Only",
        "desc": "Create a short-form UGC video for social media.",
        "href": "/ui/ugc/new",
    },
    {
        "id": "lp",
        "icon": "globe",
        "title": "Landing Page Only",
        "desc": "Generate a conversion-optimized landing page.",
        "href": "/ui/generate",
    },
]


@router.get("/", response_class=HTMLResponse)
async def start_page(request: Request):
    """Start page — workflow selector."""
    return templates.TemplateResponse(request=request, name="start.html", context={"workflows": WORKFLOWS})


@router.get("/lp", response_class=HTMLResponse)
async def lp_list(request: Request, session: AsyncSession = Depends(get_session)):
    """LP list — all landing pages ordered by newest first."""
    result = await session.execute(select(LandingPage).order_by(LandingPage.created_at.desc()))
    lps = result.scalars().all()
    return templates.TemplateResponse(request=request, name="index.html", context={"lps": lps})


async def _delete_lps(lp_ids: list[int], session: AsyncSession):
    """Shared: delete LP rows, waitlist entries, and output files."""
    result = await session.execute(select(LandingPage).where(LandingPage.id.in_(lp_ids)))
    lps = result.scalars().all()

    run_ids = [lp.run_id for lp in lps]
    file_paths: list[str] = []
    output_dirs: list[str] = []
    for lp in lps:
        if lp.html_path:
            file_paths.append(lp.html_path)
        output_dirs.append(f"output/{lp.run_id}")

    # Delete waitlist entries
    if run_ids:
        await session.execute(
            WaitlistEntry.__table__.delete().where(WaitlistEntry.lp_source.in_(run_ids))
        )

    for lp in lps:
        await session.delete(lp)
    await session.commit()

    # Clean up files and output dirs
    _delete_files_safe(file_paths)
    for d in output_dirs:
        try:
            p = Path(d)
            if p.exists():
                shutil.rmtree(p)
        except Exception:
            pass


@router.post("/lp/bulk-delete")
async def lp_bulk_delete(ids: str = Form(...), session: AsyncSession = Depends(get_session)):
    """Bulk-delete landing pages from the LP list."""
    lp_ids = [int(i) for i in ids.split(",") if i.strip().isdigit()]
    if not lp_ids:
        return RedirectResponse(url="/ui/", status_code=303)
    await _delete_lps(lp_ids, session)
    return RedirectResponse(url="/ui/", status_code=303)


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

    # Build section image data for the editor panel
    from app.ugc_tasks import IMAGEABLE_SECTIONS
    section_labels = {"benefits": "Benefits", "how_it_works": "How It Works"}
    sections_data = []
    lp_copy = lp.lp_copy or {}
    lp_images = lp.lp_section_images or {}

    for key, copy_field in IMAGEABLE_SECTIONS.items():
        items_copy = lp_copy.get(copy_field) or []
        image_paths = lp_images.get(key) or []
        items = []
        for i, item in enumerate(items_copy):
            img_path = image_paths[i] if i < len(image_paths) else None
            items.append({
                "title": item.get("title", f"Item {i+1}"),
                "image_url": _media_url(img_path) if img_path else None,
                "index": i,
            })
        if items:
            sections_data.append({"key": key, "label": section_labels.get(key, key), "entries": items})

    has_section_images = any(item["image_url"] for s in sections_data for item in s["entries"])

    return templates.TemplateResponse(
        request=request, name="preview.html",
        context={
            "lp": lp, "run_id": run_id,
            "sections_data": sections_data,
            "has_section_images": has_section_images,
        },
    )


@router.post("/deploy/{run_id}")
async def deploy_lp(run_id: str, request: Request, session: AsyncSession = Depends(get_session)):
    """Deploy LP to Cloudflare Pages. Updates status to 'deployed' on success."""
    from app.services.landing_page.deployer import deploy_to_cloudflare_pages
    from app.config import get_settings

    result = await session.execute(select(LandingPage).where(LandingPage.run_id == run_id))
    lp = result.scalar_one_or_none()
    if not lp:
        raise HTTPException(status_code=404, detail=f"LP {run_id} not found")

    settings = get_settings()

    # Extract origin for api-base injection in deployed HTML
    api_base_url = str(request.base_url).rstrip("/")

    try:
        url = await deploy_to_cloudflare_pages(lp.html_path, lp.run_id, settings, api_base_url)
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

    lp_copy = lp.lp_copy or {}

    # Load template presets for the picker UI
    from app.services.landing_page.template_builder import get_available_templates
    lp_templates = get_available_templates()

    return templates.TemplateResponse(
        request=request,
        name="lp_review.html",
        context={
            "lp": lp,
            "video_approved": video_approved,
            "modules": LP_MODULES,
            "lp_copy": lp_copy,
            "templates": lp_templates,
        },
    )


@router.get("/lp/{run_id}/status")
async def lp_status(run_id: str, session: AsyncSession = Depends(get_session)):
    """Poll LP generation status — returns JSON with status for progress bar."""
    result = await session.execute(select(LandingPage).where(LandingPage.run_id == run_id))
    lp = result.scalar_one_or_none()
    if not lp:
        raise HTTPException(status_code=404, detail=f"LP {run_id} not found")
    return JSONResponse({"status": lp.status})


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


@router.post("/lp/{run_id}/module/{module}/regenerate")
async def lp_module_regenerate(request: Request, run_id: str, module: str, session: AsyncSession = Depends(get_session)):
    """Regenerate a single LP copy module (headline/cta/benefits) and redirect back."""
    if module not in LP_MODULES or module == "hero":
        raise HTTPException(status_code=400, detail=f"Cannot regenerate '{module}' via this endpoint")

    result = await session.execute(select(LandingPage).where(LandingPage.run_id == run_id))
    lp = result.scalar_one_or_none()
    if not lp:
        raise HTTPException(status_code=404, detail=f"LP {run_id} not found")
    if lp.lp_review_locked:
        raise HTTPException(status_code=400, detail="LP review is locked")

    from app.services.landing_page.copy_generator import regenerate_module
    import asyncio

    new_fields = await asyncio.to_thread(
        regenerate_module,
        module,
        lp.product_idea,
        (lp.target_audience or "general"),
    )

    # Merge new fields into existing lp_copy
    lp_copy = dict(lp.lp_copy or {})
    lp_copy.update(new_fields)
    lp.lp_copy = lp_copy

    # Clear approval for this module since content changed
    approvals = dict(lp.lp_module_approvals or {})
    approvals.pop(module, None)
    lp.lp_module_approvals = approvals

    await session.commit()
    return RedirectResponse(url=f"/ui/lp/{run_id}/review", status_code=303)


@router.post("/lp/{run_id}/upload-hero")
async def lp_upload_hero(run_id: str, file: UploadFile = File(...), session: AsyncSession = Depends(get_session)):
    """Upload a custom hero image for the LP."""
    result = await session.execute(select(LandingPage).where(LandingPage.run_id == run_id))
    lp = result.scalar_one_or_none()
    if not lp:
        raise HTTPException(status_code=404, detail=f"LP {run_id} not found")

    import os
    os.makedirs("output/lp_frames", exist_ok=True)
    ext = Path(file.filename).suffix or ".jpg"
    dest = f"output/lp_frames/lp_hero_{run_id}_upload{ext}"
    with open(dest, "wb") as f:
        f.write(await file.read())

    lp.lp_hero_candidate_path = dest
    await session.commit()
    return RedirectResponse(url=f"/ui/lp/{run_id}/review", status_code=303)


@router.post("/lp/{run_id}/module/{module}/save")
async def lp_module_save(request: Request, run_id: str, module: str, session: AsyncSession = Depends(get_session)):
    """Save manually edited LP copy fields for a module."""
    if module not in LP_MODULES or module == "hero":
        raise HTTPException(status_code=400, detail=f"Cannot edit '{module}'")

    result = await session.execute(select(LandingPage).where(LandingPage.run_id == run_id))
    lp = result.scalar_one_or_none()
    if not lp:
        raise HTTPException(status_code=404, detail=f"LP {run_id} not found")

    form = await request.form()
    lp_copy = dict(lp.lp_copy or {})

    if module == "headline":
        lp_copy["headline"] = form.get("headline", "").strip()
        lp_copy["subheadline"] = form.get("subheadline", "").strip()
    elif module == "cta":
        lp_copy["cta_text"] = form.get("cta_text", "").strip()
        lp_copy["urgency_text"] = form.get("urgency_text", "").strip()
        lp_copy["social_proof_text"] = form.get("social_proof_text", "").strip()
    elif module == "benefits":
        benefits = lp_copy.get("benefits") or []
        for i, b in enumerate(benefits):
            t = form.get(f"benefit_title_{i}", "").strip()
            d = form.get(f"benefit_desc_{i}", "").strip()
            if t:
                b["title"] = t
            if d:
                b["description"] = d
        lp_copy["benefits"] = benefits

    lp.lp_copy = lp_copy
    await session.commit()
    return RedirectResponse(url=f"/ui/lp/{run_id}/review", status_code=303)


@router.post("/lp/{run_id}/regenerate-hero", response_class=HTMLResponse)
async def lp_regenerate_hero(request: Request, run_id: str, session: AsyncSession = Depends(get_session)):
    """HTMX: enqueue LP hero image regeneration Celery task."""
    result = await session.execute(select(LandingPage).where(LandingPage.run_id == run_id))
    lp = result.scalar_one_or_none()
    if not lp:
        raise HTTPException(status_code=404, detail=f"LP {run_id} not found")
    if lp.lp_review_locked:
        raise HTTPException(status_code=400, detail="LP review is locked — approve the linked video first")

    # Lazy import to avoid circular imports at module load time
    import app.ugc_tasks as ugc_tasks_module
    ugc_tasks_module.lp_hero_regen.delay(lp.id)

    return templates.TemplateResponse(
        request=request,
        name="partials/lp_stage_controls.html",
        context={"lp": lp, "modules": LP_MODULES, "regen_status": "Regenerating hero image..."},
    )


@router.post("/lp/{run_id}/accept-hero-candidate")
async def lp_accept_hero_candidate(run_id: str, session: AsyncSession = Depends(get_session)):
    """Swap candidate hero image into approved hero slot, then redirect."""
    result = await session.execute(select(LandingPage).where(LandingPage.run_id == run_id))
    lp = result.scalar_one_or_none()
    if not lp:
        raise HTTPException(status_code=404, detail=f"LP {run_id} not found")
    if lp.lp_hero_candidate_path is None:
        raise HTTPException(status_code=400, detail="No candidate available")

    lp.lp_hero_image_path = lp.lp_hero_candidate_path
    lp.lp_hero_candidate_path = None
    await session.commit()
    return RedirectResponse(url=f"/ui/lp/{run_id}/review", status_code=303)


@router.post("/lp/{run_id}/regenerate-hero-sync")
async def lp_regenerate_hero_sync(run_id: str, session: AsyncSession = Depends(get_session)):
    """Enqueue hero image regeneration Celery task, then redirect back."""
    result = await session.execute(select(LandingPage).where(LandingPage.run_id == run_id))
    lp = result.scalar_one_or_none()
    if not lp:
        raise HTTPException(status_code=404, detail=f"LP {run_id} not found")
    if lp.lp_review_locked:
        raise HTTPException(status_code=400, detail="LP review is locked — approve the linked video first")

    import app.ugc_tasks as ugc_tasks_module
    ugc_tasks_module.lp_hero_regen.delay(lp.id)
    return RedirectResponse(url=f"/ui/lp/{run_id}/review", status_code=303)


@router.post("/lp/{run_id}/approve-all")
async def lp_approve_all(run_id: str, session: AsyncSession = Depends(get_session)):
    """Approve all LP modules at once and mark LP as approved."""
    result = await session.execute(select(LandingPage).where(LandingPage.run_id == run_id))
    lp = result.scalar_one_or_none()
    if not lp:
        raise HTTPException(status_code=404, detail=f"LP {run_id} not found")

    lp.lp_module_approvals = {"all": "approved"}
    lp.status = "approved"
    await session.commit()
    return RedirectResponse(url=f"/ui/lp/{run_id}/review", status_code=303)


@router.post("/lp/{run_id}/generate-section-images")
async def lp_generate_section_images(
    run_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Trigger Celery task to generate unique AI images per LP section item."""
    result = await session.execute(select(LandingPage).where(LandingPage.run_id == run_id))
    lp = result.scalar_one_or_none()
    if not lp:
        raise HTTPException(status_code=404, detail=f"LP {run_id} not found")

    from app.ugc_tasks import lp_generate_section_images as task_fn
    task = task_fn.delay(lp.id)
    return JSONResponse({"task_id": task.id})


@router.post("/lp/{run_id}/regen-section-image")
async def lp_regen_section_image(
    run_id: str,
    section: str = Form(...),
    index: int = Form(...),
    session: AsyncSession = Depends(get_session),
):
    """Trigger single section image regeneration via Celery."""
    result = await session.execute(select(LandingPage).where(LandingPage.run_id == run_id))
    lp = result.scalar_one_or_none()
    if not lp:
        raise HTTPException(status_code=404, detail=f"LP {run_id} not found")

    from app.ugc_tasks import lp_regen_section_image as task_fn
    task = task_fn.delay(lp.id, section, index)
    return JSONResponse({"task_id": task.id, "section": section, "index": index})


@router.post("/lp/{run_id}/upload-section-image")
async def lp_upload_section_image(
    run_id: str,
    file: UploadFile = File(...),
    section: str = Form(...),
    index: int = Form(...),
    session: AsyncSession = Depends(get_session),
):
    """Upload a custom image to replace a section image."""
    result = await session.execute(select(LandingPage).where(LandingPage.run_id == run_id))
    lp = result.scalar_one_or_none()
    if not lp:
        raise HTTPException(status_code=404, detail=f"LP {run_id} not found")

    from app.ugc_tasks import IMAGEABLE_SECTIONS
    if section not in IMAGEABLE_SECTIONS:
        raise HTTPException(status_code=400, detail=f"Invalid section: {section}")

    images = dict(lp.lp_section_images or {})
    section_imgs = list(images.get(section) or [])
    if index < 0 or index >= len(section_imgs):
        raise HTTPException(status_code=400, detail=f"Invalid index {index} for section {section}")

    upload_dir = Path("output") / "lp_uploads" / str(lp.id)
    upload_dir.mkdir(parents=True, exist_ok=True)
    orig = file.filename or "image.png"
    suffix = Path(orig).suffix or ".png"
    filename = f"section_{section}_{index}_{uuid4().hex[:6]}{suffix}"
    dest = upload_dir / filename
    content = await file.read()
    dest.write_bytes(content)

    section_imgs[index] = str(dest)
    images[section] = section_imgs
    lp.lp_section_images = images
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(lp, "lp_section_images")
    await session.commit()

    return JSONResponse({"image_url": _media_url(str(dest))})


@router.get("/lp/{run_id}/section-image-value")
async def lp_section_image_value(
    run_id: str,
    section: str = Query(...),
    index: int = Query(...),
    session: AsyncSession = Depends(get_session),
):
    """Poll current section image path (used by JS to detect regen completion)."""
    result = await session.execute(select(LandingPage).where(LandingPage.run_id == run_id))
    lp = result.scalar_one_or_none()
    if not lp:
        raise HTTPException(status_code=404, detail=f"LP {run_id} not found")

    images = (lp.lp_section_images or {}).get(section) or []
    path = images[index] if index < len(images) else None
    return JSONResponse({"image_url": _media_url(path) if path else None})


async def _build_lp_html(lp, session: AsyncSession, template_key: Optional[str] = None):
    """Shared helper: build + optimize LP HTML, update DB. Returns html_path."""
    from app.services.landing_page.template_builder import build_landing_page
    from app.services.landing_page.optimizer import optimize_html
    from app.schemas import LandingPageCopy, ColorScheme
    from app.config import get_settings
    import os

    lp_copy = lp.lp_copy or {}
    if not lp_copy.get("headline"):
        raise HTTPException(status_code=400, detail="No LP copy to build from")

    copy = LandingPageCopy(**lp_copy)
    color_scheme = ColorScheme(
        primary="#2563EB", secondary="#1E40AF", accent="#F59E0B",
        background="#FFFFFF", text="#1F2937", source="default",
    )

    settings = get_settings()
    output_dir = Path(settings.output_dir) / lp.run_id
    output_dir.mkdir(parents=True, exist_ok=True)
    html_path = output_dir / "landing-page.html"

    hero_image_for_template = None
    if lp.lp_hero_image_path:
        abs_image = Path(lp.lp_hero_image_path).resolve()
        hero_image_for_template = os.path.relpath(abs_image, html_path.parent.resolve())

    # Collect product images from linked UGC job
    product_images_for_template = []
    if lp.ugc_job_id:
        ugc_result = await session.execute(select(UGCJob).where(UGCJob.id == lp.ugc_job_id))
        ugc_job = ugc_result.scalar_one_or_none()
        if ugc_job:
            all_paths = []
            for path_list in [ugc_job.product_image_paths, ugc_job.aroll_image_paths, ugc_job.broll_image_paths]:
                if path_list:
                    all_paths.extend(path_list)
            if ugc_job.hero_image_path:
                all_paths.append(ugc_job.hero_image_path)
            for p in all_paths:
                abs_p = Path(p).resolve()
                if abs_p.exists():
                    product_images_for_template.append(os.path.relpath(abs_p, html_path.parent.resolve()))

    # Resolve section images to relative paths
    section_images_for_template = None
    if lp.lp_section_images:
        section_images_for_template = {}
        for section, paths in lp.lp_section_images.items():
            rel_paths = []
            for p in paths:
                abs_p = Path(p).resolve()
                if abs_p.exists():
                    rel_paths.append(os.path.relpath(abs_p, html_path.parent.resolve()))
            if rel_paths:
                section_images_for_template[section] = rel_paths

    # Use stored template_key if not explicitly provided
    effective_template_key = template_key if template_key is not None else lp.template_key

    raw_html = build_landing_page(
        copy=copy, color_scheme=color_scheme,
        hero_image=hero_image_for_template, lp_source=lp.run_id,
        template_key=effective_template_key,
        product_images=product_images_for_template or None,
        section_images=section_images_for_template,
    )
    optimized_html = optimize_html(raw_html)
    html_path.write_text(optimized_html, encoding="utf-8")

    lp.html_path = str(html_path)
    if template_key is not None:
        lp.template_key = template_key
    await session.commit()

    logger.info(f"Built LP HTML for {lp.run_id}: {len(optimized_html)} chars -> {html_path}")

    # Generate waitlist page alongside LP
    from app.services.landing_page.template_builder import _create_jinja_env, _load_template_config
    env = _create_jinja_env()
    wl_template = env.get_template("waitlist_page.html.j2")
    tmpl_cfg = _load_template_config(effective_template_key) if effective_template_key else None
    product_name = copy.meta_title.split("—")[0].split("-")[0].strip() if copy.meta_title else lp.product_idea
    wl_html = wl_template.render(
        product_name=product_name,
        cta_text=copy.cta_text,
        lp_source=lp.run_id,
        color_primary=color_scheme.primary,
        color_secondary=color_scheme.secondary,
        color_accent=color_scheme.accent,
        color_bg=color_scheme.background,
        color_text=color_scheme.text,
        fonts_url=tmpl_cfg["fonts_url"] if tmpl_cfg else "",
        heading_font=tmpl_cfg["heading_font"] if tmpl_cfg else "inherit",
        body_font=tmpl_cfg["body_font"] if tmpl_cfg else "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
    )
    (output_dir / "waitlist.html").write_text(wl_html, encoding="utf-8")

    return html_path


@router.post("/lp/{run_id}/rebuild-html-ajax")
async def lp_rebuild_html_ajax(
    run_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Rebuild LP HTML and return JSON (no redirect). Used by JS to refresh iframe."""
    result = await session.execute(select(LandingPage).where(LandingPage.run_id == run_id))
    lp = result.scalar_one_or_none()
    if not lp:
        raise HTTPException(status_code=404, detail=f"LP {run_id} not found")

    await _build_lp_html(lp, session)
    return JSONResponse({"status": "ok"})


@router.post("/lp/{run_id}/build-html")
async def lp_build_html(
    run_id: str,
    template_key: Optional[str] = Form(None),
    session: AsyncSession = Depends(get_session),
):
    """Build LP HTML from approved copy + hero image, then redirect to preview."""
    result = await session.execute(select(LandingPage).where(LandingPage.run_id == run_id))
    lp = result.scalar_one_or_none()
    if not lp:
        raise HTTPException(status_code=404, detail=f"LP {run_id} not found")

    await _build_lp_html(lp, session, template_key=template_key)
    return RedirectResponse(url=f"/ui/preview/{run_id}", status_code=303)


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


@router.get("/analytics/signups/{run_id}")
async def analytics_signups(run_id: str, session: AsyncSession = Depends(get_session)):
    """Return signup list for a specific LP as JSON (used by detail modal)."""
    result = await session.execute(
        select(WaitlistEntry)
        .where(WaitlistEntry.lp_source == run_id)
        .order_by(WaitlistEntry.signed_up_at.desc())
    )
    entries = result.scalars().all()
    return JSONResponse([
        {
            "email": e.email,
            "signed_up_at": e.signed_up_at.strftime("%Y-%m-%d %H:%M") if e.signed_up_at else "\u2014",
        }
        for e in entries
    ])


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


@router.get("/quota-status")
async def quota_status():
    """Return current Veo/Imagen API quota usage (RPM + RPD)."""
    from app.services.quota_tracker import get_quota_status
    return get_quota_status()


@router.get("/ugc", response_class=HTMLResponse)
async def ugc_list(request: Request, session: AsyncSession = Depends(get_session)):
    """List all UGC jobs."""
    result = await session.execute(select(UGCJob).order_by(UGCJob.created_at.desc()))
    ugc_jobs = result.scalars().all()
    return templates.TemplateResponse(request=request, name="ugc_list.html", context={"ugc_jobs": ugc_jobs})


@router.post("/ugc/bulk-delete")
async def ugc_bulk_delete(ids: str = Form(...), session: AsyncSession = Depends(get_session)):
    """Bulk-delete UGC jobs and their generated files."""
    job_ids = [int(i) for i in ids.split(",") if i.strip().isdigit()]
    if not job_ids:
        return RedirectResponse(url="/ui/ugc", status_code=303)

    result = await session.execute(select(UGCJob).where(UGCJob.id.in_(job_ids)))
    jobs = result.scalars().all()

    # Collect all file paths to delete
    file_paths: list[str] = []
    for job in jobs:
        for col in (job.aroll_image_paths, job.broll_image_paths, job.aroll_paths, job.broll_paths):
            if col:
                file_paths.extend(col)
        # Flatten image/video history lists
        for hist in (job.aroll_image_history, job.broll_image_history, job.aroll_video_history, job.broll_video_history):
            if hist:
                for scene_list in hist:
                    if isinstance(scene_list, list):
                        file_paths.extend(scene_list)
        if job.final_video_path:
            file_paths.append(job.final_video_path)
        if job.candidate_video_path:
            file_paths.append(job.candidate_video_path)
        if job.hero_image_path:
            file_paths.append(job.hero_image_path)
        if job.hero_sketch_path:
            file_paths.append(job.hero_sketch_path)
        if job.trim_history:
            file_paths.extend(job.trim_history)
        if job.hero_image_history:
            file_paths.extend(job.hero_image_history)

    # Null out ugc_job_id on linked LandingPages
    await session.execute(
        LandingPage.__table__.update()
        .where(LandingPage.ugc_job_id.in_(job_ids))
        .values(ugc_job_id=None)
    )

    # Delete UGCJob rows
    for job in jobs:
        await session.delete(job)
    await session.commit()

    # Clean up files after commit
    _delete_files_safe(file_paths)

    return RedirectResponse(url="/ui/ugc", status_code=303)


@router.post("/dashboard/bulk-delete")
async def dashboard_bulk_delete(ids: str = Form(...), session: AsyncSession = Depends(get_session)):
    """Bulk-delete landing pages from insights dashboard."""
    lp_ids = [int(i) for i in ids.split(",") if i.strip().isdigit()]
    if not lp_ids:
        return RedirectResponse(url="/ui/dashboard", status_code=303)
    await _delete_lps(lp_ids, session)
    return RedirectResponse(url="/ui/dashboard", status_code=303)


@router.get("/ugc/new", response_class=HTMLResponse)
async def ugc_new(request: Request):
    """Serve UGC job creation form."""
    return templates.TemplateResponse(request=request, name="ugc_new.html", context={})


@router.get("/ugc/{job_id}/complete", response_class=HTMLResponse)
async def ugc_complete(request: Request, job_id: int, session: AsyncSession = Depends(get_session)):
    """Completion page shown after final approval."""
    result = await session.execute(select(UGCJob).where(UGCJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail=f"UGCJob {job_id} not found")
    if job.status != "approved":
        return RedirectResponse(url=f"/ui/ugc/{job_id}/review", status_code=303)

    # Check for linked LP
    lp_result = await session.execute(
        select(LandingPage).where(LandingPage.ugc_job_id == job_id).limit(1)
    )
    linked_lp = lp_result.scalar_one_or_none()

    # Check for A-Roll only video and B-Roll clips
    import os
    aroll_only_path = (job.final_video_path or "").replace(".mp4", "_aroll.mp4")
    aroll_only_exists = os.path.exists(aroll_only_path) if aroll_only_path else False

    return templates.TemplateResponse(
        request=request,
        name="ugc_complete.html",
        context={
            "job": job,
            "linked_lp": linked_lp,
            "aroll_only_path": aroll_only_path if aroll_only_exists else None,
            "broll_paths": job.broll_paths or [],
        },
    )


@router.get("/ugc/{job_id}/review", response_class=HTMLResponse)
async def ugc_review(request: Request, job_id: int, tab: Optional[str] = Query(None), session: AsyncSession = Depends(get_session)):
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
            completed_stages = set(stage_keys[:6])
        elif job.broll_image_paths is not None:
            running_toward = "stage_broll_review"
            completed_stages = set(stage_keys[:5])
        elif job.aroll_paths is not None:
            running_toward = "stage_broll_image_review"
            completed_stages = set(stage_keys[:4])
        elif job.aroll_image_paths is not None:
            running_toward = "stage_aroll_review"
            completed_stages = set(stage_keys[:3])
        elif job.aroll_scenes is not None:
            running_toward = "stage_aroll_image_review"
            completed_stages = set(stage_keys[:2])
        elif job.master_script is not None:
            running_toward = "stage_script_review"
            completed_stages = set(stage_keys[:1])
        else:
            running_toward = "stage_analysis_review"

    # Don't show image review tabs as completed/viewable if no image data exists
    # (old jobs created before the image review workflow)
    if not job.aroll_image_paths:
        completed_stages.discard("stage_aroll_image_review")
    if not job.broll_image_paths:
        completed_stages.discard("stage_broll_image_review")

    # Stages the user can view (completed + current)
    viewable_stages = completed_stages | ({job.status} if job.status in stage_keys else set())
    if job.status == "approved":
        viewable_stages = set(stage_keys)
        # Still hide image tabs for approved jobs with no image data
        if not job.aroll_image_paths:
            viewable_stages.discard("stage_aroll_image_review")
        if not job.broll_image_paths:
            viewable_stages.discard("stage_broll_image_review")

    # "project_settings" is always viewable (creation-time settings)
    viewable_stages.add("project_settings")

    # Active tab: from query param if viewable, else current stage
    # When running, show the tab we're running toward (the next review stage)
    if tab and tab in viewable_stages:
        active_tab = tab
    elif job.status == "running" and running_toward:
        active_tab = running_toward
    elif job.status in stage_keys:
        active_tab = job.status
    else:
        active_tab = stage_keys[0]

    # Collect uploaded reference files on disk for this job
    upload_dir = Path("output") / "ugc_uploads" / str(job_id)
    sketch_paths = sorted(upload_dir.glob("sketch_*"), key=lambda p: p.stat().st_mtime) if upload_dir.is_dir() else []
    ref_photo_paths = sorted(upload_dir.glob("refphoto_*"), key=lambda p: p.stat().st_mtime) if upload_dir.is_dir() else []

    return templates.TemplateResponse(
        request=request,
        name="ugc_review.html",
        context={
            "job": job,
            "stage_order": STAGE_ORDER,
            "completed_stages": completed_stages,
            "review_states": _REVIEW_STATES,
            "running_toward": running_toward,
            "sketch_paths": [str(p) for p in sketch_paths],
            "ref_photo_paths": [str(p) for p in ref_photo_paths],
            "active_tab": active_tab,
            "viewable_stages": viewable_stages,
        },
    )


@router.post("/ugc/{job_id}/advance", response_class=HTMLResponse)
async def ugc_ui_advance(request: Request, job_id: int, session: AsyncSession = Depends(get_session)):
    """Approve current stage (or rewind to a past stage and re-advance)."""
    result = await session.execute(select(UGCJob).where(UGCJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail=f"UGCJob {job_id} not found")

    # Optional rewind: from_stage lets the user go back to an earlier stage
    form = await request.form()
    from_stage = form.get("from_stage")
    if from_stage and from_stage != job.status and from_stage in _STAGE_ADVANCE_MAP:
        stage_keys = [s for s, _ in STAGE_ORDER]
        if from_stage not in stage_keys or job.status not in stage_keys:
            raise HTTPException(status_code=400, detail=f"Cannot rewind from '{job.status}'")
        if stage_keys.index(from_stage) >= stage_keys.index(job.status):
            raise HTTPException(status_code=400, detail="from_stage must be earlier than current status")
        # Rewind — set status directly (bypass state machine)
        job.status = from_stage
        # Clear all data columns downstream of the rewound stage
        # so _derive_stage_progress() returns the correct stage label
        for col in _DOWNSTREAM_COLUMNS.get(from_stage, []):
            setattr(job, col, None)

    if job.status not in _STAGE_ADVANCE_MAP:
        raise HTTPException(status_code=400, detail=f"Cannot advance from '{job.status}'")

    approve_event, next_task_name = _STAGE_ADVANCE_MAP[job.status]
    pre_advance_status = job.status

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

    # Skip video generation (full or partial)
    skip_cfg = _STAGE_SKIP_VIDEO_CONFIG.get(from_stage or pre_advance_status)
    if skip_cfg:
        count = len(getattr(job, skip_cfg["count_source"]) or [])
        skip_all = form.get("skip_video_gen") == "true"
        skip_indices_raw = form.get("skip_video_indices", "")
        skip_indices = set()
        if skip_all:
            skip_indices = set(range(count))
        elif skip_indices_raw:
            skip_indices = {int(i) for i in skip_indices_raw.split(",") if i.strip().isdigit()}

        if skip_indices:
            from sqlalchemy.orm.attributes import flag_modified
            paths = list(getattr(job, skip_cfg["video_col"]) or [None] * count)
            while len(paths) < count:
                paths.append(None)
            # Mark skipped slots with "__skipped__" sentinel so Celery knows to leave them as None
            for i in skip_indices:
                if 0 <= i < count:
                    paths[i] = "__skipped__"
            setattr(job, skip_cfg["video_col"], paths)
            flag_modified(job, skip_cfg["video_col"])

            if skip_indices == set(range(count)):
                # All skipped — fast-forward past video generation entirely
                # Replace sentinels with None for the final column value
                setattr(job, skip_cfg["video_col"], [None] * count)
                flag_modified(job, skip_cfg["video_col"])
                sm = UGCJobStateMachine(model=job, state_field="status", start_value=job.status)
                sm.send(skip_cfg["complete_event"])
                job.status = sm.current_state.id
                await session.commit()
                return templates.TemplateResponse(
                    request=request,
                    name="partials/ugc_stage_controls.html",
                    context={"job": job, "review_states": _REVIEW_STATES},
                )
            # Partial skip — commit pre-filled paths, Celery will generate the rest
            await session.commit()

    # Extract hero frame from approved video and unlock linked LPs
    if approve_event == "approve_final" and job.final_video_path:
        from app.services.video_compositor.thumbnail import generate_thumbnail
        try:
            frame_path = await asyncio.to_thread(
                generate_thumbnail,
                job.final_video_path,
                2.0,
                "output/lp_frames"
            )
            # Set hero image on any LP linked to this job and unlock review
            lp_result = await session.execute(
                select(LandingPage).where(LandingPage.ugc_job_id == job_id)
            )
            for lp_row in lp_result.scalars().all():
                lp_row.lp_hero_image_path = frame_path
                lp_row.lp_review_locked = False
            await session.commit()
        except Exception as e:
            logger.warning(f"Frame extraction failed for job {job_id}: {e}")

    # Enqueue next stage task
    if next_task_name:
        import app.ugc_tasks as ugc_tasks_module
        getattr(ugc_tasks_module, next_task_name).delay(job_id)

    resp = templates.TemplateResponse(
        request=request,
        name="partials/ugc_stage_controls.html",
        context={"job": job, "review_states": _REVIEW_STATES},
    )
    if approve_event == "approve_final":
        resp.headers["X-Redirect"] = f"/ui/ugc/{job_id}/complete"
    return resp


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


@router.post("/ugc/{job_id}/retry")
async def ugc_ui_retry(job_id: int, session: AsyncSession = Depends(get_session)):
    """Retry a failed UGC job — resumes from last checkpoint, redirects to review."""
    result = await session.execute(select(UGCJob).where(UGCJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail=f"UGCJob {job_id} not found")
    if job.status != "failed":
        raise HTTPException(status_code=400, detail=f"Cannot retry from '{job.status}'")

    task_name = _determine_resume_task(job)

    try:
        sm = UGCJobStateMachine(model=job, state_field="status", start_value=job.status)
        sm.send("retry")
        job.status = sm.current_state.id
    except TransitionNotAllowed as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    job.error_message = None
    await session.commit()

    import app.ugc_tasks as ugc_tasks_module
    getattr(ugc_tasks_module, task_name).delay(job_id)

    return RedirectResponse(url=f"/ui/ugc/{job_id}/review", status_code=303)


@router.post("/ugc/{job_id}/back-to-images")
async def ugc_back_to_images(job_id: int, session: AsyncSession = Depends(get_session)):
    """Reset a failed job back to image review so user can fix images before retrying."""
    result = await session.execute(select(UGCJob).where(UGCJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail=f"UGCJob {job_id} not found")
    if job.status != "failed":
        raise HTTPException(status_code=400, detail=f"Can only go back from 'failed'")

    # Parse error to determine which stage and scene failed
    error_msg = job.error_message or ""
    if "[broll_shot:" in error_msg:
        job.status = "stage_broll_image_review"
    elif "[aroll_scene:" in error_msg:
        job.status = "stage_aroll_image_review"
    elif job.broll_image_paths:
        job.status = "stage_broll_image_review"
    elif job.aroll_image_paths:
        job.status = "stage_aroll_image_review"
    else:
        job.status = "stage_script_review"

    # Keep error_message so the UI can highlight the failed scene
    # It will be cleared on next successful advance
    await session.commit()

    return RedirectResponse(url=f"/ui/ugc/{job_id}/review", status_code=303)


@router.post("/ugc/{job_id}/reopen")
async def ugc_reopen(job_id: int, session: AsyncSession = Depends(get_session)):
    """Reopen an approved job back to composition review for re-editing."""
    result = await session.execute(select(UGCJob).where(UGCJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail=f"UGCJob {job_id} not found")
    if job.status != "approved":
        raise HTTPException(status_code=400, detail="Can only reopen approved jobs")

    sm = UGCJobStateMachine(model=job, state_field="status", start_value=job.status)
    sm.send("reopen")
    job.status = sm.current_state.id
    job.approved_at = None
    await session.commit()

    return RedirectResponse(url=f"/ui/ugc/{job_id}/review", status_code=303)


@router.post("/ugc/{job_id}/trim-video")
async def ugc_trim_video(request: Request, job_id: int, session: AsyncSession = Depends(get_session)):
    """Remove short segments from the final video at specified timestamps."""
    result = await session.execute(select(UGCJob).where(UGCJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail=f"UGCJob {job_id} not found")
    if job.status != "stage_composition_review":
        raise HTTPException(status_code=400, detail="Can only trim during composition review")
    if not job.final_video_path:
        raise HTTPException(status_code=400, detail="No final video to trim")

    body = await request.json()
    ranges = body.get("ranges", [])  # list of {start, end} dicts
    if not ranges:
        raise HTTPException(status_code=400, detail="No cut regions provided")

    # Sort and merge overlapping ranges
    ranges = sorted(ranges, key=lambda r: r["start"])

    # Run blocking moviepy work in a thread
    import asyncio
    from uuid import uuid4

    src_path = job.final_video_path
    out_path = f"output/review/ugc_ad_{job_id}_trimmed_{uuid4().hex[:8]}.mp4"

    def _do_trim():
        from moviepy import VideoFileClip, concatenate_videoclips

        clip = VideoFileClip(src_path)
        duration = clip.duration

        # Build list of segments to KEEP (gaps between cut ranges)
        keep_segments = []
        cursor = 0.0
        for r in ranges:
            cut_start = max(0.0, min(r["start"], duration))
            cut_end = max(0.0, min(r["end"], duration))
            if cut_start > cursor:
                keep_segments.append((cursor, cut_start))
            cursor = max(cursor, cut_end)
        if cursor < duration:
            keep_segments.append((cursor, duration))

        if not keep_segments:
            clip.close()
            raise ValueError("All content would be removed")

        # Extract subclips and concatenate
        subclips = [clip.subclipped(s, e) for s, e in keep_segments]
        final = concatenate_videoclips(subclips)
        final.write_videofile(out_path, codec="libx264", audio_codec="aac",
                              fps=clip.fps, logger=None)
        for sc in subclips:
            sc.close()
        final.close()
        clip.close()

    try:
        await asyncio.to_thread(_do_trim)
    except Exception as exc:
        logger.error(f"Trim failed for job {job_id}: {exc}")
        raise HTTPException(status_code=500, detail=f"Trim failed: {exc}")

    # Push current version onto trim history stack for multi-undo
    from sqlalchemy.orm.attributes import flag_modified
    history = job.trim_history or []
    history.append(job.final_video_path)
    job.trim_history = history
    flag_modified(job, "trim_history")
    job.final_video_path = out_path
    await session.commit()
    logger.info(f"UGCJob {job_id} trimmed {len(ranges)} region(s), new path: {out_path}")

    return JSONResponse({"ok": True, "video_path": "/" + out_path})


@router.post("/ugc/{job_id}/undo-trim")
async def ugc_undo_trim(job_id: int, session: AsyncSession = Depends(get_session)):
    """Restore the previous video version before the last trim."""
    result = await session.execute(select(UGCJob).where(UGCJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail=f"UGCJob {job_id} not found")
    if job.status != "stage_composition_review":
        raise HTTPException(status_code=400, detail="Can only undo trim during composition review")

    history = job.trim_history or []
    if not history:
        raise HTTPException(status_code=400, detail="No previous version to restore")

    # Pop the most recent version from the stack
    from sqlalchemy.orm.attributes import flag_modified
    job.final_video_path = history.pop()
    job.trim_history = history if history else None
    flag_modified(job, "trim_history")
    await session.commit()
    logger.info(f"UGCJob {job_id} undo trim, restored: {job.final_video_path}")

    return JSONResponse({
        "ok": True,
        "video_path": "/" + job.final_video_path,
        "has_previous": len(history) > 0,
    })


# Editable analysis fields (column name -> expected type)
_ANALYSIS_FIELDS = {
    "analysis_category": str,
    "analysis_ugc_style": str,
    "analysis_emotional_tone": str,
    "analysis_target_audience": str,
    "analysis_key_features": list,
    "analysis_visual_keywords": list,
}


@router.post("/ugc/{job_id}/update-analysis")
async def ugc_update_analysis(request: Request, job_id: int, session: AsyncSession = Depends(get_session)):
    """Save manually edited analysis fields."""
    result = await session.execute(select(UGCJob).where(UGCJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail=f"UGCJob {job_id} not found")
    if job.status not in _REVIEW_STATES:
        raise HTTPException(status_code=400, detail="Can only edit during review stages")

    form = await request.form()
    for field, expected_type in _ANALYSIS_FIELDS.items():
        raw = form.get(field)
        if raw is None:
            continue
        if expected_type is list:
            # Newline-separated text → list of non-empty strings
            setattr(job, field, [s.strip() for s in raw.split("\n") if s.strip()])
        else:
            setattr(job, field, raw.strip())

    await session.commit()
    return RedirectResponse(url=f"/ui/ugc/{job_id}/review?tab=stage_analysis_review", status_code=303)


@router.post("/ugc/{job_id}/toggle-broll-creator")
async def ugc_toggle_broll_creator(job_id: int, enabled: bool = Form(...), session: AsyncSession = Depends(get_session)):
    """Toggle broll_include_creator flag on a UGC job."""
    result = await session.execute(select(UGCJob).where(UGCJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail=f"UGCJob {job_id} not found")
    job.broll_include_creator = enabled
    await session.commit()
    return JSONResponse({"ok": True, "broll_include_creator": enabled})


@router.post("/ugc/{job_id}/update-script")
async def ugc_update_script(request: Request, job_id: int, session: AsyncSession = Depends(get_session)):
    """Save manually edited script fields."""
    result = await session.execute(select(UGCJob).where(UGCJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail=f"UGCJob {job_id} not found")
    if job.status not in _REVIEW_STATES:
        raise HTTPException(status_code=400, detail="Can only edit during review stages")

    form = await request.form()

    # Snapshot old section values for change detection
    old_script = dict(job.master_script or {})

    # Update master_script fields (exclude full_script — derived server-side)
    script = dict(job.master_script or {})
    for key in ("creator_persona", "voice_direction", "hook", "problem", "proof", "cta"):
        val = form.get(f"script_{key}")
        if val is not None:
            script[key] = val.strip()

    # Recompute full_script from sections (authoritative source)
    parts = [script.get(k, "").strip() for k in ("hook", "problem", "proof", "cta")]
    script["full_script"] = "\n\n".join(p for p in parts if p)
    job.master_script = script

    # Check if any section field changed
    section_changed = any(
        script.get(k, "") != old_script.get(k, "")
        for k in ("hook", "problem", "proof", "cta")
    )

    # Update aroll_scenes (visual fields only — script_text is derived)
    scenes = list(job.aroll_scenes or [])
    for i, scene in enumerate(scenes):
        for key in ("visual_prompt", "voice_direction", "camera_angle"):
            val = form.get(f"aroll_{i}_{key}")
            if val is not None:
                scene[key] = val.strip()
    job.aroll_scenes = scenes

    # Update broll_shots
    shots = list(job.broll_shots or [])
    for i, shot in enumerate(shots):
        for key in ("image_prompt", "animation_prompt"):
            val = form.get(f"broll_{i}_{key}")
            if val is not None:
                shot[key] = val.strip()
    job.broll_shots = shots

    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(job, "master_script")
    flag_modified(job, "aroll_scenes")
    flag_modified(job, "broll_shots")

    await session.commit()

    # Re-split scene script_text in background if sections changed
    if section_changed and scenes:
        import app.ugc_tasks as ugc_tasks_module
        ugc_tasks_module.ugc_resplit_scenes.delay(job_id)

    return RedirectResponse(url=f"/ui/ugc/{job_id}/review?tab=stage_script_review", status_code=303)


@router.post("/ugc/{job_id}/upload-hero-image")
async def ugc_upload_hero_image(
    job_id: int,
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
):
    """Upload an external image as the current hero image."""
    result = await session.execute(select(UGCJob).where(UGCJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail=f"UGCJob {job_id} not found")
    if job.status not in _REVIEW_STATES:
        raise HTTPException(status_code=400, detail="Can only upload during review stages")

    upload_dir = Path("output") / "ugc_uploads" / str(job_id)
    upload_dir.mkdir(parents=True, exist_ok=True)
    orig = file.filename or "image.png"
    stem = Path(orig).stem
    suffix = Path(orig).suffix or ".png"
    filename = f"hero_{stem}_{uuid4().hex[:6]}{suffix}"
    dest = upload_dir / filename
    content = await file.read()
    dest.write_bytes(content)

    # Push current hero to history, set uploaded as current
    history = list(job.hero_image_history or [])
    if job.hero_image_path:
        history.insert(0, job.hero_image_path)
    job.hero_image_history = history
    job.hero_image_path = str(dest)
    await session.commit()

    return RedirectResponse(url=f"/ui/ugc/{job_id}/review?tab=stage_analysis_review", status_code=303)


@router.post("/ugc/{job_id}/upload-aroll-image")
async def ugc_upload_aroll_image(
    job_id: int,
    file: UploadFile = File(...),
    scene_index: int = Form(0),
    session: AsyncSession = Depends(get_session),
):
    """Upload a custom creator image for A-Roll."""
    result = await session.execute(select(UGCJob).where(UGCJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail=f"UGCJob {job_id} not found")
    if job.status not in _REVIEW_STATES:
        raise HTTPException(status_code=400, detail="Can only upload during review stages")

    paths = list(job.aroll_image_paths or [])
    if scene_index < 0 or scene_index >= max(len(paths), 1):
        raise HTTPException(status_code=400, detail="Invalid scene index")

    upload_dir = Path("output") / "ugc_uploads" / str(job_id)
    upload_dir.mkdir(parents=True, exist_ok=True)
    orig = file.filename or "image.png"
    stem = Path(orig).stem
    suffix = Path(orig).suffix or ".png"
    filename = f"aroll_{scene_index}_{stem}_{uuid4().hex[:6]}{suffix}"
    dest = upload_dir / filename
    content = await file.read()
    dest.write_bytes(content)

    # Push current image to history, set uploaded as current
    history = list(job.aroll_image_history or [])
    while len(history) <= scene_index:
        history.append([])
    if scene_index < len(paths) and paths[scene_index]:
        history[scene_index].insert(0, paths[scene_index])
    job.aroll_image_history = history

    while len(paths) <= scene_index:
        paths.append("")
    paths[scene_index] = str(dest)
    job.aroll_image_paths = paths

    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(job, "aroll_image_paths")
    flag_modified(job, "aroll_image_history")
    await session.commit()

    return RedirectResponse(url=f"/ui/ugc/{job_id}/review?tab=stage_aroll_image_review", status_code=303)


@router.post("/ugc/{job_id}/upload-broll-image")
async def ugc_upload_broll_image(
    job_id: int,
    file: UploadFile = File(...),
    shot_index: int = Form(0),
    session: AsyncSession = Depends(get_session),
):
    """Upload an external image to replace a B-Roll shot image."""
    result = await session.execute(select(UGCJob).where(UGCJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail=f"UGCJob {job_id} not found")
    if job.status not in _REVIEW_STATES:
        raise HTTPException(status_code=400, detail="Can only upload during review stages")

    paths = list(job.broll_image_paths or [])
    if shot_index < 0 or shot_index >= len(paths):
        raise HTTPException(status_code=400, detail=f"Invalid shot index {shot_index}")

    upload_dir = Path("output") / "ugc_uploads" / str(job_id)
    upload_dir.mkdir(parents=True, exist_ok=True)
    orig = file.filename or "image.png"
    suffix = Path(orig).suffix or ".png"
    filename = f"broll_{shot_index}_{uuid4().hex[:6]}{suffix}"
    dest = upload_dir / filename
    content = await file.read()
    dest.write_bytes(content)

    paths[shot_index] = str(dest)
    job.broll_image_paths = paths
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(job, "broll_image_paths")
    await session.commit()

    return RedirectResponse(
        url=f"/ui/ugc/{job_id}/review?tab=stage_broll_image_review", status_code=303
    )


@router.post("/ugc/{job_id}/upload-video")
async def ugc_upload_video(
    job_id: int,
    file: UploadFile = File(...),
    scene_type: str = Form(...),
    clip_index: int = Form(0),
    session: AsyncSession = Depends(get_session),
):
    """Upload a video file to a specific A-Roll or B-Roll clip slot."""
    result = await session.execute(select(UGCJob).where(UGCJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail=f"UGCJob {job_id} not found")
    if job.status not in _REVIEW_STATES:
        raise HTTPException(status_code=400, detail="Can only upload during review stages")

    col_map = {"aroll": "aroll_paths", "broll": "broll_paths"}
    col = col_map.get(scene_type)
    if not col:
        raise HTTPException(status_code=400, detail=f"Invalid scene_type '{scene_type}'")

    paths = list(getattr(job, col) or [])
    if clip_index < 0 or clip_index >= len(paths):
        raise HTTPException(status_code=400, detail=f"Invalid clip_index {clip_index}")

    upload_dir = Path("output") / "ugc_uploads" / str(job_id)
    upload_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(file.filename or "video.mp4").suffix or ".mp4"
    filename = f"{scene_type}_video_{clip_index}_{uuid4().hex[:6]}{suffix}"
    dest = upload_dir / filename
    content = await file.read()
    dest.write_bytes(content)

    # Normalize VFR / non-mp4 uploads (iPhone .MOV fix)
    from app.services.ugc_pipeline.ugc_compositor import normalize_video
    normalized = normalize_video(str(dest))

    paths[clip_index] = normalized
    setattr(job, col, paths)
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(job, col)
    await session.commit()

    return JSONResponse({"path": str(dest), "index": clip_index})


@router.post("/ugc/{job_id}/upload-sketch")
async def ugc_upload_sketch(
    job_id: int,
    sketch: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
):
    """Upload a hand-drawn sketch to guide hero image generation."""
    result = await session.execute(select(UGCJob).where(UGCJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail=f"UGCJob {job_id} not found")
    if job.status not in _REVIEW_STATES:
        raise HTTPException(status_code=400, detail="Can only upload during review stages")

    upload_dir = Path("output") / "ugc_uploads" / str(job_id)
    upload_dir.mkdir(parents=True, exist_ok=True)

    # Server-side limit: max 1 sketch
    existing = list(upload_dir.glob("sketch_*"))
    if len(existing) >= 1:
        return JSONResponse({"status": "error", "detail": "Max 1 sketch"})

    orig = sketch.filename or "drawing.png"
    stem = Path(orig).stem
    suffix = Path(orig).suffix or ".png"
    filename = f"sketch_{stem}_{uuid4().hex[:6]}{suffix}"
    dest = upload_dir / filename
    content = await sketch.read()
    dest.write_bytes(content)

    job.hero_sketch_path = str(dest)
    await session.commit()

    return JSONResponse({"status": "ok", "path": str(dest)})


@router.post("/ugc/{job_id}/remove-sketch")
async def ugc_remove_sketch(
    request: Request,
    job_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Remove a specific sketch file, or clear hero_sketch_path if no path given."""
    result = await session.execute(select(UGCJob).where(UGCJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail=f"UGCJob {job_id} not found")

    form = await request.form()
    path = form.get("path", "")

    # Delete file from disk if it's inside this job's upload dir
    if path:
        file_path = Path(path)
        allowed_dir = Path("output") / "ugc_uploads" / str(job_id)
        if file_path.exists() and allowed_dir in file_path.parents:
            file_path.unlink()

    # Clear DB field if it pointed to the deleted file or no sketches remain
    sketch_dir = Path("output") / "ugc_uploads" / str(job_id)
    remaining = list(sketch_dir.glob("sketch_*")) if sketch_dir.is_dir() else []
    if not remaining:
        job.hero_sketch_path = None
    elif job.hero_sketch_path == path and remaining:
        job.hero_sketch_path = str(remaining[-1])
    await session.commit()

    return JSONResponse({"status": "ok"})


@router.post("/ugc/{job_id}/upload-ref-photo")
async def ugc_upload_ref_photo(
    job_id: int,
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
):
    """Upload a product reference photo for subject-referenced hero generation."""
    result = await session.execute(select(UGCJob).where(UGCJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail=f"UGCJob {job_id} not found")
    if job.status not in _REVIEW_STATES:
        raise HTTPException(status_code=400, detail="Can only upload during review stages")

    upload_dir = Path("output") / "ugc_uploads" / str(job_id)
    upload_dir.mkdir(parents=True, exist_ok=True)

    # Server-side limit: max 2 reference photos
    existing = list(upload_dir.glob("refphoto_*"))
    if len(existing) >= 2:
        return JSONResponse({"status": "error", "detail": "Max 2 reference photos"})

    orig = file.filename or "photo.png"
    stem = Path(orig).stem
    suffix = Path(orig).suffix or ".png"
    filename = f"refphoto_{stem}_{uuid4().hex[:6]}{suffix}"
    dest = upload_dir / filename
    content = await file.read()
    dest.write_bytes(content)

    # Auto-crop to 1:1 (square) for optimal subject reference
    cropped = False
    orig_w, orig_h = 0, 0
    try:
        img = Image.open(dest)
        orig_w, orig_h = img.size
        ratio = max(orig_w, orig_h) / max(min(orig_w, orig_h), 1)
        if ratio > 1.02:  # not square (>2% difference)
            side = min(orig_w, orig_h)
            left = (orig_w - side) // 2
            top = (orig_h - side) // 2
            img = img.crop((left, top, left + side, top + side))
            img.save(dest)
            cropped = True
    except Exception:
        logger.warning("Could not auto-crop ref photo %s", dest)

    resp = {"status": "ok", "path": str(dest), "cropped": cropped}
    if cropped:
        resp["orig_width"] = orig_w
        resp["orig_height"] = orig_h
    return JSONResponse(resp)


@router.post("/ugc/{job_id}/remove-ref-photo")
async def ugc_remove_ref_photo(
    request: Request,
    job_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Remove a reference photo file."""
    result = await session.execute(select(UGCJob).where(UGCJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail=f"UGCJob {job_id} not found")

    form = await request.form()
    path = form.get("path", "")

    if path:
        file_path = Path(path)
        allowed_dir = Path("output") / "ugc_uploads" / str(job_id)
        if file_path.exists() and allowed_dir in file_path.parents:
            file_path.unlink()

    return JSONResponse({"status": "ok"})


@router.post("/ugc/{job_id}/restore-hero-image")
async def ugc_restore_hero_image(
    request: Request,
    job_id: int,
    path: str = Form(...),
    session: AsyncSession = Depends(get_session),
):
    """Restore a previous hero image from history. Swaps current into history."""
    result = await session.execute(select(UGCJob).where(UGCJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail=f"UGCJob {job_id} not found")
    if job.status not in _REVIEW_STATES:
        raise HTTPException(status_code=400, detail="Can only restore during review stages")

    history = list(job.hero_image_history or [])
    if path not in history:
        raise HTTPException(status_code=400, detail="Path not in history")

    # Remove selected from history, push current into history, set selected as current
    history.remove(path)
    if job.hero_image_path:
        history.insert(0, job.hero_image_path)
    job.hero_image_history = history
    job.hero_image_path = path
    await session.commit()

    return RedirectResponse(url=f"/ui/ugc/{job_id}/review?tab=stage_analysis_review", status_code=303)


@router.post("/ugc/{job_id}/regen-item")
async def ugc_regen_item(
    request: Request,
    job_id: int,
    item: str = Form(...),
    session: AsyncSession = Depends(get_session),
):
    """Regenerate a single analysis field or hero image via Celery.

    Text fields: re-runs AI analysis, updates ONLY the requested field.
    Hero image: generates new image using current saved text values.
    Returns JSON so the frontend can poll for completion.
    """
    result = await session.execute(select(UGCJob).where(UGCJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail=f"UGCJob {job_id} not found")
    if job.status not in _REVIEW_STATES:
        raise HTTPException(status_code=400, detail="Can only regenerate during review stages")

    import app.ugc_tasks as ugc_tasks_module

    if item == "hero_image":
        import json as _json
        form_data = await request.form()
        # Parse reference photo paths (product photos for subject reference)
        ref_paths = None
        ref_paths_raw = form_data.get("reference_paths")
        if ref_paths_raw:
            try:
                ref_paths = _json.loads(ref_paths_raw)
                if not isinstance(ref_paths, list) or not ref_paths:
                    ref_paths = None
            except (ValueError, TypeError):
                ref_paths = None
        # Parse sketch paths (hand-drawn for composition control)
        sketch_paths = None
        sketch_paths_raw = form_data.get("sketch_paths")
        if sketch_paths_raw:
            try:
                sketch_paths = _json.loads(sketch_paths_raw)
                if not isinstance(sketch_paths, list) or not sketch_paths:
                    sketch_paths = None
            except (ValueError, TypeError):
                sketch_paths = None
        task = ugc_tasks_module.ugc_regen_hero_image.delay(
            job_id, reference_paths=ref_paths, sketch_paths=sketch_paths
        )
        old_value = job.hero_image_path or ""
    elif item in _ANALYSIS_FIELDS:
        task = ugc_tasks_module.ugc_regen_analysis_field.delay(job_id, item)
        raw = getattr(job, item, None)
        old_value = "\n".join(raw) if isinstance(raw, list) else (raw or "")
    else:
        raise HTTPException(status_code=400, detail=f"Unknown item: {item}")

    return {"status": "queued", "item": item, "old_value": old_value, "task_id": task.id}


@router.get("/ugc/task-status/{task_id}")
async def ugc_task_status(task_id: str):
    """Check Celery task status for polling regen progress."""
    from app.worker import celery_app
    result = celery_app.AsyncResult(task_id)
    state = result.state  # PENDING, STARTED, SUCCESS, FAILURE, RETRY
    error = str(result.result) if state == "FAILURE" else None
    return {"state": state, "error": error}


@router.get("/ugc/{job_id}/field-value")
async def ugc_field_value(
    job_id: int,
    item: str = Query(...),
    index: Optional[int] = Query(None),
    session: AsyncSession = Depends(get_session),
):
    """Return current value of a field — used for polling after regen.

    For array fields (aroll_image_paths, broll_image_paths), pass index to get one element.
    """
    result = await session.execute(select(UGCJob).where(UGCJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail=f"UGCJob {job_id} not found")

    if item == "hero_image":
        value = job.hero_image_path or ""
    elif item == "aroll_image_paths":
        paths = job.aroll_image_paths or []
        if index is not None and 0 <= index < len(paths):
            value = paths[index]
        else:
            value = json.dumps(paths)
    elif item == "broll_image_paths":
        paths = job.broll_image_paths or []
        if index is not None and 0 <= index < len(paths):
            value = paths[index]
        else:
            value = json.dumps(paths)
    elif item in _ANALYSIS_FIELDS:
        raw = getattr(job, item, None)
        value = "\n".join(raw) if isinstance(raw, list) else (raw or "")
    else:
        raise HTTPException(status_code=400, detail=f"Unknown item: {item}")

    return {"item": item, "value": value}


@router.post("/ugc/{job_id}/regen-scene-image")
async def ugc_regen_scene_image(
    request: Request,
    job_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Regenerate a single scene/shot image via Celery.

    Accepts form fields: scene_type (aroll/broll), scene_index (int).
    Returns old value for polling.
    """
    result = await session.execute(select(UGCJob).where(UGCJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail=f"UGCJob {job_id} not found")
    if job.status not in _REVIEW_STATES:
        raise HTTPException(status_code=400, detail="Can only regenerate during review stages")

    form = await request.form()
    scene_type = form.get("scene_type", "")
    updated_prompt = form.get("updated_prompt", "").strip()
    try:
        scene_index = int(form.get("scene_index", -1))
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid scene_index")

    # Save updated prompt so the Celery task picks it up
    if updated_prompt:
        if scene_type == "aroll":
            scenes = list(job.aroll_scenes or [])
            if 0 <= scene_index < len(scenes):
                scenes[scene_index] = {**scenes[scene_index], "visual_prompt": updated_prompt}
                job.aroll_scenes = scenes
        elif scene_type == "broll":
            shots = list(job.broll_shots or [])
            if 0 <= scene_index < len(shots):
                shots[scene_index] = {**shots[scene_index], "image_prompt": updated_prompt}
                job.broll_shots = shots
        await session.commit()

    import app.ugc_tasks as ugc_tasks_module

    if scene_type == "aroll":
        paths = job.aroll_image_paths or []
        old_value = paths[scene_index] if 0 <= scene_index < len(paths) else ""
        task = ugc_tasks_module.ugc_regen_aroll_scene_image.delay(job_id, scene_index)
    elif scene_type == "broll":
        paths = job.broll_image_paths or []
        old_value = paths[scene_index] if 0 <= scene_index < len(paths) else ""
        task = ugc_tasks_module.ugc_regen_broll_shot_image.delay(job_id, scene_index)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown scene_type: {scene_type}")

    return {"status": "queued", "scene_type": scene_type, "scene_index": scene_index, "old_value": old_value, "task_id": task.id}


@router.post("/ugc/{job_id}/regen-all-scene-images")
async def ugc_regen_all_scene_images(
    request: Request,
    job_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Regenerate all A-Roll scene images together for character consistency."""
    result = await session.execute(select(UGCJob).where(UGCJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail=f"UGCJob {job_id} not found")
    if job.status not in _REVIEW_STATES:
        raise HTTPException(status_code=400, detail="Can only regenerate during review stages")

    form = await request.form()
    scene_type = form.get("scene_type", "aroll")
    if scene_type != "aroll":
        raise HTTPException(status_code=400, detail="Only aroll scene type is supported for regenerate-all")

    import app.ugc_tasks as ugc_tasks_module
    task = ugc_tasks_module.ugc_regen_all_aroll_images.delay(job_id)
    scene_count = len(job.aroll_image_paths or [])

    return {"status": "queued", "task_id": task.id, "scene_count": scene_count}


@router.post("/ugc/{job_id}/select-history-image")
async def ugc_select_history_image(
    request: Request,
    job_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Select a previous image from history for a scene/shot."""
    result = await session.execute(select(UGCJob).where(UGCJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail=f"UGCJob {job_id} not found")
    if job.status not in _REVIEW_STATES:
        raise HTTPException(status_code=400, detail="Can only change images during review stages")

    form = await request.form()
    scene_type = form.get("scene_type", "aroll")
    scene_index = int(form.get("scene_index", 0))
    history_index = int(form.get("history_index", 0))

    from sqlalchemy.orm.attributes import flag_modified

    if scene_type == "aroll":
        history = list(job.aroll_image_history or [])
        paths = list(job.aroll_image_paths or [])
        if scene_index >= len(history) or history_index >= len(history[scene_index]):
            raise HTTPException(status_code=400, detail="Invalid history index")
        # Swap: current -> top of history, selected -> current
        selected = history[scene_index].pop(history_index)
        if scene_index < len(paths) and paths[scene_index]:
            history[scene_index].insert(0, paths[scene_index])
        paths[scene_index] = selected
        job.aroll_image_paths = paths
        job.aroll_image_history = history
        flag_modified(job, "aroll_image_paths")
        flag_modified(job, "aroll_image_history")
    else:
        history = list(job.broll_image_history or [])
        paths = list(job.broll_image_paths or [])
        if scene_index >= len(history) or history_index >= len(history[scene_index]):
            raise HTTPException(status_code=400, detail="Invalid history index")
        selected = history[scene_index].pop(history_index)
        if scene_index < len(paths) and paths[scene_index]:
            history[scene_index].insert(0, paths[scene_index])
        paths[scene_index] = selected
        job.broll_image_paths = paths
        job.broll_image_history = history
        flag_modified(job, "broll_image_paths")
        flag_modified(job, "broll_image_history")

    await session.commit()
    return {"status": "ok", "selected": selected}


@router.post("/ugc/{job_id}/select-history-video")
async def ugc_select_history_video(
    request: Request,
    job_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Select a previous video from history for a clip slot."""
    result = await session.execute(select(UGCJob).where(UGCJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail=f"UGCJob {job_id} not found")
    if job.status not in _REVIEW_STATES:
        raise HTTPException(status_code=400, detail="Can only change videos during review stages")

    form = await request.form()
    scene_type = form.get("scene_type", "aroll")
    clip_index = int(form.get("clip_index", 0))
    history_index = int(form.get("history_index", 0))

    from sqlalchemy.orm.attributes import flag_modified

    if scene_type == "aroll":
        history = list(job.aroll_video_history or [])
        paths = list(job.aroll_paths or [])
        hist_col, paths_col = "aroll_video_history", "aroll_paths"
    else:
        history = list(job.broll_video_history or [])
        paths = list(job.broll_paths or [])
        hist_col, paths_col = "broll_video_history", "broll_paths"

    if clip_index >= len(history) or history_index >= len(history[clip_index]):
        raise HTTPException(status_code=400, detail="Invalid history index")

    # Swap: current -> top of history, selected -> current
    selected = history[clip_index].pop(history_index)
    if clip_index < len(paths) and paths[clip_index]:
        history[clip_index].insert(0, paths[clip_index])
    paths[clip_index] = selected

    setattr(job, paths_col, paths)
    setattr(job, hist_col, history)
    flag_modified(job, paths_col)
    flag_modified(job, hist_col)

    await session.commit()
    return {"status": "ok", "selected": selected}


@router.post("/ugc/{job_id}/regen-all-scene-videos")
async def ugc_regen_all_scene_videos(
    request: Request,
    job_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Regenerate all A-Roll video clips from their scene images."""
    result = await session.execute(select(UGCJob).where(UGCJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail=f"UGCJob {job_id} not found")
    if job.status not in _REVIEW_STATES:
        raise HTTPException(status_code=400, detail="Can only regenerate during review stages")

    import app.ugc_tasks as ugc_tasks_module
    task = ugc_tasks_module.ugc_regen_all_aroll_videos.delay(job_id)
    scene_count = len(job.aroll_paths or [])

    return {"status": "queued", "task_id": task.id, "scene_count": scene_count}


@router.post("/ugc/{job_id}/regen-script-field")
async def ugc_regen_script_field(
    request: Request,
    job_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Regenerate a single script field/scene/shot via Celery."""
    result = await session.execute(select(UGCJob).where(UGCJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail=f"UGCJob {job_id} not found")
    if job.status not in _REVIEW_STATES:
        raise HTTPException(status_code=400, detail="Can only regenerate during review stages")

    form = await request.form()
    field_type = form.get("field_type", "")
    try:
        field_index = int(form.get("field_index", 0))
    except (ValueError, TypeError):
        field_index = 0

    valid_types = [
        "master_hook", "master_problem", "master_proof", "master_cta",
        "master_full_script", "aroll_scene", "broll_shot",
    ]
    if field_type not in valid_types:
        raise HTTPException(status_code=400, detail=f"Invalid field_type: {field_type}")

    import app.ugc_tasks as ugc_tasks_module
    task = ugc_tasks_module.ugc_regen_script_field.delay(job_id, field_type, field_index)
    return {"status": "queued", "task_id": task.id, "field_type": field_type, "field_index": field_index}


@router.post("/ugc/{job_id}/regen-all-script")
async def ugc_regen_all_script(
    request: Request,
    job_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Regenerate the entire script via Celery."""
    result = await session.execute(select(UGCJob).where(UGCJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail=f"UGCJob {job_id} not found")
    if job.status not in _REVIEW_STATES:
        raise HTTPException(status_code=400, detail="Can only regenerate during review stages")

    import app.ugc_tasks as ugc_tasks_module
    task = ugc_tasks_module.ugc_regen_script.delay(job_id)
    return {"status": "queued", "task_id": task.id}


@router.post("/ugc/{job_id}/regen-all-broll-images")
async def ugc_regen_all_broll_images(
    request: Request,
    job_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Regenerate all B-Roll shot images via Celery."""
    result = await session.execute(select(UGCJob).where(UGCJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail=f"UGCJob {job_id} not found")
    if job.status not in _REVIEW_STATES:
        raise HTTPException(status_code=400, detail="Can only regenerate during review stages")

    import app.ugc_tasks as ugc_tasks_module
    task = ugc_tasks_module.ugc_regen_all_broll_images.delay(job_id)
    shot_count = len(job.broll_image_paths or [])
    return {"status": "queued", "task_id": task.id, "shot_count": shot_count}


@router.post("/ugc/{job_id}/regen-all-broll-videos")
async def ugc_regen_all_broll_videos(
    request: Request,
    job_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Regenerate all B-Roll video clips via Celery."""
    result = await session.execute(select(UGCJob).where(UGCJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail=f"UGCJob {job_id} not found")
    if job.status not in _REVIEW_STATES:
        raise HTTPException(status_code=400, detail="Can only regenerate during review stages")

    import app.ugc_tasks as ugc_tasks_module
    task = ugc_tasks_module.ugc_regen_all_broll_videos.delay(job_id)
    shot_count = len(job.broll_paths or [])
    return {"status": "queued", "task_id": task.id, "shot_count": shot_count}


@router.post("/ugc/{job_id}/regen-broll-video")
async def ugc_regen_broll_video(
    request: Request,
    job_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Regenerate a single B-Roll video clip via Celery."""
    result = await session.execute(select(UGCJob).where(UGCJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail=f"UGCJob {job_id} not found")
    if job.status not in _REVIEW_STATES:
        raise HTTPException(status_code=400, detail="Can only regenerate during review stages")

    form = await request.form()
    try:
        shot_index = int(form.get("shot_index", -1))
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid shot_index")

    import app.ugc_tasks as ugc_tasks_module
    task = ugc_tasks_module.ugc_regen_broll_shot_video.delay(job_id, shot_index)
    return {"status": "queued", "shot_index": shot_index, "task_id": task.id}


@router.post("/ugc/{job_id}/regen-scene-video")
async def ugc_regen_scene_video(
    request: Request,
    job_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Regenerate a single A-Roll video clip via Celery.

    Accepts form fields: scene_type (aroll), scene_index (int), optional updated_prompt.
    """
    result = await session.execute(select(UGCJob).where(UGCJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail=f"UGCJob {job_id} not found")
    if job.status not in _REVIEW_STATES:
        raise HTTPException(status_code=400, detail="Can only regenerate during review stages")

    form = await request.form()
    scene_type = form.get("scene_type", "")
    updated_prompt = form.get("updated_prompt", "").strip()
    try:
        scene_index = int(form.get("scene_index", -1))
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid scene_index")

    if scene_type != "aroll":
        raise HTTPException(status_code=400, detail="Only aroll video regeneration is supported")

    # Save updated prompt so the Celery task picks it up
    if updated_prompt:
        scenes = list(job.aroll_scenes or [])
        if 0 <= scene_index < len(scenes):
            scenes[scene_index] = {**scenes[scene_index], "visual_prompt": updated_prompt}
            job.aroll_scenes = scenes
            await session.commit()

    import app.ugc_tasks as ugc_tasks_module

    paths = job.aroll_paths or []
    old_value = paths[scene_index] if 0 <= scene_index < len(paths) else ""
    task = ugc_tasks_module.ugc_regen_aroll_scene_video.delay(job_id, scene_index)

    return {"status": "queued", "scene_type": scene_type, "scene_index": scene_index, "old_value": old_value, "task_id": task.id}


async def _run_generation_for_ugc(run_id: str, job: UGCJob, lp_id: int):
    """Background task: run LP generation for a UGC job and update the linked LandingPage row."""
    try:
        from app.services.landing_page import LandingPageRequest, generate_landing_page  # noqa: PLC0415
        from app.schemas import LandingPageRequest as LPRequest  # noqa: PLC0415

        lp_request = LPRequest(
            product_idea=f"{job.product_name}: {job.description}",
            target_audience=job.analysis_target_audience or "general",
            hero_image_path=job.hero_image_path,
        )
        result = await generate_landing_page(lp_request, use_mock=job.use_mock)

        async with async_session_factory() as session:
            lp_result = await session.execute(select(LandingPage).where(LandingPage.id == lp_id))
            lp = lp_result.scalar_one_or_none()
            if lp:
                lp.html_path = result.html_path
                lp.sections = result.sections
                lp.lp_copy = result.lp_copy
                lp.status = "generated"
                await session.commit()
    except Exception as e:
        logger.error(f"_run_generation_for_ugc run_id={run_id} failed: {e}")
        # Mark LP as failed so the review page shows the error
        try:
            async with async_session_factory() as session:
                lp_result = await session.execute(select(LandingPage).where(LandingPage.id == lp_id))
                lp = lp_result.scalar_one_or_none()
                if lp:
                    lp.status = "failed"
                    await session.commit()
        except Exception:
            logger.error(f"Failed to mark LP {lp_id} as failed")


@router.post("/ugc/{job_id}/generate-lp")
async def ugc_generate_lp(job_id: int, session: AsyncSession = Depends(get_session)):
    """Create a LandingPage linked to an approved UGC job and start generation."""
    result = await session.execute(select(UGCJob).where(UGCJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail=f"UGCJob {job_id} not found")
    if job.status != "approved":
        raise HTTPException(status_code=400, detail="Job must be approved before generating an LP")

    # Create LP row (locked initially, will be unlocked after frame extraction)
    run_id = uuid4().hex[:8]
    lp = LandingPage(
        run_id=run_id,
        product_idea=job.product_name,
        ugc_job_id=job.id,
        status="pending",
        lp_review_locked=True,
    )
    session.add(lp)
    await session.flush()  # get lp.id before commit
    lp_id = lp.id

    # Extract hero frame immediately (job is already approved)
    if job.final_video_path:
        from app.services.video_compositor.thumbnail import generate_thumbnail
        try:
            frame_path = await asyncio.to_thread(
                generate_thumbnail,
                job.final_video_path,
                2.0,
                "output/lp_frames"
            )
            lp.lp_hero_image_path = frame_path
            lp.lp_review_locked = False
        except Exception as e:
            logger.warning(f"Frame extraction failed for job {job_id}: {e}")

    await session.commit()

    # Start LP generation in background
    asyncio.create_task(_run_generation_for_ugc(run_id, job, lp_id))

    return RedirectResponse(url=f"/ui/lp/{run_id}/review", status_code=303)


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
