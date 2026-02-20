# Phase 21: Per-Stage Celery Tasks - Research

**Researched:** 2026-02-20
**Domain:** Celery task chains, FastAPI endpoints, UGCJob state machine, HTMX 2.0 UI
**Confidence:** HIGH

## Summary

Phase 21 converts the monolithic `generate_ugc_ad_task` (which runs all pipeline stages in one task) into six separate Celery tasks, one per pipeline stage. Each task writes its output to the `UGCJob` DB row then sets `status` to a review state, where it pauses. A user-triggered "advance" HTTP call transitions the job back to `running` and enqueues the next task.

The codebase already has everything needed: `UGCJob` model (Phase 20), `UGCJobStateMachine` guard layer, all six pipeline service functions (product_analyzer, asset_generator x3, script_engine, ugc_compositor), and the Celery infrastructure (worker, task decorator patterns). The main work is (1) splitting the monolith into six tasks, (2) threading `use_mock` explicitly through each task and service call, (3) adding submission and advance endpoints, and (4) building the HTMX review UI.

The critical problem is that all service functions (`analyze_product`, `generate_hero_image`, `generate_ugc_script`, `generate_aroll_assets`, `generate_broll_assets`, `compose_ugc_ad`) currently call `get_llm_provider()` and `get_image_provider()` which read the global `settings.use_mock_data` singleton. Since `use_mock` is stored per-job in `UGCJob.use_mock`, the service functions must accept `use_mock: bool` and instantiate providers directly rather than calling the factory.

**Primary recommendation:** Write `app/ugc_tasks.py` as a new module with six `@celery_app.task` functions. Each task loads the `UGCJob` row, runs one service function, writes output back, and sets the review status. Modify service functions to accept `use_mock: bool`. Add three FastAPI endpoints (submit, advance, status). Build HTMX review page per-stage.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| celery | 5.6.2 | Task queue for per-stage async execution | Already installed, worker configured |
| python-statemachine | 2.6.0 | Guard layer for UGCJob status transitions | Already installed, UGCJobStateMachine exists |
| SQLAlchemy (async) | 2.0.46 | Async DB access from Celery tasks via NullPool | Pattern established in compose_video_task |
| FastAPI | 0.128.8 | Submit and advance endpoints | Already the web framework |
| Jinja2 (via FastAPI) | existing | HTMX review page templates | Already used in /ui/router.py |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| HTMX | 2.0.8 (CDN) | Approve/advance buttons without full-page reload | Per-stage review UI |
| asyncio (stdlib) | - | `asyncio.run()` wrapper inside Celery sync tasks | Pattern from existing tasks.py |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| NullPool per-task engine | Module-level pooled engine | NullPool is required — prefork workers get new event loops; pooled engine causes "attached to different loop" errors (already documented in database.py) |
| Celery chain/chord | Manual task-by-task dispatch | Chain auto-fires; phase requires user approval between stages. Manual `.delay()` from the advance endpoint is correct. |

## Architecture Patterns

### Recommended File Structure

```
app/
├── ugc_tasks.py          # NEW: six per-stage Celery tasks
├── ugc_router.py         # NEW: submit, advance, status FastAPI endpoints
├── tasks.py              # EXISTING: keep as-is, register ugc_tasks
├── worker.py             # EXISTING: import app.ugc_tasks for autodiscovery
├── services/
│   └── ugc_pipeline/
│       ├── product_analyzer.py   # MODIFY: accept use_mock param
│       ├── script_engine.py      # MODIFY: accept use_mock param
│       └── asset_generator.py    # MODIFY: accept use_mock param
└── ui/
    └── templates/
        └── ugc_review.html       # NEW: HTMX stage review template
```

### Pattern 1: Per-Stage Task Shape

Every stage task follows this exact shape — load job, validate state, run service, write output, transition to review status:

```python
# app/ugc_tasks.py
import asyncio
from app.worker import celery_app

@celery_app.task(
    bind=True,
    name='app.ugc_tasks.ugc_stage_1_analyze',
    max_retries=1,
    time_limit=600,
)
def ugc_stage_1_analyze(self, job_id: int):
    """Stage 1: Product analysis. Writes analysis_* columns, sets stage_analysis_review."""
    from app.database import get_task_session_factory
    from app.models import UGCJob
    from app.state_machines.ugc_job import UGCJobStateMachine
    from app.services.ugc_pipeline.product_analyzer import analyze_product
    from sqlalchemy import select

    async def _run():
        session_factory = get_task_session_factory()
        async with session_factory() as session:
            # Load job
            result = await session.execute(select(UGCJob).where(UGCJob.id == job_id))
            job = result.scalars().first()
            if not job:
                raise ValueError(f"UGCJob {job_id} not found")

            # Guard: must be in running state
            sm = UGCJobStateMachine(model=job, state_field="status", start_value=job.status)
            # (state machine validates; if already wrong state, raises TransitionNotAllowed)

            # Run service — pass use_mock explicitly
            analysis = analyze_product(
                product_name=job.product_name,
                description=job.description,
                image_count=len(job.product_image_paths or []),
                style_preference=job.style_preference,
                product_url=job.product_url,
                use_mock=job.use_mock,  # per-job flag, not global settings
            )

            # Write output columns
            job.analysis_category = analysis.category
            job.analysis_ugc_style = analysis.ugc_style
            job.analysis_emotional_tone = analysis.emotional_tone
            job.analysis_key_features = analysis.key_features
            job.analysis_visual_keywords = analysis.visual_keywords
            job.analysis_target_audience = analysis.target_audience

            # Transition: running -> stage_analysis_review
            sm.send("complete_analysis")
            # sm.send() calls the transition which writes job.status via model binding
            await session.commit()

    asyncio.run(_run())
```

### Pattern 2: State Machine Usage in Tasks

Instantiate with `start_value=job.status` — the machine starts at the job's current persisted state, not `pending`. Use `sm.send(event_name)` to trigger transitions; the statemachine library writes the new value to `job.status` via the model binding.

```python
# Always load current status from DB, not from a stale in-memory reference
sm = UGCJobStateMachine(model=job, state_field="status", start_value=job.status)
sm.send("complete_analysis")  # raises TransitionNotAllowed if invalid
# job.status is now "stage_analysis_review" — commit to persist
```

**Important:** `UGCJobStateMachine` uses `state_field="status"` but the current implementation in `app/state_machines/ugc_job.py` does NOT set `model` or `state_field` — it only defines states and transitions. The statemachine 2.x API binds via `model` + `state_field` keyword args passed to the constructor. Verify this works by testing with a UGCJob instance before writing all six tasks.

### Pattern 3: Advance Endpoint

The "advance" endpoint transitions the job from review state back to `running`, then enqueues the next stage task:

```python
# app/ugc_router.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_session
from app.models import UGCJob
from app.state_machines.ugc_job import UGCJobStateMachine

router = APIRouter(prefix="/ugc", tags=["ugc"])

# Map: current review status -> (approve_event, next_task_function)
_STAGE_ADVANCE_MAP = {
    "stage_analysis_review": ("approve_analysis", "ugc_stage_2_hero_image"),
    "stage_script_review":   ("approve_script",   "ugc_stage_45_assets"),
    "stage_aroll_review":    ("approve_aroll",    "ugc_stage_45_assets"),  # or compose
    "stage_broll_review":    ("approve_broll",    "ugc_stage_6_compose"),
    "stage_composition_review": ("approve_final", None),  # terminal
}

@router.post("/jobs/{job_id}/advance")
async def advance_ugc_job(job_id: int, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(UGCJob).where(UGCJob.id == job_id))
    job = result.scalars().first()
    if not job:
        raise HTTPException(404, f"UGCJob {job_id} not found")

    advance = _STAGE_ADVANCE_MAP.get(job.status)
    if not advance:
        raise HTTPException(400, f"Job {job_id} not in a review state (status: {job.status})")

    approve_event, next_task_name = advance
    sm = UGCJobStateMachine(model=job, state_field="status", start_value=job.status)
    sm.send(approve_event)   # transitions job.status -> running
    await session.commit()

    # Enqueue next task if not terminal
    if next_task_name:
        from app import ugc_tasks
        task_fn = getattr(ugc_tasks, next_task_name)
        task_fn.delay(job_id)

    return {"job_id": job_id, "status": job.status, "next": next_task_name}
```

### Pattern 4: Submission Endpoint

The submission endpoint creates a UGCJob row and enqueues stage 1:

```python
@router.post("/jobs")
async def submit_ugc_job(
    product_name: str = Form(...),
    description: str = Form(...),
    use_mock: bool = Form(True),
    images: List[UploadFile] = File(...),
    session: AsyncSession = Depends(get_session),
):
    # Save uploaded images -> product_image_paths
    # Create UGCJob row with use_mock=use_mock
    # Transition: pending -> running via state machine
    # Enqueue ugc_stage_1_analyze.delay(job.id)
    ...
```

### Pattern 5: use_mock Threading Through Services

The service functions currently call `get_llm_provider()` which reads `settings.use_mock_data`. Since `use_mock` is per-job, add a `use_mock: bool = False` parameter to each service function:

```python
# product_analyzer.py — modified signature
def analyze_product(
    product_name: str,
    description: str,
    image_count: int,
    style_preference=None,
    product_url=None,
    use_mock: bool = False,   # NEW explicit arg
) -> ProductAnalysis:
    # Instead of: llm = get_llm_provider()
    from app.services.llm_provider.mock import MockLLMProvider
    from app.services.llm_provider.gemini import GeminiLLMProvider
    from app.config import get_settings
    if use_mock:
        llm = MockLLMProvider()
    else:
        settings = get_settings()
        llm = GeminiLLMProvider(api_key=settings.google_api_key)
    ...
```

Same pattern applies to `generate_ugc_script`, `generate_hero_image`, `generate_aroll_assets`, `generate_broll_assets`.

### Anti-Patterns to Avoid

- **Global settings.use_mock_data in task context:** The settings singleton is loaded at import time. If the worker has `USE_MOCK_DATA=True` in env, it applies to all jobs regardless of `job.use_mock`. Always use `job.use_mock` explicitly.
- **Celery chain for human-in-the-loop:** Celery `chain()` fires each task immediately after the previous. For a human-approval gate, tasks must be manually enqueued from the advance endpoint.
- **Reusing the module-level async engine in tasks:** Celery prefork workers create a new event loop per task. Always use `get_task_session_factory()` (NullPool) in tasks, never `async_session_factory`.
- **Mutating approved content:** Per prior decisions: never overwrite `analysis_*` columns on re-run; store in `candidate_*` and overwrite only on accept.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| State transition validation | Custom if/elif status checks | `UGCJobStateMachine.send()` | Already built in Phase 20; raises TransitionNotAllowed on invalid transition |
| DB session for tasks | Module-level async engine | `get_task_session_factory()` with NullPool | Already documented in database.py; prevents event loop conflicts |
| Mock provider selection | if/else blocks in tasks | Pass `use_mock` to service functions, let them instantiate | Keeps task code thin; service stays testable |
| HTMX polling | Custom JS polling loop | SSE extension already used in progress.html | Pattern already established in the codebase |

## Common Pitfalls

### Pitfall 1: Stage Naming Mismatch Between State Machine and Column Names

**What goes wrong:** The state machine has `stage_analysis_review` but the phase description mentions stages: analyze, hero_image, script, assets, compose. The state machine does NOT have a `stage_hero_image_review` state — hero image is bundled into the analysis review cycle.

**Root cause:** Phase 20 defined the state machine with 5 review states (analysis, script, aroll, broll, composition), not 6. Hero image generation is Stage 2 but there's no dedicated `stage_hero_image_review`.

**How to avoid:** Either (a) add `stage_hero_image_review` state to the machine (requires migration for existing rows), or (b) combine Stage 1 + Stage 2 into one task that runs analyze then hero image, then sets `stage_analysis_review`. The planner must decide. This is the biggest design decision in Phase 21.

**Current state machine review states:**
- `stage_analysis_review` — after analysis (and possibly hero image)
- `stage_script_review` — after script generation
- `stage_aroll_review` — after A-Roll generation
- `stage_broll_review` — after B-Roll generation
- `stage_composition_review` — after composition

### Pitfall 2: python-statemachine 2.x model binding API

**What goes wrong:** The statemachine 2.x model-binding API (`model=`, `state_field=`) may not work exactly as expected if `UGCJob.status` is a plain SQLAlchemy column (not a Python property with setter).

**Root cause:** statemachine 2.x binds via `setattr(model, state_field, new_value)` which works for SQLAlchemy columns (triggers SQLAlchemy change tracking). The `start_value=` param sets the initial state without firing entry callbacks.

**How to avoid:** Test the statemachine binding with a UGCJob instance early in implementation. If `sm.send()` doesn't update `job.status`, the workaround is to manually do `job.status = sm.current_state.id` after sending.

**Warning signs:** After `sm.send("complete_analysis")`, if `job.status` is still `"running"` instead of `"stage_analysis_review"`, the model binding isn't working — use manual assignment.

### Pitfall 3: use_mock=False Breaks if API Keys Missing in Worker

**What goes wrong:** If a job was submitted with `use_mock=False` but the worker's env doesn't have `GOOGLE_API_KEY`, the task will fail on import/instantiation.

**How to avoid:** The task should catch `ImportError` or `ValueError` from provider instantiation and fail the job cleanly via statemachine's `fail` transition.

### Pitfall 4: State Machine start_value vs DB Row Misalignment

**What goes wrong:** If a task reads `job.status = "running"` and creates `sm = UGCJobStateMachine(..., start_value="running")`, but the job was actually in `"stage_analysis_review"`, the machine will be in the wrong state.

**How to avoid:** Always reload the job from DB just before creating the state machine in the task. Never cache the job object across an async boundary in Celery tasks.

### Pitfall 5: HTMX SSE vs Polling for Stage Status

**What goes wrong:** Using SSE (streaming response) for status updates is correct for long-running single jobs, but SSE connections hold up FastAPI worker threads if not handled carefully.

**How to avoid:** The existing `progress.html` pattern uses SSE with `asyncio.sleep(1)` polling internally. For the UGC review page, a simpler approach is HTMX polling (`hx-get` with `hx-trigger="every 2s"`) until status reaches a review state, then showing approve/reject buttons. This avoids SSE complexity.

## Code Examples

### DB Write Pattern in Task (verified from existing tasks.py compose_video_task)

```python
# Source: app/tasks.py compose_video_task (existing pattern)
import asyncio

async def _update_job(job_id: int, **kwargs):
    from app.database import get_task_session_factory
    from app.models import UGCJob
    from sqlalchemy import select

    session_factory = get_task_session_factory()
    async with session_factory() as session:
        result = await session.execute(select(UGCJob).where(UGCJob.id == job_id))
        job = result.scalars().first()
        for k, v in kwargs.items():
            setattr(job, k, v)
        await session.commit()

# In task:
asyncio.run(_update_job(job_id, analysis_category="beauty", status="stage_analysis_review"))
```

### HTMX Approve Button Pattern (consistent with prior decisions)

```html
<!-- ugc_review.html partial for a review stage -->
<!-- hx-post triggers advance endpoint, hx-swap replaces the button area -->
<div id="stage-controls">
  <p>Stage: {{ job.status }}</p>
  <button
    hx-post="/ugc/jobs/{{ job.id }}/advance"
    hx-target="#stage-controls"
    hx-swap="outerHTML"
  >
    Approve & Continue
  </button>
</div>
```

### Per-Stage Task Registration in worker.py

```python
# app/worker.py — add after existing import
import app.ugc_tasks  # noqa: F401  registers per-stage UGC tasks
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Single monolithic `generate_ugc_ad_task` | Six separate per-stage tasks | Phase 21 | Enables human approval gate between stages |
| `get_settings().use_mock_data` singleton | `job.use_mock` per-job arg | Phase 20 decision | Allows per-job mock/real toggle |
| `_jobs` dict in-memory | `UGCJob` PostgreSQL row | Phase 20 | Survives worker restarts |

## Open Questions

1. **Hero Image: own review state or merged with Analysis?**
   - What we know: State machine has `stage_analysis_review` but no `stage_hero_image_review`. Hero image is listed as a separate stage in the phase description (Stage 2).
   - What's unclear: Should `ugc_stage_1_analyze` (analysis only) and `ugc_stage_2_hero_image` be two separate tasks that both complete before `stage_analysis_review`? Or should they be one combined task?
   - Recommendation: Combine into one task `ugc_stage_12_analyze_and_hero` that does both analysis and hero image, then sets `stage_analysis_review`. This matches the existing state machine without adding new states or a migration.

2. **A-Roll and B-Roll: separate review states or one assets review?**
   - What we know: State machine has both `stage_aroll_review` and `stage_broll_review` as separate states.
   - What's unclear: The phase plan document says `21-02: ugc_stage_45_assets` (plural, one task for both). But state machine expects separate reviews.
   - Recommendation: Two separate tasks — `ugc_stage_4_aroll` sets `stage_aroll_review`; after advance, `ugc_stage_5_broll` sets `stage_broll_review`.

3. **use_mock threading: modify service function signatures or create wrapper providers?**
   - What we know: All service functions call `get_llm_provider()` which reads global settings.
   - Recommendation: Add `use_mock: bool = False` param to each service function and instantiate providers directly. This is the minimal change and keeps backward compatibility for existing callers that don't pass the param.

## Sources

### Primary (HIGH confidence)
- Codebase: `/Users/shiniguchi/development/short-video-generator/app/tasks.py` — verified task patterns, NullPool usage, asyncio.run wrapping
- Codebase: `/Users/shiniguchi/development/short-video-generator/app/state_machines/ugc_job.py` — verified state machine states and transitions
- Codebase: `/Users/shiniguchi/development/short-video-generator/app/models.py` — verified UGCJob column names
- Codebase: `/Users/shiniguchi/development/short-video-generator/app/database.py` — verified get_task_session_factory() NullPool pattern
- Codebase: `/Users/shiniguchi/development/short-video-generator/app/services/ugc_pipeline/` — verified all six service function signatures

### Secondary (MEDIUM confidence)
- python-statemachine 2.6.0 model binding: based on statemachine 2.x documentation pattern (model=, state_field=, start_value=); should be verified against installed package in .venv.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries already installed and in use
- Architecture: HIGH — patterns directly derived from existing codebase; no new libraries
- Pitfalls: HIGH for DB/event-loop issues (documented in codebase), MEDIUM for statemachine model binding (needs test)

**Research date:** 2026-02-20
**Valid until:** 2026-03-22 (stable; no fast-moving dependencies)
