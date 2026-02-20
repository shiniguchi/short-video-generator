# Architecture Patterns: UGC Review Workflow UI Integration

**Domain:** Adding per-stage review UI to existing ViralForge UGC pipeline
**Researched:** 2026-02-20
**Confidence:** HIGH — all patterns derived from existing codebase, no speculative components

---

## Existing Architecture (What We're Integrating Into)

```
┌────────────────────────────────────────────────────────────────────────┐
│                          FastAPI App                                   │
│                                                                        │
│  ┌──────────────────────┐    ┌──────────────────────────────────────┐  │
│  │   app/ui/router.py   │    │        app/api/routes.py             │  │
│  │  /ui/* — HTML pages  │    │  /api/* — JSON REST (Bearer auth)    │  │
│  │  Jinja2Templates     │    │  POST /ugc-ad-generate               │  │
│  │  SSE /events stream  │    │  GET  /videos/{id}                   │  │
│  │  In-memory _jobs{}   │    │  POST /videos/{id}/approve           │  │
│  └──────────────────────┘    └──────────────────────────────────────┘  │
│                                                                        │
│  /ui/static → StaticFiles (ui.css, ui.js)                             │
│  /output    → StaticFiles (generated video/image files)               │
└────────────────────────────────────────────────────────────────────────┘
              │                                │
              ▼ asyncio.create_task            ▼ celery_app.task.delay
┌─────────────────────────┐        ┌───────────────────────────────────┐
│  In-process asyncio     │        │  Celery Worker (app/tasks.py)     │
│  background tasks       │        │                                   │
│  (LP generation only)   │        │  generate_ugc_ad_task:            │
│  _jobs{} dict tracks    │        │    1. analyze_product()           │
│  SSE progress state     │        │    2. generate_hero_image()       │
└─────────────────────────┘        │    3. generate_ugc_script()       │
                                   │    4. generate_aroll_assets()     │
                                   │    5. generate_broll_assets()     │
                                   │    6. compose_ugc_ad()            │
                                   │    7. Save Video record to DB     │
                                   │    8. _mark_job_complete()        │
                                   └───────────────────────────────────┘
                                                    │
                                    ┌───────────────┘
                                    ▼
                         ┌──────────────────────┐
                         │  PostgreSQL (via      │
                         │  SQLAlchemy async)   │
                         │                      │
                         │  Job: status, stage  │
                         │  Video: status, path │
                         │  Script: scenes, etc │
                         └──────────────────────┘
```

### Key Existing Patterns

| Pattern | Where Used | How It Works |
|---------|-----------|--------------|
| Celery tasks | `app/tasks.py` | Long-running generation runs in worker; DB-backed status |
| Job status tracking | `Job.status`, `Job.stage`, `Job.extra_data["completed_stages"]` | Polled from UI via API |
| SSE progress | `GET /ui/generate/{job_id}/events` | Streams in-memory `_jobs[job_id]` dict every 1s |
| In-memory job store | `_jobs: Dict[str, dict]` in `router.py` | Fast for LP generation; not persistent across restarts |
| Video status machine | `Video.status`: generated → approved/rejected | Updated via `POST /videos/{id}/approve` |
| Static file serving | `/output` mounted at app startup | Generated files served directly by FastAPI |
| Jinja2 templates | `app/ui/templates/` | Extends `base.html` pattern |

---

## UGC Pipeline: Current Stages

The existing `generate_ugc_ad_task` runs all 6 stages as a single atomic Celery task:

```
Stage 1: Product Analysis    → analyze_product() → ProductAnalysis
Stage 2: Hero Image          → generate_hero_image() → hero_image_path (PNG)
Stage 3: Script Generation   → generate_ugc_script() → AdBreakdown
Stage 4: A-Roll Generation   → generate_aroll_assets() → [mp4, mp4, ...]
Stage 5: B-Roll Generation   → generate_broll_assets() → [mp4, mp4, ...]
Stage 6: Composition         → compose_ugc_ad() → final_video.mp4
```

**Current problem:** All stages run in sequence with no review points. If the script is bad, the user cannot fix it before 5 minutes of video generation runs. The review workflow breaks each stage into a checkpoint where the user can approve, edit, or regenerate before continuing.

---

## Recommended Architecture: Stage-Gated Pipeline

### Core Concept

Replace the single monolithic `generate_ugc_ad_task` with a **stage machine** where each stage:
1. Runs and saves output to DB
2. Waits for user approval via UI
3. Only proceeds on explicit user action

```
[User submits product form]
        │
        ▼
[Stage 1 runs: Product Analysis]
        │
        ▼
[UI shows analysis results → User approves or edits]
        │ (user clicks "Approve" or "Regenerate")
        ▼
[Stage 2 runs: Hero Image]
        │
        ▼
[UI shows hero image → User approves or regenerates]
        │
        ▼
[Stage 3 runs: Script]
        │
        ▼
[UI shows script text → User edits or approves]
        │
        ▼
[Stage 4+5 run: A-Roll + B-Roll assets]
        │
        ▼
[UI shows video clips → User approves]
        │
        ▼
[Stage 6 runs: Composition → Final video ready]
```

---

## New Components

### 1. UGCJob Model (NEW — replaces `Job.extra_data` JSON bag)

**Rationale:** The existing `Job` model uses `extra_data` JSON for flexible storage. For the review workflow, we need typed columns for each stage's output so the UI can reliably read and display them without JSON key fishing.

```python
# app/models.py — ADD new table
class UGCJob(Base):
    """Tracks UGC ad generation with per-stage review checkpoints."""
    __tablename__ = "ugc_jobs"

    id = Column(Integer, primary_key=True)
    # Status machine: pending → stage_N_running → stage_N_review → ... → completed | failed
    status = Column(String(50), nullable=False, default="pending")
    current_stage = Column(Integer, default=0)  # 1-6 int, 0 = not started

    # Input
    product_name = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    product_url = Column(String(1000), nullable=True)
    target_duration = Column(Integer, default=30)
    style_preference = Column(String(50), nullable=True)
    product_image_paths = Column(JSON)  # List[str] of uploaded image paths

    # Stage 1 output: Product Analysis
    analysis = Column(JSON, nullable=True)  # ProductAnalysis dict

    # Stage 2 output: Hero Image
    hero_image_path = Column(String(1000), nullable=True)

    # Stage 3 output: Script / AdBreakdown
    script_breakdown = Column(JSON, nullable=True)  # AdBreakdown dict

    # Stage 4 output: A-Roll clips
    aroll_paths = Column(JSON, nullable=True)  # List[str]

    # Stage 5 output: B-Roll clips
    broll_paths = Column(JSON, nullable=True)  # List[str]

    # Stage 6 output: Final video
    final_video_path = Column(String(1000), nullable=True)
    video_id = Column(Integer, ForeignKey("videos.id"), nullable=True)

    # Error tracking
    error_message = Column(Text, nullable=True)
    failed_stage = Column(Integer, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
```

**Status values:**
```
pending
stage_1_running → stage_1_review
stage_2_running → stage_2_review
stage_3_running → stage_3_review
stage_4_running → stage_45_review   (A-Roll + B-Roll combined)
stage_6_running → completed
failed
```

### 2. Per-Stage Celery Tasks (NEW — replaces monolithic task)

Each stage becomes its own Celery task. Stages pause (write to DB, update status) after completion and wait for the UI to call the "advance" endpoint.

```python
# app/tasks.py — ADD per-stage tasks

@celery_app.task(bind=True, name='app.tasks.ugc_stage_1_analyze')
def ugc_stage_1_analyze(self, ugc_job_id: int):
    """Stage 1: Product analysis. Saves ProductAnalysis to UGCJob.analysis."""
    ...
    # Read UGCJob, run analyze_product(), save to ugc_job.analysis
    # Set status = "stage_1_review", current_stage = 1

@celery_app.task(bind=True, name='app.tasks.ugc_stage_2_hero_image')
def ugc_stage_2_hero_image(self, ugc_job_id: int):
    """Stage 2: Hero image. Saves path to UGCJob.hero_image_path."""
    ...
    # Use ugc_job.analysis to get ugc_style, emotional_tone, visual_keywords
    # Run generate_hero_image(), save path
    # Set status = "stage_2_review", current_stage = 2

@celery_app.task(bind=True, name='app.tasks.ugc_stage_3_script')
def ugc_stage_3_script(self, ugc_job_id: int):
    """Stage 3: Script generation. Saves AdBreakdown to UGCJob.script_breakdown."""
    ...

@celery_app.task(bind=True, name='app.tasks.ugc_stage_45_assets')
def ugc_stage_45_assets(self, ugc_job_id: int):
    """Stage 4+5: Generate A-Roll + B-Roll. Saves paths to UGCJob."""
    ...
    # A-Roll and B-Roll together (both are fast together vs user waiting twice)
    # Set status = "stage_45_review", current_stage = 5

@celery_app.task(bind=True, name='app.tasks.ugc_stage_6_compose')
def ugc_stage_6_compose(self, ugc_job_id: int):
    """Stage 6: Final composition. Saves final_video_path to UGCJob."""
    ...
    # Run compose_ugc_ad(), create Video record, set status = "completed"
```

**Why combine A-Roll + B-Roll in one task (4+5):** Both take similar time, both need review of video clips together (A-Roll and B-Roll are reviewed in context), and separating them adds a review step that provides little user value.

### 3. Review API Endpoints (NEW — in `app/ui/router.py`)

```python
# Review workflow routes — add to app/ui/router.py

GET  /ui/ugc/new                    # Form: start new UGC ad
POST /ui/ugc/new                    # Submit form → create UGCJob, start stage 1
GET  /ui/ugc/{job_id}               # Review page: shows current stage output
GET  /ui/ugc/{job_id}/events        # SSE: streams status until stage reaches review
POST /ui/ugc/{job_id}/advance       # Advance to next stage (approve current)
POST /ui/ugc/{job_id}/regenerate    # Re-run current stage (reject, try again)
POST /ui/ugc/{job_id}/edit          # Save user edits to stage output (stage 3: script text)
GET  /ui/ugc/                       # List all UGC jobs
```

**Rationale for SSE on review page:** The same SSE pattern from LP generation (`/ui/generate/{job_id}/events`) works here. The client connects, the server streams `status` until it hits a `_review` state, then the client stops polling and shows the review UI. This reuses the existing `connectSSE()` JS function.

### 4. Review UI Templates (NEW — in `app/ui/templates/`)

```
app/ui/templates/
├── ugc_new.html          # New: Product submission form
├── ugc_list.html         # New: List all UGC jobs
└── ugc_review.html       # New: Per-stage review page (single template, stage-conditional)
```

**Single review template pattern:** One `ugc_review.html` template handles all stages with `{% if ugc_job.status == "stage_1_review" %}` blocks. This keeps the template system simple — the server always renders the same URL `/ui/ugc/{job_id}` and the template shows the right stage UI.

---

## Data Flow

### New UGC Job Submission

```
[POST /ui/ugc/new — form data]
        │
        ▼
1. Validate inputs (product_name, description, uploaded images)
2. Save uploaded images to output/uploads/ (same as existing /ugc-ad-generate)
3. Create UGCJob record (status="pending", product_image_paths=[...])
4. Queue ugc_stage_1_analyze.delay(ugc_job.id)
5. Redirect to /ui/ugc/{job_id}
```

### Review Page Load + SSE

```
[GET /ui/ugc/{job_id}]
        │
        ▼
1. Load UGCJob from DB
2. If status == "stage_N_review": render review UI for stage N
3. If status == "stage_N_running": render "Generating..." + SSE script
4. If status == "completed": render final video
5. SSE stream (GET /ui/ugc/{job_id}/events):
   - Poll UGCJob.status every 1s
   - Send status JSON until status contains "_review" or "completed" or "failed"
   - Client JS: on "_review" received, reload page (window.location.reload())
```

### Stage Advance (User Approves)

```
[POST /ui/ugc/{job_id}/advance — with optional edited data]
        │
        ▼
1. Load UGCJob, verify status == "stage_N_review"
2. If edited data provided: update relevant UGCJob column (e.g., script_breakdown)
3. Queue next stage task (ugc_stage_{N+1}_...)
4. Set UGCJob.status = "stage_{N+1}_running"
5. Return redirect to /ui/ugc/{job_id}
```

### Stage Regenerate (User Rejects)

```
[POST /ui/ugc/{job_id}/regenerate]
        │
        ▼
1. Load UGCJob, verify status == "stage_N_review"
2. Clear current stage output (e.g., set ugc_job.hero_image_path = None)
3. Queue SAME stage task again
4. Set UGCJob.status = "stage_N_running"
5. Return redirect to /ui/ugc/{job_id}
```

---

## Component Boundaries

| Component | Responsibility | New or Existing | Communicates With |
|-----------|---------------|-----------------|-------------------|
| `app/models.py: UGCJob` | Store per-stage outputs + status | NEW | PostgreSQL |
| `app/ui/router.py` | Review UI routes, form handling | MODIFIED (add routes) | UGCJob model, Celery tasks |
| `app/ui/templates/ugc_*.html` | Review UI HTML | NEW | Jinja2 context from router |
| `app/tasks.py: ugc_stage_*` | Execute each pipeline stage | NEW (replaces monolithic task) | UGC pipeline services, UGCJob model |
| `app/services/ugc_pipeline/` | Generation logic | UNCHANGED | Called by new stage tasks |
| SSE stream (`/ui/ugc/{id}/events`) | Stage completion notification | NEW | UGCJob.status in DB |
| Video preview (`/output/...`) | Serve generated media for review | UNCHANGED (already mounted) | StaticFiles mount in main.py |

---

## Integration Points: Existing vs New

### What We Reuse Unchanged

| Existing Component | How the Review Workflow Reuses It |
|-------------------|----------------------------------|
| `app/services/ugc_pipeline/product_analyzer.py: analyze_product()` | Called from `ugc_stage_1_analyze` task |
| `app/services/ugc_pipeline/asset_generator.py: generate_hero_image()` | Called from `ugc_stage_2_hero_image` task |
| `app/services/ugc_pipeline/script_engine.py: generate_ugc_script()` | Called from `ugc_stage_3_script` task |
| `app/services/ugc_pipeline/asset_generator.py: generate_aroll_assets()` | Called from `ugc_stage_45_assets` task |
| `app/services/ugc_pipeline/asset_generator.py: generate_broll_assets()` | Called from `ugc_stage_45_assets` task |
| `app/services/ugc_pipeline/ugc_compositor.py: compose_ugc_ad()` | Called from `ugc_stage_6_compose` task |
| `app/worker.py: celery_app` | Same Celery app, same Redis broker |
| `/output` StaticFiles mount | Serves hero images + video clips for in-browser preview |
| SSE `StreamingResponse` pattern | Identical to existing `/ui/generate/{job_id}/events` |
| `app/database.py: get_session, get_task_session_factory` | Same session factories in stage tasks |
| `app/ui/templates/base.html` | Review templates extend it |
| `app/ui/static/ui.css` | Review UI uses existing styles |

### What We Modify

| Existing Component | Modification | Why |
|-------------------|-------------|-----|
| `app/models.py` | Add `UGCJob` model | Per-stage typed storage |
| `app/ui/router.py` | Add `/ui/ugc/*` routes | Review UI endpoints |
| `app/tasks.py` | Add `ugc_stage_*` tasks | Per-stage async execution |
| Alembic migrations | Add migration for `ugc_jobs` table | Schema change |
| `app/ui/templates/base.html` nav | Add "UGC Ads" nav link | Navigation |

### What We Deprecate

| Component | Action | Note |
|-----------|--------|------|
| `app/tasks.py: generate_ugc_ad_task` | Keep for CLI use, mark as legacy | Old API (`POST /ugc-ad-generate`) still works; new UI uses stage tasks |

---

## Patterns to Follow

### Pattern 1: Stage Task with DB-Backed Status

Every stage task follows this exact structure:

```python
@celery_app.task(bind=True, name='app.tasks.ugc_stage_2_hero_image', max_retries=2)
def ugc_stage_2_hero_image(self, ugc_job_id: int):
    """Stage 2: Generate hero image from product analysis output."""

    async def _run():
        from app.database import get_task_session_factory
        from app.models import UGCJob

        async with get_task_session_factory()() as session:
            # 1. Load UGCJob
            ugc_job = await session.get(UGCJob, ugc_job_id)
            if not ugc_job:
                raise ValueError(f"UGCJob {ugc_job_id} not found")

            # 2. Mark running
            ugc_job.status = "stage_2_running"
            ugc_job.current_stage = 2
            await session.commit()

        # 3. Run generation (outside session to avoid long-held connection)
        from app.services.ugc_pipeline.asset_generator import generate_hero_image
        analysis = ugc_job.analysis  # Already JSON dict from Stage 1
        hero_path = generate_hero_image(
            product_image_path=ugc_job.product_image_paths[0],
            ugc_style=analysis["ugc_style"],
            emotional_tone=analysis["emotional_tone"],
            visual_keywords=analysis["visual_keywords"]
        )

        # 4. Save output + mark review
        async with get_task_session_factory()() as session:
            ugc_job = await session.get(UGCJob, ugc_job_id)
            ugc_job.hero_image_path = hero_path
            ugc_job.status = "stage_2_review"
            await session.commit()

    try:
        asyncio.run(_run())
    except Exception as exc:
        asyncio.run(_mark_ugc_job_failed(ugc_job_id, stage=2, error=str(exc)))
        raise
```

### Pattern 2: SSE Stage Completion Notification

Reuses the exact SSE pattern from LP generation:

```python
@router.get("/ugc/{job_id}/events")
async def ugc_stage_events(job_id: int, session: AsyncSession = Depends(get_session)):
    """SSE: stream UGCJob status until stage reaches review/completed/failed."""

    async def event_stream():
        for _ in range(300):  # max 5 min (300 x 1s)
            ugc_job = await session.get(UGCJob, job_id)
            data = {
                "status": ugc_job.status if ugc_job else "not_found",
                "current_stage": ugc_job.current_stage if ugc_job else 0
            }
            yield f"data: {json.dumps(data)}\n\n"
            # Stop streaming when stage is in review or terminal state
            if not ugc_job or ugc_job.status in ("completed", "failed", "not_found"):
                break
            if "_review" in ugc_job.status:
                break
            await asyncio.sleep(1)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
```

### Pattern 3: In-Browser Media Preview

Generated files are served via the existing `/output` StaticFiles mount:

```python
# main.py already has:
app.mount("/output", StaticFiles(directory=str(_output_dir)), name="lp-output")

# Templates use this directly:
# <img src="/output/{{ relative_path_from_output_dir }}">
# <video src="/output/{{ relative_path }}"></video>
```

Hero images, A-Roll clips, and B-Roll clips are all written to subdirectories of `output/`. No additional mounts needed.

### Pattern 4: Script Edit (Stage 3 User Editing)

Stage 3 (script) needs user editing. Use a `<textarea>` form that posts back the edited `master_script.full_script`:

```python
@router.post("/ugc/{job_id}/edit")
async def ugc_edit_stage(
    job_id: int,
    field: str = Form(...),       # "script_text"
    value: str = Form(...),        # edited text
    session: AsyncSession = Depends(get_session)
):
    """Save user edits to stage output without regenerating."""
    ugc_job = await session.get(UGCJob, job_id)
    if ugc_job.status != "stage_3_review":
        raise HTTPException(400, "Can only edit during stage 3 review")

    if field == "script_text":
        breakdown = ugc_job.script_breakdown
        breakdown["master_script"]["full_script"] = value
        ugc_job.script_breakdown = breakdown

    await session.commit()
    return RedirectResponse(url=f"/ui/ugc/{job_id}", status_code=303)
```

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Passing Stage Results via Celery Task Arguments

**What goes wrong:** Chaining stages as `stage_1.apply_async() | stage_2.apply_async()` — Celery passes `ProductAnalysis` dict as task arg. Works, but the UI cannot inspect the result without also calling `AsyncResult`.

**Why bad:** No DB record of what each stage produced. UI can't display analysis results from DB. Recovery after restart loses intermediate outputs.

**Instead:** Write stage outputs to `UGCJob` columns. Each task reads inputs from DB and writes outputs to DB. Tasks are stateless — only job ID is passed.

### Anti-Pattern 2: Long-Polling the Celery Task ID

**What goes wrong:** Frontend polls `GET /api/tasks/{celery_task_id}` for completion. Requires Celery result backend to be queryable per-task.

**Why bad:** Celery result expiry (default 24h), result backend adds complexity, task IDs must be tracked separately. SSE against DB is simpler and already used.

**Instead:** Store task status in `UGCJob.status`. SSE stream polls DB every 1s. Stage tasks update DB status. No Celery task ID needed in the frontend.

### Anti-Pattern 3: One Large Monolithic Review Template

**What goes wrong:** Building a single template with all 6 stage review UIs visible at once (tabbed or accordion), loading all media upfront.

**Why bad:** A-Roll + B-Roll clips can be 6-10 large mp4 files. Loading all at page load is slow. Template becomes complex and hard to test.

**Instead:** Render only the current stage's review UI. `ugc_review.html` uses `{% if ugc_job.status == "stage_2_review" %}` guards. Earlier stage outputs are collapsed/hidden by default but accessible on scroll.

### Anti-Pattern 4: Blocking the FastAPI Event Loop in Advance/Regenerate Handlers

**What goes wrong:** `POST /ui/ugc/{job_id}/advance` calls `celery_task.get()` to wait for completion.

**Why bad:** FastAPI runs in a single async event loop. `task.get()` blocks the thread for minutes, freezing all requests.

**Instead:** `advance` handler just queues the next Celery task, updates DB status to `stage_N_running`, and redirects. The SSE stream does the waiting.

---

## Build Order (Integration Sequence)

Build order respects dependencies: DB schema before tasks, tasks before routes, routes before templates.

### Step 1: Data Model
**Files:** `app/models.py` (add `UGCJob`), new Alembic migration
**Why first:** All other components read/write `UGCJob`. Nothing else can be tested without it.

### Step 2: Per-Stage Celery Tasks
**Files:** `app/tasks.py` (add `ugc_stage_1` through `ugc_stage_6`)
**Why second:** Tasks are pure Python, testable without UI. Run via `task.delay(job_id)` from Django shell or pytest. Confirms pipeline logic works with DB intermediates before UI is built.

### Step 3: Review API Routes
**Files:** `app/ui/router.py` (add `/ui/ugc/*` routes)
**Why third:** Routes depend on models and tasks. The advance/regenerate handlers can be tested with curl before templates exist (return JSON temporarily).

### Step 4: Review UI Templates
**Files:** `app/ui/templates/ugc_new.html`, `ugc_list.html`, `ugc_review.html`
**Why fourth:** Templates are purely presentation. All logic is already in routes and tasks. Build incrementally: new form → list → per-stage review sections.

### Step 5: Media Preview Wiring
**Files:** Template `<img>/<video>` tags using `/output/` paths, `ui.css` additions
**Why fifth:** Requires real generated files to verify. Depends on Stage 2 (images) and Stage 4-5 (video clips) having run at least once.

---

## Scalability Notes

| Concern | At Current Scale (1 user) | At 10 concurrent jobs |
|---------|--------------------------|----------------------|
| Celery worker | `worker_prefetch_multiplier=1` means 1 task at a time | Add `--concurrency=4` to Celery worker |
| DB connections | SQLAlchemy async pool (default 5) | Fine; each task holds connection only during DB ops |
| SSE connections | One per browser tab | FastAPI handles many SSE streams as async generators |
| Stage output storage | Files in `output/`, paths in `UGCJob` JSON columns | Fine up to ~1000 jobs before disk management needed |
| Media preview | FastAPI StaticFiles | At high load: Nginx to serve `output/` directly |

---

## Sources

All findings are HIGH confidence — derived directly from codebase inspection:

- `app/tasks.py: generate_ugc_ad_task` — existing monolithic pipeline structure (lines 355-510)
- `app/services/ugc_pipeline/` — 4 service modules: product_analyzer, script_engine, asset_generator, ugc_compositor
- `app/ui/router.py` — SSE pattern (lines 72-86), in-memory `_jobs` dict, Jinja2Templates usage
- `app/models.py` — existing `Job`, `Video`, `LandingPage` model patterns
- `app/pipeline.py` — `_update_job_status`, `_mark_job_complete`, `_mark_job_failed` helpers (reuse as-is)
- `app/main.py` — `/output` StaticFiles mount (line 89), router mounting pattern
- `app/database.py` — `get_task_session_factory` for Celery task DB access
- `.planning/phases/17-web-ui/17-RESEARCH.md` — SSE + asyncio background task patterns
- `.planning/phases/19-admin-dashboard-deployment/19-RESEARCH.md` — existing router patterns, confirmed patterns
