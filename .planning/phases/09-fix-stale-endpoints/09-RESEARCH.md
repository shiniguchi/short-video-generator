# Phase 9: Fix Stale Manual Endpoints - Research

**Researched:** 2026-02-14
**Domain:** FastAPI endpoint signature compatibility and backward-compatible Celery task invocation
**Confidence:** HIGH

## Summary

Phase 9 addresses integration gaps created when Phase 7 threaded `job_id` as a required first parameter through the pipeline task chain. This broke two manual (non-orchestrated) API endpoints that previously invoked these tasks without job context. The fix requires making `job_id` optional in task signatures and creating Job records on-demand when endpoints invoke tasks manually.

**Primary domain:** FastAPI request handling with optional parameters + Celery task invocation patterns + database record creation in API handlers.

**Key insight:** Phase 7's refactor optimized for pipeline-driven flows (POST /generate) but inadvertently broke manual step-by-step debugging flows (POST /generate-content, POST /compose-video). The solution is to make `job_id` optional with a default of `None`, then create a Job record in the API handler if the endpoint is called manually (without job context).

**Primary recommendation:** Use `Optional[int] = None` for job_id parameters in both endpoint signatures and task signatures. API handlers should create Job records before invoking tasks when job_id is not provided. This maintains backward compatibility for manual flows while preserving pipeline data lineage.

## Standard Stack

### Core Dependencies (Already in Project)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | >=0.100.0 | REST API framework | Modern async Python web framework, type-safe routing |
| Pydantic | (via FastAPI) | Request/response schemas | Data validation and serialization for API payloads |
| SQLAlchemy | (existing) | ORM for Job record creation | Already used for all database operations |
| Celery | (existing) | Task queue | Already used for all async pipeline tasks |

### No New Dependencies Required

This phase requires **zero new packages**. All fixes are pure application code using existing FastAPI/Celery/SQLAlchemy patterns already established in Phases 1-8.

## Architecture Patterns

### Pattern 1: Optional Parameter with Default None

**What:** Use Python's `Optional[T] = None` pattern to make parameters work in both manual and orchestrated contexts.

**When to use:** When a function needs to support two call patterns:
1. Called from pipeline orchestrator (job_id provided)
2. Called from manual API endpoint (job_id not provided initially)

**FastAPI endpoint example:**
```python
from typing import Optional
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

@router.post("/generate-content")
async def trigger_content_generation(
    job_id: Optional[int] = None,
    session: AsyncSession = Depends(get_session)
):
    # Create Job if not provided (manual flow)
    if job_id is None:
        job = Job(status="pending", stage="content_generation", theme="manual")
        session.add(job)
        await session.commit()
        await session.refresh(job)
        job_id = job.id

    # Now invoke task with job_id
    from app.tasks import generate_content_task
    task = generate_content_task.delay(job_id)
    return {"task_id": str(task.id), "job_id": job_id, "status": "queued"}
```

**Celery task signature (already done in Phase 7):**
```python
@celery_app.task(bind=True)
def generate_content_task(self, job_id: int, theme_config_path: Optional[str] = None):
    # job_id is required here — endpoint ensures it's always provided
    logger.info(f"Starting content generation for job {job_id}")
    # ... rest of task
```

**Key principle:** Endpoint layer handles optionality. Task layer expects job_id to always be provided.

### Pattern 2: Backward-Compatible Endpoint Signatures

**What:** Existing endpoints don't currently accept job_id. Adding it as optional maintains backward compatibility.

**Current broken signature (routes.py:172):**
```python
@router.post("/generate-content")
async def trigger_content_generation():
    from app.tasks import generate_content_task
    task = generate_content_task.delay()  # BROKEN: missing job_id
    return {"task_id": str(task.id), "status": "queued"}
```

**Fixed signature with backward compatibility:**
```python
@router.post("/generate-content")
async def trigger_content_generation(
    job_id: Optional[int] = None,
    theme_config_path: Optional[str] = None,
    session: AsyncSession = Depends(get_session)
):
    # Create Job record if manual invocation
    if job_id is None:
        job = Job(status="pending", stage="content_generation", theme="manual")
        session.add(job)
        await session.commit()
        await session.refresh(job)
        job_id = job.id

    # Invoke task with job_id
    from app.tasks import generate_content_task
    task = generate_content_task.delay(job_id, theme_config_path)
    return {
        "task_id": str(task.id),
        "job_id": job_id,  # Include job_id in response
        "status": "queued",
        "description": "Generating content: script, video, and voiceover"
    }
```

**Why this works:**
- Old callers: `POST /generate-content` with empty body → job_id defaults to None, new Job created
- New callers: `POST /generate-content?job_id=123` → uses existing Job 123
- Pipeline orchestrator: Already passes job_id directly to task, doesn't use endpoint

### Pattern 3: Request Body vs Query Parameter

**What:** FastAPI supports optional parameters as query params, request body, or both.

**For simple optional integers (like job_id):**
```python
async def my_endpoint(job_id: Optional[int] = None):
    # FastAPI treats this as query parameter: POST /endpoint?job_id=123
```

**For complex request bodies with optional job_id:**
```python
from pydantic import BaseModel

class ContentGenerationRequest(BaseModel):
    job_id: Optional[int] = None
    theme_config_path: Optional[str] = None

@router.post("/generate-content")
async def trigger_content_generation(
    request: ContentGenerationRequest,
    session: AsyncSession = Depends(get_session)
):
    job_id = request.job_id
    # ... create Job if None
```

**Recommendation for this phase:** Use query parameter approach (simpler, no schema changes needed). Only 2 endpoints affected, both have simple signatures.

### Anti-Patterns to Avoid

- **Don't make job_id optional in task signatures:** Tasks should always receive job_id. Optionality belongs in the API layer.
- **Don't create Jobs inside tasks:** Job creation is orchestrator/endpoint responsibility, not task responsibility. Tasks consume Jobs, they don't create them.
- **Don't silently skip job_id:** If job_id is None in a task, that's a bug. Always create Job in endpoint before invoking task.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Job creation validation | Custom validation logic | SQLAlchemy model defaults + database constraints | Database already defines required fields, constraints |
| Request parameter parsing | Manual query string parsing | FastAPI type hints with Optional[T] = None | FastAPI auto-parses and validates, generates OpenAPI docs |
| Task ID generation | Custom UUID generation | Celery's automatic task_id | Celery generates unique IDs by default, appears in logs |
| Job ID in response | Custom JSON serialization | Return dict with job_id field | FastAPI auto-serializes to JSON |

**Key insight:** FastAPI + Pydantic + Celery already handle 95% of the work. This phase is primarily wiring, not new functionality.

## Common Pitfalls

### Pitfall 1: Forgetting to await session.commit()

**What goes wrong:** Job record created in endpoint but not committed before task starts. Task tries to load Job and gets "Job not found" error.

**Why it happens:** SQLAlchemy async sessions require explicit `await session.commit()` to persist changes.

**How to avoid:**
```python
# WRONG
job = Job(...)
session.add(job)
task = generate_content_task.delay(job.id)  # job.id is None! Not committed yet

# CORRECT
job = Job(...)
session.add(job)
await session.commit()      # Persist to database
await session.refresh(job)  # Load generated ID
task = generate_content_task.delay(job.id)  # job.id is now populated
```

**Warning signs:**
- Task logs show "Job X not found" errors
- `job.id` is None when passed to task
- Race condition (sometimes works, sometimes fails)

### Pitfall 2: Wrong Parameter Order in compose_video_task

**What goes wrong:** Phase 7 added `job_id` as the **first** parameter to `compose_video_task(job_id, script_id, video_path, audio_path, cost_data)`. The manual endpoint currently calls it as `compose_video_task.delay(script_id, video_path, audio_path)`.

**Why it happens:** Positional arguments are order-sensitive. Phase 7 added job_id at position 0, shifting all other arguments.

**Current broken code (routes.py:252):**
```python
@router.post("/compose-video")
async def trigger_video_composition(
    script_id: int,
    video_path: str,
    audio_path: str
):
    from app.tasks import compose_video_task
    task = compose_video_task.delay(script_id, video_path, audio_path)
    # WRONG: passes script_id as job_id, video_path as script_id, audio_path as video_path
```

**Correct fix:**
```python
@router.post("/compose-video")
async def trigger_video_composition(
    script_id: int,
    video_path: str,
    audio_path: str,
    job_id: Optional[int] = None,
    session: AsyncSession = Depends(get_session)
):
    # Create Job if not provided
    if job_id is None:
        job = Job(status="pending", stage="composition", theme="manual")
        session.add(job)
        await session.commit()
        await session.refresh(job)
        job_id = job.id

    from app.tasks import compose_video_task
    # CORRECT: job_id first, then script_id, video_path, audio_path
    task = compose_video_task.delay(job_id, script_id, video_path, audio_path)
    return {"task_id": str(task.id), "job_id": job_id, "status": "queued"}
```

**Warning signs:**
- TypeError: wrong number of arguments
- Confusing errors like "expected int for script_id, got str"
- Task logs show nonsensical values (script_id appears in job_id field)

### Pitfall 3: Missing Session Dependency Injection

**What goes wrong:** Endpoint needs to create Job record but doesn't inject AsyncSession dependency.

**Why it happens:** Existing endpoints that only triggered tasks didn't need database access. Now they do.

**How to avoid:**
```python
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_session

@router.post("/generate-content")
async def trigger_content_generation(
    job_id: Optional[int] = None,
    session: AsyncSession = Depends(get_session)  # ADD THIS
):
    # Now can create Job records
```

**Warning signs:**
- NameError: 'session' is not defined
- Endpoint doesn't have database access

### Pitfall 4: Removing output/final/ Directory Without Checking References

**What goes wrong:** Hardcoded references to "output/final" in code cause runtime errors after directory removal.

**Why it happens:** Directory may exist in multiple places: config defaults, documentation, old code paths.

**How to avoid:**
1. Grep for all references: `rg "output/final"` in codebase
2. Check if any are in active code (not just docs/plans)
3. Verify config.py uses "output/review" not "output/final"
4. Check VideoCompositor constructor default

**Current status:** Phase 5 already changed config.py to `composition_output_dir = "output/review"`. The only remaining reference is in VideoCompositor constructor docstring/default parameter (app/services/video_compositor/compositor.py:31). This needs to be updated to match config.py.

**Warning signs:**
- FileNotFoundError when composing videos
- Videos appear in wrong directory
- Config mismatch between settings and code defaults

## Code Examples

### Example 1: Fixed POST /generate-content Endpoint

```python
# File: app/api/routes.py
# Location: Line 172-177 (current)

@router.post("/generate-content")
async def trigger_content_generation(
    job_id: Optional[int] = None,
    theme_config_path: Optional[str] = None,
    session: AsyncSession = Depends(get_session)
):
    """Trigger full content generation pipeline (config -> script -> video -> voiceover).

    Creates a Job record if job_id not provided (manual invocation).
    """
    from app.tasks import generate_content_task
    from app.models import Job

    # Create Job record if manual invocation
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
```

### Example 2: Fixed POST /compose-video Endpoint

```python
# File: app/api/routes.py
# Location: Line 244-253 (current)

@router.post("/compose-video")
async def trigger_video_composition(
    script_id: int,
    video_path: str,
    audio_path: str,
    job_id: Optional[int] = None,
    cost_data: Optional[dict] = None,
    session: AsyncSession = Depends(get_session)
):
    """Trigger video composition task with text overlays and audio mixing.

    Creates a Job record if job_id not provided (manual invocation).
    """
    from app.tasks import compose_video_task
    from app.models import Job

    # Create Job record if manual invocation
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

    # IMPORTANT: job_id is first parameter (Phase 7 signature)
    task = compose_video_task.delay(job_id, script_id, video_path, audio_path, cost_data)
    return {
        "task_id": str(task.id),
        "job_id": job_id,
        "status": "queued",
        "description": "Composing final video..."
    }
```

### Example 3: Verify Task Signatures (No Changes Needed)

```python
# File: app/tasks.py
# These signatures were already fixed in Phase 7 — no changes needed in Phase 9

@celery_app.task(bind=True, name='app.tasks.generate_content_task', ...)
def generate_content_task(self, job_id: int, theme_config_path: Optional[str] = None):
    # job_id is required (not Optional) — endpoint ensures it's always provided
    logger.info(f"Starting content generation for job {job_id}")
    # ... task implementation

@celery_app.task(bind=True, name='app.tasks.compose_video_task', ...)
def compose_video_task(self, job_id: int, script_id: int, video_path: str, audio_path: str, cost_data: dict = None):
    # job_id is first parameter (Phase 7 change)
    logger.info(f"Starting video composition for job {job_id}, script {script_id}")
    # ... task implementation
```

### Example 4: Remove output/final Reference in VideoCompositor

```python
# File: app/services/video_compositor/compositor.py
# Location: Line 31-36 (current)

# BEFORE (stale reference to output/final):
class VideoCompositor:
    def __init__(self, output_dir: str = "output/final"):
        """Initialize video compositor.

        Args:
            output_dir: Directory for output videos (default: output/final)
        """

# AFTER (aligned with config.py):
class VideoCompositor:
    def __init__(self, output_dir: str = "output/review"):
        """Initialize video compositor.

        Args:
            output_dir: Directory for output videos (default: output/review)
        """
```

**Note:** This change aligns the code default with the config.py setting established in Phase 5. The actual output directory is still controlled by `settings.composition_output_dir` when VideoCompositor is instantiated in tasks.py, so this is primarily a documentation/fallback alignment.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Manual endpoints invoke tasks directly without job context | All tasks require job_id for data lineage | Phase 7 (2026-02-14) | Manual endpoints broke, need Job creation layer |
| Videos output to output/final/ | Videos output to output/review/ for approval workflow | Phase 5 (2026-02-14) | output/final/ directory is now unused legacy artifact |
| FastAPI query params using str &#124; None syntax | Python 3.9 compatibility requires Optional[T] | Project-wide | Must use `from typing import Optional` not `str &#124; None` |

**Deprecated/outdated:**
- **output/final/ directory**: Created in Phase 4, replaced by output/review/ in Phase 5, now empty and unused
- **Manual task invocation without job_id**: Phase 7 refactor made job_id mandatory for data lineage

## Open Questions

None. All information needed to plan this phase is available:

1. **Endpoint locations**: routes.py:172 (POST /generate-content) and routes.py:244 (POST /compose-video)
2. **Task signatures**: Already fixed in Phase 7, documented in 07-01-PLAN.md
3. **Database models**: Job model exists with all required fields (models.py:9-20)
4. **Config settings**: composition_output_dir correctly set to "output/review" (config.py:49)
5. **Output directory status**: output/final/ exists but is empty (verified with ls -la)

## Sources

### Primary (HIGH confidence)

- **Codebase inspection:**
  - `/Users/naokitsk/Documents/short-video-generator/app/api/routes.py` — Current endpoint signatures (lines 172-177, 244-253)
  - `/Users/naokitsk/Documents/short-video-generator/app/tasks.py` — Task signatures updated in Phase 7 (lines 100, 200)
  - `/Users/naokitsk/Documents/short-video-generator/app/models.py` — Job model definition (lines 9-20)
  - `/Users/naokitsk/Documents/short-video-generator/app/config.py` — composition_output_dir setting (line 49)
  - `/Users/naokitsk/Documents/short-video-generator/.planning/phases/07-pipeline-data-lineage/07-01-PLAN.md` — Phase 7 refactor details

- **v1.0 Milestone Audit:**
  - `.planning/v1.0-MILESTONE-AUDIT.md` — Documents exact integration gaps this phase closes (lines 13-14, 29-31)

### Secondary (MEDIUM confidence)

- [FastAPI Query Parameters](https://fastapi.tiangolo.com/tutorial/query-params/) — Official docs for optional parameters with defaults
- [Python typing.Optional documentation](https://docs.python.org/3/library/typing.html) — Official Python type hints reference
- [Real Python: Using Python Optional Arguments](https://realpython.com/python-optional-arguments/) — Best practices for optional parameters

### Tertiary (LOW confidence)

None required. All critical information verified from codebase and official documentation.

## Metadata

**Confidence breakdown:**
- Endpoint signatures and task signatures: HIGH — Direct codebase inspection, Phase 7 plan documents exact changes
- FastAPI optional parameter patterns: HIGH — Official FastAPI documentation and established patterns in existing codebase
- Job creation pattern: HIGH — Job model already exists, pattern used in POST /generate endpoint (routes.py:503-548)
- Output directory cleanup: HIGH — Grep confirmed only one code reference, directory exists but empty

**Research date:** 2026-02-14
**Valid until:** 90 days (stable API patterns, no fast-moving dependencies)

**No unknowns or gaps.** All information needed to create detailed PLAN.md files is available.
