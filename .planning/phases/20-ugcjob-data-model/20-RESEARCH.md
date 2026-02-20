# Phase 20: UGCJob Data Model - Research

**Researched:** 2026-02-20
**Domain:** SQLAlchemy ORM, Alembic migrations, python-statemachine 2.x, PostgreSQL state tracking
**Confidence:** HIGH

## Summary

Phase 20 introduces a dedicated `UGCJob` SQLAlchemy model that persists all UGC pipeline state in PostgreSQL. The existing `Job` model in `app/models.py` stores UGC pipeline state in a generic `extra_data` JSON blob — this must NOT be reused. A new table `ugc_jobs` gets typed columns for each stage output.

State transitions are guarded by python-statemachine 2.6.0, which is NOT yet in `requirements.txt` and must be added. The DB column `status` remains the source of truth — the state machine is a guard layer only (validates transitions, never owns state).

The Alembic migration pattern is already established in the project (5 existing migrations). The new migration will be `006_ugcjob_schema.py`. The project uses async SQLAlchemy with asyncpg for PostgreSQL and aiosqlite for SQLite (local dev).

**Primary recommendation:** Add `UGCJob` as a new SQLAlchemy model in `app/models.py`, write a hand-crafted Alembic migration `006_ugcjob_schema.py`, and define a `UGCJobStateMachine` class using python-statemachine 2.6.0 with the DB column as source of truth.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| SQLAlchemy | 2.0.46 (already installed) | ORM model definition | Already used for all DB models |
| Alembic | 1.16.5 (already installed) | Schema migrations | Already used, 5 existing migrations |
| python-statemachine | 2.6.0 (NOT YET INSTALLED) | State transition guard layer | Explicitly specified in phase decisions |
| asyncpg | 0.31.0 (already installed) | Async PostgreSQL driver | Already used |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| aiosqlite | 0.22.1 (already installed) | Local dev SQLite async driver | SQLite DB URL for dev |
| pydantic | 2.12.5 (already installed) | Schema validation for API responses | UGCJob response schemas |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| python-statemachine | transitions (0.9.x) | transitions has no typed enum support; python-statemachine is specified by phase |
| python-statemachine | manual string validation | Would miss invalid transitions silently; state machine raises TransitionNotAllowed |
| typed columns | JSON blob extra_data | JSON loses type safety, indexing, and query performance on status |

**Installation:**
```bash
pip install python-statemachine==2.6.0
# Add to requirements.txt
```

## Architecture Patterns

### Recommended Project Structure
```
app/
├── models.py            # Add UGCJob model here (alongside existing models)
├── schemas.py           # Add UGCJobResponse schema
├── state_machines/
│   └── ugc_job.py       # UGCJobStateMachine (new file)
alembic/
└── versions/
    └── 006_ugcjob_schema.py   # New migration
```

### Pattern 1: UGCJob SQLAlchemy Model — Typed Columns Per Stage

**What:** Each pipeline stage has its own typed column(s), not a JSON blob.
**When to use:** Always for UGC jobs — enables per-column indexing and type-safe queries.

UGC pipeline stages from `tasks.py` (`generate_ugc_ad_task`):
1. `product_analysis` — outputs: category, ugc_style, emotional_tone, visual_keywords
2. `hero_image` — output: hero_image_path
3. `script` — output: master_script (JSON), aroll_scenes (JSON), broll_shots (JSON)
4. `aroll` — output: aroll_paths (JSON list of paths)
5. `broll` — output: broll_paths (JSON list of paths)
6. `composition` — output: final_video_path

Status machine values (from phase decisions): `pending`, `running`, `stage_N_review`, `approved`, `failed`

```python
# app/models.py — add after LandingPage model
from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, Float
from sqlalchemy.sql import func

class UGCJob(Base):
    """UGC product ad pipeline job — all state persists in DB."""
    __tablename__ = "ugc_jobs"

    id = Column(Integer, primary_key=True)

    # --- Input ---
    product_name = Column(String(500), nullable=False)
    description = Column(Text, nullable=False)
    product_url = Column(String(1000), nullable=True)
    product_image_paths = Column(JSON, nullable=True)   # list of uploaded paths
    target_duration = Column(Integer, default=30)
    style_preference = Column(String(100), nullable=True)
    use_mock = Column(Boolean, default=True)            # passed explicitly, never from settings

    # --- State machine ---
    status = Column(String(50), nullable=False, default="pending")
    # Values: pending | running | stage_analysis_review | stage_script_review |
    #         stage_aroll_review | stage_broll_review | stage_composition_review |
    #         approved | failed
    error_message = Column(Text, nullable=True)

    # --- Stage 1: Product Analysis ---
    analysis_category = Column(String(200), nullable=True)
    analysis_ugc_style = Column(String(200), nullable=True)
    analysis_emotional_tone = Column(String(200), nullable=True)
    analysis_key_features = Column(JSON, nullable=True)    # list[str]
    analysis_visual_keywords = Column(JSON, nullable=True) # list[str]
    analysis_target_audience = Column(String(500), nullable=True)

    # --- Stage 2: Hero Image ---
    hero_image_path = Column(String(1000), nullable=True)

    # --- Stage 3: Script ---
    master_script = Column(JSON, nullable=True)      # MasterScript dict
    aroll_scenes = Column(JSON, nullable=True)        # list[ArollScene dict]
    broll_shots = Column(JSON, nullable=True)         # list[BrollShot dict]

    # --- Stage 4: A-Roll ---
    aroll_paths = Column(JSON, nullable=True)         # list[str]

    # --- Stage 5: B-Roll ---
    broll_paths = Column(JSON, nullable=True)         # list[str]

    # --- Stage 6: Composition ---
    final_video_path = Column(String(1000), nullable=True)
    cost_usd = Column(Float, nullable=True)

    # --- Candidate (for regeneration) ---
    # Regeneration stores candidate here, never overwrites approved output
    candidate_video_path = Column(String(1000), nullable=True)

    # --- Timestamps ---
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    approved_at = Column(DateTime(timezone=True), nullable=True)
```

### Pattern 2: UGCJobStateMachine — Guard Layer Only

**What:** State machine validates transitions; DB column is source of truth.
**When to use:** Always instantiate with the `UGCJob` instance bound so state reads/writes go to the DB column.

```python
# app/state_machines/ugc_job.py
from statemachine import StateMachine, State

class UGCJobStateMachine(StateMachine):
    """Guard layer for UGCJob status transitions.

    DB column is source of truth. Instantiate with model bound:
        sm = UGCJobStateMachine(job, state_field="status")
    """
    pending = State(initial=True)
    running = State()
    stage_analysis_review = State()
    stage_script_review = State()
    stage_aroll_review = State()
    stage_broll_review = State()
    stage_composition_review = State()
    approved = State(final=True)
    failed = State(final=True)

    # Transitions
    start = pending.to(running)
    complete_analysis = running.to(stage_analysis_review)
    approve_analysis = stage_analysis_review.to(running)
    reject_analysis = stage_analysis_review.to(failed)
    complete_script = running.to(stage_script_review)
    approve_script = stage_script_review.to(running)
    reject_script = stage_script_review.to(failed)
    complete_aroll = running.to(stage_aroll_review)
    approve_aroll = stage_aroll_review.to(running)
    reject_aroll = stage_aroll_review.to(failed)
    complete_broll = running.to(stage_broll_review)
    approve_broll = stage_broll_review.to(running)
    reject_broll = stage_broll_review.to(failed)
    complete_composition = running.to(stage_composition_review)
    approve_final = stage_composition_review.to(approved)
    reject_final = stage_composition_review.to(failed)
    fail = running.to(failed)
```

**Instantiation with model binding:**
```python
# Source: python-statemachine docs — model binding pattern
sm = UGCJobStateMachine(ugc_job, state_field="status", start_value=ugc_job.status)
sm.start()  # validates: pending -> running; writes ugc_job.status = "running"
await session.commit()  # DB write is the persistence step
```

### Pattern 3: Alembic Migration — Hand-Crafted (Project Standard)

The project uses hand-crafted migrations, NOT autogenerate. All 5 existing migrations are manual `op.create_table()` calls.

```python
# alembic/versions/006_ugcjob_schema.py
revision: str = '006'
down_revision: Union[str, None] = '039d14368a2d'  # last migration revision

def upgrade() -> None:
    op.create_table(
        'ugc_jobs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('product_name', sa.String(500), nullable=False),
        # ... all columns ...
        sa.Column('status', sa.String(50), nullable=False, server_default='pending'),
        sa.PrimaryKeyConstraint('id'),
    )

def downgrade() -> None:
    op.drop_table('ugc_jobs')
```

**CRITICAL:** `down_revision` must be `'039d14368a2d'` (the revision ID from migration 005, not `'005'`).

### Anti-Patterns to Avoid

- **Reusing `Job` model for UGC:** Phase decision explicitly forbids extending `_jobs` dict or `Job` model for UGC. `Job` tracks the old LP pipeline only.
- **State machine as source of truth:** Never read `sm.current_state.id` as canonical status — read `ugc_job.status` from DB.
- **Calling `get_settings().use_mock_data` inside tasks:** Phase decision requires `use_mock: bool` passed explicitly as argument, not read from singleton.
- **Mutating approved content on regeneration:** Store candidate in `candidate_video_path`, never overwrite `final_video_path` until explicit acceptance.
- **Using `autogenerate` for migration:** Project standard is hand-crafted migrations. `alembic revision --autogenerate` is not used.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| State transition validation | Custom if/elif status chain | python-statemachine 2.6.0 | Raises `TransitionNotAllowed` automatically; catches invalid jumps |
| Migration idempotency | Custom SQL checks | Alembic revision chain | Alembic tracks applied revisions in `alembic_version` table |
| Async DB session in Celery | New engine per call | `get_task_session_factory()` | Already handles NullPool + new event loop for Celery workers |

**Key insight:** The project already solved the Celery + asyncio event loop problem in `database.py` with `get_task_session_factory()`. All DB writes in Celery tasks must use this, not the module-level `engine`.

## Common Pitfalls

### Pitfall 1: Wrong `down_revision` in Migration
**What goes wrong:** Migration chain breaks; `alembic upgrade head` fails with "Can't locate revision".
**Why it happens:** Migration 005 has a non-sequential revision ID `039d14368a2d`, not `005`.
**How to avoid:** Set `down_revision = '039d14368a2d'` in migration 006.
**Warning signs:** `alembic history` shows a gap; `alembic upgrade head` raises revision not found.

### Pitfall 2: State Machine Owns State (Not DB)
**What goes wrong:** SM in-memory state diverges from DB after process restart.
**Why it happens:** Forgetting `start_value=ugc_job.status` at instantiation — SM starts at `pending` regardless of DB value.
**How to avoid:** Always pass `start_value=ugc_job.status` when constructing SM from an existing row.
**Warning signs:** Reloaded jobs always appear as `pending` even when `approved` in DB.

### Pitfall 3: `TransitionNotAllowed` in Celery Task Crashes Job
**What goes wrong:** Task raises uncaught exception, Celery retries, job status corrupts.
**Why it happens:** SM raises `TransitionNotAllowed` if a transition is called in wrong state.
**How to avoid:** Wrap SM calls in try/except; catch `TransitionNotAllowed` and call `_mark_job_failed()`.
**Warning signs:** Celery logs show `TransitionNotAllowed` before the retry.

### Pitfall 4: JSON Blob Columns for Stage Outputs
**What goes wrong:** Can't query by stage field; no index; type errors at runtime.
**Why it happens:** Lazy column design (reusing `extra_data` JSON).
**How to avoid:** Use typed columns per stage as shown in the model above. Script/scene data CAN be JSON since they're structured nested objects — but use `Column(JSON)` explicitly, not buried in a catch-all.
**Warning signs:** Queries like `WHERE extra_data->>'category' = 'tech'` instead of `WHERE analysis_category = 'tech'`.

### Pitfall 5: Missing `__init__.py` for state_machines package
**What goes wrong:** `from app.state_machines.ugc_job import UGCJobStateMachine` fails with ModuleNotFoundError.
**Why it happens:** New directory without `__init__.py`.
**How to avoid:** Create `app/state_machines/__init__.py` alongside `ugc_job.py`.

## Code Examples

Verified patterns from official sources and codebase:

### Creating UGCJob Row (API handler)
```python
# Mirrors existing Job creation pattern in app/api/routes.py
from app.models import UGCJob

job = UGCJob(
    product_name=product_name,
    description=description,
    product_image_paths=product_image_paths,
    use_mock=use_mock,
    status="pending",
)
session.add(job)
await session.commit()
await session.refresh(job)
```

### Writing Stage Output to DB (Celery task)
```python
# Use get_task_session_factory() — existing pattern from tasks.py
async def _save_analysis(job_id: int, analysis: ProductAnalysis) -> None:
    async with get_task_session_factory()() as session:
        query = select(UGCJob).where(UGCJob.id == job_id)
        result = await session.execute(query)
        job = result.scalars().first()
        job.analysis_category = analysis.category
        job.analysis_ugc_style = analysis.ugc_style
        job.analysis_emotional_tone = analysis.emotional_tone
        job.analysis_key_features = analysis.key_features
        job.analysis_visual_keywords = analysis.visual_keywords
        job.analysis_target_audience = analysis.target_audience
        job.status = "stage_analysis_review"
        job.updated_at = datetime.now(timezone.utc)
        await session.commit()

asyncio.run(_save_analysis(job_id, analysis))
```

### Validating Transition with State Machine
```python
# Guard check before proceeding
from statemachine.exceptions import TransitionNotAllowed
from app.state_machines.ugc_job import UGCJobStateMachine

async def _transition_job(job_id: int, event: str) -> None:
    async with get_task_session_factory()() as session:
        job = await _load_ugc_job(session, job_id)
        sm = UGCJobStateMachine(job, state_field="status", start_value=job.status)
        try:
            sm.send(event)  # e.g., "start", "complete_analysis"
        except TransitionNotAllowed as e:
            raise ValueError(f"Invalid transition '{event}' from '{job.status}'") from e
        job.updated_at = datetime.now(timezone.utc)
        await session.commit()
```

### Alembic Migration Run Command
```bash
# Apply on fresh DB
alembic upgrade head

# Apply on existing DB (idempotent — alembic_version table tracks applied)
alembic upgrade head

# Verify
alembic current
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `Job.extra_data` JSON blob for all UGC state | Typed `UGCJob` columns per stage | Phase 20 (now) | Enables per-stage queries, indexing, type safety |
| In-memory `_jobs` dict for UGC tracking | DB-persisted `UGCJob` row | Phase 20 (now) | Survives restarts, visible to all workers |
| No state machine guard | python-statemachine 2.6.0 guard layer | Phase 20 (now) | Invalid transitions raise exceptions instead of silently corrupting |
| SQLAlchemy 1.x `declarative_base` | SQLAlchemy 2.0 `declarative_base` (already used) | Existing | Async-native, future=True engine |

**Deprecated/outdated:**
- `sqlalchemy.ext.declarative.declarative_base`: Technically deprecated in SA 2.0 in favor of `sqlalchemy.orm.DeclarativeBase`. The project currently uses the old import — match it for consistency, don't upgrade in this phase.

## Open Questions

1. **Which review stages need per-stage review vs. full-pipeline approval only?**
   - What we know: Phase decision says `pending/running/stage_N_review/approved/failed`. "stage_N" is plural — implies multiple review points.
   - What's unclear: Does every stage (analysis, script, aroll, broll, composition) get its own `_review` state, or just the final composition?
   - Recommendation: Model all 5 `stage_*_review` states (future-proof). Unused transitions are cheap.

2. **`use_mock` column or task argument only?**
   - What we know: Phase decision says "Pass `use_mock: bool` explicitly through task chain. Do not mutate `get_settings()` singleton per request."
   - What's unclear: Does `use_mock` need to persist in the DB row (so retries replay with same setting) or is it only a task argument?
   - Recommendation: Store `use_mock` as a DB column — retries must reproduce original behavior.

3. **`product_image_paths` storage — paths or GCS/S3 URLs?**
   - What we know: Current code saves uploads to `output/uploads/` local paths.
   - What's unclear: Phase 20 only specifies the data model, not storage backend changes.
   - Recommendation: Store local paths in DB for now (`Column(JSON)` list of strings). Future phases can migrate to URLs.

## Sources

### Primary (HIGH confidence)
- Codebase: `app/models.py` — existing model patterns (Column types, Base, func.now())
- Codebase: `app/database.py` — `get_task_session_factory()` pattern (Celery + asyncio)
- Codebase: `app/tasks.py` — `generate_ugc_ad_task` stage sequence (defines what columns are needed)
- Codebase: `alembic/versions/005_landing_pages_schema.py` — migration template and `down_revision` value
- Codebase: `alembic/env.py` — async migration setup (no changes needed)
- Codebase: `requirements.txt` — confirms python-statemachine NOT installed

### Secondary (MEDIUM confidence)
- python-statemachine docs (readthedocs.io/en/latest) — model binding with `state_field`, `start_value`
- python-statemachine integrations page — Django MachineMixin pattern (maps to SQLAlchemy equivalent)
- python-statemachine user machine example — `StateMachine(model, state_field="status", start_value=...)` instantiation

### Tertiary (LOW confidence)
- WebSearch: SQLAlchemy state machine patterns 2025 — confirmed python-statemachine is the maintained choice; sqlalchemy-state-machine package is inactive

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all core libs already in requirements.txt; only python-statemachine is new (verified on PyPI)
- Architecture: HIGH — directly derived from existing codebase patterns (models.py, tasks.py, alembic/)
- State machine API: MEDIUM — verified via official docs; SQLAlchemy binding pattern inferred from Django Mixin docs (same principle)
- Pitfalls: HIGH — down_revision pitfall verified by reading migration 005; others from codebase analysis

**Research date:** 2026-02-20
**Valid until:** 2026-03-20 (stable libraries, 30-day window)
