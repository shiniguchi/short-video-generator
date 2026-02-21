---
phase: 25-lp-integration
plan: 01
subsystem: ui, database
tags: [alembic, sqlalchemy, htmx, jinja2, landing-page, lp-review]

# Dependency graph
requires:
  - phase: 24-media-preview
    provides: media_url filter and media card CSS patterns used in lp_review.html
  - phase: 20-ugc-data-model
    provides: UGCJob model queried in stage gate check
provides:
  - LandingPage model with 6 LP integration columns (ugc_job_id, lp_module_approvals, lp_hero_image_path, lp_hero_candidate_path, lp_review_locked, lp_copy)
  - Migration 007 adding columns to landing_pages table
  - LP review page at /ui/lp/{run_id}/review with 4 module cards
  - Module approve endpoint: POST /ui/lp/{run_id}/module/{module}/approve
  - lp_copy persisted in DB at LP generation time via updated pipeline
affects:
  - 25-02 (LP generation trigger from UGC review page will use ugc_job_id and lp_review_locked)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "LP_MODULES list as single source of truth for module names across router and templates"
    - "lp_module_approvals JSON column with dict reassignment pattern to trigger SQLAlchemy dirty detection"
    - "Stage gate via ugc_job_id FK — lp_review_locked unlocked when UGCJob.status == approved"

key-files:
  created:
    - alembic/versions/007_lp_integration_schema.py
    - app/ui/templates/lp_review.html
    - app/ui/templates/partials/lp_stage_controls.html
  modified:
    - app/models.py
    - app/schemas.py
    - app/services/landing_page/generator.py
    - app/ui/router.py

key-decisions:
  - "lp_copy field renamed from copy in LandingPageResult to avoid shadowing Pydantic BaseModel.copy() method"
  - "standalone LP (ugc_job_id is None) skips stage gate — video_approved defaults to True"
  - "lp_module_approvals reassigned as new dict after mutation to trigger SQLAlchemy dirty tracking"

patterns-established:
  - "LP review partial (lp_stage_controls.html) targets #lp-stage-controls with hx-swap=outerHTML — same pattern as UGC stage controls"

# Metrics
duration: ~2min
completed: 2026-02-21
---

# Phase 25 Plan 01: LP Integration Schema and Review Page Summary

**LP DB schema (6 new columns + migration 007), per-module review UI with HTMX approve buttons, and stage gate locking review until UGC video is approved**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-02-21T11:45:23Z
- **Completed:** 2026-02-21T11:47:39Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments
- LandingPage model extended with 6 LP integration columns including FK to UGCJob and JSON module approvals
- Migration 007 adds all 6 columns to landing_pages table as nullable with server defaults
- LP review page renders 4 module cards (headline, hero, cta, benefits) from stored lp_copy JSON
- Module approve endpoint updates lp_module_approvals dict per-module via HTMX
- Stage gate blocks LP review when linked UGCJob.status != "approved"
- lp_copy persisted at generation time — no extra LLM calls at review time

## Task Commits

Each task was committed atomically:

1. **Task 1: Add LP integration columns to LandingPage model and create migration** - `6f2adcd` (feat)
2. **Task 2: Create LP review page with module cards, approve endpoint, and stage gate** - `2238085` (feat)

## Files Created/Modified
- `alembic/versions/007_lp_integration_schema.py` — Migration adding 6 columns to landing_pages
- `app/models.py` — LandingPage model with new LP integration columns
- `app/schemas.py` — LandingPageResult gains lp_copy field (Optional[dict])
- `app/services/landing_page/generator.py` — Passes copy.model_dump() into result.lp_copy
- `app/ui/router.py` — LP_MODULES constant, lp_review GET, lp_module_approve POST, lp_copy stored in _run_generation
- `app/ui/templates/lp_review.html` — LP review page with per-module cards and stage gate
- `app/ui/templates/partials/lp_stage_controls.html` — HTMX partial with approval progress counter

## Decisions Made
- `lp_copy` field name used in `LandingPageResult` (not `copy`) — `copy` shadows Pydantic BaseModel method, causing UserWarning
- Standalone LPs (ugc_job_id is None) skip the stage gate (`video_approved = True`) — no video means no gate
- Module approvals dict reassigned (`lp.lp_module_approvals = approvals`) rather than mutated in place — SQLAlchemy JSON dirty detection requires reassignment

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Renamed LandingPageResult.copy to lp_copy to avoid Pydantic shadow**
- **Found during:** Task 1 verification
- **Issue:** Field named `copy` shadows Pydantic `BaseModel.copy()` method, producing UserWarning in Python 3.11+
- **Fix:** Renamed field to `lp_copy` in schema, generator, and router
- **Files modified:** app/schemas.py, app/services/landing_page/generator.py, app/ui/router.py
- **Verification:** Imports cleanly with no warnings
- **Committed in:** 6f2adcd (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - bug fix)
**Impact on plan:** Required rename of one field across 3 files. No scope creep.

## Issues Encountered
None — plan executed cleanly after field rename.

## User Setup Required
None — no external service configuration required.

## Next Phase Readiness
- Schema and review UI complete — 25-02 can wire the LP generation trigger from the UGC review page
- ugc_job_id FK ready to be populated when LP is generated from an approved UGC job
- lp_review_locked will need to be set to False when ugc_job is approved (25-02 work)

---
*Phase: 25-lp-integration*
*Completed: 2026-02-21*

## Self-Check: PASSED
- All 4 key files found on disk
- Both task commits (6f2adcd, 2238085) verified in git log
