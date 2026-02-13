# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-13)

**Core value:** Reliably produce publish-ready short-form videos from a theme/product input — full pipeline from trend analysis through composition — without manual intervention between stages.
**Current focus:** Phase 2: Trend Intelligence — In Progress

## Current Position

Phase: 2 of 6 (Trend Intelligence)
Plan: 2 of 3 in current phase (02-02 complete)
Status: Executing
Last activity: 2026-02-13 — Phase 02-02 complete: scrapers, engagement velocity, UPSERT, collection task

Progress: [██████░░░░] 60%

## Performance Metrics

**Velocity:**
- Total plans completed: 5
- Average duration: 4 min
- Total execution time: 0.6 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01 | 3 | 9 min | 3 min |
| 02 | 2 | 10 min | 5 min |

**Recent Trend:**
- Last 5 plans: 01-02 (5 min), 01-03 (2 min), 02-01 (5 min), 02-02 (5 min)
- Trend: Steady

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

Last session: 2026-02-13 (phase 2 execution)
Stopped at: Completed 02-02-PLAN.md (scrapers, engagement, UPSERT, collection task)
Resume file: None

---
*State initialized: 2026-02-13*
*Last updated: 2026-02-13*
