---
phase: 22-review-api-routes-sse
plan: "01"
subsystem: api

tags: [sse, fastapi, streaming, sqlalchemy, asyncio]

requires:
  - phase: 21-per-stage-celery-tasks
    provides: UGC router with job submit, advance, and status endpoints

provides:
  - GET /ugc/jobs — lists all jobs ordered newest first
  - GET /ugc/jobs/{id}/events — SSE stream with per-iteration session, disconnect guard, terminal-state exit

affects:
  - 23-review-workflow-ui (consumes SSE stream via HTMX EventSource)

tech-stack:
  added: []
  patterns:
    - "SSE with per-iteration async_session_factory() — never hold session open across stream duration"
    - "await request.is_disconnected() at top of loop — check before querying DB"

key-files:
  created: []
  modified:
    - app/ugc_router.py

key-decisions:
  - "No Depends(get_session) on SSE endpoint — generator opens/closes session per iteration to avoid held connections"
  - "_TERMINAL_STATES includes all review states (not just approved/failed) so stream stops when user action is needed"

patterns-established:
  - "SSE pattern: for _ in range(600) → disconnect check → fresh session → yield → terminal check → sleep(1)"

duration: 1min
completed: 2026-02-21
---

# Phase 22 Plan 01: SSE Progress Streaming + Job List Summary

**GET /ugc/jobs list endpoint and GET /ugc/jobs/{id}/events SSE stream using per-iteration async_session_factory() with disconnect guard and terminal-state exit**

## Performance

- **Duration:** ~1 min
- **Started:** 2026-02-21T10:15:09Z
- **Completed:** 2026-02-21T10:16:20Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments

- `GET /ugc/jobs` — returns all UGCJobs ordered by `created_at DESC` with id, product_name, status, use_mock, created_at, error_message
- `GET /ugc/jobs/{id}/events` — SSE stream polling every 1s, exits on client disconnect or terminal state
- SSE generator uses `async_session_factory()` per iteration — never holds a connection for the full stream duration
- 600-iteration (10 min) safety cap prevents leaked coroutines if terminal state is never reached

## Task Commits

1. **Task 1: Add job list and SSE progress endpoints** - `2f9b638` (feat)

## Files Created/Modified

- `/Users/shiniguchi/development/short-video-generator/app/ugc_router.py` — added `list_ugc_jobs`, `ugc_job_events`, `_TERMINAL_STATES`, new imports (`asyncio`, `json`, `Request`, `StreamingResponse`, `async_session_factory`)

## Decisions Made

- `_TERMINAL_STATES` includes all review states (not just `approved`/`failed`) so the SSE stream stops as soon as user action is required — client doesn't need to keep polling during review
- `await request.is_disconnected()` placed at top of loop (before DB query) to avoid a wasted session open on disconnect

## Deviations from Plan

None - plan executed exactly as written.

The plan's verify command used `/jobs` as the expected path string, but the router stores full paths including the `/ugc/` prefix (`/ugc/jobs`). Verified with correct path — both routes confirmed present.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- SSE endpoint ready for consumption by HTMX EventSource in Phase 23 UI
- Job list endpoint ready to power the jobs list view
- No blockers

---
*Phase: 22-review-api-routes-sse*
*Completed: 2026-02-21*

## Self-Check: PASSED

- FOUND: app/ugc_router.py
- FOUND: 22-01-SUMMARY.md
- FOUND: commit 2f9b638
