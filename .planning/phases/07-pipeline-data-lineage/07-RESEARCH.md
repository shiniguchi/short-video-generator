# Phase 7: Pipeline Data Lineage - Research

**Researched:** 2026-02-14
**Domain:** Database foreign key relationships, async SQLAlchemy patterns, Celery task parameter passing
**Confidence:** HIGH

## Summary

Phase 7 addresses critical data lineage gaps identified in the v1.0 milestone audit: Job records cannot trace to their Script and Video outputs because `job_id` is never propagated through the pipeline task chain. This is a pure integration fix — no new features, just wiring existing foreign keys correctly.

The research reveals three discrete fixes needed:
1. **Pipeline orchestrator** must pass `job_id` to downstream tasks (trivial — add kwargs to existing task calls)
2. **Script generator** must accept and populate `Script.job_id` (simple — add parameter to existing async function)
3. **Video compositor** must accept and populate `Video.job_id` (simple — add parameter to existing Celery task)

All database schema is already correct (foreign keys exist on both Script and Video models). No migrations needed. No new libraries required. This is pure parameter threading.

**Primary recommendation:** Implement all three fixes in a single atomic plan. The fixes are tightly coupled (breaking one breaks the chain) and total code changes are minimal (~15 lines across 3 files).

## Standard Stack

### Core (Already in Use)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| SQLAlchemy | 2.x (async) | ORM with foreign key relationships | De facto Python ORM, excellent async support, foreign keys are core feature |
| aiosqlite | latest | SQLite async driver | Required for async SQLAlchemy with SQLite |
| Celery | 5.x | Task queue with parameter passing | Industry standard for Python async task orchestration |
| Pydantic | 2.x | Schema validation | Already used throughout codebase for request/response validation |

### Supporting (No Additional Libraries Needed)

This phase requires **zero new dependencies**. All necessary functionality exists in the current stack:
- SQLAlchemy ForeignKey columns already defined in models.py
- Celery task signatures support kwargs natively
- asyncio.run() pattern already established for sync→async bridges

### Why No New Libraries

Foreign key population is core SQLAlchemy functionality. Passing parameters through Celery tasks is core Celery functionality. This phase is pure integration work using existing primitives.

## Architecture Patterns

### Pattern 1: Async Foreign Key Population in Sync Context

**What:** Celery tasks are synchronous but must write to async database. Use `asyncio.run()` to bridge.

**When to use:** When a Celery task (sync) needs to create/update database records with foreign key relationships.

**Example (from current codebase):**
```python
# In tasks.py (sync Celery task)
from app.services.script_generator import save_production_plan

# Call async function from sync context
script_id = asyncio.run(save_production_plan(
    plan_data=plan,
    theme_config=config.model_dump(),
    trend_report_id=trend_report_id,
    job_id=job_id  # ← NEW: Pass job_id through
))
```

**Source:** Already used in tasks.py lines 140-144 (Phase 3), compose_video_task lines 311-318 (Phase 4). Pattern is proven and working.

### Pattern 2: Task Parameter Threading

**What:** Pass context parameters (like job_id) through Celery task chain by adding them to task signatures.

**When to use:** When downstream tasks need context from the orchestrator that isn't part of their return values.

**Example:**
```python
# In pipeline.py orchestrate_pipeline_task
task_func.apply_async(args=[job_id, *other_args])  # Pass job_id as first arg

# In tasks.py
@celery_app.task
def generate_content_task(self, job_id: int, theme_config_path: Optional[str] = None):
    # job_id now available throughout task
    script_id = asyncio.run(save_production_plan(..., job_id=job_id))
```

**Source:** [Celery Calling Tasks Documentation](https://docs.celeryq.dev/en/stable/userguide/calling.html) — tasks accept args/kwargs like normal Python functions.

### Pattern 3: Chained Task Parameter Preservation

**What:** When chaining tasks (content_generation → composition), preserve job_id by passing explicitly.

**When to use:** In Phase 7, compose_video_task is chained from generate_content_task and needs job_id.

**Example:**
```python
# In generate_content_task (tasks.py line 173)
compose_result = compose_video_task.delay(
    job_id,  # ← NEW: Pass job_id as first parameter
    script_id,
    video_path,
    audio_path,
    cost_data
)
```

**Note:** Celery's immutable signatures are NOT needed here because we're explicitly passing job_id, not relying on return value propagation.

**Source:** [Celery Canvas Documentation](https://docs.celeryq.dev/en/stable/userguide/canvas.html) — explicit parameters override chain propagation.

### Pattern 4: Query by Foreign Key (Post-Implementation Verification)

**What:** After pipeline runs, verify Job can query its Script/Video outputs.

**When to use:** In verification testing and future API endpoints (e.g., GET /jobs/{id}/outputs).

**Example:**
```python
# Future API endpoint pattern (not implemented in Phase 7)
from app.models import Job, Script, Video

# Query scripts for a job
scripts = await session.execute(
    select(Script).where(Script.job_id == job_id)
)

# Query videos for a job
videos = await session.execute(
    select(Video).where(Video.job_id == job_id)
)
```

**Async consideration:** Because foreign keys are simple scalar values (integers), no eager loading needed. Direct queries are efficient.

**Source:** [SQLAlchemy Async Documentation](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html) — scalar foreign keys don't trigger implicit IO.

### Anti-Patterns to Avoid

- **Don't add relationship() objects to models.py:** Foreign keys are sufficient. SQLAlchemy relationship() with lazy loading causes async context errors. We only need to store job_id integers, not navigate object graphs.
  - **Why:** Per [SQLAlchemy Async Discussion #7934](https://github.com/sqlalchemy/sqlalchemy/discussions/7934), lazy loading in async contexts requires explicit eager loading strategies. Overkill for our use case.

- **Don't use Celery task chains with return value propagation:** Explicitly pass job_id as a parameter instead of returning it and relying on chain() to thread it through.
  - **Why:** Return values are for business logic results (script_id, video_path), not context. Mixing the two creates confusion.

- **Don't modify Job.extra_data to store script_id/video_id:** Use foreign keys in Script/Video tables, not reverse references in Job.extra_data.
  - **Why:** Database foreign keys enable indexed queries. JSON fields don't.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Foreign key relationship navigation | Custom JSON lookup in Job.extra_data | SQLAlchemy ForeignKey columns | Database indexes, referential integrity, standard SQL queries |
| Async database writes from sync Celery | Threading or multiprocessing | asyncio.run() | Already established pattern, single-threaded simplicity, no race conditions |
| Task parameter passing | Global state or Redis side-channel | Celery task kwargs | Built-in, type-safe, visible in task signatures |

**Key insight:** Foreign key propagation is solved infrastructure — just thread the parameters through. Don't reinvent async bridges or invent custom tracking mechanisms.

## Common Pitfalls

### Pitfall 1: Forgetting to Pass job_id Through Full Chain

**What goes wrong:** You pass job_id to generate_content_task but forget to thread it to compose_video_task. Video.job_id remains NULL.

**Why it happens:** The chained task (compose_video_task) is called from within generate_content_task, not directly by the orchestrator. Easy to forget the intermediate step.

**How to avoid:**
1. Update orchestrator to pass job_id → ✓
2. Update generate_content_task to receive job_id → ✓
3. Update generate_content_task to pass job_id to compose_video_task → **Critical: Don't forget this**
4. Update compose_video_task to receive and use job_id → ✓

**Warning signs:** After implementation, run full pipeline and query Video table. If Video.job_id is NULL, you forgot step 3.

### Pitfall 2: Not Updating Task Signature to Match New Parameters

**What goes wrong:** You add job_id parameter to save_production_plan() but forget to update the call site in generate_content_task. TypeError at runtime.

**Why it happens:** Changes span multiple files (pipeline.py → tasks.py → script_generator.py). Easy to update one without updating callers.

**How to avoid:**
- Use type hints in function signatures so IDE catches mismatches
- Test immediately after each change (don't implement all 3 fixes blindly)
- Grep for function names to find all call sites: `rg "save_production_plan"`, `rg "compose_video_task.delay"`

**Warning signs:** Celery task failures with TypeError: missing required positional argument.

### Pitfall 3: Using relationship() Without Eager Loading in Async

**What goes wrong:** You add `relationship("Job", back_populates="scripts")` to Script model and try to access `script.job` in an async context. SQLAlchemy raises "greenlet_spawn has not been called" error.

**Why it happens:** SQLAlchemy's lazy loading tries to issue a SQL query when you access `script.job`, but AsyncSession doesn't allow implicit queries outside async context.

**How to avoid:** Don't add relationship() objects at all for this phase. You only need to store job_id integers, not navigate from Script→Job. If you ever need reverse navigation, use explicit queries (Pattern 4 above).

**Warning signs:** "greenlet" errors, "cannot perform IO" errors when accessing relationship attributes.

**Source:** [SQLAlchemy Async Documentation](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html#preventing-implicit-io-when-using-asyncsession)

### Pitfall 4: Null job_id Due to Orchestrator Calling Without job_id Kwarg

**What goes wrong:** You update save_production_plan(job_id=None) with default None, but orchestrator still calls tasks without job_id kwarg. Script.job_id stays NULL.

**Why it happens:** Default parameters mask the missing kwarg — no error raised, just silent NULL insertion.

**How to avoid:**
- Make job_id required (no default) in final implementation
- During development, use default=None and log warnings when job_id is None
- Verification step: query for NULL job_id records after test pipeline run

**Warning signs:** Pipeline succeeds but Job → Script/Video foreign keys remain NULL in database.

## Code Examples

Verified patterns from codebase and official sources:

### Example 1: Update Orchestrator to Pass job_id

```python
# In app/pipeline.py orchestrate_pipeline_task (lines 214-218)
stage_tasks = [
    (STAGE_TREND_COLLECTION, collect_trends_task, []),
    (STAGE_TREND_ANALYSIS, analyze_trends_task, []),
    (STAGE_CONTENT_GENERATION, generate_content_task, [job_id, theme_config_path]),  # ← CHANGE: Add job_id
]
```

**Note:** job_id must be first arg because generate_content_task signature changes to (self, job_id: int, theme_config_path: Optional[str]).

### Example 2: Update generate_content_task Signature and Pass to save_production_plan

```python
# In app/tasks.py generate_content_task (line 100)
@celery_app.task(...)
def generate_content_task(self, job_id: int, theme_config_path: Optional[str] = None):  # ← CHANGE: Add job_id parameter
    logger.info(f"Starting content generation for job {job_id}")

    # ... existing code ...

    # In save_production_plan call (line 140)
    script_id = asyncio.run(save_production_plan(
        plan_data=plan,
        theme_config=config.model_dump(),
        trend_report_id=trend_report_id,
        job_id=job_id  # ← CHANGE: Pass job_id
    ))
```

### Example 3: Update save_production_plan to Accept and Populate job_id

```python
# In app/services/script_generator.py save_production_plan (line 357)
async def save_production_plan(
    plan_data: dict,
    theme_config: dict,
    trend_report_id: Optional[int] = None,
    job_id: Optional[int] = None  # ← CHANGE: Add parameter
) -> int:
    """Save production plan to database.

    Args:
        plan_data: Dict matching VideoProductionPlanCreate schema
        theme_config: Theme config snapshot to store
        trend_report_id: Optional ID of trend report used
        job_id: Optional ID of Job orchestrating this pipeline run
    """
    from app.models import Script
    from app.database import async_session_factory

    async with async_session_factory() as session:
        script = Script(
            job_id=job_id,  # ← CHANGE: Populate foreign key
            video_prompt=plan_data['video_prompt'],
            # ... rest of fields unchanged ...
        )

        session.add(script)
        await session.commit()
        await session.refresh(script)

        logger.info(f"Saved production plan as Script ID {script.id} for Job {job_id}")
        return script.id
```

### Example 4: Update compose_video_task to Receive and Populate job_id

```python
# In app/tasks.py compose_video_task (line 199)
@celery_app.task(...)
def compose_video_task(self, job_id: int, script_id: int, video_path: str, audio_path: str, cost_data: dict = None):  # ← CHANGE: Add job_id as first param
    """Compose final video with text overlays, audio mixing, and thumbnail generation.

    Args:
        job_id: Database ID of the Job orchestrating this pipeline run
        script_id: Database ID of the Script record containing text_overlays
        video_path: Path to generated video file
        audio_path: Path to generated voiceover audio file
        cost_data: Dict with claude_cost, tts_cost, video_gen_cost
    """
    logger.info(f"Starting video composition for job {job_id}, script {script_id}")

    # ... existing code ...

    # In _save_video_record call (line 311)
    async def _save_video_record(job_id: int, script_id: int, file_path: str, ...):  # ← CHANGE: Add job_id param
        from app.database import async_session_factory
        from app.models import Video

        async with async_session_factory() as session:
            video = Video(
                job_id=job_id,  # ← CHANGE: Populate foreign key
                script_id=script_id,
                file_path=file_path,
                # ... rest of fields unchanged ...
            )
            session.add(video)
            await session.commit()
            await session.refresh(video)
            return video.id

    video_id = asyncio.run(_save_video_record(
        job_id=job_id,  # ← CHANGE: Pass job_id
        script_id=script_id,
        # ... rest of args ...
    ))
```

### Example 5: Update generate_content_task Chain to Pass job_id

```python
# In app/tasks.py generate_content_task (line 173)
compose_result = compose_video_task.delay(
    job_id,  # ← CHANGE: Add job_id as first arg
    script_id,
    video_path,
    audio_path,
    cost_data
)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| NULL job_id in Script/Video | Populated job_id from orchestrator | Phase 7 (2026-02-14) | Enables data lineage queries, checkpoint auditability |
| Task results as sole return values | Context parameters (job_id) + return values | Phase 7 | Separates orchestration context from business results |
| No relationship between Job and outputs | Foreign key relationships | Schema exists (Phase 1), wiring added (Phase 7) | Job records can query their Script/Video outputs |

**Deprecated/outdated:**
- **Implicit task chains without context:** Celery's chain() return value propagation is fine for linear data flow, but context like job_id must be explicit.
- **JSON-based reverse lookups:** Storing script_id/video_id in Job.extra_data instead of using foreign keys in child tables.

## Open Questions

None. This is a straightforward integration fix with well-established patterns.

## Sources

### Primary (HIGH confidence)

- Codebase inspection: app/models.py (foreign keys already exist), app/pipeline.py (orchestrator structure), app/tasks.py (task signatures and asyncio.run patterns), app/services/script_generator.py (save_production_plan function)
- [Celery Calling Tasks Documentation](https://docs.celeryq.dev/en/stable/userguide/calling.html) - Official docs on task parameter passing
- [SQLAlchemy Async Documentation](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html) - Official async session patterns
- v1.0 Milestone Audit (.planning/v1.0-MILESTONE-AUDIT.md) - Gap identification

### Secondary (MEDIUM confidence)

- [Celery Canvas Documentation](https://docs.celeryq.dev/en/stable/userguide/canvas.html) - Task chaining patterns
- [SQLAlchemy Async Discussion #7934](https://github.com/sqlalchemy/sqlalchemy/discussions/7934) - Community discussion on backref/relationship pitfalls in async
- [The Async Side of SQLModel Relationships](https://arunanshub.hashnode.dev/the-async-side-of-sqlmodel-relationships-part-1) - Practical guide to async relationship patterns

### Tertiary (LOW confidence)

None required. Official docs and codebase inspection are sufficient.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - No new libraries, using existing SQLAlchemy/Celery features
- Architecture: HIGH - Patterns already proven in codebase (asyncio.run in tasks.py, foreign keys in models.py)
- Pitfalls: HIGH - Based on codebase inspection and official async SQLAlchemy warnings

**Research date:** 2026-02-14
**Valid until:** 90 days (stable domain - foreign keys and task parameters are mature features)
