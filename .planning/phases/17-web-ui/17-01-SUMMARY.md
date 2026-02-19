---
phase: 17-web-ui
plan: 01
subsystem: ui
tags: [fastapi, jinja2, sqlalchemy, alembic, staticfiles, python-multipart]

requires:
  - phase: 16-waitlist
    provides: WaitlistEntry model and database connection pattern

provides:
  - LandingPage SQLAlchemy model with run_id, status, html_path, deployed_url columns
  - Alembic migration 005 creating landing_pages table (down_revision: 004)
  - app/ui/ package with APIRouter at prefix /ui with Jinja2Templates
  - base.html layout with nav bar (Dashboard, Generate links)
  - index.html dashboard placeholder
  - ui.css minimal styles (nav, buttons, forms, content layout)
  - ui.js placeholder for SSE/deploy logic (Plans 02-03)
  - /ui/static/* StaticFiles mount in main.py
  - /output StaticFiles mount for LP preview

affects:
  - 17-02 (SSE generate form — uses ui/router.py and ui/templates)
  - 17-03 (LP list/deploy UI — expands index.html with LandingPage model)
  - 18 (Cloudflare deployment — uses LandingPage.deployed_url and status)

tech-stack:
  added: [python-multipart, jinja2 (already present)]
  patterns:
    - "Jinja2Templates with Path(__file__).parent for template directory — relative path independent"
    - "StaticFiles mounted at /ui/static with str(Path) for Docker compatibility"
    - "APIRouter prefix /ui with tags=['web-ui'] for clean route grouping"

key-files:
  created:
    - app/ui/__init__.py
    - app/ui/router.py
    - app/ui/static/ui.css
    - app/ui/static/ui.js
    - app/ui/templates/base.html
    - app/ui/templates/index.html
    - alembic/versions/005_landing_pages_schema.py
  modified:
    - app/models.py
    - app/main.py
    - requirements.txt

key-decisions:
  - "StaticFiles uses str(Path(__file__).parent / ...) pattern — resolves correctly regardless of working directory"
  - "UI router mounted BEFORE API router in main.py — static mount must precede dynamic routes for correct priority"
  - "backports.asyncio.runner pinned to 1.0.0 (not 1.2.0) — 1.2.0 only supports Python <3.11, Docker uses 3.11"

patterns-established:
  - "UI templates extend base.html via {% extends %} — consistent nav + layout"
  - "Router returns TemplateResponse(request=request, name=..., context={}) — FastAPI 0.100+ style"

duration: 9min
completed: 2026-02-19
---

# Phase 17 Plan 01: LandingPage Model + Web UI Scaffold Summary

**LandingPage SQLAlchemy model with migration 005, app/ui/ package with Jinja2 router serving /ui/ dashboard via base.html layout and StaticFiles mounts**

## Performance

- **Duration:** 9 min
- **Started:** 2026-02-19T21:33:48Z
- **Completed:** 2026-02-19T21:43:41Z
- **Tasks:** 2
- **Files modified:** 10

## Accomplishments
- LandingPage model with 11 columns (run_id, product_idea, status, html_path, deployed_url, etc.)
- Alembic migration 005 chained to 004 (waitlist schema)
- app/ui/ package with APIRouter at /ui, Jinja2Templates, base + index templates
- /ui/static StaticFiles and /output StaticFiles mounted in main.py
- python-multipart added for Form() parsing in Plans 02+

## Task Commits

Each task was committed atomically:

1. **Task 1: Add LandingPage model, migration, python-multipart** - `d80ab58` (feat)
2. **Task 2: Create web UI scaffold** - `d79a6bc` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified
- `app/models.py` - Added LandingPage class with all 11 columns + UniqueConstraint on run_id
- `alembic/versions/005_landing_pages_schema.py` - Migration creating landing_pages table, down_revision='004'
- `requirements.txt` - Added python-multipart, fixed backports.asyncio.runner to 1.0.0
- `app/ui/__init__.py` - Package init
- `app/ui/router.py` - APIRouter prefix=/ui, Jinja2Templates, GET /ui/ returning index.html
- `app/ui/templates/base.html` - HTML5 layout with nav bar (ViralForge brand, Dashboard + Generate links)
- `app/ui/templates/index.html` - Extends base.html, placeholder LP list dashboard
- `app/ui/static/ui.css` - Minimal CSS (~70 lines): reset, nav, content, buttons, form inputs
- `app/ui/static/ui.js` - Empty placeholder (SSE added in Plan 02)
- `app/main.py` - Added StaticFiles imports, Path import, ui_router import, 3 new mounts

## Decisions Made
- `str(Path(__file__).parent / ...)` for all directory paths — Docker working directory varies, this always resolves correctly
- UI router and static mounts placed BEFORE `app.include_router(routes.router)` — mount order matters for Starlette route priority
- backports.asyncio.runner downgraded to 1.0.0 — 1.2.0 declares Requires-Python < 3.11 but Docker uses Python 3.11

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Fixed backports.asyncio.runner version for Python 3.11 Docker build**
- **Found during:** Task 2 (starting Docker web container for verification)
- **Issue:** requirements.txt pinned `backports.asyncio.runner==1.2.0` which only supports Python <3.11; Dockerfile uses Python 3.11-slim, causing pip install failure
- **Fix:** Changed pin to `backports.asyncio.runner==1.0.0` (the only compatible version)
- **Files modified:** requirements.txt
- **Verification:** Docker build succeeded, container started, all endpoints tested
- **Committed in:** `d79a6bc` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking build issue)
**Impact on plan:** Fix was necessary to verify Task 2 in Docker. Pre-existing requirements bug, not introduced by this plan.

## Issues Encountered
- uvicorn not available in local conda env (Python 3.8 base) — used Docker for server verification as intended by project setup

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- app/ui/ scaffold ready for Plan 02 (generate form with SSE progress)
- LandingPage model ready for Plan 03 (LP list table with deploy actions)
- Migration 005 ready to apply via `alembic upgrade head` in Docker

---
*Phase: 17-web-ui*
*Completed: 2026-02-19*
