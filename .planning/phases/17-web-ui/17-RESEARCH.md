# Phase 17: Web UI - Research

**Researched:** 2026-02-19
**Domain:** FastAPI Jinja2Templates + StaticFiles + SSE + LandingPage DB model
**Confidence:** HIGH

## Summary

Phase 17 adds a browser-based UI on top of the existing FastAPI app. No new frameworks are needed — FastAPI already supports Jinja2Templates and StaticFiles natively via Starlette. The key additions are: (1) a web router serving HTML pages, (2) a background task mechanism so LP generation doesn't timeout in the browser, (3) SSE streaming for real-time progress feedback, (4) an iframe-based LP preview endpoint, and (5) a `LandingPage` DB model to track LP status (generated/deployed/archived).

The project already has `fastapi==0.128.8` (venv shows `0.129.0`), `jinja2==3.1.6`, and all LP generation logic in `app/services/landing_page/`. The web UI is purely a new router + templates layer on top of existing services. No new Python packages are required.

The hardest design question is how to handle LP generation in the browser — `generate_landing_page` is async but takes 10-60 seconds (research + LLM). The browser can't block that long. The answer is: kick off generation as a background task, return a job ID immediately, poll with SSE or fetch for status, then redirect to results.

**Primary recommendation:** Add `app/ui/` package with a Jinja2 web router, mount `app/ui/static/` for CSS/JS, add `LandingPage` model + migration `005`, wire LP generation to background asyncio tasks tracked in-memory (no Celery needed for this UI-scale load), stream progress via SSE.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | 0.128.8 (installed) | Web router with Jinja2 support | Already in use |
| Jinja2 | 3.1.6 (installed) | Server-rendered HTML templates | Already in use for LP generation |
| Starlette StaticFiles | bundled with FastAPI | Serve CSS/JS/assets | Standard FastAPI pattern |
| SQLAlchemy | 2.0.46 (installed) | LandingPage model for LP status | Already in use for all models |
| Alembic | 1.16.5 (installed) | Migration 005 for landing_pages table | Same pattern as 001-004 |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `asyncio` (stdlib) | bundled | Background LP generation task | When using in-process async tasks |
| `BackgroundTasks` (FastAPI) | bundled | Trigger LP generation without blocking response | For simple single-request background work |
| SSE via StreamingResponse | bundled with starlette | Real-time progress to browser | For generation progress updates |
| `FileResponse` (FastAPI) | bundled | Serve generated LP HTML files | For LP preview endpoint |
| `StaticFiles` + `directory` mount | bundled | Serve output/ LP HTML files | For browsing generated LP directories |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| In-process asyncio background task | Celery task | Celery already exists but adds complexity; asyncio task is simpler for this use case |
| SSE with `StreamingResponse` | WebSocket | SSE is unidirectional (server→client) — sufficient for progress; simpler than WebSocket |
| `BackgroundTasks` (FastAPI built-in) | `asyncio.create_task()` | BackgroundTasks runs after response; create_task runs concurrently — both work, BackgroundTasks is idiomatic |
| Jinja2 server-rendered pages | Full SPA (React/Vue) | PROJECT.md explicitly decided "FastAPI templates (Jinja2): No separate frontend build, stays in Python ecosystem" — SPA is out of scope |
| Serving LP via iframe to same origin | Opening LP in new tab | iframe keeps user in the UI; simpler than new tab but requires CSP header consideration |

**Installation:**
```bash
# No new packages needed — all available in current venv
```

## Architecture Patterns

### Recommended Project Structure
```
app/
├── ui/
│   ├── __init__.py          # Web router package
│   ├── router.py            # Jinja2 web routes (GET /ui/*, POST /ui/*)
│   ├── static/              # CSS, minimal JS for UI
│   │   ├── ui.css           # Admin UI styles
│   │   └── ui.js            # SSE client, form handlers
│   └── templates/           # Jinja2 HTML templates for web UI
│       ├── base.html        # Base layout (nav, footer)
│       ├── index.html       # Dashboard / LP list
│       ├── generate.html    # LP generation form
│       ├── progress.html    # Generation progress page
│       └── preview.html     # LP preview + deploy actions
├── api/
│   └── routes.py            # Existing API routes (unchanged)
└── main.py                  # Mount ui.router + static
```

### Pattern 1: Jinja2Templates Web Router
**What:** Add a new router in `app/ui/router.py` that serves HTML pages using `Jinja2Templates`.
**When to use:** Every browser-facing page (dashboard, form, preview, progress).
**Example:**
```python
# Source: https://fastapi.tiangolo.com/advanced/templates/
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter(prefix="/ui", tags=["web-ui"])
templates = Jinja2Templates(directory="app/ui/templates")

@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    # Fetch LP list from DB
    lps = await get_landing_pages()
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"lps": lps}
    )
```

### Pattern 2: Mount StaticFiles for UI Assets
**What:** Mount `app/ui/static/` at `/ui/static` and `output/` at `/output` for LP preview.
**When to use:** Any static file serving (CSS/JS for the admin UI, generated LP HTML files).
**Example:**
```python
# In app/main.py — add alongside existing include_router
from fastapi.staticfiles import StaticFiles
from app.ui import router as ui_router

app.mount("/ui/static", StaticFiles(directory="app/ui/static"), name="ui-static")
app.mount("/output", StaticFiles(directory="output", html=True), name="output")
app.include_router(ui_router.router)
```
**Critical note:** `html=True` on StaticFiles makes it serve `index.html` automatically for directory paths — not needed here since we want direct file access.

### Pattern 3: Background LP Generation + In-Memory Job Tracking
**What:** POST to `/ui/generate` starts LP generation in background, returns a `job_id`. Browser polls `/ui/generate/{job_id}/status` for progress.
**When to use:** Any endpoint that kicks off a slow task (generation takes 10-60s).
**Example:**
```python
import asyncio
from uuid import uuid4
from typing import Dict

# In-memory job store (process-scoped; fine for single-worker local use)
_jobs: Dict[str, dict] = {}

@router.post("/generate")
async def start_generate(request: Request, form: LPGenerateForm):
    job_id = uuid4().hex[:8]
    _jobs[job_id] = {"status": "running", "progress": 0, "html_path": None, "error": None}

    # Fire and forget — runs concurrently in same event loop
    asyncio.create_task(_run_generation(job_id, form))

    return RedirectResponse(url=f"/ui/generate/{job_id}/progress", status_code=303)


async def _run_generation(job_id: str, form):
    try:
        _jobs[job_id]["progress"] = 10
        result = await generate_landing_page(request_obj, use_mock=form.mock)
        _jobs[job_id]["status"] = "done"
        _jobs[job_id]["html_path"] = result.html_path
    except Exception as e:
        _jobs[job_id]["status"] = "error"
        _jobs[job_id]["error"] = str(e)
```

### Pattern 4: SSE for Generation Progress
**What:** `/ui/generate/{job_id}/events` streams `text/event-stream` data to the browser while generation runs.
**When to use:** Any page that needs real-time progress without polling.
**Example:**
```python
# Source: FastAPI StreamingResponse with SSE format
import asyncio
import json
from fastapi.responses import StreamingResponse

@router.get("/generate/{job_id}/events")
async def generation_events(job_id: str):
    async def event_stream():
        while True:
            job = _jobs.get(job_id)
            if not job:
                yield f"data: {json.dumps({'status': 'not_found'})}\n\n"
                break
            yield f"data: {json.dumps(job)}\n\n"
            if job["status"] in ("done", "error"):
                break
            await asyncio.sleep(1)

    return StreamingResponse(event_stream(), media_type="text/event-stream")
```

**Browser JavaScript (in progress.html template):**
```javascript
const evtSource = new EventSource("/ui/generate/{{ job_id }}/events");
evtSource.onmessage = (event) => {
    const data = JSON.parse(event.data);
    if (data.status === "done") {
        window.location.href = `/ui/preview/{{ job_id }}`;
        evtSource.close();
    } else if (data.status === "error") {
        document.getElementById("error").textContent = data.error;
        evtSource.close();
    }
    document.getElementById("progress").textContent = data.progress + "%";
};
```

### Pattern 5: LP Preview via iframe
**What:** `/ui/preview/{run_id}` serves a page with an `<iframe src="/output/{run_id}/landing-page.html">`.
**When to use:** UI-03 — User can preview generated LP inline before deployment.
**Example:**
```html
<!-- preview.html Jinja2 template -->
<iframe
  src="/output/{{ run_id }}/landing-page.html"
  style="width:100%; height:80vh; border:none;"
  title="LP Preview">
</iframe>
<button onclick="triggerDeploy('{{ run_id }}')">Deploy to Cloudflare</button>
```
**Important:** Both `/output` and the preview iframe are on the same origin (localhost), so no CORS issues. The waitlist form in the LP POSTs to `/waitlist` which already exists — it will work correctly when the LP is served via `/output/`.

### Pattern 6: LandingPage DB Model for LP Status (UI-05)
**What:** Add a `LandingPage` SQLAlchemy model to track LP status (generated, deployed, archived) + metadata (product_idea, html_path, run_id).
**When to use:** Required for UI-05 (view all LPs with status) and Phase 19 (deploy tracking).
**Example:**
```python
# Add to app/models.py
class LandingPage(Base):
    """Generated landing pages with status tracking."""
    __tablename__ = "landing_pages"

    id = Column(Integer, primary_key=True)
    run_id = Column(String(50), nullable=False, unique=True)  # 8-char hex, e.g. "23a06df0"
    product_idea = Column(String(500), nullable=False)
    target_audience = Column(String(500))
    html_path = Column(String(1000))          # Local file path to landing-page.html
    status = Column(String(50), default="generated")  # generated, deployed, archived
    color_scheme_source = Column(String(50))  # extract, research, preset
    sections = Column(JSON)                   # List of section names
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    deployed_at = Column(DateTime(timezone=True), nullable=True)
    deployed_url = Column(String(1000), nullable=True)  # Cloudflare Pages URL (Phase 19)
```

**Migration:** `005_landing_pages_schema.py` following existing `004_waitlist_schema.py` pattern.

### Pattern 7: LP Form Submission (UI-01, UI-02)
**What:** HTML form with `method="POST"` submitting to `/ui/generate`. FastAPI reads form data via `Form(...)`.
**When to use:** No need for fetch()/AJAX on the initial form submit — classic POST+redirect is simpler for a non-JS-heavy admin UI.
**Example:**
```python
from fastapi import Form
from fastapi.responses import RedirectResponse

@router.post("/generate")
async def submit_generate(
    request: Request,
    product_idea: str = Form(...),
    target_audience: str = Form(...),
    use_mock: bool = Form(False),
):
    job_id = uuid4().hex[:8]
    # ...start background task...
    return RedirectResponse(url=f"/ui/generate/{job_id}/progress", status_code=303)
```

### Anti-Patterns to Avoid
- **Blocking the event loop in route handlers:** Never call `generate_landing_page_sync()` directly in a route. It blocks all requests. Use `asyncio.create_task()` or `BackgroundTasks`.
- **Storing job state in a DB for each progress tick:** Write only the final result to DB. Use in-memory `_jobs` dict for transient progress. Writing status to DB every second creates unnecessary I/O.
- **Serving output/ without a prefix:** Mounting StaticFiles at `/` conflicts with all other routes. Mount at `/output`.
- **Using WebSockets when SSE is enough:** SSE (EventSource) is unidirectional and sufficient for progress. WebSocket adds unnecessary complexity.
- **Putting web UI templates in the LP service template directory:** LP templates (`app/services/landing_page/templates/`) are Jinja2 LP section templates, not HTTP page templates. Keep web UI templates in `app/ui/templates/`.
- **Forgetting CSP headers on preview iframe:** When serving the LP HTML via iframe on the same origin, no special CSP is needed. If origins differ (e.g., preview via a CDN URL), add `sandbox` attribute to the iframe for safety.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Template rendering | Custom string concat for HTML | `Jinja2Templates.TemplateResponse()` | Escaping, inheritance, filters built-in |
| Static file serving | Custom file endpoint per asset | `StaticFiles` mount | Range requests, caching headers, ETag automatic |
| LP file serving | Custom endpoint to read + return HTML | `StaticFiles(directory="output")` mount | Handles all file types in output dir |
| Form parsing | Custom body parser | `Form(...)` dependency | FastAPI handles multipart/form-encoded automatically |
| SSE connection management | Custom pub/sub | Simple `asyncio.sleep` poll of `_jobs` dict | For single-process local use, polling is sufficient |

**Key insight:** The web UI is a thin layer. 90% of the work is already done in `app/services/landing_page/`. The UI just wraps it with forms and pages.

## Common Pitfalls

### Pitfall 1: LP generation blocks the event loop
**What goes wrong:** If `generate_landing_page()` is awaited directly in the route handler, no other requests can be served during generation (10-60s).
**Why it happens:** FastAPI uses a single async event loop. Awaiting a long coroutine blocks it.
**How to avoid:** Use `asyncio.create_task()` to run generation concurrently. The route handler returns immediately.
**Warning signs:** Browser hangs on form submit; other requests time out during generation.

### Pitfall 2: StaticFiles mount order matters
**What goes wrong:** Mounting StaticFiles at `/` or `/output` AFTER the API router means API routes are shadowed.
**Why it happens:** FastAPI/Starlette route matching is first-match.
**How to avoid:** Mount StaticFiles before `include_router` calls, or use specific non-overlapping prefixes (`/ui/static`, `/output`).
**Warning signs:** API endpoints return 404 or return static files instead of JSON.

### Pitfall 3: In-memory `_jobs` dict lost on restart
**What goes wrong:** Server restart clears all in-progress jobs. Browser shows stale progress page.
**Why it happens:** `_jobs` is a module-level dict. Not persisted.
**How to avoid:** Write `LandingPage` record to DB on task completion. If browser reconnects, check DB for result. Show "generation may have been interrupted" if job_id not in `_jobs` and not in DB.
**Warning signs:** Progress page stuck at "Running..." after server restart.

### Pitfall 4: LP HTML uses relative paths for assets (video, images)
**What goes wrong:** LP preview in iframe shows broken images/video because relative paths like `../../output/images/hero.jpg` don't resolve correctly when served via `/output/{run_id}/`.
**Why it happens:** `generator.py` uses `os.path.relpath()` to compute relative asset paths relative to the HTML file's location. When StaticFiles serves from `output/`, the base URL is `/output/{run_id}/` — relative paths within the LP HTML resolve correctly as long as assets are inside the `output/` directory.
**How to avoid:** Verify that `generator.py` asset paths stay within the `output/` directory. The StaticFiles mount at `/output` will serve them correctly.
**Warning signs:** iframe shows 404 for video/image assets.

### Pitfall 5: CSRF on the generate form
**What goes wrong:** Form is POST-able from any external site (CSRF).
**Why it happens:** No CSRF token protection.
**How to avoid:** For a local admin tool (not public-facing), CSRF is low-risk. Add a note in code. If needed in future, use `starlette-csrf` or a simple token in session. Don't over-engineer for v1 internal tool.
**Warning signs:** N/A for local use; flag for production deployment.

### Pitfall 6: Missing `python-multipart` for Form() parsing
**What goes wrong:** `422 Unprocessable Entity` when submitting the generate form.
**Why it happens:** FastAPI requires `python-multipart` to parse `application/x-www-form-urlencoded` and `multipart/form-data`.
**How to avoid:** Check if `python-multipart` is installed. It is NOT in `requirements.txt` currently.
**Warning signs:** FastAPI logs `form data requires python-multipart`; form submission returns 422.

```bash
pip install python-multipart
# Add to requirements.txt
```

## Code Examples

Verified patterns from official sources and existing codebase:

### Jinja2Templates Setup (from FastAPI official docs)
```python
# app/ui/router.py
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

router = APIRouter(prefix="/ui")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={}
    )
```

### StaticFiles mount in main.py (from FastAPI official docs)
```python
# app/main.py — add these lines
from fastapi.staticfiles import StaticFiles
from app.ui import router as ui_router

# Mount BEFORE include_router to avoid shadowing
app.mount("/ui/static", StaticFiles(directory="app/ui/static"), name="ui-static")
app.mount("/output", StaticFiles(directory="output"), name="lp-output")

app.include_router(ui_router.router)
app.include_router(routes.router)  # existing API routes
```

### SSE StreamingResponse (verified pattern)
```python
# Source: FastAPI StreamingResponse docs + Starlette internals
import json, asyncio
from fastapi.responses import StreamingResponse

@router.get("/generate/{job_id}/events")
async def generation_events(job_id: str):
    async def event_stream():
        for _ in range(120):  # max 2 min timeout
            job = _jobs.get(job_id, {"status": "not_found"})
            yield f"data: {json.dumps(job)}\n\n"
            if job["status"] in ("done", "error", "not_found"):
                break
            await asyncio.sleep(1)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }
    )
```

### LandingPage model (follows existing models.py pattern)
```python
# Add to app/models.py after WaitlistEntry
class LandingPage(Base):
    """Generated landing pages with deployment status."""
    __tablename__ = "landing_pages"

    id = Column(Integer, primary_key=True)
    run_id = Column(String(50), nullable=False, unique=True)
    product_idea = Column(String(500), nullable=False)
    target_audience = Column(String(500), nullable=True)
    html_path = Column(String(1000), nullable=True)
    status = Column(String(50), default="generated")  # generated, deployed, archived
    color_scheme_source = Column(String(50), nullable=True)
    sections = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    deployed_at = Column(DateTime(timezone=True), nullable=True)
    deployed_url = Column(String(1000), nullable=True)
```

### Background task with asyncio.create_task (verified pattern)
```python
@router.post("/generate", response_class=HTMLResponse)
async def submit_generate(
    request: Request,
    product_idea: str = Form(...),
    target_audience: str = Form(...),
    mock: bool = Form(False),
):
    job_id = uuid4().hex[:8]
    _jobs[job_id] = {"status": "running", "progress": 0, "html_path": None, "error": None}
    asyncio.create_task(_run_generation(job_id, product_idea, target_audience, mock))
    return RedirectResponse(url=f"/ui/generate/{job_id}/progress", status_code=303)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Long-polling for progress | Server-Sent Events (EventSource) | ~2015, now universally supported | Simpler client code, persistent connection |
| Jinja2 + WSGI (Flask/Django) | Jinja2 + ASGI (FastAPI/Starlette) | 2019+ | Async support, no blocking |
| Separate frontend build (webpack) | Server-rendered Jinja2 | PROJECT.md decision | No npm, no build step, simpler deployment |
| Celery for all async tasks | `asyncio.create_task` for lightweight tasks | FastAPI matured | Avoids Celery dependency for simple local tasks |

**Deprecated/outdated:**
- `long-polling`: Replaced by SSE for progress streaming — simpler and more efficient.
- `threading.Thread` for background work in Flask: Replaced by `asyncio.create_task` in async context.

## Open Questions

1. **UI-04: Deploy to Cloudflare trigger from web UI**
   - What we know: Phase 19 handles actual Cloudflare deployment logic. Phase 17 only needs the UI trigger button.
   - What's unclear: Should Phase 17 implement a stub "Deploy" button that sets status="deployed" in DB (placeholder), or skip it entirely for Phase 19?
   - Recommendation: Add "Deploy" button in preview.html that calls `POST /ui/deploy/{run_id}` — stub endpoint that returns "Coming in Phase 19". This satisfies UI-04 as a UI element without implementing actual deployment. Avoids rework.

2. **LP listing scope (UI-05)**
   - What we know: LPs are currently only tracked as files in `output/{run_id}/`. No DB record exists.
   - What's unclear: Should the LP list scan the filesystem for `output/*/landing-page.html` (no DB needed) or read from the new `landing_pages` DB table?
   - Recommendation: Create the `LandingPage` DB model now (needed for Phase 19 anyway). Populate it when generation completes. The list view reads from DB. For existing LPs (created before Phase 17), scan filesystem on first load and backfill DB. This is cleaner than parsing the filesystem every page load.

3. **python-multipart missing from requirements.txt**
   - What we know: `python-multipart` is not in `requirements.txt`. FastAPI's `Form(...)` requires it.
   - What's unclear: Is it already installed as a transitive dependency?
   - Recommendation: Check on first task. Add to `requirements.txt` if missing. This is a hard dependency for any form submission.

4. **Web UI authentication**
   - What we know: The existing API uses Bearer token (`API_SECRET_KEY`). The web UI is for internal/colleague use.
   - What's unclear: Should the web UI have any auth, or is it open (local Docker only)?
   - Recommendation: No auth for web UI in Phase 17. It's behind Docker/localhost. Document this assumption. Auth can be added in a future phase if the tool is hosted publicly.

5. **LP sidecar JSON consistency**
   - What we know: Some LPs have `landing-page.json` sidecar (product_idea only), some don't (no sidecar written by generator currently, only by edit CLI).
   - What's unclear: The generator (`generator.py`) does not currently write a sidecar — only `edit_lp_section.py` reads one.
   - Recommendation: Write the `LandingPage` DB record in the generation task instead of relying on sidecar JSON. The DB is the source of truth for Phase 17+.

## Sources

### Primary (HIGH confidence)
- FastAPI official docs: https://fastapi.tiangolo.com/advanced/templates/ — Jinja2Templates setup, TemplateResponse, StaticFiles
- FastAPI official docs: https://fastapi.tiangolo.com/advanced/custom-response/ — FileResponse, StreamingResponse
- Codebase: `app/main.py` — existing CORS, router mounting, FastAPI app setup
- Codebase: `app/api/routes.py` — route patterns, Depends, HTTPException
- Codebase: `app/models.py` — SQLAlchemy model patterns, Column types, server_default
- Codebase: `app/services/landing_page/generator.py` — `generate_landing_page()` async signature, run_id pattern
- Codebase: `app/services/landing_page/template_builder.py` — existing Jinja2 env setup (LP uses FileSystemLoader directly)
- Codebase: `requirements.txt` — verified python-multipart NOT present
- Codebase: `output/` — verified LP structure: `output/{run_id}/landing-page.html`

### Secondary (MEDIUM confidence)
- FastAPI docs: Form() requires python-multipart — confirmed in official FastAPI form docs
- SSE StreamingResponse pattern — verified with FastAPI's StreamingResponse + text/event-stream media type
- StaticFiles `html=True` behavior — from Starlette docs (FastAPI inherits)

### Tertiary (LOW confidence)
- `X-Accel-Buffering: no` header for SSE behind nginx — community pattern, not in official FastAPI docs
- In-memory `_jobs` dict approach — simple pattern; production would use Redis but not needed for local tool

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries already installed, patterns verified in FastAPI official docs
- Architecture: HIGH — all patterns follow existing codebase conventions
- LandingPage model: HIGH — identical pattern to WaitlistEntry, Job, Video models
- SSE pattern: MEDIUM — verified format (`data: ...\n\n`) against SSE spec; specific FastAPI integration verified via official StreamingResponse docs
- python-multipart gap: HIGH — confirmed absent from requirements.txt

**Research date:** 2026-02-19
**Valid until:** 2026-03-19 (stable libraries, no fast-moving dependencies)
