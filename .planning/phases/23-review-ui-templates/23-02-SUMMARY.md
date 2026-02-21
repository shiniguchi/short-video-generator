---
phase: 23-review-ui-templates
plan: 02
subsystem: ui
tags: [htmx, jinja2, fastapi, sqlalchemy, ugc, sse, review]

requires:
  - phase: 23-01
    provides: HTMX in base.html, ugc_list/ugc_new routes, UGCJob imported in ui/router.py
  - phase: 22-review-api-routes
    provides: _STAGE_ADVANCE_MAP, _STAGE_REGEN_MAP, UGCJob model, SSE endpoint

provides:
  - GET /ui/ugc/{id}/review rendering ugc_review.html with stage stepper and per-item card grids
  - POST /ui/ugc/{id}/advance returning stage-controls partial after state advance
  - POST /ui/ugc/{id}/regenerate returning stage-controls partial after regen enqueue
  - Stage stepper CSS (step-active, step-done, step-locked)
  - Card grid CSS for per-item review display
  - SSE progress div with auto-reload on stream close

affects: [24-video-player]

tech-stack:
  added: []
  patterns:
    - HTMX outerHTML swap for in-place approve/regenerate without page reload
    - Jinja2 include of partials for HTMX swap targets
    - Running-toward heuristic: derive in-progress stage from populated data columns

key-files:
  created:
    - app/ui/templates/ugc_review.html
    - app/ui/templates/partials/ugc_stage_controls.html
  modified:
    - app/ui/static/ui.css
    - app/ui/router.py

key-decisions:
  - "Per-item card grids: each analysis field, each script scene, each file path is its own card so user can visually evaluate every item before approving the stage"
  - "running_toward heuristic: inspects populated data columns to determine which stage is in flight when status=running — no extra DB column needed"
  - "Lazy import of ugc_tasks inside advance/regenerate handlers prevents circular import at module load"
  - "datetime.now(timezone.utc) in ugc_ui_advance uses module-level import — no inline import"

duration: ~2min
completed: 2026-02-21
---

# Phase 23 Plan 02: Review Page Templates Summary

**Stage stepper + per-item card grids + HTMX approve/regenerate partial swap + SSE live progress wired into ugc_review.html, ugc_stage_controls.html, and three new ui/router.py routes**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-02-21T11:02:47Z
- **Completed:** 2026-02-21T11:04:44Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- `ugc_review.html` renders a 5-step stage stepper (Analysis, Script, A-Roll, B-Roll, Composition) with active/done/locked visual states based on job.status
- Each stage's output items are individual cards in a card grid — user reviews every field/file before gating at stage level
- SSE progress section appears only when `status == "running"`, connects to `/ugc/jobs/{id}/events`, reloads page on stream close
- `ugc_stage_controls.html` is the HTMX swap target: shows review hint + Approve & Continue + Regenerate buttons, swaps in place via `outerHTML`
- Three new routes: GET /ui/ugc/{id}/review, POST /ui/ugc/{id}/advance (HTML partial), POST /ui/ugc/{id}/regenerate (HTML partial)
- Stage stepper, card grid, status message, and SSE progress CSS added to ui.css

## Task Commits

1. **Task 1: Review page template + stage controls partial + CSS** - `33f4472` (feat)
2. **Task 2: Review GET route + UI wrapper POST routes for advance and regenerate** - `432c6b7` (feat)

## Files Created/Modified

- `app/ui/templates/ugc_review.html` - Full review page: stepper, per-item cards, SSE, includes partial
- `app/ui/templates/partials/ugc_stage_controls.html` - HTMX swap target with approve/regenerate
- `app/ui/static/ui.css` - Stepper, card grid, stage card, review hint, status msg, sse-progress
- `app/ui/router.py` - STAGE_ORDER + _REVIEW_STATES constants, three new routes, new imports

## Decisions Made

- Per-item card display (not one card per stage) so users can clearly evaluate every analysis field, every scene, every file path before deciding to approve the stage
- `running_toward` heuristic derives in-progress stage from which data columns are populated — avoids adding a new DB column or API call
- Lazy `import app.ugc_tasks` inside advance/regenerate handlers to prevent circular import at router load time
- `datetime.now(timezone.utc)` in `ugc_ui_advance` uses the module-level `from datetime import ... timezone` — no redundant inline import

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None.

## Next Phase Readiness

- `/ui/ugc/{id}/review` is live with full stage stepper and per-item review cards
- HTMX approve/regenerate wired: no page reload, controls swap in place
- Phase 24 (video player) can replace file path cards with actual media preview players

## Self-Check: PASSED

- app/ui/templates/ugc_review.html: FOUND
- app/ui/templates/partials/ugc_stage_controls.html: FOUND
- app/ui/static/ui.css: FOUND
- app/ui/router.py: FOUND
- Commit 33f4472 (Task 1): FOUND
- Commit 432c6b7 (Task 2): FOUND
