---
phase: 23-review-ui-templates
plan: 01
subsystem: ui
tags: [htmx, jinja2, fastapi, sqlalchemy, ugc]

requires:
  - phase: 22-review-api-routes
    provides: UGCJob model, /ugc/jobs POST endpoint, status flow
  - phase: 20-ugc-data-model
    provides: UGCJob SQLAlchemy model with all columns

provides:
  - HTMX 2.0.8 + SSE extension 2.2.4 loaded on every page via base.html
  - GET /ui/ugc route rendering ugc_list.html
  - GET /ui/ugc/new route rendering ugc_new.html
  - UGC status badge CSS for all job states
  - Form submit script that POSTs to /ugc/jobs and redirects to review page

affects: [23-02-review-page, 24-video-player]

tech-stack:
  added: [htmx 2.0.8 (CDN), htmx-ext-sse 2.2.4 (CDN)]
  patterns: [hidden+checkbox mock toggle pattern, fetch+redirect form submit for JSON APIs]

key-files:
  created:
    - app/ui/templates/ugc_new.html
    - app/ui/templates/ugc_list.html
  modified:
    - app/ui/templates/base.html
    - app/ui/static/ui.css
    - app/ui/router.py

key-decisions:
  - "HTMX loaded in base.html head (after CSS link) so it's available on every page"
  - "fetch+redirect instead of form POST for ugc_new.html because /ugc/jobs returns JSON not redirect"
  - "hidden+checkbox mock toggle: hidden sends false when unchecked, checkbox value=true overrides when checked"

patterns-established:
  - "Mock toggle pattern: <input type=hidden name=use_mock value=false> followed by <input type=checkbox name=use_mock value=true checked>"
  - "UGC status badge class: status-badge status-{{ job.status }} — CSS handles color per status"

duration: 2min
completed: 2026-02-21
---

# Phase 23 Plan 01: UGC Entry Points Summary

**HTMX 2.0.8 + SSE 2.2.4 wired into base.html, UGC job list and creation form templates added, two GET routes in ui/router.py**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-02-21T10:59:09Z
- **Completed:** 2026-02-21T11:00:41Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- HTMX 2.0.8 + SSE extension 2.2.4 CDN scripts with integrity hashes now load on every page
- `ugc_list.html` renders job table with status badges, mock toggle display, and Review links
- `ugc_new.html` renders creation form with all fields, hidden+checkbox mock toggle, and fetch+redirect submit script
- Two new routes in `ui/router.py`: `GET /ui/ugc` and `GET /ui/ugc/new`
- UGC nav link added to nav bar; CSS status badges cover all 9 UGCJob states

## Task Commits

1. **Task 1: HTMX CDN scripts in base.html + UGC nav link** - `8bb988a` (feat)
2. **Task 2: Job creation form, job list template, and GET routes** - `66fd9d2` (feat)

## Files Created/Modified

- `app/ui/templates/base.html` - Added HTMX + SSE CDN scripts, UGC nav link
- `app/ui/static/ui.css` - Added UGC status badge CSS classes (9 states)
- `app/ui/templates/ugc_new.html` - Job creation form with mock toggle and fetch+redirect script
- `app/ui/templates/ugc_list.html` - Job list table with status badges and review links
- `app/ui/router.py` - Imported UGCJob, added ugc_list and ugc_new GET routes

## Decisions Made

- HTMX loaded in `<head>` after CSS so it's available before DOMContentLoaded
- `ugc_new.html` uses `fetch()` + JS redirect rather than a plain HTML form POST, because `/ugc/jobs` returns JSON `{"job_id": N}` — a plain POST would display raw JSON to the user
- Mock toggle uses hidden input + checkbox pattern: hidden sends `false` as fallback, checked checkbox sends `true` and overrides it

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- `/ui/ugc` and `/ui/ugc/new` are live — Plan 23-02 can build the review page at `/ui/ugc/{id}/review`
- HTMX available globally — SSE streaming and hx-post interactions can be used in review page immediately

---
*Phase: 23-review-ui-templates*
*Completed: 2026-02-21*
