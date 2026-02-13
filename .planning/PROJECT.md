# ViralForge

## What This Is

ViralForge is a fully containerized (Docker Compose) Python web application that automatically generates short-form videos (TikTok / YouTube Shorts) by analyzing trending viral content and producing AI-generated videos aligned to a user-defined theme or product. The system is controlled via Google Sheets as the single source of truth for configuration, with no dashboard UI for MVP. The complete 8-stage pipeline runs locally in Docker with visible logs for every stage.

## Core Value

The complete pipeline must reliably take a theme/product defined in Google Sheets and produce a publish-ready short-form video — from trend analysis through script generation, video creation, voiceover, and final composition — without manual intervention between stages.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Trend collection from TikTok (Apify) and YouTube (Data API v3) on configurable cron
- [ ] LLM-powered trend pattern analysis with engagement velocity scoring
- [ ] Prompt-chain script generation producing full Video Production Plans
- [ ] AI video generation via Stable Video Diffusion (local, swappable to Veo/Sora)
- [ ] TTS voiceover generation via OpenAI TTS (swappable to ElevenLabs/Fish Audio)
- [ ] FFmpeg video composition with text overlays, voiceover, and background music
- [ ] Review queue with file-based approval workflow synced to Google Sheets
- [ ] Auto-publishing to TikTok and YouTube (config-gated, disabled by default)
- [ ] Google Sheets as master data source (config, content refs, generation log)
- [ ] Per-video cost tracking logged to Google Sheets
- [ ] 6 app services + 2 infra services in Docker Compose
- [ ] Sequential 8-stage pipeline with full error handling and retries

### Out of Scope

- Dashboard UI — Google Sheets is the control plane for MVP
- Multi-language support — English only for all generated content
- Cloud deployment — local Docker first, GCP Cloud Run is future migration path
- Real-time streaming — batch pipeline only
- Custom model training — uses pre-trained APIs only

## Context

- **Pipeline architecture**: 8 sequential stages (Trend Collection → Pattern Analysis → Script Generation → Video Generation → Voiceover → Composition → Review → Publishing)
- **Microservices**: 6 app services (orchestrator, trend-scraper, analyzer, generator, composer, publisher) + PostgreSQL + Redis
- **Video generation strategy**: Start with Stable Video Diffusion running locally in Docker (free, no API key needed). Architecture supports swapping to Google Veo 3.1 or OpenAI Sora 2 via config change.
- **Google Sheets**: Full integration code built, but prototype uses sample/local config data until service account is set up. Three sheets: Config, Product/Content References, Generation Log.
- **Target output**: 1 video per day, 15-30 seconds, 9:16 vertical format, ultra-realistic cinematic style
- **Tech stack**: Python 3.12+, FastAPI, Celery + Redis, PostgreSQL 16, FFmpeg, Docker Compose

## Constraints

- **Local Docker first**: Every service must run in Docker Compose. No cloud dependencies except external APIs.
- **Google Sheets single source of truth**: All config from Sheets, all output written back. No separate config files for business logic.
- **Dynamically prompt-able**: Changing the `theme` cell must change all generated content without code modifications.
- **Cost tracking**: Every API call cost must be logged. Per-video cost in Generation Log.
- **Manual review before posting (MVP)**: Videos go to `/output/review/`. No auto-posting until `auto_post=true`.
- **GCP Cloud Run migration path**: Each Docker service maps 1:1 to future Cloud Run service. Environment variables for all config.
- **Video generation**: Stable Video Diffusion locally for prototype. Must be swappable to Veo/Sora via config.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Stable Video Diffusion for prototype | Free, local, no API key needed. Architecture designed for easy swap to Veo/Sora. | — Pending |
| Google Sheets with local fallback | Build full Sheets integration but use sample data until service account configured | — Pending |
| 6 microservices (not monolith) | PRD specifies microservice architecture; each maps to future Cloud Run service | — Pending |
| Celery + Redis for task queue | Standard Python async task processing; handles pipeline stage coordination | — Pending |

---
*Last updated: 2026-02-13 after initialization*
