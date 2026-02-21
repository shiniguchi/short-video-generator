---
phase: 25-lp-integration
plan: 02
subsystem: ui
tags: [htmx, celery, fastapi, jinja2, video-thumbnail, frame-extraction]

# Dependency graph
requires:
  - phase: 25-01
    provides: LP DB schema, lp_hero_image_path, lp_hero_candidate_path, lp_review_locked columns, LP review page
provides:
  - Frame extraction via asyncio.to_thread on approve_final, stored as lp_hero_image_path on linked LPs
  - POST /ui/ugc/{job_id}/generate-lp endpoint — creates linked LandingPage, extracts frame, starts generation
  - Generate LP button on approved UGC review page
  - lp_hero_regen Celery task — generates new hero image and stores as candidate
  - POST /ui/lp/{run_id}/regenerate-hero — enqueues lp_hero_regen
  - POST /ui/lp/{run_id}/accept-hero-candidate — swaps candidate into approved slot
  - Regen + accept buttons in LP review hero card and stage controls
affects: [future phases deploying LP, LP analytics, any LP copy editing]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - asyncio.to_thread for blocking generate_thumbnail call in async FastAPI endpoint
    - Lazy import ugc_tasks inside endpoint (avoid circular import)
    - Candidate pattern: regeneration stores result as lp_hero_candidate_path, accept swaps it into lp_hero_image_path
    - _run_generation_for_ugc async background task creates LP via asyncio.create_task

key-files:
  created: []
  modified:
    - app/ui/router.py
    - app/ugc_tasks.py
    - app/ui/templates/ugc_review.html
    - app/ui/templates/lp_review.html
    - app/ui/templates/partials/lp_stage_controls.html

key-decisions:
  - "Frame extraction uses asyncio.to_thread(generate_thumbnail) to avoid blocking event loop"
  - "generate-lp creates LP row immediately, starts background generation via asyncio.create_task"
  - "lp_hero_regen stores result as candidate — never mutates approved lp_hero_image_path directly"
  - "Regenerate Hero button hidden once hero module is approved"

patterns-established:
  - "LP hero regen: Celery task -> lp_hero_candidate_path -> accept endpoint -> lp_hero_image_path"

# Metrics
duration: ~3min
completed: 2026-02-21
---

# Phase 25 Plan 02: LP Integration — Frame Extraction & Hero Regen Summary

**Video frame extraction on approve_final, Generate LP button, and LP hero regen Celery task with candidate/accept flow**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-02-21T11:50:12Z
- **Completed:** 2026-02-21T11:52:41Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- Frame extracted at t=2.0s via `asyncio.to_thread(generate_thumbnail)` on `approve_final`, stored as `lp_hero_image_path` on all linked LPs
- `POST /ui/ugc/{job_id}/generate-lp` creates linked `LandingPage`, extracts hero frame, redirects to LP review
- `lp_hero_regen` Celery task generates new image via `generate_hero_image`, stores as `lp_hero_candidate_path`
- Accept endpoint swaps candidate into approved hero slot
- "Generate LP" button on approved UGC review page; Regenerate Hero + Accept Candidate buttons in LP review UI

## Task Commits

1. **Task 1: Wire frame extraction on approve_final and add Generate LP button** - `028d86c` (feat)
2. **Task 2: Add LP hero image regeneration Celery task and endpoints** - `1c7a64f` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified
- `app/ui/router.py` - Added logger, frame extraction in ugc_ui_advance, generate-lp endpoint, regenerate-hero/accept-hero-candidate endpoints, _run_generation_for_ugc helper
- `app/ugc_tasks.py` - Added lp_hero_regen Celery task
- `app/ui/templates/ugc_review.html` - Added Generate LP button section for approved jobs
- `app/ui/templates/lp_review.html` - Added Regenerate Hero button and candidate comparison to hero card
- `app/ui/templates/partials/lp_stage_controls.html` - Added regen_status message and Regenerate Hero button

## Decisions Made
- `asyncio.to_thread` for `generate_thumbnail` — blocking IO call in async context
- Candidate pattern applies to LP hero same as video: never overwrite approved content
- `generate-lp` starts generation immediately (job already approved, frame ready)

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None — no external service configuration required.

## Next Phase Readiness
- LP-UGC pipeline fully wired: video approve -> frame extraction -> LP generation -> hero regen
- v3.0 milestone complete — all 25 plans done
- Ready for deployment and live validation

---
*Phase: 25-lp-integration*
*Completed: 2026-02-21*
