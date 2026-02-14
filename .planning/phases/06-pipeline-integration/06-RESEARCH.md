# Phase 6: Pipeline Integration - Research

**Researched:** 2026-02-14
**Domain:** Task pipeline orchestration, workflow state management, error recovery
**Confidence:** MEDIUM-HIGH

## Summary

Phase 6 integrates all prior phases (trend collection, pattern analysis, script generation, video generation, voiceover, composition, review) into a single orchestrated pipeline with per-stage checkpointing, retry logic, and real-time status monitoring. The system already has individual Celery tasks for each stage working in isolation. This phase adds: (1) orchestration layer that sequences all stages, (2) database-backed state tracking using the existing Job model, (3) resume-from-checkpoint capability after failures, and (4) REST API endpoints for triggering and monitoring pipeline runs.

**Critical architectural decisions already made:** Celery task queue is established, SQLAlchemy async database layer exists, Job model schema is defined but unused, individual stage tasks (collect_trends_task, analyze_trends_task, generate_content_task, compose_video_task) are implemented and tested.

**Primary technical challenges:**
1. Celery Canvas primitives (chains, groups, chords) don't natively support database-backed checkpointing - need custom implementation
2. Existing tasks are independent - need orchestration wrapper that tracks stage transitions in database
3. Task retry is per-task not per-pipeline - need to distinguish transient failures (retry stage) from permanent failures (fail pipeline)
4. Real-time status visibility requires task metadata updates and efficient query patterns
5. Resume-from-checkpoint requires mapping Job.stage to correct task entry point

**Primary recommendation:** Build a lightweight orchestration layer using the existing Job model for state persistence, wrap individual stage tasks in a master orchestrate_pipeline_task that updates Job status after each stage, implement stage-to-task mapping for resume capability, and expose FastAPI endpoints for trigger (POST /api/generate) and status (GET /api/jobs/{id}).

## Standard Stack

### Core (Already Installed)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| celery | 5.6.2 | Task queue & orchestration | Already in use, supports canvas primitives (chain, group, chord) for workflow composition |
| sqlalchemy | ^2.0 | Database state persistence | Already in use, async support for Job model updates |
| fastapi | >=0.100.0 | REST API endpoints | Already in use, provides /health, task trigger endpoints |
| aiosqlite | latest | Async SQLite operations | Already in use, enables non-blocking Job status updates |

### Supporting (Already Installed)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| tenacity | latest | Retry with exponential backoff | Already imported in requirements.txt, use for API call retries within tasks |
| pydantic | ^2.0 | Request/response validation | Already in use, validate POST /api/generate request body |

### No New Dependencies Required
Phase 6 uses existing libraries. Celery's built-in retry mechanisms (autoretry_for, retry_backoff, retry_jitter) handle exponential backoff. SQLAlchemy Job model handles state persistence. No orchestration framework (Airflow/Prefect/Dagster) needed - this is a simple 8-stage sequential pipeline.

**Installation:**
```bash
# All dependencies already installed
# No new packages required for Phase 6
```

## Architecture Patterns

### Recommended Pattern: Database-Backed Orchestration

**NOT using Celery Canvas chains** - Canvas primitives don't checkpoint to database, entire chain must restart on failure. Instead, use explicit stage sequencing with Job model updates.

**Pattern: Orchestrator Task + Stage Tasks**
```
orchestrate_pipeline_task (master)
├── Stage 1: collect_trends_task
├── Stage 2: analyze_trends_task
├── Stage 3: generate_content_task (includes script + video + voiceover)
└── Stage 4: compose_video_task (chained from generate_content_task)
```

Existing codebase already chains generate_content_task -> compose_video_task. Phase 6 adds orchestration wrapper that tracks all stages in Job model.

### Pattern 1: Job-Driven Pipeline Orchestration
**What:** Single orchestrate_pipeline_task that sequences all stages and updates Job model after each completion
**When to use:** For sequential multi-stage pipelines with checkpoint/resume requirements
**Example:**
```python
# app/tasks.py
@celery_app.task(bind=True, name='app.tasks.orchestrate_pipeline_task')
def orchestrate_pipeline_task(self, job_id: int, theme_config_path: Optional[str] = None):
    """Orchestrate full 8-stage pipeline with checkpointing."""

    # Helper to update job status
    def update_job(stage: str, status: str, error_msg: str = None):
        asyncio.run(_update_job_status(job_id, stage, status, error_msg))

    try:
        update_job(stage="trend_collection", status="running")
        collect_result = collect_trends_task.apply_async()
        collect_result.get()  # Block until complete (or raise exception)
        update_job(stage="trend_collection", status="completed")

        update_job(stage="trend_analysis", status="running")
        analyze_result = analyze_trends_task.apply_async()
        analyze_result.get()
        update_job(stage="trend_analysis", status="completed")

        update_job(stage="content_generation", status="running")
        content_result = generate_content_task.apply_async(args=[theme_config_path])
        content_data = content_result.get()
        # generate_content_task already chains into compose_video_task
        # Just need to wait for composition to complete
        compose_task_id = content_data.get("compose_task_id")
        if compose_task_id:
            compose_result = celery_app.AsyncResult(compose_task_id)
            compose_result.get()
        update_job(stage="composition", status="completed")

        # Final stage: review (manual, no task)
        update_job(stage="review", status="completed")

        # Mark job complete
        update_job(stage="review", status="completed")
        asyncio.run(_mark_job_complete(job_id))

        return {"status": "success", "job_id": job_id}

    except Exception as exc:
        logger.error(f"Pipeline failed at stage {stage}: {exc}")
        update_job(stage=stage, status="failed", error_msg=str(exc))
        raise

async def _update_job_status(job_id, stage, status, error_msg=None):
    from app.database import async_session_factory
    from app.models import Job
    from sqlalchemy import select

    async with async_session_factory() as session:
        query = select(Job).where(Job.id == job_id)
        result = await session.execute(query)
        job = result.scalars().first()
        if job:
            job.stage = stage
            job.status = status
            if error_msg:
                job.error_message = error_msg
            job.updated_at = datetime.now(timezone.utc)
            await session.commit()
```

### Pattern 2: Resume From Checkpoint
**What:** Skip completed stages when restarting failed pipeline
**When to use:** When retrying a failed pipeline run
**Example:**
```python
# app/tasks.py
def orchestrate_pipeline_task(self, job_id: int, theme_config_path: Optional[str] = None):
    """Orchestrate pipeline with resume-from-checkpoint."""

    # Load job to check current stage
    job = asyncio.run(_load_job(job_id))
    completed_stages = job.extra_data.get("completed_stages", []) if job.extra_data else []

    # Stage sequence with conditional execution
    stages = [
        ("trend_collection", collect_trends_task, []),
        ("trend_analysis", analyze_trends_task, []),
        ("content_generation", generate_content_task, [theme_config_path]),
    ]

    for stage_name, task_func, args in stages:
        if stage_name in completed_stages:
            logger.info(f"Skipping completed stage: {stage_name}")
            continue

        update_job(stage=stage_name, status="running")
        try:
            result = task_func.apply_async(args=args)
            result.get()  # Wait for completion
            update_job(stage=stage_name, status="completed")

            # Track completion
            completed_stages.append(stage_name)
            asyncio.run(_update_completed_stages(job_id, completed_stages))
        except Exception as exc:
            update_job(stage=stage_name, status="failed", error_msg=str(exc))
            raise
```

### Pattern 3: Task Status Polling Endpoint
**What:** REST endpoint that returns current pipeline status by querying Job model
**When to use:** For real-time monitoring from client applications
**Example:**
```python
# app/api/routes.py
@router.get("/jobs/{job_id}")
async def get_job_status(
    job_id: int,
    session: AsyncSession = Depends(get_session)
):
    """Get real-time pipeline status."""
    from app.models import Job
    from sqlalchemy import select

    query = select(Job).where(Job.id == job_id)
    result = await session.execute(query)
    job = result.scalars().first()

    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    return {
        "id": job.id,
        "status": job.status,  # pending, running, completed, failed
        "stage": job.stage,    # trend_collection, trend_analysis, content_generation, etc.
        "theme": job.theme,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
        "error_message": job.error_message,
        "extra_data": job.extra_data
    }
```

### Pattern 4: Manual Pipeline Trigger
**What:** POST /api/generate endpoint that creates Job record and triggers orchestrate_pipeline_task
**When to use:** Manual pipeline execution on demand
**Example:**
```python
# app/api/routes.py
@router.post("/generate")
async def trigger_pipeline(
    theme: Optional[str] = None,
    session: AsyncSession = Depends(get_session)
):
    """Trigger full pipeline execution."""
    from app.models import Job
    from app.tasks import orchestrate_pipeline_task
    from datetime import datetime, timezone

    # Create Job record
    job = Job(
        status="pending",
        stage="initialization",
        theme=theme or "default",
        created_at=datetime.now(timezone.utc),
        extra_data={"completed_stages": []}
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)

    # Trigger orchestration task
    task = orchestrate_pipeline_task.delay(job_id=job.id, theme_config_path=None)

    return {
        "job_id": job.id,
        "task_id": str(task.id),
        "status": "queued",
        "message": "Pipeline execution started"
    }
```

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Task retry with backoff | Custom retry loop with sleep() | Celery autoretry_for + retry_backoff | Celery built-in handles exponential backoff, jitter, max retries automatically |
| Result polling | Busy-wait loop checking task status | Celery AsyncResult.get() | Blocks efficiently using broker's result backend, no polling overhead |
| Task scheduling | Cron script calling tasks | Celery Beat | Native Celery scheduler with distributed lock support |
| Distributed locking | Redis SETNX or file locks | Celery task acks_late + worker concurrency | Celery handles task deduplication and prevents concurrent execution |
| Task timeout | No timeout enforcement | Celery time_limit + soft_time_limit | Hard and soft timeout enforcement with graceful shutdown |

**Key insight:** Celery already provides battle-tested solutions for distributed task execution, retries, timeouts, and scheduling. Don't reinvent these primitives - use Celery's configuration options.

## Common Pitfalls

### Pitfall 1: Blocking Event Loop in Async Context
**What goes wrong:** Calling result.get() or asyncio.run() inside async function blocks event loop
**Why it happens:** Mixing sync Celery task calls with async FastAPI endpoints
**How to avoid:** In FastAPI endpoints, only create Job and trigger task.delay() - don't wait for result. Client polls GET /jobs/{id} for status updates.
**Warning signs:** FastAPI endpoints timing out, workers hanging, "Task X is hanging" logs

### Pitfall 2: Infinite Task Retries
**What goes wrong:** Task retries forever on permanent failures (bad config, missing API key)
**Why it happens:** autoretry_for=(Exception,) catches all exceptions including non-transient ones
**How to avoid:** Set max_retries=3 explicitly. Catch config errors in task and raise without retry. Distinguish transient (network timeout) from permanent (404 not found) failures.
**Warning signs:** Tasks retrying hundreds of times, queue growing unbounded, worker CPU at 100%

### Pitfall 3: Lost Task Results
**What goes wrong:** Pipeline fails but no record of which stage failed or why
**Why it happens:** Not persisting stage transitions to database, relying only on Celery result backend
**How to avoid:** Update Job model after every stage transition (running, completed, failed). Store error messages in Job.error_message. Use extra_data for detailed context.
**Warning signs:** "It failed but I don't know where", no audit trail, can't debug production failures

### Pitfall 4: Non-Idempotent Operations
**What goes wrong:** Pipeline retries duplicate database writes, API calls, file creations
**Why it happens:** Not designing tasks to be safely retriable
**How to avoid:** Use database UPSERT for trends (already implemented with unique constraint). Check if Video/Script exists before creating. Use idempotency keys for external API calls. Skip stages already marked completed in Job.extra_data.
**Warning signs:** Duplicate database records, double-billing from APIs, multiple identical files

### Pitfall 5: Chaining Without Error Propagation
**What goes wrong:** Stage 2 starts even though Stage 1 failed
**Why it happens:** Using task.delay() instead of task.apply_async() with link_error
**How to avoid:** Use apply_async().get() to block and propagate exceptions. Or use Celery canvas chain() which stops on first failure. Update Job.status="failed" before raising.
**Warning signs:** Pipeline continues after failure, later stages receive invalid inputs, cascading failures

### Pitfall 6: Hardcoded Stage Names
**What goes wrong:** Adding new stage requires updating code in 5+ places
**Why it happens:** Stage names duplicated across orchestrator, resume logic, status endpoint, constants
**How to avoid:** Define stage constants at module level: `STAGE_TREND_COLLECTION = "trend_collection"`. Use enum or list for stage sequence. Single source of truth for stage names.
**Warning signs:** Typos in stage names ("analsis" vs "analysis"), inconsistent naming, brittle resume logic

## Code Examples

Verified patterns from Celery documentation and FastAPI integration guides:

### Celery Task Retry Configuration (Standard)
```python
# Source: https://docs.celeryq.dev/en/stable/userguide/tasks.html
@celery_app.task(
    bind=True,
    max_retries=3,
    autoretry_for=(Exception,),
    retry_backoff=True,        # Exponential: 1s, 2s, 4s, 8s...
    retry_backoff_max=600,     # Cap at 10 minutes
    retry_jitter=True,         # Add randomness to prevent thundering herd
)
def my_task(self):
    # Task implementation
    pass
```

### Job Status Update Helper (Database Pattern)
```python
# Pattern for async database updates from sync Celery tasks
async def _update_job_status(job_id: int, stage: str, status: str, error_msg: str = None):
    from app.database import async_session_factory
    from app.models import Job
    from sqlalchemy import select
    from datetime import datetime, timezone

    async with async_session_factory() as session:
        query = select(Job).where(Job.id == job_id)
        result = await session.execute(query)
        job = result.scalars().first()

        if not job:
            raise ValueError(f"Job {job_id} not found")

        job.stage = stage
        job.status = status
        job.updated_at = datetime.now(timezone.utc)

        if error_msg:
            job.error_message = error_msg

        await session.commit()
        await session.refresh(job)
        return job
```

### FastAPI Non-Blocking Task Trigger
```python
# Source: FastAPI + Celery integration best practices
@router.post("/generate")
async def trigger_pipeline(
    theme: Optional[str] = None,
    session: AsyncSession = Depends(get_session)
):
    """Trigger pipeline without blocking response."""
    from app.models import Job
    from app.tasks import orchestrate_pipeline_task

    # Create Job record
    job = Job(status="pending", stage="initialization", theme=theme)
    session.add(job)
    await session.commit()
    await session.refresh(job)

    # Trigger async task (non-blocking)
    task = orchestrate_pipeline_task.delay(job_id=job.id)

    # Return immediately with job_id for status polling
    return {
        "job_id": job.id,
        "task_id": str(task.id),
        "status": "queued",
        "poll_url": f"/api/jobs/{job.id}"
    }
```

### Stage Checkpoint Pattern
```python
# Track completed stages for resume capability
async def _mark_stage_complete(job_id: int, stage: str):
    from app.database import async_session_factory
    from app.models import Job
    from sqlalchemy import select

    async with async_session_factory() as session:
        query = select(Job).where(Job.id == job_id)
        result = await session.execute(query)
        job = result.scalars().first()

        if not job.extra_data:
            job.extra_data = {}

        if "completed_stages" not in job.extra_data:
            job.extra_data["completed_stages"] = []

        if stage not in job.extra_data["completed_stages"]:
            job.extra_data["completed_stages"].append(stage)

        job.stage = stage
        job.status = "running"
        job.updated_at = datetime.now(timezone.utc)

        await session.commit()
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Celery Canvas chains | Database-backed orchestration | 2024+ | Canvas primitives (chain, chord) don't checkpoint to persistent storage. Entire chain restarts on failure. Modern pattern: explicit stage sequencing with database state. |
| Polling Celery result backend | WebSocket or Server-Sent Events | 2025+ | Real-time updates without polling. For this project: stick with polling (simpler, FastAPI SSE requires extra setup). |
| Monolithic orchestrator task | Task DAG with dependencies | 2023+ | Airflow/Prefect/Dagster popularized DAG pattern. For simple sequential pipelines: overkill. Use when >20 tasks with complex dependencies. |
| Fire-and-forget tasks | Saga pattern with compensating actions | 2024+ | Distributed transactions need rollback logic. This project: not critical (content generation failures are acceptable, just retry). |

**Deprecated/outdated:**
- **Celery Canvas for stateful workflows**: Canvas is great for fire-and-forget fan-out, but doesn't persist intermediate state. Use database checkpoints for resume capability.
- **Synchronous task result waiting**: `result.get()` blocks worker. Better: store job_id in database, client polls status endpoint.
- **Hardcoded retry counts**: Modern approach uses exponential backoff with jitter (retry_backoff=True, retry_jitter=True) to prevent thundering herd.

## Open Questions

1. **Question: Should pipeline support partial restart (resume from specific stage)?**
   - What we know: Job.extra_data can store completed_stages list
   - What's unclear: UI/API for "restart from stage X" vs "restart from last checkpoint"
   - Recommendation: Implement automatic resume from last checkpoint. Manual stage selection is nice-to-have, defer to post-MVP.

2. **Question: How to handle stage dependencies (e.g., skip trend analysis if no new trends)?**
   - What we know: analyze_trends_task already handles empty result (returns "skipped")
   - What's unclear: Should orchestrator skip downstream stages if upstream returns "skipped"?
   - Recommendation: Let each stage handle empty inputs gracefully. Orchestrator always runs all stages. Stage-level early return is cleaner than orchestrator logic.

3. **Question: Should failed jobs support manual retry via API?**
   - What we know: Can create new Job and copy theme/config from failed job
   - What's unclear: POST /api/jobs/{id}/retry vs DELETE failed job + POST /api/generate?
   - Recommendation: Implement POST /api/jobs/{id}/retry that resets status to "pending" and re-triggers orchestrate_pipeline_task with same job_id. Checkpoint resume will skip completed stages automatically.

## Sources

### Primary (HIGH confidence)
- [Canvas: Designing Work-flows — Celery 5.6.2 documentation](https://docs.celeryq.dev/en/stable/userguide/canvas.html) - Official Celery canvas primitives (chains, groups, chords)
- [Tasks — Celery 5.6.2 documentation](https://docs.celeryq.dev/en/stable/userguide/tasks.html) - Task retry configuration, autoretry_for, retry_backoff
- [Celery Result Backends: Options, Configurations & Best Practices | PythonRoadmap](https://pythonroadmap.com/blog/celery-result-backends-options-and-best-practices) - Database result backend with SQLAlchemy
- [Asynchronous Tasks with FastAPI and Celery | TestDriven.io](https://testdriven.io/blog/fastapi-and-celery/) - FastAPI + Celery integration patterns

### Secondary (MEDIUM confidence)
- [Building a Production Grade Workflow Orchestrator with Celery | ITNEXT](https://itnext.io/building-a-production-grade-workflow-orchestrator-with-celery-ad2d48aa054d) - Database-backed checkpointing patterns
- [Celery: The Complete Guide for 2026 | DevToolbox Blog](https://devtoolbox.dedyn.io/blog/celery-complete-guide) - Current best practices including Flower monitoring
- [GitHub - mher/flower: Real-time monitor and web admin for Celery](https://github.com/mher/flower) - Celery monitoring dashboard (optional for production)
- [DBOS (Database Operating System) — DBOS Transact Python](https://github.com/dbos-inc/dbos-transact-py) - Postgres-backed workflow checkpointing (alternative pattern, not used)

### Tertiary (LOW confidence, marked for validation)
- [Retry pattern - Azure Architecture Center](https://learn.microsoft.com/en-us/azure/architecture/patterns/retry) - General retry best practices (cloud-agnostic)
- [Idempotency in Distributed Systems | AlgoMaster.io](https://algomaster.io/learn/system-design/idempotency) - Idempotency patterns for task design
- Web search results on "POST /api/generate pipeline trigger endpoint design best practices" - Various CI/CD platforms (GitLab, Azure DevOps, CircleCI) use POST for pipeline triggers

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All libraries already installed and in use
- Architecture patterns: HIGH - Database orchestration pattern verified in codebase (Job model exists, async patterns established)
- Pitfalls: MEDIUM-HIGH - Based on Celery documentation + common production issues
- Code examples: HIGH - Verified against Celery 5.6.2 docs and existing codebase patterns

**Research date:** 2026-02-14
**Valid until:** 60 days (Celery stable, patterns unlikely to change)
