# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-20)

**Core value:** Enable rapid product idea validation: product idea in → video ads + landing page out → deploy → measure waitlist signups — cheapest possible, zero manual steps between stages.

**Current focus:** Phase 20 — UGCJob Data Model (v3.0 start)

## Current Milestone

**v3.0 Review Workflow UI** (Phases 20-25)
- Wires UGC video pipeline + LP generation into web UI with linear review workflow
- Per-frame approve/reject at each stage, stage gate enforcement, SSE progress, mock/real toggle

## Current Position

Phase: 20 of 25 (UGCJob Data Model)
Plan: 0 of TBD in current phase
Status: Ready to plan
Last activity: 2026-02-20 — v3.0 roadmap created (Phases 20-25)

Progress: [░░░░░░░░░░░░░░░░░░░░░░░░] 0% (v3.0)

## Performance Metrics

**v1.0 (SHIPPED):** 30 plans, 13 phases, ~2.5 hours, avg 3 min/plan

**v2.0 (SHIPPED):** 14 plans, 6 phases, avg ~7 min/plan (includes human-verify checkpoints)

**v3.0:** Not started

## Accumulated Context

### Key Decisions (v3.0 scoped)

- **UGCJob not in-memory**: All UGC job state goes to PostgreSQL. Existing `_jobs` dict stays for LP generation only — do not extend it.
- **Regeneration produces candidates**: Never mutate approved content in place. Store candidate separately, overwrite only on explicit acceptance.
- **HTMX 2.0.8 + SSE Extension 2.2.4**: CDN-loaded, no build step. Approve/reject via `hx-post` + `hx-swap="outerHTML"` on partial templates.
- **python-statemachine 2.6.0**: Guard layer for state transitions only. DB column is source of truth, not statemachine.
- **HTTP 206 for video**: `StreamingResponse` with manual range parsing for `.mp4`. `FileResponse` alone does not handle Range headers — browser seek breaks.
- **Mock flag as argument**: Pass `use_mock: bool` explicitly through task chain. Do not mutate `get_settings()` singleton per request.

### Research Flags for Planning

- **Phase 22 (SSE)**: Verify `request.is_disconnected()` behavior against installed Starlette version before implementing.
- **Phase 24 (206 range)**: Test open-ended range `bytes=N-` and multi-range edge cases in browser DevTools before marking done.

### Pending Todos

None.

### Blockers/Concerns

None.

## Session Continuity

Last session: 2026-02-20
Stopped at: v3.0 roadmap created, ready to plan Phase 20
Resume file: None
Next step: `/gsd:plan-phase 20`

---
*State initialized: 2026-02-13*
*Last updated: 2026-02-20 - v3.0 roadmap created (Phases 20-25, 15 requirements mapped)*
