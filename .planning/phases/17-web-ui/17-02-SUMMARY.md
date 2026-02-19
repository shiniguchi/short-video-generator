---
phase: 17-web-ui
plan: 02
subsystem: ui
tags: [fastapi, jinja2, sse, background-tasks, sqlalchemy]

requires:
  - phase: 17-01
    provides: app/ui scaffold with router, templates, staticfiles

provides:
  - GET /ui/generate — LP generation form (product_idea, target_audience, color_preference, mock)
  - POST /ui/generate — starts background task, 303 redirects to progress page
  - GET /ui/generate/{job_id}/progress — progress page with SSE client
  - GET /ui/generate/{job_id}/events — SSE endpoint streaming JSON status updates
  - LandingPage DB record created on successful generation
  - connectSSE() in ui.js redirects to /ui/preview/{run_id} when status=done

affects:
  - 17-03 (LP list/deploy UI — LandingPage records now populated)
  - 18 (Cloudflare deployment — uses same LandingPage records)

tech-stack:
  added: []
  patterns:
    - "asyncio.create_task() for background generation without blocking request"
    - "_jobs dict for in-memory job tracking (survives request lifecycle)"
    - "StreamingResponse with text/event-stream for SSE"
    - "Lazy imports in background task to avoid google-genai crash at startup"
    - "async_session_factory() used directly in background task (not get_session Depends)"

key-files:
  created:
    - app/ui/templates/generate.html
    - app/ui/templates/progress.html
  modified:
    - app/ui/router.py
    - app/ui/static/ui.js
    - app/ui/static/ui.css
    - app/services/llm_provider/__init__.py

key-decisions:
  - "Lazy import of landing page service in _run_generation — avoids google.genai module-level import crash when google-genai package not installed in Docker"
  - "async_session_factory() directly in background task — get_session() is a FastAPI Depends generator, not designed for standalone use in tasks"
  - "Default color_preference=research not extract — extract requires image_path, unavailable in form submission"
  - "GeminiLLMProvider import moved to lazy in llm_provider/__init__.py — fixes startup crash for all callers"

duration: 4min
completed: 2026-02-19
---

# Phase 17 Plan 02: LP Generate Form + SSE Progress Summary

**LP generation form at /ui/generate with background asyncio task, in-memory job tracking, SSE progress streaming, and LandingPage DB record creation on completion**

## Performance

- **Duration:** 4 min
- **Started:** 2026-02-19T21:46:34Z
- **Completed:** 2026-02-19T21:50:42Z
- **Tasks:** 1
- **Files modified:** 6

## Accomplishments

- generate.html form with all 4 fields (product_idea, target_audience, color_preference, mock)
- progress.html with status text, progress bar, error display, SSE client script
- POST /ui/generate starts background asyncio task, 303 redirects to progress page
- SSE endpoint streams JSON events at 1s intervals until done/error
- connectSSE() in ui.js updates DOM in real time, redirects to preview on done
- LandingPage record inserted to DB after successful generation
- CSS additions: form-group, progress-track/bar, error-msg styles

## Task Commits

1. **Task 1: Generate form, SSE progress, background task runner** - `7676862` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `app/ui/templates/generate.html` - LP generation form (product_idea, target_audience, color_preference, mock checkbox)
- `app/ui/templates/progress.html` - Progress display with status, progress bar, error, SSE script
- `app/ui/router.py` - 4 new routes: GET/POST /generate, progress page, SSE events; _run_generation background task
- `app/ui/static/ui.js` - connectSSE() function: streams events, updates DOM, redirects on done
- `app/ui/static/ui.css` - form-group, form-check, progress-track/bar, error-msg, status styles
- `app/services/llm_provider/__init__.py` - GeminiLLMProvider import made lazy

## Decisions Made

- Lazy import of LP service in `_run_generation` — google-genai package not installed in Docker, module-level import crashes server
- `async_session_factory()` used directly (not `get_session()`) — background tasks run outside FastAPI Depends injection
- Default color_preference changed from `extract` to `research` — extract requires `image_path` not available in form
- GeminiLLMProvider now lazily imported in `get_llm_provider()` — fixes the root cause for all callers

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Lazy import to avoid google.genai startup crash**
- **Found during:** Task 1 (first Docker rebuild failed with ImportError)
- **Issue:** `app/services/llm_provider/__init__.py` imported `GeminiLLMProvider` at module level, triggering `from google import genai` which fails when `google-genai` not installed in Docker
- **Fix:** Two-layer fix: (1) moved GeminiLLMProvider to lazy import inside `get_llm_provider()`, (2) moved entire LP service import to inside `_run_generation()` background function
- **Files modified:** `app/services/llm_provider/__init__.py`, `app/ui/router.py`
- **Commit:** `7676862`

**2. [Rule 1 - Bug] Fixed default color_preference causing extract error**
- **Found during:** Task 1 (SSE returned error "image_path required for 'extract' preference")
- **Issue:** Form defaulted to `color_preference=extract` which requires `image_path` — form doesn't have image upload
- **Fix:** Changed default to `research` in both template (`selected` attribute) and router (`Form("research")`)
- **Files modified:** `app/ui/templates/generate.html`, `app/ui/router.py`
- **Commit:** `7676862`

---

**Total deviations:** 2 auto-fixed (1 import crash, 1 wrong default)

## Verification Results

All plan verification criteria met:
1. GET /ui/generate returns form with product_idea, target_audience, color_preference, mock — PASS
2. POST /ui/generate redirects 303 to /ui/generate/{job_id}/progress — PASS
3. Progress page contains connectSSE("{job_id}") script — PASS
4. SSE endpoint streams JSON events with status, progress, message — PASS
5. SSE sends status="done" with run_id on completion — PASS
6. LandingPage record in DB after successful generation — PASS (verified via psql)
7. Error during generation shows error in SSE stream — PASS (tested with extract mode)

## Next Phase Readiness

- Plan 03 (LP list/deploy UI) can query LandingPage records now populated from web UI
- Preview route /ui/preview/{run_id} needed before redirected-to URL works in browser

## Self-Check: PASSED

All files found on disk. Task commit 7676862 verified in git log.

---
*Phase: 17-web-ui*
*Completed: 2026-02-19*
