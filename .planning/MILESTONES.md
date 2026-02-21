# Milestones

## v1.0 MVP (Shipped: 2026-02-15)

**Phases completed:** 13 phases, 30 plans
**Timeline:** 3 days (2026-02-13 → 2026-02-15)

**Key accomplishments:**
- Docker Compose environment with PostgreSQL, Redis, FastAPI, Celery worker
- 5-stage orchestrated pipeline: trend collection → analysis → content generation → composition → review
- Pluggable AI providers: Gemini, Kling, Minimax, Veo, Imagen, ElevenLabs, HeyGen — all with mock fallbacks
- Google AI unification: single API key for Gemini LLM + Imagen images + Veo video
- UGC product ad pipeline: product input → hero image → script → A-Roll/B-Roll → composite
- MoviePy/FFmpeg video composition with text overlays, voiceover, background music

---

## v2.0 Smoke Test Platform (Shipped: 2026-02-20)

**Phases completed:** 6 phases, 14 plans
**Timeline:** 2 days (2026-02-19 → 2026-02-20)

**Key accomplishments:**
- AI-generated landing pages from product idea with proven copywriting formulas
- Auto-deployment of LPs to Cloudflare Pages with one action
- Cloudflare Worker + D1 analytics: pageviews, clicks, form submissions per LP
- Waitlist email collection with validation, dedup, and honeypot spam prevention
- Admin dashboard with per-LP traffic, signup count, conversion rate, CSV export
- Browser-based web UI for product idea input, LP generation, preview, and deployment

---

## v3.0 Review Workflow UI (Shipped: 2026-02-21)

**Phases completed:** 6 phases (20-25), 10 plans, 19 tasks
**Timeline:** 2 days (2026-02-20 → 2026-02-21)
**Git range:** feat(20-01) → feat(25-02)
**Files changed:** 56 files, +8,313 lines
**Total codebase:** 12,190 LOC Python

**Key accomplishments:**
- DB-backed UGC job state with typed per-stage columns, state machine guard layer, Alembic migration
- Five per-stage Celery tasks with NullPool sessions, use_mock threading, state transitions
- HTTP API: job list, SSE progress stream, advance/regenerate/edit with stage gate validation
- HTMX-powered review UI: stage stepper, per-item card grids, in-place partial swaps
- Inline media preview: Jinja2 media_url filter, img/video with HTTP 206 seek support
- LP integration: per-module review, video frame extraction, LP hero regen via Celery

**Tech debt:**
- SSE raw JSON in progress div (cosmetic — page reloads on terminal state)
- Accept-hero-candidate shows controls partial, not updated hero image (requires reload)
- Dead import in ui/router.py (LandingPageRequest shadowed by LPRequest alias)

---
