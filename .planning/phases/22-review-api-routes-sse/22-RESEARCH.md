# Phase 22: Review API Routes + SSE - Research

**Researched:** 2026-02-20
**Domain:** FastAPI SSE endpoints, Starlette disconnect detection, HTMX SSE extension, stage gate validation
**Confidence:** HIGH

## Summary

Phase 22 adds SSE progress streaming and review-action endpoints to the UGC pipeline already built in Phase 21. The two goals are: (1) a GET SSE endpoint that streams job progress while a Celery stage task runs, and (2) advance/regenerate/edit endpoints with stage gate validation. The codebase already has a working SSE pattern in `app/ui/router.py` (the landing-page generation progress endpoint) — Phase 22 ports and adapts that pattern for UGC jobs backed by PostgreSQL.

The critical research flag from STATE.md was: verify `request.is_disconnected()` behavior in the installed Starlette version. **Verified:** Starlette 0.52.1 is installed (requirements.txt says 0.49.3, but the venv has 0.52.1). `request.is_disconnected()` is a coroutine function — it must be called with `await`. It uses `anyio.CancelScope` with instant cancellation to check for a pending `http.disconnect` message without blocking. This is the correct non-blocking disconnect pattern and works correctly in Starlette 0.52.1.

The stage gate requirement (REVIEW-04) maps to: `advance_ugc_job` must return 400 if `job.status` is not a review state. This is already implemented in Phase 21's `_STAGE_ADVANCE_MAP` check. Phase 22 adds a more specific error variant: if the status is `running` (task actively running, no review yet), the error message must distinguish that from a completed, reviewable state that hasn't been approved. The "unapproved items" language from ROADMAP.md reflects a future per-item approval model (REVIEW-02); for Phase 22, stage gate = status must be a review state before advancing.

**Primary recommendation:** Add a GET `/ugc/jobs/{id}/events` SSE endpoint to `ugc_router.py` that polls the DB every second, emits the current status, and cleanly exits when the stage completes or the client disconnects. Add regenerate and edit endpoints to `ugc_router.py` as POST routes. Keep all new code in `ugc_router.py` — no new files needed.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | 0.128.8 | SSE via StreamingResponse, advance/regen endpoints | Already the web framework |
| Starlette | 0.52.1 | `Request.is_disconnected()` for client disconnect detection | Installed in venv; verified API is async coroutine |
| SQLAlchemy (async) | 2.0.46 | DB polling in SSE generator for job status | Already established pattern |
| asyncio (stdlib) | — | `asyncio.sleep(1)` between SSE polls | Same pattern as existing progress.html events endpoint |
| HTMX | 2.0.8 (CDN) | Approve/regenerate buttons trigger POST endpoints | Prior decision; already in base.html |
| HTMX SSE Extension | 2.2.4 (CDN) | `hx-ext="sse"` + `sse-connect` for live progress | Prior decision; CDN-loaded |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| python-statemachine | 2.6.0 | Guard advance transitions | Already used in Phase 21 advance endpoint |
| Jinja2 | 3.1.6 | Partial template fragments for HTMX swaps | Approve/regen buttons swap outerHTML partials |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| DB polling in SSE | Redis pub/sub | Redis pub/sub requires Celery tasks to publish events — more coupling; DB polling is simpler for 5 stages, adequate for 1-second resolution |
| `request.is_disconnected()` | try/except GeneratorExit | `is_disconnected()` is the Starlette-idiomatic non-blocking check; GeneratorExit is a fallback for sync generators |
| HTMX SSE extension | Vanilla JS EventSource | Vanilla JS already used in progress.html; HTMX SSE extension is a prior decision for the review page template |

**Installation:** No new packages needed. All are already installed.

## Architecture Patterns

### Recommended File Structure

```
app/
├── ugc_router.py          # EXTEND: add SSE + regenerate + edit endpoints
└── ui/
    └── templates/
        └── ugc_review.html  # NEW: stage review page with HTMX SSE + approve buttons
```

No new modules. All Phase 22 endpoints go into the existing `app/ugc_router.py`.

### Pattern 1: SSE Endpoint with Disconnect Handling

**What:** GET endpoint returns `StreamingResponse` with `text/event-stream` MIME type. Generator polls DB every second, emits JSON status. Exits when status reaches a review/done/failed state OR when the client disconnects.

**When to use:** Always — this is the only SSE pattern in the codebase.

**Example:**
```python
# app/ugc_router.py — add to existing router
import json
import asyncio
from fastapi import Request
from fastapi.responses import StreamingResponse

@router.get("/jobs/{job_id}/events")
async def ugc_job_events(job_id: int, request: Request, session: AsyncSession = Depends(get_session)):
    """SSE stream for UGC job progress. Emits status every 1s until stage completes or client disconnects."""

    # Terminal states — stop streaming when reached
    _TERMINAL_STATES = {"stage_analysis_review", "stage_script_review", "stage_aroll_review",
                        "stage_broll_review", "stage_composition_review", "approved", "failed"}

    async def event_stream():
        for _ in range(600):  # max 10 min (600 x 1s)
            # Check disconnect FIRST — client may have closed tab
            if await request.is_disconnected():
                break

            # Poll current job status from DB
            result = await session.execute(select(UGCJob).where(UGCJob.id == job_id))
            job = result.scalars().first()
            if not job:
                yield f"data: {json.dumps({'status': 'not_found'})}\n\n"
                break

            payload = {"status": job.status, "error_message": job.error_message}
            yield f"data: {json.dumps(payload)}\n\n"

            if job.status in _TERMINAL_STATES:
                break

            await asyncio.sleep(1)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
```

**Key points:**
- `await request.is_disconnected()` is non-blocking — uses `anyio.CancelScope` with instant cancel to check without waiting
- Check disconnect at the TOP of the loop, before the DB query — avoids one extra DB hit after tab close
- `X-Accel-Buffering: no` header disables nginx buffering — required for SSE through reverse proxies
- Terminal states include all review states (not just `approved`/`failed`) — streaming stops when a stage completes and user needs to review

### Pattern 2: Stage Gate Validation

**What:** The existing `_STAGE_ADVANCE_MAP` check in `advance_ugc_job` already gates advance. Phase 22 adds a `regenerate` endpoint that also uses a gated check: regeneration is only allowed from a review state (not from `running` or `pending`).

**When to use:** All mutating endpoints (advance, regenerate, edit) must validate status before acting.

**Example:**
```python
# Stage gate: status must be in a review state
_REVIEW_STATES = set(_STAGE_ADVANCE_MAP.keys())  # derive from the map

@router.post("/jobs/{job_id}/regenerate")
async def regenerate_ugc_stage(job_id: int, session: AsyncSession = Depends(get_session)):
    """Re-run current stage. Only allowed from a review state (stage gate)."""
    result = await session.execute(select(UGCJob).where(UGCJob.id == job_id))
    job = result.scalars().first()
    if not job:
        raise HTTPException(status_code=404, detail=f"UGCJob {job_id} not found")

    if job.status not in _REVIEW_STATES:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot regenerate from status '{job.status}' — job must be in a review state",
        )

    # Transition back to running, re-enqueue the same stage's task
    _STAGE_REGEN_MAP = {
        "stage_analysis_review":    ("approve_analysis", "ugc_stage_1_analyze"),
        "stage_script_review":      ("approve_script",   "ugc_stage_2_script"),
        "stage_aroll_review":       ("approve_aroll",    "ugc_stage_3_aroll"),
        "stage_broll_review":       ("approve_broll",    "ugc_stage_4_broll"),
        "stage_composition_review": ("approve_final",    "ugc_stage_5_compose"),
    }
    # NOTE: Regeneration uses the approve event to get back to running,
    # then re-enqueues the same stage (not the next stage).
    approve_event, task_name = _STAGE_REGEN_MAP[job.status]
    sm = UGCJobStateMachine(model=job, state_field="status", start_value=job.status)
    sm.send(approve_event)
    job.status = sm.current_state.id  # now "running"
    await session.commit()

    import app.ugc_tasks as ugc_tasks_module
    task_fn = getattr(ugc_tasks_module, task_name)
    task_fn.delay(job_id)

    return {"job_id": job_id, "status": job.status, "regenerating": task_name}
```

**Important:** `stage_composition_review` uses `approve_final` which transitions to `approved`, not `running`. This means composition cannot be regenerated via state machine transitions alone — a special override or new `restart_composition` event in the state machine is needed. See Open Questions.

### Pattern 3: HTMX SSE Consumer in Template

**What:** The review page connects to the SSE endpoint and updates status display. When streaming stops (status hit a review state), HTMX swaps in the approve/regenerate buttons.

**When to use:** ugc_review.html — the per-job review page.

**Example:**
```html
<!-- Source: prior decision — HTMX 2.0.8 + SSE Extension 2.2.4 (CDN-loaded) -->

<!-- Base template must load: -->
<!-- <script src="https://cdn.jsdelivr.net/npm/htmx.org@2.0.8/dist/htmx.min.js"></script> -->
<!-- <script src="https://cdn.jsdelivr.net/npm/htmx-ext-sse@2.2.4/sse.js"></script> -->

<!-- SSE progress area: connects while job is running -->
<div id="progress-area"
     hx-ext="sse"
     sse-connect="/ugc/jobs/{{ job.id }}/events"
     sse-swap="message"
     hx-swap="innerHTML">
  <p>Connecting to progress stream...</p>
</div>

<!-- Approve button (shown when job.status is a review state) -->
{% if job.status in review_states %}
<div id="stage-controls">
  <button
    hx-post="/ugc/jobs/{{ job.id }}/advance"
    hx-target="#stage-controls"
    hx-swap="outerHTML">
    Approve & Continue
  </button>
  <button
    hx-post="/ugc/jobs/{{ job.id }}/regenerate"
    hx-target="#stage-controls"
    hx-swap="outerHTML">
    Regenerate
  </button>
</div>
{% endif %}
```

### Pattern 4: Job List Endpoint

**What:** GET `/ugc/jobs` returns a list of UGCJob rows for the review dashboard. Already implied by plan 22-01 ("job list and detail routes").

**When to use:** Review dashboard listing page.

**Example:**
```python
@router.get("/jobs")
async def list_ugc_jobs(session: AsyncSession = Depends(get_session)):
    """List all UGCJobs ordered by newest first."""
    result = await session.execute(select(UGCJob).order_by(UGCJob.created_at.desc()))
    jobs = result.scalars().all()
    return [
        {"id": j.id, "product_name": j.product_name, "status": j.status,
         "created_at": j.created_at, "error_message": j.error_message}
        for j in jobs
    ]
```

### Anti-Patterns to Avoid

- **Not awaiting `is_disconnected()`:** `request.is_disconnected()` is a coroutine — missing `await` means the check never runs and generators leak after tab close.
- **Checking disconnect at end of loop:** Check disconnect at the TOP before any DB query — avoids one unnecessary DB round-trip after client leaves.
- **Missing `X-Accel-Buffering: no` header:** Without it, nginx (if in front) buffers SSE chunks, causing the stream to appear broken or delayed.
- **Polling without a max iteration cap:** Always cap SSE loops (e.g., 600 iterations = 10 min) to prevent infinite generators on missed disconnect signals.
- **Forgetting `Cache-Control: no-cache`:** Browsers may cache SSE responses without this header, replaying stale events.
- **Re-using `session` across `asyncio.sleep` in SSE:** The `AsyncSession` passed via `Depends(get_session)` holds a connection from the pool across the entire SSE stream duration. For long-lived SSE (minutes), prefer opening a new session per poll iteration using `async_session_factory()`. (See Pitfalls.)

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Disconnect detection | Custom signal handler or try/except | `await request.is_disconnected()` | Starlette built-in; uses anyio.CancelScope for non-blocking check |
| SSE framing | Custom multipart or chunked encoding | `StreamingResponse` with `text/event-stream` MIME | Starlette handles chunked transfer encoding |
| Stage gate validation | `if status == "running": raise` | Check `if job.status not in _STAGE_ADVANCE_MAP` | `_STAGE_ADVANCE_MAP` is the single source of truth — derive `_REVIEW_STATES` from its keys |
| Status-to-task lookup for regen | Separate dict | Derive from `_STAGE_ADVANCE_MAP` or a parallel `_STAGE_REGEN_MAP` | Keeps all stage mappings co-located |

**Key insight:** All the plumbing (session, state machine, task dispatch) is already built. Phase 22 is routing + generator wiring, not new infrastructure.

## Common Pitfalls

### Pitfall 1: SQLAlchemy Session Held Open During SSE Stream

**What goes wrong:** `Depends(get_session)` hands the endpoint a session that wraps a connection from the pool. If the SSE generator runs for 10 minutes, that connection stays checked out for 10 minutes — starving other requests.

**Why it happens:** `get_session` is a FastAPI dependency that yields a single session for the entire request lifetime. SSE endpoints have a long request lifetime by design.

**How to avoid:** Inside the SSE generator, use `async_session_factory()` to open a fresh, short-lived session per poll iteration:

```python
from app.database import async_session_factory

async def event_stream():
    for _ in range(600):
        if await request.is_disconnected():
            break
        async with async_session_factory() as s:
            result = await s.execute(select(UGCJob).where(UGCJob.id == job_id))
            job = result.scalars().first()
        # session auto-closed after the async with block
        yield f"data: {json.dumps({'status': job.status if job else 'not_found'})}\n\n"
        if not job or job.status in _TERMINAL_STATES:
            break
        await asyncio.sleep(1)
```

**Warning signs:** Connection pool exhaustion errors under concurrent SSE connections; `asyncpg.exceptions.TooManyConnectionsError`.

### Pitfall 2: Regeneration from `stage_composition_review` Breaks State Machine

**What goes wrong:** `stage_composition_review` only has the `approve_final` transition, which goes to `approved` (a final state). There is no `running` state reachable from `stage_composition_review` in the current state machine.

**Why it happens:** The state machine (`app/state_machines/ugc_job.py`) marks `approved` as `State(final=True)`. Trying to run `ugc_stage_5_compose` again requires going back to `running`, but there's no transition for that.

**How to avoid:** Two options:
1. Add a `retry_composition = stage_composition_review.to(running)` transition to the state machine (and a corresponding Alembic migration is NOT needed — the state machine is code-only, no DB schema change).
2. Only allow regeneration from stages 1–4 (analysis, script, aroll, broll). Exclude `stage_composition_review` from the regeneration endpoint.

**Recommendation:** Option 2 for Phase 22 (simpler, no state machine change). If the planner wants to enable regeneration of composition, add the `retry_composition` event in the same plan.

**Warning signs:** `TransitionNotAllowed` exception on regenerate call from `stage_composition_review`.

### Pitfall 3: SSE Endpoint Not Receiving Disconnect When Behind a Proxy

**What goes wrong:** Nginx or another reverse proxy may not propagate the client disconnect to the upstream FastAPI process immediately. `request.is_disconnected()` may not return `True` even after the browser tab closes.

**Why it happens:** Some proxies buffer the connection and send a TCP close only after their own timeout.

**How to avoid:** The iteration cap (600 max = 10 min) ensures the generator always terminates eventually. For development (no proxy), `is_disconnected()` works correctly. The `X-Accel-Buffering: no` header tells nginx to disable response buffering — this also helps propagate disconnects faster.

**Warning signs:** Generators continue running for minutes after the browser tab closes in production (behind nginx); not observable in local dev.

### Pitfall 4: HTMX SSE Extension Not Loaded Before SSE Attributes Are Parsed

**What goes wrong:** If the SSE extension script tag is loaded AFTER the HTML element with `hx-ext="sse"`, HTMX parses the element before the extension is registered and silently ignores the SSE behavior.

**Why it happens:** HTMX processes extensions at DOM parse time when elements are initialized.

**How to avoid:** Load SSE extension script in `<head>` or before the `hx-ext="sse"` element in base.html:
```html
<script src="https://cdn.jsdelivr.net/npm/htmx.org@2.0.8/dist/htmx.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/htmx-ext-sse@2.2.4/sse.js"></script>
```

**Warning signs:** SSE connection is never established — browser dev tools show no request to `/ugc/jobs/{id}/events`.

### Pitfall 5: `is_disconnected()` Returns False on First Call Even When Client Is Gone

**What goes wrong:** The first call to `is_disconnected()` at the top of the loop returns `False` even though the client disconnected during the previous `asyncio.sleep(1)`. The disconnect is only detected on the SECOND call.

**Why it happens:** The `anyio.CancelScope` trick checks the receive queue for a pending message — there may be a one-iteration lag before the TCP close propagates to the ASGI receive queue.

**How to avoid:** This is acceptable behavior — the worst case is one extra DB query and one extra SSE emit after disconnect. The generator terminates on the next iteration. No mitigation needed.

## Code Examples

### SSE Endpoint Pattern (verified against existing app/ui/router.py:71-86)

```python
# Source: app/ui/router.py:71-86 (existing pattern, adapted for UGC + disconnect handling)
@router.get("/jobs/{job_id}/events")
async def ugc_job_events(job_id: int, request: Request):
    """SSE: emits job status every 1s until stage completes or client disconnects."""
    from app.database import async_session_factory
    from app.models import UGCJob
    from sqlalchemy import select
    import json

    _TERMINAL = {"stage_analysis_review", "stage_script_review", "stage_aroll_review",
                 "stage_broll_review", "stage_composition_review", "approved", "failed"}

    async def event_stream():
        for _ in range(600):  # 10-min cap
            if await request.is_disconnected():
                break
            async with async_session_factory() as s:
                result = await s.execute(select(UGCJob).where(UGCJob.id == job_id))
                job = result.scalars().first()
            if not job:
                yield f"data: {json.dumps({'status': 'not_found'})}\n\n"
                break
            yield f"data: {json.dumps({'status': job.status, 'error': job.error_message})}\n\n"
            if job.status in _TERMINAL:
                break
            await asyncio.sleep(1)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
```

### Starlette `is_disconnected()` Source (verified in venv)

```python
# Verified: Starlette 0.52.1, app/ui/router.py behavior confirmed
# request.is_disconnected() is async and non-blocking:
async def is_disconnected(self) -> bool:
    if not self._is_disconnected:
        message: Message = {}
        with anyio.CancelScope() as cs:
            cs.cancel()  # instant cancel — checks queue without blocking
            message = await self._receive()
        if message.get("type") == "http.disconnect":
            self._is_disconnected = True
    return self._is_disconnected
```

### Advance Endpoint (existing in Phase 21 — NO CHANGE NEEDED)

```python
# Source: app/ugc_router.py:93-136 (already implemented in Phase 21)
# Phase 22 does NOT need to re-implement this.
# The existing 400 on non-review status IS the stage gate for REVIEW-04.
```

### HTMX SSE Consumer Pattern

```html
<!-- Source: STACK.md decision — HTMX 2.0.8 + SSE Extension 2.2.4 -->
<!-- Requires both scripts in base.html <head> -->
<div id="progress"
     hx-ext="sse"
     sse-connect="/ugc/jobs/{{ job.id }}/events"
     sse-swap="message"
     hx-swap="innerHTML">
  Connecting...
</div>
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Vanilla JS `EventSource` in ui.js | HTMX SSE extension (`hx-ext="sse"`) | Phase 22 decision | Declarative SSE — no JS to write for the review page |
| Single-session per SSE request | New session per poll iteration via `async_session_factory()` | Phase 22 pattern | Prevents connection pool starvation on concurrent SSE connections |
| No disconnect handling (progress.html pattern) | `await request.is_disconnected()` at loop top | Phase 22 addition | Generators exit cleanly on tab close |

**Deprecated/outdated:**
- Using `Depends(get_session)` inside SSE generator functions: valid for short requests, causes pool starvation for long-lived SSE. Use `async_session_factory()` directly inside the generator body.

## Open Questions

1. **Regeneration from `stage_composition_review`**
   - What we know: The state machine has no transition from `stage_composition_review` back to `running`. The `approve_final` event goes to `approved` (final).
   - What's unclear: Does the planner want composition to be regeneratable, or is it approve-only?
   - Recommendation: Exclude `stage_composition_review` from the regenerate endpoint in Phase 22. If needed, add `retry_composition = stage_composition_review.to(running)` in the state machine (no migration needed) in a follow-up.

2. **Edit endpoint scope**
   - What we know: Plan 22-02 lists "edit endpoints". The model has JSON columns for `master_script`, `aroll_scenes`, `broll_shots` that could be editable.
   - What's unclear: Does "edit" mean a full JSON body PUT to overwrite a column, or inline field edits via HTMX?
   - Recommendation: Implement as a PATCH `/ugc/jobs/{id}/edit` endpoint that accepts a JSON body with optional fields to overwrite. Only allow edits from a review state (same stage gate as advance/regenerate).

3. **SSE terminal state for `running` status**
   - What we know: If a job is in `running` state and the user opens the review page, SSE should stream. If the job is already in a review state, SSE should immediately emit the status and stop.
   - What's unclear: Should the SSE endpoint also serve a historical review page (emit once and close) or always stream?
   - Recommendation: Always stream. The terminal state check handles both cases — if status is already a review state, the generator emits once and exits immediately. The HTMX SSE element simply receives the one event and the frontend can refresh the controls.

## Sources

### Primary (HIGH confidence)
- Codebase: `app/ugc_router.py` — existing advance, status, submit endpoints from Phase 21
- Codebase: `app/ui/router.py:71-86` — existing SSE pattern (`StreamingResponse`, `event_stream()` generator, `text/event-stream`, `Cache-Control` headers)
- Codebase: `app/state_machines/ugc_job.py` — verified state machine transitions; confirmed `stage_composition_review` has no `running` reachable transition
- Verified: `starlette 0.52.1` installed in `.venv`; `Request.is_disconnected()` source inspected — confirmed async coroutine using `anyio.CancelScope`
- Codebase: `app/models.py:147-203` — UGCJob column layout for edit endpoint scope
- Codebase: `.planning/STATE.md` — confirmed prior decisions (HTMX 2.0.8, SSE Extension 2.2.4, `_STAGE_ADVANCE_MAP` as single source of truth)

### Secondary (MEDIUM confidence)
- `.planning/research/STACK.md` — confirmed HTMX 2.0.8 + SSE Extension 2.2.4 CDN URLs and `hx-ext="sse"` / `sse-connect` attribute pattern; verified against HTMX docs pattern
- `.planning/REQUIREMENTS.md:73-79` — REVIEW-04 and REVIEW-05 text; interpreted stage gate meaning in context of current data model

### Tertiary (LOW confidence)
- Proxy disconnect propagation behavior with `is_disconnected()`: based on known ASGI/nginx behavior patterns; not verified against this project's specific nginx config.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries already installed, no new dependencies
- SSE endpoint pattern: HIGH — directly verified from existing working implementation in `app/ui/router.py`
- `is_disconnected()` behavior: HIGH — source code inspected in installed venv
- Regeneration state machine issue: HIGH — verified by reading state machine source
- Architecture: HIGH — all patterns derived from existing codebase
- Pitfalls: HIGH for session starvation and SSE load order; MEDIUM for proxy disconnect behavior

**Research date:** 2026-02-20
**Valid until:** 2026-03-22 (stable; no fast-moving dependencies; Starlette API unlikely to change)
