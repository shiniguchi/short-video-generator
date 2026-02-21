# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-20)

**Core value:** Enable rapid product idea validation: product idea in → video ads + landing page out → deploy → measure waitlist signups — cheapest possible, zero manual steps between stages.

**Current focus:** Phase 23 complete — ready for Phase 24 (Video Player)

## Current Milestone

**v3.0 Review Workflow UI** (Phases 20-25)
- Wires UGC video pipeline + LP generation into web UI with linear review workflow
- Per-frame approve/reject at each stage, stage gate enforcement, SSE progress, mock/real toggle

## Current Position

Phase: 23 of 25 (Review UI Templates) — COMPLETE
Plan: 2 of 2 in current phase (complete)
Status: Phase 23 complete — review page, stage controls partial, stepper/card CSS, advance/regenerate routes
Last activity: 2026-02-21 — Phase 23 Plan 02 complete

Progress: [███████░░░░░░░░░░░░░░░░░] 28% (v3.0, 7/25 plans)

## Performance Metrics

**v1.0 (SHIPPED):** 30 plans, 13 phases, ~2.5 hours, avg 3 min/plan

**v2.0 (SHIPPED):** 14 plans, 6 phases, avg ~7 min/plan (includes human-verify checkpoints)

**v3.0 (in progress):**

| Phase | Plan | Duration | Tasks | Files |
|-------|------|----------|-------|-------|
| 20-01 | UGCJob data model | ~3 min | 2 | 5 |
| 21-01 | Per-stage Celery tasks | ~4 min | 2 | 4 |
| 21-02 | UGC router and worker wiring | ~2 min | 2 | 3 |
| 22-01 | SSE + job list endpoints | ~1 min | 1 | 1 |
| 22-02 | Regenerate + edit endpoints | ~2 min | 2 | 1 |
| 23-01 | UGC entry point templates | ~2 min | 2 | 5 |
| 23-02 | Review page + advance/regen routes | ~2 min | 2 | 4 |

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
- **No Depends(get_session) on SSE endpoint**: Generator opens/closes `async_session_factory()` per iteration — never holds a session for the full stream duration.
- **_TERMINAL_STATES includes all review states**: Stream stops when user action is required (not just on approved/failed) — client doesn't need to keep polling during review.
- **_STAGE_REGEN_MAP excludes stage_composition_review**: SM has no review->running path from composition review — approve_final goes directly to approved.
- **Regenerate reuses _STAGE_ADVANCE_MAP approve events**: Drives SM review->running transition before re-enqueuing without adding new SM events.
- **Per-item card display in review page**: Each analysis field, script scene, and file path is its own card — user evaluates every item before approving the stage.
- **running_toward heuristic**: Derives which stage is in flight from populated data columns — no extra DB column needed.
- **HTMX outerHTML swap on stage controls**: Approve/regenerate updates controls in place — no page reload needed.

### Research Flags for Planning

- **Phase 22 (SSE)**: Verify `request.is_disconnected()` behavior against installed Starlette version before implementing.
- **Phase 24 (206 range)**: Test open-ended range `bytes=N-` and multi-range edge cases in browser DevTools before marking done.

### Pending Todos

None.

### Blockers/Concerns

None.

## Session Continuity

Last session: 2026-02-21
Stopped at: Completed 23-02-PLAN.md
Resume file: None
Next step: Phase 24 (Video Player)

---
*State initialized: 2026-02-13*
*Last updated: 2026-02-21 - Phase 23 Plan 02 complete (Review page — stage stepper, per-item card grids, HTMX advance/regenerate routes)*
