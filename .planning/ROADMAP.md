# Roadmap: ViralForge

## Overview

ViralForge's roadmap follows the natural flow of its 8-stage video pipeline: foundation infrastructure first, then trend intelligence (data collection and analysis), content generation (script, video, voiceover), video composition (assembly and finalization), review gates (quality control and cost tracking), and finally end-to-end pipeline orchestration that ties all stages together into an automated workflow.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Foundation & Infrastructure** - Docker Compose environment with core services and configuration
- [x] **Phase 2: Trend Intelligence** - Trend collection from TikTok/YouTube and AI-powered pattern analysis
- [ ] **Phase 3: Content Generation** - Script generation, AI video creation, and voiceover synthesis
- [ ] **Phase 4: Video Composition** - FFmpeg assembly with text overlays, audio, and final rendering
- [ ] **Phase 5: Review & Output** - File-based review workflow with cost tracking and approval system
- [ ] **Phase 6: Pipeline Integration** - End-to-end orchestration with checkpointing, retries, and monitoring

## Phase Details

### Phase 1: Foundation & Infrastructure
**Goal**: Core services run locally in Docker with database, task queue, API, and health monitoring established
**Depends on**: Nothing (first phase)
**Requirements**: INFRA-01, INFRA-02, INFRA-03, INFRA-04, INFRA-05, INFRA-06, INFRA-07
**Success Criteria** (what must be TRUE):
  1. All services start successfully via `docker-compose up` with visible logs
  2. FastAPI health check endpoint returns service and database status
  3. Celery workers connect to Redis and can execute test tasks
  4. PostgreSQL migrations run successfully and schema is created
  5. Local config files provide sample data when Google Sheets is unavailable
**Plans**: 3 plans

Plans:
- [x] 01-01-PLAN.md — Docker infrastructure with PostgreSQL, Redis, config system, and local data fallback
- [x] 01-02-PLAN.md — Database layer with SQLAlchemy async models and Alembic migrations
- [x] 01-03-PLAN.md — FastAPI REST API with health endpoint and Celery worker with test task

### Phase 2: Trend Intelligence
**Goal**: System collects trending videos from TikTok and YouTube, then analyzes patterns with engagement velocity scoring
**Depends on**: Phase 1
**Requirements**: TREND-01, TREND-02, TREND-03, TREND-04, TREND-05, ANLYS-01, ANLYS-02, ANLYS-03, ANLYS-04, ANLYS-05
**Success Criteria** (what must be TRUE):
  1. System scrapes top 50 videos from both TikTok (via Apify) and YouTube Shorts (via Data API v3) on schedule
  2. Collected trends include all metadata (title, hashtags, engagement, creator, sound, thumbnail)
  3. PostgreSQL stores deduplicated trends with no duplicate (platform, external_id) entries
  4. Claude API analyzes collected videos and produces structured Trend Report JSON with patterns
  5. Trend reports include engagement velocity scores and style classifications (cinematic, talking-head, etc.)
**Plans**: 3 plans

Plans:
- [x] 02-01-PLAN.md — Data foundation: schema migration, Pydantic schemas, config, and mock data fixtures
- [x] 02-02-PLAN.md — Trend collection: TikTok/YouTube scrapers, engagement velocity, DB UPSERT, Celery task
- [x] 02-03-PLAN.md — Trend analysis: Claude API analyzer, TrendReport storage, Celery Beat schedule, API endpoints

### Phase 3: Content Generation
**Goal**: System reads theme config and generates complete videos from AI-generated scripts, visuals, and voiceover
**Depends on**: Phase 2
**Requirements**: SCRIPT-01, SCRIPT-02, SCRIPT-03, SCRIPT-04, VIDEO-01, VIDEO-02, VIDEO-03, VIDEO-04, VIDEO-05, VOICE-01, VOICE-02, VOICE-03
**Success Criteria** (what must be TRUE):
  1. System reads theme/product configuration from local config file (Google Sheets when connected)
  2. Claude API generates Video Production Plans aligned with current trend patterns via 5-step prompt chain
  3. Production Plans include all required fields (video_prompt, scenes, text_overlays, voiceover_script, hashtags, title, description)
  4. Stable Video Diffusion generates 9:16 vertical video clips (2-4 seconds each) chained to target duration (15-30 seconds)
  5. OpenAI TTS generates voiceover audio synced to video duration with configurable provider backend
**Plans**: 3 plans

Plans:
- [ ] 03-01-PLAN.md — Config reader service, Production Plan schemas, and Alembic migration
- [ ] 03-02-PLAN.md — Video and voiceover provider abstraction with mock providers and clip chaining
- [ ] 03-03-PLAN.md — Claude 5-step prompt chain script generator, Celery content task, and API endpoints

### Phase 4: Video Composition
**Goal**: FFmpeg composites raw video, voiceover, text overlays, and background music into publish-ready MP4
**Depends on**: Phase 3
**Requirements**: COMP-01, COMP-02, COMP-03, COMP-04, COMP-05
**Success Criteria** (what must be TRUE):
  1. FFmpeg successfully combines AI video clips, voiceover audio, and text overlays into single MP4
  2. Text overlays appear with correct font (Montserrat Bold default), timing, position, color, shadow, and animation
  3. Final output is 9:16 vertical MP4 (H.264 video, AAC audio) with all components synchronized
  4. System generates thumbnail image extracted from configurable video frame
  5. Optional background music mixes correctly at configurable volume level without overpowering voiceover
**Plans**: TBD

Plans:
- TBD (plans defined during `/gsd:plan-phase 4`)

### Phase 5: Review & Output
**Goal**: Generated videos saved to review directory with approval workflow, generation logging, and per-video cost tracking
**Depends on**: Phase 4
**Requirements**: REVIEW-01, REVIEW-02, REVIEW-03, REVIEW-04, REVIEW-05
**Success Criteria** (what must be TRUE):
  1. Final videos appear in `/output/review/` directory after generation completes
  2. Generation log records all metadata (gen_id, timestamp, theme, trend pattern, prompts, model, cost, path, status)
  3. REST API endpoint accepts approval requests and moves videos to `/output/approved/`
  4. REST API endpoint accepts rejection requests and moves videos to `/output/rejected/`
  5. Per-video cost tracking sums all API call costs (Claude, OpenAI TTS, video generation) and logs to generation record
**Plans**: TBD

Plans:
- TBD (plans defined during `/gsd:plan-phase 5`)

### Phase 6: Pipeline Integration
**Goal**: Full 8-stage pipeline executes sequentially with checkpointing, error recovery, retries, and status monitoring
**Depends on**: Phase 5
**Requirements**: ORCH-01, ORCH-02, ORCH-03, ORCH-04, ORCH-05
**Success Criteria** (what must be TRUE):
  1. Pipeline executes all 8 stages in sequence: trend collection -> pattern analysis -> script generation -> video generation -> voiceover -> composition -> review
  2. Per-stage checkpointing allows resume from last completed stage after failure without restarting pipeline
  3. Failed stages retry up to configurable limit (default: 3) with exponential backoff between attempts
  4. Pipeline status is visible via REST API endpoints and Docker container logs in real-time
  5. Manual trigger via POST /api/generate kicks off full pipeline run from theme config through final video output
**Plans**: TBD

Plans:
- TBD (plans defined during `/gsd:plan-phase 6`)

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4 -> 5 -> 6

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation & Infrastructure | 3/3 | Complete | 2026-02-13 |
| 2. Trend Intelligence | 3/3 | Complete | 2026-02-13 |
| 3. Content Generation | 0/3 | Planning complete | - |
| 4. Video Composition | 0/0 | Not started | - |
| 5. Review & Output | 0/0 | Not started | - |
| 6. Pipeline Integration | 0/0 | Not started | - |

---
*Roadmap created: 2026-02-13*
*Last updated: 2026-02-13 -- Phase 3 planned*
