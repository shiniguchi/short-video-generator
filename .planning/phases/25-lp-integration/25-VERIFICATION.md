---
phase: 25-lp-integration
verified: 2026-02-21T12:15:00Z
status: gaps_found
score: 7/8 must-haves verified
gaps:
  - truth: "LP stage controls partial renders correctly after module approval"
    status: failed
    reason: "lp_stage_controls.html line 3 uses `selectattr('equalto', 'approved')` on dict values — Jinja2 selectattr requires an attribute name, not a test. Correct filter is `select('equalto', 'approved')`. This throws `No test named 'approved'` at render time whenever the partial is returned (after approve, regen, or accept-candidate)."
    artifacts:
      - path: "app/ui/templates/partials/lp_stage_controls.html"
        issue: "Line 3: `approvals.values() | selectattr('equalto', 'approved')` must be `approvals.values() | select('equalto', 'approved')`"
    missing:
      - "Change `selectattr` to `select` on line 3 of lp_stage_controls.html"
---

# Phase 25: LP Integration Verification Report

**Phase Goal:** Users can review LP modules individually and the LP hero image is populated from approved video frames by default.
**Verified:** 2026-02-21T12:15:00Z
**Status:** gaps_found
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | LP review page shows each module (headline, hero, CTA, benefits) as a separate card | VERIFIED | `lp_review.html` iterates `modules` (LP_MODULES = 4 items), renders a `stage-card` div per module with content from `lp_module_content` |
| 2 | Each LP module can be individually approved | PARTIAL | Approve endpoint (`POST /lp/{run_id}/module/{module}/approve`) correctly updates `lp_module_approvals` and commits. Returns `lp_stage_controls.html` partial — but that partial throws a Jinja2 runtime error (`No test named 'approved'`) due to `selectattr` misuse |
| 3 | LP review is locked when the linked UGCJob is not yet approved | VERIFIED | `lp_review` GET queries `UGCJob` via `ugc_job_id` FK, sets `video_approved = (ugc_job.status == "approved")`, renders locked message when False |
| 4 | LP copy content is stored in DB at generation time | VERIFIED | `generator.py` passes `lp_copy=copy.model_dump()` into `LandingPageResult`; `_run_generation()` sets `lp_record.lp_copy = result.lp_copy` |
| 5 | LP hero image defaults to a frame extracted from the approved combined video | VERIFIED | `ugc_ui_advance` calls `asyncio.to_thread(generate_thumbnail, ..., 2.0, "output/lp_frames")` on `approve_final` and stores result in `lp_row.lp_hero_image_path`; `ugc_generate_lp` does the same immediately |
| 6 | User can trigger LP-specific image regeneration to replace the video frame default | VERIFIED | `POST /lp/{run_id}/regenerate-hero` calls `ugc_tasks_module.lp_hero_regen.delay(lp.id)`; task runs `generate_hero_image()` and stores result as `lp_hero_candidate_path`; accept endpoint swaps to `lp_hero_image_path` |
| 7 | User can generate an LP from an approved UGC job via a button on the review page | VERIFIED | `ugc_review.html` shows "Generate LP" form for approved jobs; `POST /ugc/{job_id}/generate-lp` creates LP row, extracts frame, starts background generation, redirects to LP review |
| 8 | Frame extraction runs in a thread to avoid blocking the event loop | VERIFIED | Both `ugc_ui_advance` and `ugc_generate_lp` use `await asyncio.to_thread(generate_thumbnail, ...)` |

**Score:** 7/8 truths verified (1 partial/failed due to template bug)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `alembic/versions/007_lp_integration_schema.py` | Migration adding 6 columns to landing_pages | VERIFIED | revision='007', down_revision='006', 6 `add_column` calls, all nullable |
| `app/models.py` LandingPage | New LP integration columns | VERIFIED | All 6 columns present: `ugc_job_id`, `lp_module_approvals`, `lp_hero_image_path`, `lp_hero_candidate_path`, `lp_review_locked`, `lp_copy` |
| `app/ui/templates/lp_review.html` | LP module review page with per-module cards and stage gate | VERIFIED | 85 lines, contains stage gate check, 4-module card loop, per-module approve buttons with `hx-post` |
| `app/ui/templates/partials/lp_stage_controls.html` | HTMX partial for LP approve buttons | STUB/BUG | File exists with correct structure but line 3 has broken Jinja2 filter (`selectattr` instead of `select`) — renders as error at runtime |
| `app/ugc_tasks.py` lp_hero_regen | LP hero image regeneration Celery task | VERIFIED | Task registered as `app.ugc_tasks.lp_hero_regen`, calls `generate_hero_image()`, stores as `lp_hero_candidate_path` |
| `app/schemas.py` LandingPageResult | lp_copy field | VERIFIED | `lp_copy: Optional[dict] = None` present |
| `app/services/landing_page/generator.py` | Returns lp_copy in result | VERIFIED | `lp_copy=copy.model_dump()` passed to LandingPageResult constructor |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `app/ui/router.py` lp_review | `app/models.py` LandingPage + UGCJob | `select(LandingPage).where(run_id)` + `select(UGCJob).where(ugc_job_id)` | WIRED | Lines 159, 166 — queries both models, derives `video_approved` |
| `app/ui/templates/lp_review.html` | `app/ui/router.py` lp_module_approve | `hx-post="/ui/lp/{{ lp.run_id }}/module/{{ module }}/approve"` | WIRED | Line 70-74 — correct HTMX post |
| `app/ui/router.py` lp_module_approve | `lp_stage_controls.html` | Returns partial as HTMX response | BROKEN | Partial renders correctly in structure but crashes due to `selectattr` bug |
| `app/ui/router.py` ugc_ui_advance | `generate_thumbnail` | `asyncio.to_thread(generate_thumbnail, ...)` on `approve_final` | WIRED | Lines 471-489 — conditional on `approve_event == "approve_final"` and `job.final_video_path` |
| `app/ui/router.py` regenerate-hero endpoint | `app/ugc_tasks.py` lp_hero_regen | `ugc_tasks_module.lp_hero_regen.delay(lp.id)` | WIRED | Line 237 — lazy import + .delay() call |
| `app/ui/templates/ugc_review.html` | `app/ui/router.py` generate-lp | `form action="/ui/ugc/{{ job.id }}/generate-lp"` | WIRED | Lines 215-217 — form POST for approved jobs only |
| `app/ui/router.py` lp_copy storage | `app/services/landing_page/generator.py` | `result.lp_copy` assigned from `LandingPageResult.lp_copy` | WIRED | Lines 558, 644-646 |

### Requirements Coverage

| Requirement | Status | Blocking Issue |
|-------------|--------|----------------|
| LP review stage shows each module (headline, hero, CTA, benefits) as a separate card with approve/reject | SATISFIED | Cards render correctly in `lp_review.html` |
| LP hero image defaults to a frame extracted from the approved combined video | SATISFIED | Frame extraction wired on `approve_final` and on `generate-lp` |
| User can trigger LP-specific image regeneration to replace the video frame default | SATISFIED | Regen endpoint + Celery task + accept endpoint wired |
| LP review is locked until the video pipeline is fully approved | SATISFIED | Stage gate implemented via `lp_review_locked` + `ugc_job_id` FK check |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `app/ui/templates/partials/lp_stage_controls.html` | 3 | `selectattr("equalto", "approved")` on string values — wrong Jinja2 filter | Blocker | Any HTMX action that returns this partial (approve module, regenerate hero, accept candidate) throws `No test named 'approved'` at render time. The approve action itself commits to DB correctly, but the HTMX response fails, breaking the UI loop. |

### Human Verification Required

#### 1. Generate LP flow end-to-end

**Test:** With an approved UGC job that has `final_video_path` set, click "Generate LP". Check the LP review page renders with a hero image from the video.
**Expected:** LP review page shows hero module with an extracted video frame image, other modules show copy text, review is unlocked.
**Why human:** Requires a real or mock video file on disk; `generate_thumbnail` has a `moviepy` dependency that can't be tested statically.

#### 2. Approve module HTMX partial update (after bug fix)

**Test:** After fixing the `selectattr` -> `select` bug, approve a module on the LP review page. Check the controls partial updates correctly showing N/4 count and "LP review complete" when all 4 are done.
**Expected:** Partial re-renders with updated count, no error.
**Why human:** Requires browser + running server to validate HTMX swap behavior.

### Gaps Summary

One blocker gap exists: the `lp_stage_controls.html` partial uses `selectattr("equalto", "approved")` on a dict's `.values()` collection. Jinja2's `selectattr` filter is for selecting objects by attribute name — it doesn't accept test names like "equalto". The correct filter for testing scalar string values is `select("equalto", "approved")`.

This is a single-character fix (`selectattr` -> `select`) but it breaks every HTMX interaction that returns the partial:
- POST `/lp/{run_id}/module/{module}/approve`
- POST `/lp/{run_id}/regenerate-hero`
- POST `/lp/{run_id}/accept-hero-candidate`

The underlying DB writes all succeed — the bug only affects the HTMX response rendering. The full LP review page (`lp_review.html`) is unaffected since it uses a different pattern to check approvals.

The fix: In `lp_stage_controls.html` line 3, change:
```
{% set approved_count = approvals.values() | selectattr("equalto", "approved") | list | length %}
```
to:
```
{% set approved_count = approvals.values() | select("equalto", "approved") | list | length %}
```

---
_Verified: 2026-02-21T12:15:00Z_
_Verifier: Claude (gsd-verifier)_
