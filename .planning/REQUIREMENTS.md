# Requirements: ViralForge

**Defined:** 2026-02-13
**Core Value:** Reliably produce publish-ready short-form videos from a theme/product input — full pipeline from trend analysis through composition — without manual intervention between stages.

## v1 Requirements

Requirements for initial prototype. Each maps to roadmap phases.

### Infrastructure

- [ ] **INFRA-01**: System runs locally via Docker Compose with PostgreSQL, Redis, and app containers
- [ ] **INFRA-02**: Celery + Redis handles async task execution for all pipeline stages
- [ ] **INFRA-03**: PostgreSQL stores jobs, trends, scripts, video metadata with Alembic migrations
- [ ] **INFRA-04**: FastAPI provides REST API for manual pipeline trigger and status monitoring
- [ ] **INFRA-05**: Local config files (YAML/JSON) provide sample data as Google Sheets fallback
- [ ] **INFRA-06**: Environment variables configure all API keys and service connections (.env file)
- [ ] **INFRA-07**: Health check endpoint reports service status and database connectivity

### Trend Collection

- [ ] **TREND-01**: System scrapes top 50 trending TikTok videos via Apify API per run
- [ ] **TREND-02**: System scrapes top 50 trending YouTube Shorts (< 60s) via YouTube Data API v3
- [ ] **TREND-03**: Collected data includes title, description, hashtags, engagement counts, duration, creator info, sound name, thumbnail URL
- [ ] **TREND-04**: Trends stored in PostgreSQL with deduplication on (platform, external_id)
- [ ] **TREND-05**: Trend collection runs on configurable schedule (default: every 6 hours)

### Pattern Analysis

- [ ] **ANLYS-01**: System aggregates last 24h of collected trending videos for analysis
- [ ] **ANLYS-02**: Claude API classifies videos by style (cinematic, talking-head, montage, text-heavy, etc.)
- [ ] **ANLYS-03**: System calculates engagement velocity: (likes + comments + shares) / hours_since_posted
- [ ] **ANLYS-04**: System clusters top-performing videos and extracts patterns (format, duration, hook type, text overlay strategy, audio type)
- [ ] **ANLYS-05**: Structured Trend Report JSON stored in PostgreSQL

### Script Generation

- [ ] **SCRIPT-01**: System reads theme/product config from local config file (or Google Sheets when connected)
- [ ] **SCRIPT-02**: Claude API generates Video Production Plan via 5-step prompt chain (theme interpretation → trend alignment → scene construction → narration → text overlay design)
- [ ] **SCRIPT-03**: Production Plan includes: video_prompt, duration_target, aspect_ratio, text_overlays[], voiceover_script, hook_text, cta_text, hashtags[], title, description
- [ ] **SCRIPT-04**: Generated scripts align with current trend patterns from analysis stage

### Video Generation

- [ ] **VIDEO-01**: System generates video clips using Stable Video Diffusion locally in Docker
- [ ] **VIDEO-02**: Video output is 9:16 vertical format at configurable resolution (720p default)
- [ ] **VIDEO-03**: System chains multiple 2-4 second clips to reach target duration (15-30 seconds)
- [ ] **VIDEO-04**: Generated clips downloaded as MP4 to local storage
- [ ] **VIDEO-05**: Video generation backend is abstracted behind interface (swappable to Veo/Sora later)

### Voiceover

- [ ] **VOICE-01**: System generates TTS audio from voiceover_script using OpenAI TTS API (tts-1-hd)
- [ ] **VOICE-02**: Output audio file (MP3/WAV) synced to video duration
- [ ] **VOICE-03**: TTS provider is configurable (OpenAI default, ElevenLabs/Fish Audio swappable)

### Composition

- [ ] **COMP-01**: FFmpeg composites raw AI video + voiceover audio + text overlays into final MP4
- [ ] **COMP-02**: Text overlays support configurable font (Montserrat Bold default), position, color, shadow, animation, timing
- [ ] **COMP-03**: Output is final MP4 (H.264 video, AAC audio) in 9:16 aspect ratio
- [ ] **COMP-04**: System generates thumbnail from configurable video frame
- [ ] **COMP-05**: Optional background music mixing with configurable volume level

### Review & Output

- [ ] **REVIEW-01**: Final videos saved to /output/review/ directory
- [ ] **REVIEW-02**: Generation log tracks: gen_id, timestamp, theme, trend pattern, prompts, model used, cost, output path, status
- [ ] **REVIEW-03**: REST API endpoint allows approving videos (moves to /output/approved/)
- [ ] **REVIEW-04**: REST API endpoint allows rejecting videos (moves to /output/rejected/)
- [ ] **REVIEW-05**: Per-video cost tracked and logged (all API call costs summed)

### Pipeline Orchestration

- [ ] **ORCH-01**: Full 8-stage pipeline executes sequentially: trend → analysis → script → video → voiceover → composition → review
- [ ] **ORCH-02**: Pipeline has per-stage checkpointing (resume from last completed stage on failure)
- [ ] **ORCH-03**: Each stage has configurable retry count (default: 3) with exponential backoff
- [ ] **ORCH-04**: Pipeline status visible via REST API and Docker logs
- [ ] **ORCH-05**: Manual trigger via POST /api/generate kicks off full pipeline run

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Google Sheets Integration

- **SHEETS-01**: Google Sheets Config sheet drives all generation parameters
- **SHEETS-02**: Google Sheets Generation Log receives all generation output
- **SHEETS-03**: Google Sheets Product/Content References provide content inputs
- **SHEETS-04**: Bidirectional sync between PostgreSQL and Google Sheets

### Auto-Publishing

- **PUB-01**: Auto-upload approved videos to TikTok via Content Posting API
- **PUB-02**: Auto-upload approved videos to YouTube Shorts via YouTube Data API v3
- **PUB-03**: Publishing gated by auto_post boolean in config (default: false)
- **PUB-04**: Published video URL written back to generation log

### Microservices Split

- **MICRO-01**: Pipeline split into 6 independent services (orchestrator, scraper, analyzer, generator, composer, publisher)
- **MICRO-02**: Each service has its own Dockerfile and can be deployed independently
- **MICRO-03**: Services communicate via Celery task queues (no direct HTTP calls)

### Advanced Features

- **ADV-01**: Viral prediction scoring for generated content
- **ADV-02**: Pattern recognition from historically successful content
- **ADV-03**: Content variant generation for A/B testing
- **ADV-04**: Niche-specific style templates

## Out of Scope

| Feature | Reason |
|---------|--------|
| Dashboard UI | Google Sheets (v2) is the control plane; no custom UI for MVP |
| Multi-language support | English only for all generated content |
| Cloud deployment (GCP) | Local Docker first; Cloud Run migration is post-MVP |
| Real-time streaming | Batch pipeline only |
| Custom model training | Uses pre-trained APIs only |
| Video editor features | Trim, effects, transitions — users can edit elsewhere |
| Multi-user collaboration | Single-user workflow for MVP |
| Live preview during generation | Show progress status instead |
| Voice cloning | Legal considerations; use pre-built TTS voices |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| INFRA-01 | — | Pending |
| INFRA-02 | — | Pending |
| INFRA-03 | — | Pending |
| INFRA-04 | — | Pending |
| INFRA-05 | — | Pending |
| INFRA-06 | — | Pending |
| INFRA-07 | — | Pending |
| TREND-01 | — | Pending |
| TREND-02 | — | Pending |
| TREND-03 | — | Pending |
| TREND-04 | — | Pending |
| TREND-05 | — | Pending |
| ANLYS-01 | — | Pending |
| ANLYS-02 | — | Pending |
| ANLYS-03 | — | Pending |
| ANLYS-04 | — | Pending |
| ANLYS-05 | — | Pending |
| SCRIPT-01 | — | Pending |
| SCRIPT-02 | — | Pending |
| SCRIPT-03 | — | Pending |
| SCRIPT-04 | — | Pending |
| VIDEO-01 | — | Pending |
| VIDEO-02 | — | Pending |
| VIDEO-03 | — | Pending |
| VIDEO-04 | — | Pending |
| VIDEO-05 | — | Pending |
| VOICE-01 | — | Pending |
| VOICE-02 | — | Pending |
| VOICE-03 | — | Pending |
| COMP-01 | — | Pending |
| COMP-02 | — | Pending |
| COMP-03 | — | Pending |
| COMP-04 | — | Pending |
| COMP-05 | — | Pending |
| REVIEW-01 | — | Pending |
| REVIEW-02 | — | Pending |
| REVIEW-03 | — | Pending |
| REVIEW-04 | — | Pending |
| REVIEW-05 | — | Pending |
| ORCH-01 | — | Pending |
| ORCH-02 | — | Pending |
| ORCH-03 | — | Pending |
| ORCH-04 | — | Pending |
| ORCH-05 | — | Pending |

**Coverage:**
- v1 requirements: 40 total
- Mapped to phases: 0
- Unmapped: 40 (pending roadmap creation)

---
*Requirements defined: 2026-02-13*
*Last updated: 2026-02-13 after initial definition*
