---
created: 2026-03-04T21:58:06.262Z
title: Deploy LP to Cloudflare and run live E2E signup test
area: deployment
files:
  - app/services/landing_page/deployer.py
  - app/services/landing_page/templates/sections/hero.html.j2
  - app/ui/router.py
---

## Problem

Local E2E testing of inline signup forms passed (hero + CTA repeat forms both submit, duplicates rejected, DB rows created). But live deployment test is blocked — `CLOUDFLARE_API_TOKEN` not set in `.env`.

Need to verify:
- `POST /ui/deploy/{run_id}` succeeds and returns deployed URL
- Deployed page has `<meta name="api-base">` tag (JS reads this to POST back to app server)
- Cross-origin waitlist signup from CF-hosted page reaches the app server DB
- CORS headers work correctly in production (already `allow_origins=["*"]` in `app/main.py`)

## Solution

1. Get a free Cloudflare Pages API token (free tier supports this)
2. Set in `.env`:
   ```
   CF_API_TOKEN=<token>
   CF_ACCOUNT_ID=<account_id>
   ```
3. Rebuild: `docker compose up -d --build web celery-worker`
4. Deploy: `POST /ui/deploy/{run_id}` → get deployed URL
5. Open deployed URL in browser, run these checks:
   - `document.querySelector('meta[name="api-base"]').content` → should be the app server URL
   - Submit unique test email → verify DB row created with correct `lp_source`
   - Submit duplicate → verify inline error
6. Bonus: test from incognito/different browser to confirm no cookie/session dependency
