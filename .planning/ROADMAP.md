# Roadmap: ViralForge

## Milestones

- ✅ **v1.0 MVP** - Phases 1-13 (shipped 2026-02-15)
- 🚧 **v2.0 Smoke Test Platform** - Phases 14-19 (in progress)

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

### 🚧 v2.0 Smoke Test Platform (In Progress)

**Milestone Goal:** Extend ViralForge from video generator into full smoke test tool with LP generation, free static hosting deployment, analytics collection, and admin dashboard.

**Phase Numbering:**
- Integer phases (14, 15, 16): Planned milestone work
- Decimal phases (14.1, 14.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 14: Landing Page Generation** - AI-generated single-file HTML LPs with video embed — completed 2026-02-19
- [x] **Phase 15: AI Section Editing** - Edit LP sections via AI prompts after generation — completed 2026-02-19
- [ ] **Phase 16: Waitlist Collection** - Email capture, validation, storage with spam prevention
- [ ] **Phase 17: Web UI** - Browser-based product idea input and generation trigger
- [ ] **Phase 18: Cloudflare Analytics** - Pageview/signup tracking via Worker + D1
- [ ] **Phase 19: Admin Dashboard & Deployment** - Dashboard + Cloudflare Pages auto-deploy

## Phase Details

### Phase 14: Landing Page Generation
**Goal**: User can generate a production-ready landing page from a product idea, with AI-written copy, embedded video, and waitlist form.

**Depends on**: Nothing (first phase in v2.0)

**Requirements**: LP-01, LP-02, LP-03, LP-04, LP-05, LP-07

**Success Criteria** (what must be TRUE):
  1. User can input product idea and generate a complete landing page
  2. Generated LP uses proven copy formulas (Pain+Solution+Hook headline, benefits, CTAs)
  3. Generated LP is a single self-contained HTML file with inline CSS
  4. Generated LP is mobile-responsive with thumb-friendly touch targets
  5. Generated LP includes embedded product video in hero section
  6. Generated LP includes waitlist email capture form with honeypot spam prevention

**Plans:** 3 plans

Plans:
- [x] 14-01-PLAN.md -- Foundation, schemas, color extractor, and LP research module
- [x] 14-02-PLAN.md -- AI copy generator and Jinja2 template system
- [x] 14-03-PLAN.md -- Optimizer, CLI command, pipeline integration, and visual verification

### Phase 15: AI Section Editing
**Goal**: User can refine generated landing pages by editing individual sections using AI prompts without touching HTML.

**Depends on**: Phase 14

**Requirements**: LP-06

**Success Criteria** (what must be TRUE):
  1. User can target specific LP sections (headline, benefits, CTA) for editing
  2. User can submit natural language prompts (e.g., "make headline shorter", "add urgency")
  3. AI regenerates only the targeted section while preserving other content
  4. Updated LP maintains structural integrity (no broken HTML/CSS)

**Plans:** 2 plans

Plans:
- [x] 15-01-PLAN.md -- Section editor module with section-scoped schemas and AI copy regeneration
- [x] 15-02-PLAN.md -- CLI command, sidecar metadata, and module exports

### Phase 16: Waitlist Collection
**Goal**: Visitors can submit emails via LP waitlist form with server-side validation, duplicate prevention, and database storage.

**Depends on**: Phase 14

**Requirements**: WAIT-01, WAIT-02, WAIT-03, WAIT-04, WAIT-05

**Success Criteria** (what must be TRUE):
  1. Visitor can submit email via LP waitlist form
  2. Invalid emails are rejected with clear error message
  3. Duplicate emails are rejected with friendly message
  4. Visitor sees confirmation message after successful signup
  5. Waitlist entries are stored in database with timestamp and source LP

**Plans**: TBD

Plans:
- [ ] 16-01: TBD

### Phase 17: Web UI
**Goal**: Users can interact with ViralForge via browser instead of CLI, triggering LP generation and viewing results.

**Depends on**: Phase 14, Phase 16

**Requirements**: UI-01, UI-02, UI-03, UI-04, UI-05

**Success Criteria** (what must be TRUE):
  1. User can input product idea via browser form
  2. User can trigger LP generation from web UI with visual feedback
  3. User can preview generated LP inline before deployment
  4. User can trigger deployment to Cloudflare from web UI
  5. User can view list of all generated LPs with status (generated, deployed, archived)

**Plans**: TBD

Plans:
- [ ] 17-01: TBD

### Phase 18: Cloudflare Analytics
**Goal**: Every deployed LP automatically tracks pageviews, form submissions, and traffic sources via Cloudflare Worker + D1, queryable from Python backend.

**Depends on**: Phase 14

**Requirements**: ANLYT-01, ANLYT-02, ANLYT-03, ANLYT-04, ANLYT-05, DEPLOY-04

**Success Criteria** (what must be TRUE):
  1. Cloudflare Worker intercepts and tracks all LP pageviews
  2. Cloudflare Worker captures form submissions with timestamp
  3. Analytics data persists in Cloudflare D1 database
  4. Python backend can query analytics via Worker HTTP proxy
  5. Traffic source (referrer) is captured with each pageview
  6. Generated LPs include analytics beacon script before deployment

**Plans**: TBD

Plans:
- [ ] 18-01: TBD

### Phase 19: Admin Dashboard & Deployment
**Goal**: User can view conversion metrics per LP, export signups, and deploy LPs to Cloudflare Pages with one click.

**Depends on**: Phase 17, Phase 18

**Requirements**: DASH-01, DASH-02, DASH-03, DASH-04, DASH-05, DEPLOY-01, DEPLOY-02, DEPLOY-03

**Success Criteria** (what must be TRUE):
  1. User can view list of all waitlist signups with email, timestamp, and source LP
  2. Dashboard displays per-LP traffic, signup count, and conversion rate
  3. User can export waitlist emails to CSV
  4. User can filter dashboard data by date range
  5. User can deploy generated LP to Cloudflare Pages with one action
  6. Deployed LP is publicly accessible at Cloudflare Pages URL
  7. LP deployment status is tracked in database (generated, deployed, archived)

**Plans**: TBD

Plans:
- [ ] 19-01: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 14 → 15 → 16 → 17 → 18 → 19

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
| 16. Waitlist Collection | v2.0 | 0/TBD | Not started | - |
| 17. Web UI | v2.0 | 0/TBD | Not started | - |
| 18. Cloudflare Analytics | v2.0 | 0/TBD | Not started | - |
| 19. Admin Dashboard & Deployment | v2.0 | 0/TBD | Not started | - |

---
*Roadmap created: 2026-02-13*
*Last updated: 2026-02-19 - Phase 15 complete (2/2 plans)*
