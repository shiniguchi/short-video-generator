# Project Research Summary

**Project:** ViralForge — v3.0 Linear Review Workflow UI
**Domain:** Per-stage review pipeline for AI-generated UGC video ads
**Researched:** 2026-02-20
**Confidence:** HIGH

## Executive Summary

ViralForge v3.0 adds a linear review UI on top of an existing FastAPI + Celery + SQLAlchemy stack. The core architectural shift is breaking the monolithic `generate_ugc_ad_task` into discrete per-stage Celery tasks that pause at each checkpoint and wait for user approval before proceeding. This approach is well-established in AI content tools (Visla Director Mode, Frame.io) and maps cleanly onto the existing infrastructure — no new frameworks, just new task structure and UI routes.

The recommended approach requires only two new dependencies: `python-statemachine==2.6.0` for transition validation and HTMX 2.0.8 (CDN, no build step). All generation logic, DB session factories, SSE infrastructure, and static file serving already exist and are reused unchanged. The new work is the `UGCJob` model (typed per-stage columns), five per-stage Celery tasks, six UI routes, and three templates.

The critical risk is data integrity during regeneration: approved scene state must be stored separately from generated content, and regeneration must produce candidates rather than overwrite in place. A secondary risk is the existing in-memory `_jobs` dict — it must not be extended to the new review workflow; all state goes to PostgreSQL.

---

## Key Findings

### Recommended Stack

The v3.0 stack adds two dependencies on top of what v2.0 ships. HTMX 2.0.8 handles per-frame approve/reject/regenerate buttons via `hx-post` + `hx-swap="outerHTML"` with no page reload — it pairs directly with Jinja2 partial templates and avoids any JavaScript build tooling. `python-statemachine==2.6.0` validates state transitions (pending → approved/rejected/regenerating) as a guard layer over the existing `String(50)` DB column.

Video serving requires `StreamingResponse` with manual HTTP 206 range handling for `.mp4` files — `FileResponse` does not handle Range headers automatically, and without 206 responses the browser seek bar will not work.

**Core technologies:**
- **HTMX 2.0.8** (CDN): Inline review actions, no build step — replaces JSON API + client-side render
- **HTMX SSE Extension 2.2.4** (CDN): Per-frame regeneration progress — reuses existing SSE pattern
- **python-statemachine 2.6.0**: State transition validation — guard layer, not DB source of truth
- **StreamingResponse + Range handling** (Starlette, already installed): Video seeking support
- **Alembic** (already installed): Migration for new `ugc_jobs` table

### Expected Features

**Must have (table stakes):**
- Stage progress indicator (stepper) — users need orientation in a 5-stage pipeline
- Stage gate enforcement — N+1 blocked until all N items are approved
- Per-item approve / reject buttons — baseline review interaction for all content types
- Generation status / progress feedback — reuse existing SSE; show spinner per item
- Thumbnail/preview grid per stage — text cards for script, thumbnails for images, playable clips for video
- Inline prompt editing + single-item regeneration — must ship together; blind regeneration alone is low value
- Rejection with optional reason — passed to regeneration prompt as constraint

**Should have (competitive):**
- Bulk approve-all shortcut — differentiator; no competitor offers this
- Side-by-side version comparison — prevents accidental overwrites after regeneration
- Stage-level re-run — resets entire stage when all items are bad
- LP module review — extend the same review card component to LP pipeline

**Defer (v2+):**
- Persistent prompt history per item — useful for iteration, not required at launch
- Export review link (read-only share) — out of scope for single-user tool
- Analytics on review rejection rates — no user base to analyze yet

### Architecture Approach

The architecture replaces the single monolithic Celery task with a stage machine: each stage runs, writes output to a typed `UGCJob` DB column, sets status to `stage_N_review`, and waits. The UI polls status via SSE (identical to existing LP generation pattern), renders the current stage review UI from a single `ugc_review.html` template, and advances to the next stage only on explicit user action. All existing generation service functions (`analyze_product`, `generate_hero_image`, etc.) are called unchanged from the new per-stage tasks.

**Major components:**
1. **`UGCJob` model** — Typed per-stage output columns; replaces `Job.extra_data` JSON bag for UGC pipeline
2. **Per-stage Celery tasks** (`ugc_stage_1` through `ugc_stage_6`) — Each reads from DB, runs one service function, writes output to DB
3. **Review UI routes** (`/ui/ugc/*`) — Form, list, review page, SSE stream, advance, regenerate, edit
4. **Review templates** (`ugc_new.html`, `ugc_list.html`, `ugc_review.html`) — Single review template with stage-conditional blocks
5. **SSE stage-completion stream** — DB-polled every 1s; client reloads page when `_review` status received

### Critical Pitfalls

1. **In-memory `_jobs` dict extended to review workflow** — Do not reuse. New `UGCJob` model persists all state to PostgreSQL. `_jobs` stays for LP generation only.
2. **Regeneration overwrites approved scene state** — Store per-scene approval separate from content. Regeneration produces a candidate, not an overwrite. Never mutate approved content in place.
3. **SSE generator leaks connections on tab close** — Wrap generator body in `try/except (anyio.EndOfStream, asyncio.CancelledError, GeneratorExit)`. Check `request.is_disconnected()` each loop iteration.
4. **Video served via Python byte-loading** — Never `open(path, 'rb').read()`. Use `FileResponse(path)` for images or `StreamingResponse` with 206 range handling for `.mp4`. Without 206, browser seek bar breaks.
5. **Mock/real AI flag mutates global settings** — Pass `use_mock: bool` as explicit argument through call chain. Do not mutate `get_settings()` singleton per request.

---

## Implications for Roadmap

Based on combined research, the natural build sequence follows data dependency order: DB schema → tasks → routes → templates → media wiring.

### Phase 1: UGCJob Data Model + Migration

**Rationale:** Every other component reads/writes `UGCJob`. Nothing is testable without it.
**Delivers:** `ugc_jobs` table with typed columns for all 6 stage outputs, status state machine values, Alembic migration.
**Addresses:** Stage gate enforcement (status column is the gate), persistence requirement (no in-memory state).
**Avoids:** In-memory job state loss (Pitfall 1), approved-state overwrite (Pitfall 2 — separate columns per stage, not shared JSON).

### Phase 2: Per-Stage Celery Tasks

**Rationale:** Tasks are pure Python, testable without UI. Validate pipeline logic works with DB intermediates before UI exists.
**Delivers:** Five tasks (`ugc_stage_1_analyze`, `ugc_stage_2_hero_image`, `ugc_stage_3_script`, `ugc_stage_45_assets`, `ugc_stage_6_compose`). Each reads from DB, runs existing service function, writes to DB.
**Uses:** `python-statemachine==2.6.0` for status transition validation in each task.
**Avoids:** Stage chaining via task args (anti-pattern — use DB as intermediary). Blocking FastAPI event loop (tasks are async Celery, not `create_task`).

### Phase 3: Review API Routes + SSE

**Rationale:** Routes depend on models and tasks. Test with curl before templates exist.
**Delivers:** `/ui/ugc/new`, `/ui/ugc/{job_id}`, `/ui/ugc/{job_id}/events`, `/ui/ugc/{job_id}/advance`, `/ui/ugc/{job_id}/regenerate`, `/ui/ugc/{job_id}/edit`, `/ui/ugc/`.
**Uses:** Existing `get_task_session_factory`, existing SSE `StreamingResponse` pattern.
**Avoids:** SSE disconnect leak (Pitfall 3 — add disconnect handling here, in first SSE endpoint). Mock flag bleed (Pitfall 5 — `advance` endpoint passes `use_mock` as argument).

### Phase 4: Review UI Templates

**Rationale:** Purely presentation; all logic is in routes and tasks. Build incrementally per stage.
**Delivers:** `ugc_new.html` (form), `ugc_list.html` (job list), `ugc_review.html` (single template, stage-conditional blocks with HTMX approve/reject/regenerate actions).
**Uses:** HTMX 2.0.8 CDN, HTMX SSE Extension 2.2.4, existing `base.html`, existing `ui.css`.
**Avoids:** One large monolithic template loading all media upfront (anti-pattern — render only current stage's UI).

### Phase 5: Media Preview Wiring

**Rationale:** Requires real generated files to verify. Depends on Stage 2 (images) and Stage 4-5 (video clips) having run.
**Delivers:** Working `<img>` and `<video>` previews for all stage outputs, HTTP 206 range support for video seeking, path traversal protection.
**Uses:** `StreamingResponse` with manual range parsing for `.mp4`, existing `/output` StaticFiles mount for images.
**Avoids:** Video seek breaking (Pitfall 4 — return 206 with `Content-Range`, never byte-load into memory). Path traversal — validate all paths are within `output/` before serving.

### Phase 6: Differentiator Features

**Rationale:** Build after core review flow validates and users confirm stage gating works.
**Delivers:** Bulk approve-all shortcut, side-by-side version comparison, stage-level re-run, LP module review extension.
**Addresses:** Should-have features from FEATURES.md (P2 priority items).

### Phase Ordering Rationale

- DB first — tasks, routes, and templates all depend on `UGCJob` columns existing
- Tasks before routes — `advance` and `regenerate` handlers queue tasks; tasks must exist
- Routes before templates — templates are presentation only; routes define what data is available
- Media preview last — needs real generated files from at least one full pipeline run
- Differentiators deferred — avoid scope creep before core loop is validated
- Monolithic task preserved (marked legacy) so existing `/ugc-ad-generate` API keeps working

### Research Flags

Phases needing deeper research during planning:
- **Phase 3 (SSE + Routes):** SSE disconnect handling has subtle async behavior differences between `anyio` versions. Verify `request.is_disconnected()` against installed Starlette version before implementing.
- **Phase 5 (Media Preview):** HTTP 206 range parsing edge cases (open-ended range `bytes=N-`, multi-range). Test with browser DevTools before marking done.

Phases with standard patterns (skip research):
- **Phase 1 (Data Model):** Alembic migration for new table is well-documented. Add model, generate migration, apply.
- **Phase 2 (Celery Tasks):** Pattern is identical to existing `generate_ugc_ad_task` — same session factory, same error handling, same retry structure.
- **Phase 4 (Templates):** HTMX attribute pattern documented with working examples in STACK.md. No discovery needed.
- **Phase 6 (Differentiators):** All P2 features reuse components built in Phases 3–5. No new infrastructure.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All components verified with official sources. Two new deps, rest already installed. |
| Features | MEDIUM | Competitor analysis solid. User prioritization inferred from industry patterns, not user interviews. |
| Architecture | HIGH | Derived directly from codebase inspection, not speculation. Existing patterns confirmed with file references. |
| Pitfalls | HIGH | Specific pitfalls traced to existing code files with line references. Not generic warnings. |

**Overall confidence:** HIGH

### Gaps to Address

- **User validation of stage grouping:** A-Roll + B-Roll are combined in one review step (stage 4+5). This reduces review steps but may frustrate users who want to approve A-Roll before B-Roll generates. Validate with first real user session.
- **Script editing scope:** Stage 3 review allows editing `master_script.full_script` as free text. If AdBreakdown has per-scene structure, per-scene editing may be needed. Assess after seeing real script output format.
- **Inline prompt editing for Stages 2 and 4–5:** FEATURES.md marks this P1 (must-have). ARCHITECTURE.md covers script text editing (Stage 3) but not hero image prompt or video clip prompt editing. Implementation pattern for those stages needs design before Phase 4.
- **Side-by-side comparison storage conflict:** FEATURES.md says regeneration should produce a candidate not overwrite. ARCHITECTURE.md's `regenerate` handler clears the existing path and reruns. These conflict — resolve in Phase 6 planning by adding a `candidates` column or separate table.

---

## Sources

### Primary (HIGH confidence)

- `app/tasks.py` — existing monolithic task structure (lines 355–510), confirmed patterns
- `app/ui/router.py` — SSE pattern, in-memory `_jobs` dict (confirmed in-use)
- `app/models.py` — existing model conventions (Job, Video, LandingPage)
- `app/pipeline.py` — `_update_job_status`, `_mark_job_complete`, `_mark_job_failed` helpers
- `app/main.py` — `/output` StaticFiles mount, router mounting pattern
- `app/database.py` — `get_task_session_factory` for Celery task DB access
- [python-statemachine PyPI](https://pypi.org/project/python-statemachine/) — v2.6.0, released 2026-02-13
- [HTMX 2.0.8 CDN](https://cdn.jsdelivr.net/npm/htmx.org@2.0.8/dist/htmx.min.js) — stable since June 2024
- [FastAPI Custom Responses Docs](https://fastapi.tiangolo.com/advanced/custom-response/) — FileResponse, StreamingResponse
- [FastAPI StreamingResponse Range Discussion](https://github.com/fastapi/fastapi/discussions/7718) — HTTP 206 range handling

### Secondary (MEDIUM confidence)

- [Visla AI Director Mode](https://www.visla.us/blog/news/introducing-ai-director-mode-storyboard-first-ai-video-with-real-control/) — per-scene regeneration patterns
- [Frame.io at Adobe MAX 2025](https://blog.frame.io/2025/10/28/adobe-max-2025-connected-creativity-for-modern-content-production/) — per-asset approval workflow
- [ShapeOfAI Regenerate Pattern](https://www.shapeof.ai/patterns/regenerate) — branching vs overwrite; confirms candidate approach
- [Nielsen Norman Group: AI Image Generation Stages](https://www.nngroup.com/articles/ai-imagegen-stages/) — define, explore, refine, export model
- [Streaming Video with FastAPI](https://stribny.name/posts/fastapi-video/) — range request implementation pattern
- [HTMX FastAPI patterns 2025](https://testdriven.io/blog/fastapi-htmx/) — partial template rendering, `hx-target`/`hx-swap` patterns

### Tertiary (reference)

- [FastAPI background task pitfalls](https://leapcell.io/blog/understanding-pitfalls-of-async-task-management-in-fastapi-requests) — in-memory task state loss confirmed
- [FastAPI memory leak discussion](https://github.com/fastapi/fastapi/discussions/11079) — SSE connection leak patterns

---

*Research completed: 2026-02-20*
*Ready for roadmap: yes*
