# ViralForge

## What This Is

ViralForge is a product smoke test platform that generates short-form video ads and landing pages from a product idea, deploys LPs to free static hosting, and tracks waitlist signups to validate demand. Colleagues clone the repo, run locally via Docker, input a product idea, and get publish-ready TikTok/YouTube videos + a live landing page with conversion tracking — all automated. Built on a pluggable multi-provider AI stack (Google Gemini/Imagen/Veo, Kling, ElevenLabs, HeyGen).

## Core Value

Enable rapid product idea validation: product idea in → video ads + landing page out → deploy → measure waitlist signups — cheapest possible, zero manual steps between stages.

## Current Milestone: v3.0 Review Workflow UI

**Goal:** Wire the v1.0 video pipeline and LP generation into the web UI with a linear review workflow — users review and approve each stage (script, images, video clips, combined video, LP) before the next begins.

**Target features:**
- Linear review pipeline in web UI: Idea → Script → Images → Videos → Combined → LP
- Per-frame review at every stage (approve/reject each scene individually)
- AI regeneration on reject + manual prompt tweaking for specific changes
- Video and LP as independent generation paths (user picks which to generate)
- LP images sourced from video frames by default, with option to regenerate LP-specific images
- Mock mode by default, toggle to real AI providers when ready
- SSE progress streaming for each generation stage

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

### Active

- [ ] Linear review pipeline: Idea → Script → Images → Videos → Combined → LP in web UI
- [ ] Per-frame script review with approve/reject per scene
- [ ] Per-frame image review with approve/reject per frame
- [ ] Per-frame video clip review with approve/reject per clip
- [ ] Combined video preview with final approval
- [ ] LP module review with approve/reject per section
- [ ] AI regeneration on rejected frames with prompt feedback
- [ ] Manual prompt tweaking and re-generation option
- [ ] Video and LP as independent generation paths
- [ ] LP images from video frames by default, option to regenerate
- [ ] Mock/real AI toggle in web UI

### Out of Scope

- Multi-language support — English only for all generated content
- Real-time streaming — batch pipeline only
- Custom model training — uses pre-trained APIs only
- Voice cloning — legal considerations; use pre-built TTS voices
- Auto-publishing to social platforms — separate concern, manual post for now
- Payment processing — LPs collect waitlist signups only, no actual purchases
- A/B testing — single LP per product idea for v2; A/B is future scope
- Custom domain per LP — single domain with subpaths (e.g., domain.com/product-a)

## Context

**Shipped v1.0 with 7,628 LOC Python across 13 phases (30 plans).**

- **Pipeline architecture**: 5-stage orchestrated pipeline (trend_collection → trend_analysis → content_generation → composition → review) + dedicated UGC product ad pipeline
- **AI Providers**: Pluggable providers for LLM (Gemini, Claude), video (Kling, Minimax, Veo), images (Imagen), TTS (OpenAI, ElevenLabs, Fish Audio), avatars (HeyGen) — all with mock fallbacks
- **Google AI unification**: Single GOOGLE_API_KEY drives Gemini + Imagen + Veo, replacing need for separate API keys
- **UGC Pipeline**: Product input → Gemini analysis → Imagen hero image → Veo A-Roll/B-Roll → MoviePy composite
- **Tech stack**: Python 3.9+, FastAPI, Celery + Redis, PostgreSQL/SQLite, MoviePy v2, Docker Compose
- **Local dev**: SQLite + aiosqlite, USE_MOCK_DATA=true default, no API keys required

**v2.0 distribution model**: Colleagues clone private GitHub repo, run via Docker Compose locally. Code designed to switch to hosted public server deployment without changes. LPs always deployed to Cloudflare (publicly accessible for TikTok/YouTube traffic). Analytics always via Cloudflare Worker + D1 (works regardless of whether app is local or hosted).

## Constraints

- **Local Docker first**: Every service runs in Docker Compose. No cloud dependencies except external APIs.
- **Mock-first development**: Every AI provider has mock fallback for development without API keys.
- **Manual review before posting**: Videos go to `/output/review/`. No auto-posting.
- **GCP Cloud Run migration path**: Each Docker service maps 1:1 to future Cloud Run service.
- **Python 3.9 compatibility**: Use `from typing import List, Optional` not `list[str]`.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Stable Video Diffusion for prototype | Free, local, no API key needed. Architecture designed for easy swap. | ✓ Good — swapped to Kling/Veo in Phase 11-12 |
| Google Sheets with local fallback | Build full integration, use sample data until configured | ⚠️ Revisit — local config only, Sheets integration deferred to v2 |
| 6 microservices architecture | Each maps to future Cloud Run service | ✓ Good — clean separation of concerns |
| Celery + Redis for task queue | Standard Python async task processing | ✓ Good — handles pipeline orchestration well |
| Provider abstraction pattern | ABC base + mock + real providers with factory function | ✓ Good — enabled plugging in 10+ providers |
| Google AI unification (Phase 12) | Single API key for LLM + images + video | ✓ Good — simplified deployment |
| LLMProvider two-call pattern | generate_text() for freeform + generate_structured() for schema | ✓ Good — reliable structured output |
| MoviePy v2 immutable API | with_* methods instead of set_*, explicit resource cleanup | ✓ Good — prevented memory leaks |
| UGC Hook-Problem-Proof-CTA structure | Proven ad script framework, category-agnostic | ✓ Good — works for any product type |
| Cloudflare Pages + Worker + D1 for LP hosting + analytics | $0 cost, globally distributed, works with local or hosted app | — Pending |
| Single-file HTML LPs | No build step, no framework, deploy = copy one file | — Pending |
| Web UI as FastAPI templates (Jinja2) | No separate frontend build, stays in Python ecosystem | — Pending |

---
*Last updated: 2026-02-20 after v3.0 milestone start*
