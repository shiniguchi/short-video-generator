# ViralForge

## What This Is

ViralForge is a fully containerized (Docker Compose) Python web application that automatically generates short-form marketing videos (TikTok / YouTube Shorts) from product or theme input. It analyzes trending viral content, generates AI scripts and visuals, and composites final 9:16 MP4 videos — all through a pluggable multi-provider AI stack (Google Gemini/Imagen/Veo, Kling, ElevenLabs, HeyGen, and more). Includes a dedicated UGC product ad pipeline for universal product-to-video generation.

## Core Value

Reliably produce publish-ready short-form videos from a theme/product input — full pipeline from trend analysis through composition — without manual intervention between stages.

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

### Active

(None — next milestone not yet planned)

### Out of Scope

- Dashboard UI — Google Sheets or API-only for control plane
- Multi-language support — English only for all generated content
- Cloud deployment (GCP) — local Docker first; Cloud Run migration is post-MVP
- Real-time streaming — batch pipeline only
- Custom model training — uses pre-trained APIs only
- Voice cloning — legal considerations; use pre-built TTS voices
- Auto-publishing to social platforms — deferred to v2

## Context

**Shipped v1.0 with 7,628 LOC Python across 13 phases (30 plans).**

- **Pipeline architecture**: 5-stage orchestrated pipeline (trend_collection → trend_analysis → content_generation → composition → review) + dedicated UGC product ad pipeline
- **AI Providers**: Pluggable providers for LLM (Gemini, Claude), video (Kling, Minimax, Veo), images (Imagen), TTS (OpenAI, ElevenLabs, Fish Audio), avatars (HeyGen) — all with mock fallbacks
- **Google AI unification**: Single GOOGLE_API_KEY drives Gemini + Imagen + Veo, replacing need for separate API keys
- **UGC Pipeline**: Product input → Gemini analysis → Imagen hero image → Veo A-Roll/B-Roll → MoviePy composite
- **Tech stack**: Python 3.9+, FastAPI, Celery + Redis, PostgreSQL/SQLite, MoviePy v2, Docker Compose
- **Local dev**: SQLite + aiosqlite, USE_MOCK_DATA=true default, no API keys required

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

---
*Last updated: 2026-02-15 after v1.0 milestone*
