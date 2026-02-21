# ViralForge

## What This Is

ViralForge is a product smoke test platform that generates short-form video ads and landing pages from a product idea, deploys LPs to free static hosting, and tracks waitlist signups to validate demand. Users input a product idea and get: AI-generated UGC video ads (with per-stage review and approval), a landing page with analytics, and conversion tracking. Built on a pluggable multi-provider AI stack (Google Gemini/Imagen/Veo, Kling, ElevenLabs, HeyGen) with HTMX-powered review UI.

## Core Value

Enable rapid product idea validation: product idea in → video ads + landing page out → deploy → measure waitlist signups — cheapest possible, zero manual steps between stages.

## Requirements

### Validated

- ✓ Docker Compose environment with PostgreSQL, Redis, FastAPI, Celery worker — v1.0
- ✓ Trend collection from TikTok (Apify) and YouTube (Data API v3) on configurable schedule — v1.0
- ✓ LLM-powered trend pattern analysis with engagement velocity scoring — v1.0
- ✓ Prompt-chain script generation producing full Video Production Plans — v1.0
- ✓ AI video generation via pluggable providers (Kling, Minimax, Veo, mock) — v1.0
- ✓ TTS voiceover generation via pluggable providers (OpenAI, ElevenLabs, Fish Audio) — v1.0
- ✓ MoviePy/FFmpeg video composition with text overlays, voiceover, and background music — v1.0
- ✓ Review queue with file-based approval/rejection workflow — v1.0
- ✓ Per-video cost tracking in generation metadata — v1.0
- ✓ Sequential 5-stage pipeline with checkpointing, retries, and status monitoring — v1.0
- ✓ HeyGen avatar integration for talking-head presenter videos — v1.0
- ✓ Google AI unification (Gemini LLM + Imagen images + Veo video) under single API key — v1.0
- ✓ UGC product ad pipeline: product input → hero image → script → A-Roll/B-Roll → composite — v1.0
- ✓ AI-generated landing pages from product idea input — v2.0
- ✓ Auto-deployment of LPs to Cloudflare Pages — v2.0
- ✓ Analytics collection (pageviews, clicks, form submissions) via Cloudflare Worker + D1 — v2.0
- ✓ Waitlist email collection on LP — v2.0
- ✓ Admin dashboard with per-LP traffic, CVR, and signup counts — v2.0
- ✓ Browser-based web UI for product idea input and generation — v2.0
- ✓ Linear review pipeline: Idea → Script → Images → Videos → Combined → LP in web UI — v3.0
- ✓ Per-frame review at every stage (approve/reject each scene/image/clip) — v3.0
- ✓ DB-backed UGC job state with typed per-stage columns and state machine — v3.0
- ✓ Mock/real AI toggle per job — v3.0
- ✓ SSE real-time progress streaming for each generation stage — v3.0
- ✓ Stage gate enforcement (next stage locked until current approved) — v3.0
- ✓ Inline media preview (images + video with HTTP 206 seek) — v3.0
- ✓ LP per-module review with video frame hero image and LP-specific regen — v3.0

### Active

(None — next milestone not yet defined)

### Out of Scope

- Multi-language support — English only for all generated content
- Real-time streaming — batch pipeline only
- Custom model training — uses pre-trained APIs only
- Voice cloning — legal considerations; use pre-built TTS voices
- Auto-publishing to social platforms — separate concern, manual post for now
- Payment processing — LPs collect waitlist signups only, no actual purchases
- A/B testing — single LP per product idea; future scope
- Custom domain per LP — single domain with subpaths
- Full video timeline editor — regeneration handles most needs
- Real-time collaborative review — single-user tool
- Parallel stage review — breaks linear pipeline contract

## Context

**Shipped v3.0 with 12,190 LOC Python across 25 phases (54 plans).**

- **UGC Review Pipeline**: 5-stage linear review (Analysis → Script → A-Roll → B-Roll → Composition) with HTMX approve/reject cards, SSE progress, stage gates
- **LP Pipeline**: LP generation from UGC output, per-module review (headline, hero, CTA, benefits), hero image from video frames with regen option
- **AI Providers**: Pluggable providers for LLM (Gemini, Claude), video (Kling, Minimax, Veo), images (Imagen), TTS (OpenAI, ElevenLabs, Fish Audio), avatars (HeyGen) — all with mock fallbacks
- **Tech stack**: Python 3.9+, FastAPI, Celery + Redis, PostgreSQL, HTMX 2.0.8, MoviePy v2, Docker Compose
- **Frontend**: Jinja2 templates + HTMX (no build step, no JS framework)
- **State management**: UGCJob model with python-statemachine 2.6.0 guard layer, per-job use_mock toggle

**Known tech debt (v3.0):**
- SSE raw JSON in progress div (cosmetic)
- Accept-hero-candidate shows controls partial only (requires reload for hero image)
- Dead import in ui/router.py (LandingPageRequest)

## Constraints

- **Local Docker first**: Every service runs in Docker Compose. No cloud dependencies except external APIs.
- **Mock-first development**: Every AI provider has mock fallback for development without API keys.
- **Manual review before posting**: Videos go to `/output/review/`. No auto-posting.
- **GCP Cloud Run migration path**: Each Docker service maps 1:1 to future Cloud Run service.
- **Python 3.9 compatibility**: Use `from typing import List, Optional` not `list[str]`.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Stable Video Diffusion for prototype | Free, local, no API key needed | ✓ Good — swapped to Kling/Veo in Phase 11-12 |
| 6 microservices architecture | Each maps to future Cloud Run service | ✓ Good — clean separation of concerns |
| Celery + Redis for task queue | Standard Python async task processing | ✓ Good — handles pipeline orchestration well |
| Provider abstraction pattern | ABC base + mock + real providers with factory function | ✓ Good — enabled plugging in 10+ providers |
| Google AI unification (Phase 12) | Single API key for LLM + images + video | ✓ Good — simplified deployment |
| LLMProvider two-call pattern | generate_text() for freeform + generate_structured() for schema | ✓ Good — reliable structured output |
| MoviePy v2 immutable API | with_* methods instead of set_*, explicit resource cleanup | ✓ Good — prevented memory leaks |
| UGC Hook-Problem-Proof-CTA structure | Proven ad script framework, category-agnostic | ✓ Good — works for any product type |
| Cloudflare Pages + Worker + D1 | $0 cost, globally distributed | ✓ Good — works for both local and hosted app |
| Single-file HTML LPs | No build step, deploy = copy one file | ✓ Good — fast deployment |
| Web UI as FastAPI templates (Jinja2) | No separate frontend build, stays in Python ecosystem | ✓ Good — HTMX handles interactivity well |
| python-statemachine as guard layer | DB column is source of truth, SM validates transitions only | ✓ Good — clean separation |
| UGCJob typed columns (not JSON blob) | Each stage output has its own column with proper type | ✓ Good — queryable, validated |
| HTMX outerHTML swap for review actions | No page reload on approve/reject/regenerate | ✓ Good — instant UI feedback |
| SSE per-iteration session pattern | Fresh DB session per poll, not held for stream duration | ✓ Good — no connection leaks |
| Candidate pattern for regeneration | Never mutate approved content; store candidate separately | ✓ Good — safe content management |

---
*Last updated: 2026-02-21 after v3.0 milestone*
