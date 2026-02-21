# Roadmap: ViralForge

## Milestones

- ✅ **v1.0 MVP** - Phases 1-13 (shipped 2026-02-15)
- ✅ **v2.0 Smoke Test Platform** - Phases 14-19 (shipped 2026-02-20)
- 🚧 **v3.0 Review Workflow UI** - Phases 20-25 (in progress)

## Phases

<details>
<summary>✅ v1.0 MVP (Phases 1-13) - SHIPPED 2026-02-15</summary>

- [x] Phase 1: Foundation & Infrastructure (3/3 plans) - completed 2026-02-13
- [x] Phase 2: Trend Intelligence (3/3 plans) - completed 2026-02-13
- [x] Phase 3: Content Generation (3/3 plans) - completed 2026-02-14
- [x] Phase 4: Video Composition (2/2 plans) - completed 2026-02-14
- [x] Phase 5: Review & Output (1/1 plans) - completed 2026-02-14
- [x] Phase 6: Pipeline Integration (2/2 plans) - completed 2026-02-14
- [x] Phase 7: Pipeline Data Lineage (1/1 plans) - completed 2026-02-14
- [x] Phase 8: Docker Compose Validation (2/2 plans) - completed 2026-02-14
- [x] Phase 9: Fix Stale Manual Endpoints (1/1 plans) - completed 2026-02-14
- [x] Phase 10: Documentation Cleanup (2/2 plans) - completed 2026-02-14
- [x] Phase 11: Real AI Providers (3/3 plans) - completed 2026-02-14
- [x] Phase 12: Google AI Provider Suite (4/4 plans) - completed 2026-02-15
- [x] Phase 13: UGC Product Ad Pipeline (3/3 plans) - completed 2026-02-15

Full details: `.planning/milestones/v1.0-ROADMAP.md`

</details>

<details>
<summary>✅ v2.0 Smoke Test Platform (Phases 14-19) - SHIPPED 2026-02-20</summary>

- [x] Phase 14: Landing Page Generation (3/3 plans) - completed 2026-02-19
- [x] Phase 15: AI Section Editing (2/2 plans) - completed 2026-02-19
- [x] Phase 16: Waitlist Collection (2/2 plans) - completed 2026-02-19
- [x] Phase 17: Web UI (3/3 plans) - completed 2026-02-20
- [x] Phase 18: Cloudflare Analytics (2/2 plans) - completed 2026-02-20
- [x] Phase 19: Admin Dashboard & Deployment (2/2 plans) - completed 2026-02-20

Full details: `.planning/phases/` (14-01 through 19-02)

</details>

### 🚧 v3.0 Review Workflow UI (In Progress)

**Milestone Goal:** Wire the UGC video pipeline into the web UI with a linear review workflow — users approve each stage (script, images, video clips, combined video, LP) before the next begins.

**Phase Numbering:**
- Integer phases (20-25): Planned milestone work
- Decimal phases (20.1, 20.2): Urgent insertions (marked with INSERTED)

- [x] **Phase 20: UGCJob Data Model** - DB-backed job state with typed per-stage columns and migration - completed 2026-02-20
- [x] **Phase 21: Per-Stage Celery Tasks** - Five stage tasks that run, write to DB, and wait for approval - completed 2026-02-20
- [x] **Phase 22: Review API Routes + SSE** - HTTP routes for job creation, stage advance, SSE progress stream - completed 2026-02-21
- [x] **Phase 23: Review UI Templates** - HTMX-powered review pages with stepper, approve/reject grid - completed 2026-02-21
- [x] **Phase 24: Media Preview** - Image and video serving with HTTP 206 range support for seek - completed 2026-02-21
- [ ] **Phase 25: LP Integration** - LP module review, video frame sourcing, LP-specific image regeneration

## Phase Details

### Phase 20: UGCJob Data Model
**Goal**: All UGC job state persists in PostgreSQL with typed columns for every stage output — nothing in memory.

**Depends on**: Nothing (first phase in v3.0)

**Requirements**: PIPE-04

**Success Criteria** (what must be TRUE):
  1. UGCJob row is created in DB when user submits a new generation request
  2. Each pipeline stage has a typed DB column (not a JSON blob) for its output
  3. Job status field has valid state machine values (pending/running/stage_N_review/approved/failed)
  4. Alembic migration applies cleanly on fresh DB and existing DB

**Plans**: 1 plan

Plans:
- [x] 20-01-PLAN.md — UGCJob model + migration + state machine guard layer

### Phase 21: Per-Stage Celery Tasks
**Goal**: Users can submit a generation job and each pipeline stage executes sequentially, pausing at each checkpoint for approval.

**Depends on**: Phase 20

**Requirements**: PIPE-01, PIPE-02, PIPE-03

**Success Criteria** (what must be TRUE):
  1. User can submit a product idea via web form and a UGCJob is created and queued
  2. Each stage (analyze, hero image, script, assets, compose) runs as a separate Celery task
  3. Each stage writes output to its UGCJob DB column then sets status to stage_N_review
  4. Stage N+1 task only starts after user explicitly advances past stage N
  5. Mock/real AI flag is passed as explicit argument through the task chain (no global mutation)

**Plans**: 2 plans

Plans:
- [x] 21-01-PLAN.md — use_mock threading through service functions + five per-stage Celery tasks
- [x] 21-02-PLAN.md — submit/advance/status endpoints + worker registration + main.py wiring

### Phase 22: Review API Routes + SSE
**Goal**: Every review action (view job, advance stage, regenerate item, stream progress) is wired to an HTTP endpoint.

**Depends on**: Phase 21

**Requirements**: REVIEW-04, REVIEW-05

**Success Criteria** (what must be TRUE):
  1. Calling advance on a stage that has unapproved items returns an error (stage gate enforced)
  2. SSE stream emits progress events while a stage task is running
  3. SSE stream notifies client when stage completes and review is ready
  4. SSE connection cleans up on tab close (no leaked generator)

**Plans**: 2 plans

Plans:
- [x] 22-01-PLAN.md — Job list endpoint + SSE progress stream with disconnect handling
- [x] 22-02-PLAN.md — Regenerate and edit endpoints with stage gate validation

### Phase 23: Review UI Templates
**Goal**: Users can navigate the full review pipeline in the browser — see their position, review items as a grid, and approve or reject each one.

**Depends on**: Phase 22

**Requirements**: REVIEW-01, REVIEW-02, REVIEW-03

**Success Criteria** (what must be TRUE):
  1. User sees a stage progress stepper showing which stage is active and which are complete
  2. User sees all items for the current stage as a thumbnail/card grid
  3. User can approve or reject each item individually with one click (no page reload)
  4. Locked stages (N+1) are visually disabled until stage N is fully approved
  5. Approve/reject actions update the item card in place via HTMX partial swap

**Plans**: 2 plans

Plans:
- [x] 23-01-PLAN.md — HTMX CDN setup, job creation form, job list page
- [x] 23-02-PLAN.md — Review page with stage stepper, item grids, HTMX approve/reject

### Phase 24: Media Preview
**Goal**: Users can view generated images and play video clips directly in the review grid with full seek support.

**Depends on**: Phase 23

**Requirements**: MEDIA-01, MEDIA-02, MEDIA-03

**Success Criteria** (what must be TRUE):
  1. Generated images render inline in the review grid (not broken img tags)
  2. Generated video clips are playable in-browser with a working seek bar
  3. Combined final video is watchable inline before approval
  4. Video serving returns HTTP 206 partial content (browser seek does not break)
  5. File paths are validated within the output directory (no path traversal)

**Plans**: 1 plan

Plans:
- [x] 24-01-PLAN.md — Jinja2 media_url filter + inline img/video tags in review template + responsive media CSS

### Phase 25: LP Integration
**Goal**: Users can review LP modules individually and the LP hero image is populated from approved video frames by default.

**Depends on**: Phase 23, Phase 24

**Requirements**: LP-08, LP-09, LP-10

**Success Criteria** (what must be TRUE):
  1. LP review stage shows each module (headline, hero, CTA, benefits) as a separate card with approve/reject
  2. LP hero image defaults to a frame extracted from the approved combined video
  3. User can trigger LP-specific image regeneration to replace the video frame default
  4. LP review is locked until the video pipeline is fully approved

**Plans**: TBD

Plans:
- [ ] 25-01: LP module review cards and stage gate wiring from video approval
- [ ] 25-02: Video frame extraction for LP hero, LP-specific image regeneration endpoint

## Progress

**Execution Order:**
Phases execute in numeric order: 20 → 21 → 22 → 23 → 24 → 25

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Foundation & Infrastructure | v1.0 | 3/3 | Complete | 2026-02-13 |
| 2. Trend Intelligence | v1.0 | 3/3 | Complete | 2026-02-13 |
| 3. Content Generation | v1.0 | 3/3 | Complete | 2026-02-14 |
| 4. Video Composition | v1.0 | 2/2 | Complete | 2026-02-14 |
| 5. Review & Output | v1.0 | 1/1 | Complete | 2026-02-14 |
| 6. Pipeline Integration | v1.0 | 2/2 | Complete | 2026-02-14 |
| 7. Pipeline Data Lineage | v1.0 | 1/1 | Complete | 2026-02-14 |
| 8. Docker Compose Validation | v1.0 | 2/2 | Complete | 2026-02-14 |
| 9. Fix Stale Manual Endpoints | v1.0 | 1/1 | Complete | 2026-02-14 |
| 10. Documentation Cleanup | v1.0 | 2/2 | Complete | 2026-02-14 |
| 11. Real AI Providers | v1.0 | 3/3 | Complete | 2026-02-14 |
| 12. Google AI Provider Suite | v1.0 | 4/4 | Complete | 2026-02-15 |
| 13. UGC Product Ad Pipeline | v1.0 | 3/3 | Complete | 2026-02-15 |
| 14. Landing Page Generation | v2.0 | 3/3 | Complete | 2026-02-19 |
| 15. AI Section Editing | v2.0 | 2/2 | Complete | 2026-02-19 |
| 16. Waitlist Collection | v2.0 | 2/2 | Complete | 2026-02-19 |
| 17. Web UI | v2.0 | 3/3 | Complete | 2026-02-20 |
| 18. Cloudflare Analytics | v2.0 | 2/2 | Complete | 2026-02-20 |
| 19. Admin Dashboard & Deployment | v2.0 | 2/2 | Complete | 2026-02-20 |
| 20. UGCJob Data Model | v3.0 | 1/1 | Complete | 2026-02-20 |
| 21. Per-Stage Celery Tasks | v3.0 | 2/2 | Complete | 2026-02-20 |
| 22. Review API Routes + SSE | v3.0 | 2/2 | Complete | 2026-02-21 |
| 23. Review UI Templates | v3.0 | 2/2 | Complete | 2026-02-21 |
| 24. Media Preview | v3.0 | 1/1 | Complete | 2026-02-21 |
| 25. LP Integration | v3.0 | 0/TBD | Not started | - |

---
*Roadmap created: 2026-02-13*
*Last updated: 2026-02-21 - Phase 24 complete (Media Preview)*
