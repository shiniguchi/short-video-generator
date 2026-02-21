---
phase: 22-review-api-routes-sse
plan: "02"
subsystem: api

tags: [fastapi, statemachine, celery, pydantic, stage-gate]

requires:
  - phase: 22-review-api-routes-sse
    provides: GET /ugc/jobs list and GET /ugc/jobs/{id}/events SSE stream (plan 01)
  - phase: 21-per-stage-celery-tasks
    provides: ugc_stage_1_analyze through ugc_stage_5_compose celery tasks

provides:
  - POST /ugc/jobs/{id}/regenerate — re-runs current stage celery task from review state
  - PATCH /ugc/jobs/{id}/edit — updates stage output columns while in review state
  - _STAGE_REGEN_MAP mapping review states to celery task names
  - _REVIEW_STATES derived from _STAGE_ADVANCE_MAP for gate checks

affects:
  - 23-review-workflow-ui (approve/reject/regenerate/edit UI buttons wire to these endpoints)

tech-stack:
  added: []
  patterns:
    - "Stage gate pattern: check job.status against _STAGE_REGEN_MAP or _REVIEW_STATES before mutation"
    - "Reuse advance-map approve event to transition review->running for regeneration"
    - "Pydantic model with Optional fields + model_dump(exclude_none=True) for partial PATCH"
    - "Lazy import app.ugc_tasks inside endpoint to avoid circular import"

key-files:
  created: []
  modified:
    - app/ugc_router.py

key-decisions:
  - "_STAGE_REGEN_MAP excludes stage_composition_review — SM has no review->running transition for that state (approve_final goes directly to approved)"
  - "Regenerate reuses _STAGE_ADVANCE_MAP approve events to drive SM review->running transition before re-enqueuing"
  - "TransitionNotAllowed moved from inline import in advance_ugc_job to file-level import"

patterns-established:
  - "Regenerate pattern: gate on _STAGE_REGEN_MAP -> SM transition review->running -> commit -> lazy import ugc_tasks -> getattr(task_name).delay(job_id)"
  - "Edit pattern: gate on _REVIEW_STATES -> model_dump(exclude_none=True) -> setattr loop -> commit"

duration: 2min
completed: 2026-02-21
---

# Phase 22 Plan 02: Regenerate and Edit Endpoints Summary

**POST /ugc/jobs/{id}/regenerate and PATCH /ugc/jobs/{id}/edit with stage gate validation — regenerate re-runs the current stage celery task, edit patches output columns, both blocked outside review states**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-02-21T10:18:30Z
- **Completed:** 2026-02-21T10:19:54Z
- **Tasks:** 2
- **Files modified:** 1

## Accomplishments

- `POST /ugc/jobs/{id}/regenerate` — gates on `_STAGE_REGEN_MAP`, transitions review->running via SM, re-enqueues the stage's celery task; returns 400 for `stage_composition_review` (specific message) and non-review states
- `PATCH /ugc/jobs/{id}/edit` — gates on `_REVIEW_STATES`, accepts optional JSON fields via `UGCJobEdit` pydantic model, patches only provided fields via `setattr`
- `_STAGE_REGEN_MAP` and `_REVIEW_STATES` constants defined at module level as single source of truth
- `TransitionNotAllowed` deduplicated to file-level import (was inline in advance endpoint)

## Task Commits

1. **Tasks 1+2: Regenerate endpoint + Edit endpoint** - `dcc4c33` (feat)

## Files Created/Modified

- `/Users/shiniguchi/development/short-video-generator/app/ugc_router.py` — added `_STAGE_REGEN_MAP`, `_REVIEW_STATES`, `UGCJobEdit` model, `regenerate_ugc_stage` endpoint, `edit_ugc_job` endpoint; moved `TransitionNotAllowed` to file-level import

## Decisions Made

- `stage_composition_review` excluded from `_STAGE_REGEN_MAP` because `approve_final` transitions directly to `approved` — there is no SM path back to `running` from composition review
- Regenerate reuses the `_STAGE_ADVANCE_MAP` approve event (e.g. `approve_analysis`) to drive the SM transition from review -> running, rather than defining a separate "rerun" event — keeps SM unchanged
- `_REVIEW_STATES = set(_STAGE_ADVANCE_MAP.keys())` avoids duplicating the list of review states

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

Plan verify commands used `/jobs/{job_id}/...` path strings but router stores full paths including `/ugc/` prefix. Same pattern as 22-01. Verified with correct `/ugc/jobs/{job_id}/regenerate` and `/ugc/jobs/{job_id}/edit` paths — both confirmed present.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Regenerate and edit endpoints ready for UI integration in Phase 23
- All five review endpoints now complete: list, status, SSE, advance, regenerate, edit
- No blockers

---
*Phase: 22-review-api-routes-sse*
*Completed: 2026-02-21*

## Self-Check: PASSED

- FOUND: app/ugc_router.py
- FOUND: 22-02-SUMMARY.md
- FOUND: commit dcc4c33
