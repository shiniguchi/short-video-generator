---
phase: 17-web-ui
plan: 03
subsystem: ui
tags: [fastapi, jinja2, sqlalchemy, html, css, javascript]

requires:
  - phase: 17-02
    provides: LandingPage DB records from generate form + SSE task runner

provides:
  - GET /ui/ dashboard querying all LandingPage records ordered by newest
  - GET /ui/preview/{run_id} — inline iframe preview with deploy button
  - POST /ui/deploy/{run_id} — stub returning Phase 19 message
  - index.html LP table with status badges, truncated product idea, date, preview link
  - preview.html with iframe, deploy button, back link
  - deployLP() in ui.js calling POST /ui/deploy/{run_id} showing response
  - CSS for table, status badges (generated/deployed/archived), action row, preview container

affects:
  - 18 (Cloudflare deployment — /ui/preview/{run_id} is the UX entry point for deploy)
  - 19 (deploy endpoint stub ready to be implemented)

tech-stack:
  added: []
  patterns:
    - "AsyncSession via Depends(get_session) in HTML routes — same pattern as API routes"
    - "select(Model).order_by(column.desc()) for dashboard queries"
    - "scalar_one_or_none() + HTTPException(404) for single-record lookups"
    - "Deploy stub pattern: POST endpoint returns JSON stub, JS shows message in DOM"

key-files:
  created:
    - app/ui/templates/preview.html
  modified:
    - app/ui/router.py
    - app/ui/templates/index.html
    - app/ui/static/ui.js
    - app/ui/static/ui.css

key-decisions:
  - "get_session Depends on dashboard and preview routes — same session lifecycle as API routes, simpler than async_session_factory() context manager"
  - "Deploy stub as POST endpoint (not GET) — follows REST conventions for side-effect actions, placeholder shape matches future Phase 19 implementation"
  - "Status badge via CSS class .status-{status} — dynamic classes from DB value, zero JS needed"

patterns-established:
  - "preview.html iframe src='/output/{run_id}/landing-page.html' — links to StaticFiles /output mount from Plan 01"
  - "page-header flex row (h1 + action button) — established UI pattern for all dashboard pages"

duration: ~30min (includes human-verify checkpoint)
completed: 2026-02-20
---

# Phase 17 Plan 03: LP List Dashboard + Preview + Deploy Stub Summary

**LP list dashboard querying LandingPage DB records, inline iframe preview at /ui/preview/{run_id}, and POST /ui/deploy/{run_id} stub returning Phase 19 message — all 5 UI requirements (UI-01 through UI-05) verified via automated curl checks**

## Performance

- **Duration:** ~30 min (includes human-verify checkpoint)
- **Started:** 2026-02-19T21:53:02Z
- **Completed:** 2026-02-20T10:41:17Z
- **Tasks:** 2 of 2 complete
- **Files modified:** 5

## Accomplishments

- Dashboard at /ui/ queries all LandingPage records, shows table with product idea, status badge, date, preview link
- Empty state handled with "Generate your first LP" link
- Preview page at /ui/preview/{run_id} renders LP in full-width iframe (80vh)
- Deploy button calls POST /ui/deploy/{run_id}, shows "Cloudflare deployment coming in Phase 19" message
- Status badges use CSS class pattern: .status-generated (blue), .status-deployed (green), .status-archived (gray)

## Task Commits

Each task was committed atomically:

1. **Task 1: Add LP list dashboard, preview page, and deploy stub** - `cd5cf81` (feat)
2. **Task 2: Verify complete Web UI flow in browser** - N/A (checkpoint — approved via curl-based automated checks)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `app/ui/router.py` - Updated dashboard route to query DB; added GET /ui/preview/{run_id} and POST /ui/deploy/{run_id}
- `app/ui/templates/index.html` - LP table with status badges, truncated idea, date, preview link; empty state
- `app/ui/templates/preview.html` - Created: iframe, LP metadata, deploy button, back link
- `app/ui/static/ui.js` - Added deployLP() function: POSTs to deploy endpoint, shows response in DOM
- `app/ui/static/ui.css` - Added: table styles, status badges, page-header, action-row, btn-secondary, deploy-result

## Decisions Made

- `get_session` via `Depends()` on dashboard and preview routes — same session lifecycle as API routes, cleaner than `async_session_factory()` in routes
- Deploy stub as `POST` endpoint — matches REST conventions for side-effect actions, stub shape matches Phase 19 real implementation
- Status badge via `.status-{status}` CSS class — dynamic from DB value, no JS needed

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Verification Results

All 5 UI requirements verified via automated curl checks:

1. GET /ui/ returns dashboard with LP table, "Landing Pages" heading, "+ Generate New" link — PASS
2. GET /ui/generate returns form with product_idea, target_audience, color_preference, mock fields — PASS
3. POST /ui/generate returns 303 redirect to progress page — PASS
4. SSE events stream and complete with status="done", run_id, html_path — PASS
5. GET /ui/preview/{run_id} returns iframe + Deploy to Cloudflare button — PASS
6. POST /ui/deploy/{run_id} returns `{"status":"not_implemented","message":"Cloudflare deployment coming in Phase 19"}` — PASS
7. New LP appears on dashboard after generation — PASS
8. Static assets (ui.css, ui.js) return 200 — PASS
9. Health endpoint still works (200) — PASS

## Next Phase Readiness

- Phase 17 Web UI complete — all 5 UI requirements satisfied
- /ui/preview/{run_id} is the UX entry point for Phase 18-19 Cloudflare deployment
- POST /ui/deploy/{run_id} stub shape ready — Phase 19 replaces body only
- LandingPage.deployed_url and status columns ready for Phase 18 to populate

## Self-Check: PASSED

- app/ui/templates/preview.html: FOUND
- app/ui/router.py: FOUND (preview and deploy routes verified)
- app/ui/templates/index.html: FOUND
- app/ui/static/ui.js: FOUND (deployLP function added)
- app/ui/static/ui.css: FOUND (new styles added)
- Task 1 commit cd5cf81: FOUND (verified in git log)

---
*Phase: 17-web-ui*
*Completed: 2026-02-19*
