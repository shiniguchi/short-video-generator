# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-20)

**Core value:** Enable rapid product idea validation: product idea in → video ads + landing page out → deploy → measure waitlist signups — cheapest possible, zero manual steps between stages.

**Current focus:** Phase 21 complete — ready for Phase 22 (SSE progress streaming)

## Current Milestone

**v3.0 Review Workflow UI** (Phases 20-25)
- Wires UGC video pipeline + LP generation into web UI with linear review workflow
- Per-frame approve/reject at each stage, stage gate enforcement, SSE progress, mock/real toggle

## Current Position

Phase: 21 of 25 (Per-Stage Celery Tasks)
Plan: 2 of 2 in current phase (complete)
Status: Phase 21 complete — UGC HTTP endpoints, Celery task wiring, and worker registration done
Last activity: 2026-02-20 — Phase 21 Plan 02 executed

Progress: [███░░░░░░░░░░░░░░░░░░░░░] 12% (v3.0, 3/25 plans)

## Performance Metrics

**v1.0 (SHIPPED):** 30 plans, 13 phases, ~2.5 hours, avg 3 min/plan

**v2.0 (SHIPPED):** 14 plans, 6 phases, avg ~7 min/plan (includes human-verify checkpoints)

**v3.0 (in progress):**

| Phase | Plan | Duration | Tasks | Files |
|-------|------|----------|-------|-------|
| 20-01 | UGCJob data model | ~3 min | 2 | 5 |
| 21-01 | Per-stage Celery tasks | ~4 min | 2 | 4 |
| 21-02 | UGC router and worker wiring | ~2 min | 2 | 3 |

## Accumulated Context

### Key Decisions (v3.0 scoped)

- **UGCJob not in-memory**: All UGC job state goes to PostgreSQL. Existing `_jobs` dict stays for LP generation only — do not extend it.
- **Regeneration produces candidates**: Never mutate approved content in place. Store candidate separately, overwrite only on explicit acceptance.
- **HTMX 2.0.8 + SSE Extension 2.2.4**: CDN-loaded, no build step. Approve/reject via `hx-post` + `hx-swap="outerHTML"` on partial templates.
- **python-statemachine 2.6.0**: Guard layer for state transitions only. DB column is source of truth, not statemachine. Instantiate with `start_value=job.status` for existing rows.
- **HTTP 206 for video**: `StreamingResponse` with manual range parsing for `.mp4`. `FileResponse` alone does not handle Range headers — browser seek breaks.
- **Mock flag as argument**: Pass `use_mock: bool` explicitly through task chain. Do not mutate `get_settings()` singleton per request.
- **use_mock per UGCJob row**: Stored in UGCJob.use_mock column, not read from settings singleton — allows per-job mock toggle.
- **Direct provider instantiation in services**: `analyze_product`, `generate_ugc_script`, `generate_hero_image`, `generate_aroll_assets`, `generate_broll_assets` instantiate providers directly based on `use_mock` param — no global factory calls.
- **Stages 1+2 combined in ugc_stage_1_analyze**: Analysis + hero image run in one task since state machine has no `stage_hero_image_review` state — avoids adding new states or migration.
- **Lazy import ugc_tasks in endpoints**: Import `app.ugc_tasks` inside endpoint functions to avoid circular import at module load time.
- **_STAGE_ADVANCE_MAP as single source of truth**: Dict maps each review status to `(approve_event, next_task_name)` — advance endpoint logic reads only this map.

### Research Flags for Planning

- **Phase 22 (SSE)**: Verify `request.is_disconnected()` behavior against installed Starlette version before implementing.
- **Phase 24 (206 range)**: Test open-ended range `bytes=N-` and multi-range edge cases in browser DevTools before marking done.

### Pending Todos

None.

### Blockers/Concerns

None.

## Session Continuity

Last session: 2026-02-20
Stopped at: Completed 21-02-PLAN.md (UGC router, worker wiring, main.py mount)
Resume file: None
Next step: Phase 22 (SSE progress streaming)

---
*State initialized: 2026-02-13*
*Last updated: 2026-02-20 - Phase 21 Plan 02 complete (UGC HTTP router, Celery worker wiring, main.py mount)*
