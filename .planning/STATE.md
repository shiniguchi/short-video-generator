# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-19)

**Core value:** Enable rapid product idea validation: product idea in → video ads + landing page out → deploy → measure waitlist signups — cheapest possible, zero manual steps between stages.

**Current focus:** Phase 19 Plan 01 COMPLETE — admin dashboard with per-LP analytics, waitlist table, CSV export

## Current Milestone

**v2.0 Smoke Test Platform** (Phases 14-19)
- Extends ViralForge from video generator to full smoke test tool
- Adds: LP generation, Cloudflare deployment, analytics, admin dashboard, web UI

## Current Position

Phase: 19 of 19 (Admin Dashboard & Deployment) - IN PROGRESS
Plan: 1 of 2 - COMPLETE
Status: Phase 19 Plan 01 complete — dashboard, waitlist, CSV export routes + templates
Last activity: 2026-02-20 - Phase 19 Plan 01 executed (2 tasks, 2 commits)

Progress: [███████████████████████░] 97% (43/44 plans total, v1.0 complete, v2.0 phase 18+19-01 complete)

## Performance Metrics

**Velocity (v1.0 shipped):**
- Total plans completed: 30
- Phases completed: 13
- Total execution time: ~2.5 hours
- Timeline: 3 days (Feb 13-15, 2026)
- Average duration: 3 min/plan

**v2.0 (in progress):**
- Total plans: 14 (across 6 phases)
- Plans completed: 5
- Phase 14 Plan 01: 6.2 minutes, 2 tasks, 2 commits
- Phase 14 Plan 02: 3.8 minutes, 2 tasks, 2 commits
- Phase 14 Plan 03: 32 minutes, 2 tasks, 1 commit (includes human-verify checkpoint)
- Phase 15 Plan 01: 1 minute, 1 task, 1 commit
- Phase 15 Plan 02: 3 minutes, 1 task, 1 commit
- Phase 16 Plan 01: 4 minutes, 2 tasks, 2 commits
- Phase 16 Plan 02: 2 minutes, 2 tasks, 2 commits
- Phase 17 Plan 01: 9 minutes, 2 tasks, 2 commits
- Phase 17 Plan 02: 4 minutes, 1 task, 1 commit
- Phase 17 Plan 03: ~30 minutes, 2 tasks, 1 commit (includes human-verify checkpoint)
- Phase 18 Plan 01: 1 minute, 2 tasks, 2 commits
- Phase 18 Plan 02: 2 minutes, 2 tasks, 2 commits
- Phase 19 Plan 01: 3 minutes, 2 tasks, 2 commits

## Accumulated Context

### Decisions

**Phase 14 Plan 01:**
- **3 color scheme modes (extract/research/preset)**: Provides flexibility per user preference (14-CONTEXT.md decision)
- **Mock-first research pattern**: Allows development without internet, follows project pattern
- **Playwright for scraping**: Modern LPs are JavaScript-heavy, need full browser vs simple requests

**Phase 14 Plan 02:**
- [Phase 14-02]: PAS as default copywriting formula - performs well for waitlist/early-stage products
- [Phase 14-02]: Honeypot position: absolute (left: -9999px) - invisible to humans but filled by bots, whereas display:none is easily detected
- [Phase 14-02]: Inline styles in section templates - makes sections truly modular and swappable in Phase 15

**Phase 14 Plan 03:**
- [Phase 14-03]: rcssmin for CSS minification — lightweight, pure Python, no build step (29% reduction achieved)
- [Phase 14-03]: generate_lp_from_pipeline() wraps LP in try/except — pipeline never fails due to LP errors
- [Phase 14-03]: Auto-open browser after generation for immediate preview; --no-open flag for CI/batch mode

**Phase 15 Plan 01:**
- [Phase 15-01]: Section-scoped schemas (8 small schemas) instead of full LandingPageCopy — smaller prompts, accurate targeted edits
- [Phase 15-01]: HTML file as source of truth — extract context via regex, no JSON sidecar state
- [Phase 15-01]: gallery excluded from EDITABLE_SECTIONS — image paths not copy, clear error returned
- [Phase 15-01]: Always call optimize_html() after replacement — prevents CSS duplication on repeated edits

**Phase 15 Plan 02:**
- [Phase 15-02]: Sidecar written by CLI on first edit (not by generator) — generator stays simple, CLI owns persistence
- [Phase 15-02]: product_idea fallback order: --product flag > landing-page.json sidecar > error with tip

**Phase 16 Plan 01:**
- [Phase 16-01]: Public endpoint pattern — no require_api_key on submit_waitlist, LP visitors don't have API keys
- [Phase 16-01]: Two-layer duplicate protection: SELECT before INSERT + catch IntegrityError for race conditions
- [Phase 16-01]: CORS_ALLOWED_ORIGINS defaults to "*" for dev — single env var change tightens for production

**Phase 16 Plan 02:**
- [Phase 16-02]: Meta tag data bridge — lp_source in `<meta name="lp-source">` lets section JS read it without Jinja2 in section templates, keeping sections modular
- [Phase 16-02]: Graceful degradation on network error — show success locally rather than error, better UX when LP can't reach API server
- [Phase 16-02]: api-base meta tag pattern — optional override for base URL, empty = same origin, handles both local dev and deployed LP

**Phase 17 Plan 01:**
- [Phase 17-01]: str(Path(__file__).parent / ...) for all directory paths — Docker working directory varies, this resolves correctly everywhere
- [Phase 17-01]: UI router + static mounts placed BEFORE API router in main.py — Starlette mount order determines route priority
- [Phase 17-01]: backports.asyncio.runner pinned to 1.0.0 — 1.2.0 declares Requires-Python < 3.11, Docker uses Python 3.11-slim

**Phase 17 Plan 02:**
- [Phase 17-02]: GeminiLLMProvider lazy import in get_llm_provider() — google-genai not installed in Docker, module-level import crashes server
- [Phase 17-02]: LP service lazy import in _run_generation background task — same reason, deferred until task actually runs
- [Phase 17-02]: async_session_factory() directly in background task — get_session() is a FastAPI Depends generator, not for standalone use
- [Phase 17-02]: Default color_preference=research not extract — extract requires image_path not available in form submission

**Phase 17 Plan 03:**
- [Phase 17-03]: get_session Depends on dashboard and preview routes — same session lifecycle as API routes, simpler than async_session_factory() in HTML routes
- [Phase 17-03]: Deploy stub as POST endpoint — REST convention for side-effect actions, stub shape matches Phase 19 real implementation
- [Phase 17-03]: Status badge via .status-{status} CSS class — dynamic from DB value, zero JS needed

**Phase 18 Plan 01:**
- [Phase 18-01]: No framework (no Hono) — 2 routes under threshold; native URL routing adds no complexity
- [Phase 18-01]: request.text()+JSON.parse() in handleTrack — sendBeacon sends Content-Type: text/plain, request.json() throws
- [Phase 18-01]: ctx.waitUntil() for D1 writes in /track — beacon returns 204 immediately, write continues in background
- [Phase 18-01]: database_id left as PLACEHOLDER — user must run wrangler d1 create and fill in UUID before deploy
- [Phase 18-01]: Wildcard CORS on /track only — /analytics/:lp_id is server-to-server with Bearer auth gate

**From PROJECT.md affecting v2.0 work:**
- **Cloudflare Pages + Worker + D1 for LP hosting + analytics**: $0 cost, globally distributed, works with local or hosted app (Phase 18-19)
- **Single-file HTML LPs**: No build step, no framework, deploy = copy one file (Phase 14)
- **Web UI as FastAPI templates (Jinja2)**: No separate frontend build, stays in Python ecosystem (Phase 17)

Full decision log: .planning/PROJECT.md Key Decisions table

**Phase 18 Plan 02:**
- [Phase 18-02]: inject_analytics_beacon at deploy-time not generation-time — Phase 19 calls it in deploy flow
- [Phase 18-02]: Graceful fallback returns zeros dict with error key — analytics endpoint always 200, never 500
- [Phase 18-02]: Lazy import CloudflareAnalyticsClient in route body — avoids import failure if httpx missing

**Phase 19 Plan 01:**
- [Phase 19-01]: asyncio.gather for concurrent analytics — fetches all LP analytics in parallel, not sequentially
- [Phase 19-01]: StreamingResponse with generator for CSV — avoids loading all rows into memory
- [Phase 19-01]: _parse_date_range() extracted as helper — date parsing reused by all 3 routes without duplication
- [Phase 19-01]: End date + timedelta(days=1) makes inclusive — user-entered end date includes that full day

### Pending Todos

None yet.

### Blockers/Concerns

None yet.

## Session Continuity

Last session: 2026-02-20
Stopped at: Completed 19-01-PLAN.md (admin dashboard + waitlist + CSV export)
Resume file: None
Next step: Execute Phase 19 Plan 02 (Cloudflare deployment implementation)

---
*State initialized: 2026-02-13*
*Last updated: 2026-02-20 - Phase 19-01 complete (dashboard + waitlist routes, Jinja2 templates, CSV export, date filtering)*
