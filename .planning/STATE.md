# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-13)

**Core value:** Reliably produce publish-ready short-form videos from a theme/product input — full pipeline from trend analysis through composition — without manual intervention between stages.
**Current focus:** Phase 13 — UGC Product Ad Pipeline (Google AI only)

## Current Position

Phase: 13 of 13 (UGC Product Ad Pipeline)
Plan: 2 of 3 in current phase
Status: In progress
Last activity: 2026-02-15 — Completed 13-02-PLAN.md (UGC Asset Generation & Composition)

Progress: [█████████░] 94%

## Performance Metrics

**Velocity:**
- Total plans completed: 27
- Average duration: 3 min
- Total execution time: 2.3 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01 | 3 | 9 min | 3 min |
| 02 | 3 | 14 min | 5 min |
| 03 | 3 | 18 min | 6 min |
| 04 | 2 | 3 min | 2 min |
| 05 | 1 | 3 min | 3 min |
| 06 | 2 | 3 min | 2 min |
| 07 | 1 | 2 min | 2 min |
| 08 | 2 | 3 min | 2 min |
| 09 | 1 | 1 min | 1 min |
| 10 | 2 | 7 min | 4 min |
| 11 | 3 | 7 min | 2 min |
| 12 | 4 | 13 min | 3 min |
| 13 | 2 | 5 min | 2 min |

**Recent Trend:**
- Last 5 plans: 12-01 (3 min), 12-03 (2 min), 12-04 (2 min), 13-01 (2 min), 13-02 (2 min)
- Trend: Excellent (Consistent fast execution)

*Updated after each plan completion*
| Phase 10 P01 | 189 | 1 tasks | 1 files |
| Phase 10 P02 | 4 | 2 tasks | 2 files |
| Phase 11 P01 | 3 | 2 tasks | 6 files |
| Phase 11 P02 | 2 | 2 tasks | 6 files |
| Phase 11 P03 | 2 | 2 tasks | 8 files |
| Phase 11 P03 | 2 | 2 tasks | 8 files |
| Phase 12 P02 | 164 | 2 tasks | 4 files |
| Phase 12 P03 | 2 | 2 tasks | 5 files |
| Phase 12 P01 | 284 | 2 tasks | 6 files |
| Phase 12 P04 | 2 | 2 tasks | 4 files |
| Phase 13 P01 | 2 | 2 tasks | 2 files |
| Phase 13 P02 | 161 | 2 tasks | 3 files |
| Phase 13 P02 | 161 | 2 tasks | 3 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- Stable Video Diffusion for prototype (local, free, swappable to Veo/Sora)
- Google Sheets with local fallback (build full integration, use sample data until service account configured)
- 6 microservices architecture (each maps to future Cloud Run service)
- Celery + Redis for task queue (standard Python async task processing)
- [Phase 01]: Use expire_on_commit=False in async SQLAlchemy session factory to prevent implicit queries
- [Phase 01]: Use JSON columns for flexible metadata storage in pipeline entities
- [Phase 01]: SQLAlchemy 'metadata' is reserved — use extra_data = Column("metadata", JSON) pattern
- [Phase 01]: Local dev uses SQLite + aiosqlite and SQLAlchemy Celery transport (no Docker/Redis/PostgreSQL required)
- [Phase 01]: Python 3.9 compatibility — FastAPI pinned to >=0.100.0, migration uses CURRENT_TIMESTAMP not now()
- [Phase 02-01]: Composite unique constraint (platform, external_id) prevents duplicate trends across platforms
- [Phase 02-01]: Store engagement_velocity as calculated field for query performance
- [Phase 02-01]: USE_MOCK_DATA=True default enables testing without API credentials
- [Phase 02-01]: JSON columns in TrendReport allow flexible analysis schema evolution
- [Phase 02-02]: Use httpx for synchronous Apify REST API calls (simpler than async apify-client in Celery tasks)
- [Phase 02-02]: Cycle mock data with _dup_N suffix to support any limit size
- [Phase 02-02]: SQLite UPSERT with on_conflict_do_update prevents duplicates on (platform, external_id)
- [Phase 02-02]: Minimum 0.1 hour threshold in engagement velocity prevents division by zero
- [Phase 02-03]: Tool-use pattern for Claude structured outputs (more reliable than output_config for complex schemas)
- [Phase 02-03]: Recursively add additionalProperties: false to JSON schema for Claude API requirement
- [Phase 02-03]: Fallback to mock data on Claude API errors ensures analysis always succeeds
- [Phase 02-03]: Celery Beat runs collection and analysis at same 6h interval but independently
- [Phase 02-03]: Use 'or 0' pattern for None values in engagement_velocity field (dict.get() default doesn't handle None)
- [Phase 03-01]: ThemeConfig reads from sample-data.yml with Pydantic validation
- [Phase 03-01]: Production Plan schema has 11 required fields validated by VideoProductionPlanCreate
- [Phase 03-02]: Provider abstraction pattern: ABC base + mock + real providers with factory function
- [Phase 03-02]: MockVideoProvider generates solid-color 720x1280 MP4 clips via moviepy
- [Phase 03-02]: MockTTSProvider generates silent audio with duration from text length (~15 chars/sec)
- [Phase 03-03]: Claude 5-step prompt chain optimized to 2 API calls (steps 1-4 analysis + step 5 structured output)
- [Phase 03-03]: generate_content_task returns {script_id, video_path, audio_path} — compositing deferred to Phase 4
- [Phase 04-01]: MoviePy v2.x immutable API — use with_* methods instead of set_* (with_audio, with_start, with_duration, with_position, with_multiply_volume)
- [Phase 04-01]: Explicit resource cleanup — context managers for VideoFileClip/AudioFileClip, explicit .close() on composite clips to prevent memory leaks
- [Phase 04-01]: Position mapping for 9:16 video — top=(center, 100), center=(center, center), bottom=(center, 1100)
- [Phase 04-01]: Montserrat font family — bold=Montserrat-Bold, normal=Montserrat-Regular, highlight=Montserrat-ExtraBold
- [Phase 04-01]: Background music at 30% volume default ensures voiceover is dominant
- [Phase 04-01]: H.264/AAC encoding with 5Mbps video and 128k audio bitrate for platform compatibility
- [Phase 04-02]: End-to-end pipeline chaining: generate_content_task automatically chains into compose_video_task
- [Phase 04-02]: Async database helpers in Celery tasks follow asyncio.run() pattern from Phase 3
- [Phase 05-01]: Changed composition_output_dir from output/final to output/review for review workflow
- [Phase 05-01]: Generation metadata stored in Video.extra_data includes gen_id, timestamp, theme, trend_pattern, prompts, model, cost, path, status
- [Phase 06-01]: orchestrate_pipeline_task has max_retries=0 — individual stages handle their own retries
- [Phase 06-01]: Composition chained from content generation — extracted compose_task_id and waited for completion
- [Phase 06-01]: completed_stages list in Job.extra_data enables resume-from-checkpoint capability
- [Phase 06-01]: Review stage marked complete by orchestrator — manual review happens via API endpoints
- [Phase 06-02]: Lazy imports in endpoints avoid circular dependencies between routes, pipeline, and models
- [Phase 06-02]: Progress percentage computed on-the-fly from Job.extra_data["completed_stages"]
- [Phase 06-02]: Retry endpoint preserves completed_stages to enable true resume-from-checkpoint
- [Phase 06-02]: Poll URL pattern (/jobs/{id}) enables client-side status monitoring
- [Phase 07-01]: Use optional job_id parameter instead of required for backward compatibility
- [Phase 08-01]: Migration entrypoint pattern — bash script runs alembic upgrade head before exec'ing to service command
- [Phase 08-01]: Celery worker depends on web service_healthy to ensure migrations completed before worker starts
- [Phase 08-01]: USE_MOCK_DATA=true default in Docker prevents accidental external API calls during development
- [Phase 08-01]: Health check start_period accounts for initialization time (postgres 10s, redis 5s, web 30s for migrations)
- [Phase 08-02]: Created 6-step validation script covering syntax, services, health, pipeline, and logs
- [Phase 08-02]: Validation script uses POSIX-compatible JSON parsing (grep/cut) avoiding jq dependency
- [Phase 09]: On-demand Job creation pattern for manual endpoints (job_id optional, creates Job when None)
- [Phase 10-02]: Phase 4 VERIFICATION.md created with evidence-backed claims from actual source file reads
- [Phase 10-02]: Phase 8 VERIFICATION.md updated from human_needed to passed reflecting Docker Desktop installation
- [Phase 10-01]: VERIFICATION.md template follows Phase 1 structure with YAML frontmatter, observable truths, artifacts grouped by plan, key links, requirements, anti-patterns, human verification sections
- [Phase 10-01]: Verification status can be "passed" with pending human verification items listed (established pattern across Phases 1, 2, 5, 6, 7, 9)
- [Phase 10-02]: Phase 4 VERIFICATION.md created with evidence-backed claims from actual source file reads
- [Phase 10-02]: Phase 8 VERIFICATION.md updated from human_needed to passed reflecting Docker Desktop installation
- [Phase 11-01]: fal.ai unified API gateway for multiple video models (Kling, Minimax, future models without separate SDKs)
- [Phase 11-01]: Kling 3.0 as premium quality option ($0.029/sec, 4K support)
- [Phase 11-01]: Minimax as budget-friendly option ($0.02-0.05/video, fast generation)
- [Phase 11-01]: Mock fallback pattern when FAL_KEY is empty or USE_MOCK_DATA=true (consistent with OpenAI TTS provider)
- [Phase 11-02]: ElevenLabs as premium TTS provider (70+ languages, superior marketing voices, $99/mo)
- [Phase 11-02]: Fish Audio as budget TTS provider (50-70% cheaper, competitive quality, good for high-volume testing)
- [Phase 11-02]: ElevenLabs eleven_turbo_v2_5 model for fast generation and cost efficiency
- [Phase 11-02]: httpx for Fish Audio API (simple REST API, no SDK needed)
- [Phase 11-03]: HeyGen avatar video replaces both video + voiceover (complete talking-head with embedded audio)
- [Phase 11-03]: Avatar generation as Step 6b (after voiceover generation) for pipeline flexibility
- [Phase 11-03]: Avatar provider only activates when AVATAR_PROVIDER_TYPE in ('heygen',), mock stays default
- [Phase 11]: HeyGen avatar video replaces both video + voiceover (complete talking-head with embedded audio)
- [Phase 12]: Imagen 4 via google.generativeai SDK (deprecated, needs migration to google.genai)
- [Phase 12-02]: Aspect ratio derived from width/height ratio for Imagen API (9:16/16:9/1:1)
- [Phase 12-03]: Veo 3.1 duration clamping to 8s max with warning log
- [Phase 12-03]: Image-to-video as Veo extension method (not part of VideoProvider ABC)
- [Phase 12-01]: Use deprecated google-generativeai SDK for Python 3.9 compatibility
- [Phase 12-01]: LLMProvider.generate_structured() accepts Pydantic schema and returns validated instance
- [Phase 12-01]: MockLLMProvider inspects schema.model_json_schema() to generate type-appropriate defaults
- [Phase 12-04]: script_generator and trend_analyzer use LLMProvider abstraction instead of direct Anthropic SDK
- [Phase 12-04]: Two-call pattern: generate_text() for freeform analysis, generate_structured() for schema output
- [Phase 13-02]: Use GoogleVeoProvider directly for image-to-video (not via VideoGeneratorService)
- [Phase 13-02]: B-Roll audio stripped via without_audio() to preserve A-Roll voice
- [Phase 13-02]: B-Roll overlays at 80% scale centered for picture-in-picture effect
- [Phase 13-02]: Use GoogleVeoProvider directly for image-to-video (not via VideoGeneratorService)
- [Phase 13-02]: B-Roll audio stripped via without_audio() to preserve A-Roll voice
- [Phase 13-02]: B-Roll overlays at 80% scale centered for picture-in-picture effect

### Roadmap Evolution

- Phase 11 added: Real AI Provider Integration — pluggable video (Kling/Runway/Veo/Minimax), avatar (HeyGen), and TTS (ElevenLabs/Fish Audio/OpenAI) providers
- Phase 12 added: Google AI Provider Suite — unified Gemini (LLM) + Imagen (images) + Veo (video) under single GOOGLE_API_KEY, replaces need for separate Claude/fal.ai/TTS APIs
- Phase 13 added: UGC Product Ad Pipeline — universal UGC×product ad creation using Google AI only (Gemini scripts → Imagen images → Veo video → FFmpeg composite)

### Pending Todos

None yet.

### Blockers/Concerns

**Phase 2 (Trend Intelligence):**
- TikTok API access requires developer account approval with unclear criteria
- Google Sheets API quota (60 requests/minute/user) needs validation during sync implementation

**Phase 3 (Content Generation):**
- Stable Video Diffusion production experience limited — plan for quality validation during implementation
- Temporal drift in AI video beyond 2-3 seconds — architecture designed for short clips (2-4s) to mitigate

**Phase 6 (Pipeline Integration):**
- Cloud Run GPU support limitation — video-generator service may need GCE/GKE deployment or cloud-only APIs (Veo/Sora)

**Phase 8 (Docker Compose Validation):**
- ~~Docker not installed on local development machine~~ — Resolved: Docker Desktop installed and validated
- Runtime fixes required: asyncpg event loop conflicts (NullPool), dialect-aware UPSERT, MoviePy v2 API, font installation, Celery thread pool

## Session Continuity

Last session: 2026-02-15 (Phase 13 in progress)
Stopped at: Completed 13-02-PLAN.md
Resume file: None

---
*State initialized: 2026-02-13*
*Last updated: 2026-02-15*
