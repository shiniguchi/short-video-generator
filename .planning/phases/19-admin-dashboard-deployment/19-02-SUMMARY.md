---
phase: 19-admin-dashboard-deployment
plan: 02
subsystem: ui, deployment
tags: [fastapi, cloudflare-pages, wrangler, asyncio, jinja2]

requires:
  - phase: 18-cloudflare-analytics
    provides: inject_analytics_beacon() called at deploy-time in deployer.py
  - phase: 17-web-ui
    provides: deploy stub POST /ui/deploy/{run_id} replaced in this plan
  - phase: 19-01
    provides: LandingPage.deployed_url, deployed_at fields + preview.html base

provides:
  - app/services/landing_page/deployer.py — deploy_to_cloudflare_pages() via wrangler CLI
  - POST /ui/deploy/{run_id} real implementation (replaces Phase 17 stub)
  - Preview UI: deployed URL link, Re-deploy button, deployed-info bar

affects: [final-smoke-test-workflow, cloudflare-pages-hosting]

tech-stack:
  added: [asyncio.create_subprocess_exec for wrangler CLI, tempfile.TemporaryDirectory for ephemeral HTML]
  patterns: [lazy import deployer inside route body, beacon injection at deploy-time not generation-time, graceful error return on missing CF credentials]

key-files:
  created:
    - app/services/landing_page/deployer.py
  modified:
    - app/config.py
    - app/ui/router.py
    - app/ui/static/ui.js
    - app/ui/templates/preview.html
    - app/ui/static/ui.css

key-decisions:
  - "Beacon injection at deploy-time in deployer.py — source HTML stays clean, beacon only on deployed copies"
  - "asyncio.create_subprocess_exec for wrangler — non-blocking subprocess, 120s timeout with proc.kill() on timeout"
  - "Graceful error return dict (not HTTPException) on missing CF credentials — better UX than 500 error"
  - "Re-deploy supported by overwriting deployed_url and deployed_at — no special logic needed"
  - "Lazy import deployer inside route body — consistent with project pattern, avoids import chain at server start"

duration: ~2min
completed: 2026-02-20
---

# Phase 19 Plan 02: Cloudflare Pages Deployment Summary

**One-click LP deployment to Cloudflare Pages via wrangler CLI subprocess, replacing the Phase 17 stub with beacon injection, DB status tracking, and deployed URL display in preview UI.**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-02-20T14:39:32Z
- **Completed:** 2026-02-20T14:41:13Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- `deploy_to_cloudflare_pages()` reads LP HTML, injects analytics beacon (if Worker URL set), writes to temp dir, calls `npx wrangler pages deploy` with CF credentials from env
- Deploy route replaces Phase 17 stub: fetches LP from DB, calls deployer, updates `status='deployed'`, `deployed_url`, `deployed_at` on success
- Preview UI: deployed URL shown as clickable link, button changes to "Re-deploy" after first deploy, `deployed-info` bar with green styling shows live URL for already-deployed LPs
- Error path returns `{"status":"error","message":"..."}` when `CLOUDFLARE_API_TOKEN` or `CF_PAGES_PROJECT_NAME` not set — no crash, clear message shown in red

## Task Commits

1. **Task 1: Create deployer service and add config settings** - `1d90f2c` (feat)
2. **Task 2: Replace deploy stub with real deployment and update preview UI** - `c7c72e0` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `app/services/landing_page/deployer.py` — New module: deploy_to_cloudflare_pages() + _extract_pages_url()
- `app/config.py` — Added cf_api_token, cf_account_id, cf_pages_project_name settings
- `app/ui/router.py` — Replaced stub with real implementation, added session Depends, DB update on success
- `app/ui/static/ui.js` — deployLP() handles deployed URL link, error in red, Re-deploy button text
- `app/ui/templates/preview.html` — deployed-info bar, dynamic button text for already-deployed LPs
- `app/ui/static/ui.css` — .deployed-info, .deployed-info a, .deployed-label styles

## Decisions Made

- Beacon injection at deploy-time not generation-time — source HTML stays clean; consistent with Phase 18-02 decision
- `asyncio.create_subprocess_exec` for wrangler — non-blocking, 120s timeout with `proc.kill()` on timeout
- Graceful error return dict on missing CF credentials — better UX than HTTP 500, JS can display message in red
- Re-deploy by overwriting `deployed_url` and `deployed_at` — no extra logic, same code path handles both first deploy and re-deploy
- Lazy import deployer inside route body — consistent with project pattern from Phase 17-02 and 18-02 decisions

## Deviations from Plan

None — plan executed exactly as written.

## User Setup Required

Before deploying LPs, users must configure:
- `CLOUDFLARE_API_TOKEN` — Cloudflare Dashboard > My Profile > API Tokens > Create Token (Cloudflare Pages:Edit)
- `CF_ACCOUNT_ID` — Cloudflare Dashboard > any domain > Overview > right sidebar
- `CF_PAGES_PROJECT_NAME` — Name of pre-existing Pages project (create with: `npx wrangler pages project create <name>`)

## Next Phase Readiness

Phase 19 is complete. Full smoke test workflow now operational:
1. Generate LP via `/ui/generate` (form) or CLI
2. Preview at `/ui/preview/{run_id}`
3. Deploy to Cloudflare Pages with one click — beacon injected automatically
4. View analytics at `/ui/dashboard`, manage signups at `/ui/waitlist`

---
*Phase: 19-admin-dashboard-deployment*
*Completed: 2026-02-20*
