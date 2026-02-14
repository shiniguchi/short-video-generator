# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-13)

**Core value:** Reliably produce publish-ready short-form videos from a theme/product input — full pipeline from trend analysis through composition — without manual intervention between stages.
**Current focus:** Phase 4 In Progress — Video Composition

## Current Position

Phase: 4 of 6 (Video Composition) — IN PROGRESS
Plan: 1 of 2 in current phase (04-01 complete)
Status: Active
Last activity: 2026-02-14 — 04-01 executed: VideoCompositor service with text overlay, audio mixing, and thumbnail generation

Progress: [████████░░] 83%

## Performance Metrics

**Velocity:**
- Total plans completed: 10
- Average duration: 4 min
- Total execution time: 1.1 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01 | 3 | 9 min | 3 min |
| 02 | 3 | 14 min | 5 min |
| 03 | 3 | 18 min | 6 min |
| 04 | 1 | 2 min | 2 min |

**Recent Trend:**
- Last 5 plans: 02-03 (4 min), 03-01 (5 min), 03-02 (7 min), 03-03 (6 min), 04-01 (2 min)
- Trend: Improving (Phase 4 started fast)

*Updated after each plan completion*

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

## Session Continuity

Last session: 2026-02-14 (phase 4 plan 01 execution complete)
Stopped at: Completed 04-01-PLAN.md — VideoCompositor service built. Ready for 04-02 (Celery task integration).
Resume file: None

---
*State initialized: 2026-02-13*
*Last updated: 2026-02-14*
