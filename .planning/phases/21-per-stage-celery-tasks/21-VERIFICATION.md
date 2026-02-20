---
phase: 21-per-stage-celery-tasks
verified: 2026-02-20T20:39:48Z
status: passed
score: 9/9 must-haves verified
re_verification: false
---

# Phase 21: Per-Stage Celery Tasks Verification Report

**Phase Goal:** Users can submit a generation job and each pipeline stage executes sequentially, pausing at each checkpoint for approval.
**Verified:** 2026-02-20T20:39:48Z
**Status:** PASSED
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|---------|
| 1 | User can submit a product idea via web form and a UGCJob is created and queued | VERIFIED | POST /ugc/jobs in ugc_router.py:39-88 — accepts Form fields + file uploads, creates UGCJob, transitions pending->running, calls ugc_stage_1_analyze.delay(job.id) |
| 2 | Each stage (analyze, hero image, script, aroll, broll, compose) runs as a separate Celery task | VERIFIED | Five tasks in app/ugc_tasks.py: ugc_stage_1_analyze (lines 46-121), ugc_stage_2_script (126-195), ugc_stage_3_aroll (200-254), ugc_stage_4_broll (259-313), ugc_stage_5_compose (318-396) |
| 3 | Each stage writes output to its UGCJob DB column then sets status to stage_N_review | VERIFIED | Each task writes columns (job.analysis_*, job.hero_image_path, job.master_script, etc.) then calls sm.send("complete_X") + job.status = sm.current_state.id + session.commit() |
| 4 | Stage N+1 task only starts after user explicitly advances past stage N | VERIFIED | advance_ugc_job endpoint (ugc_router.py:93-136) checks _STAGE_ADVANCE_MAP, validates review state, sends approve event, then calls task_fn.delay(job_id) only for non-None next_task_name |
| 5 | Mock/real AI flag is passed as explicit argument (no global mutation) | VERIFIED | All 5 service functions have use_mock: bool = False param; tasks pass use_mock=job.use_mock; grep confirms zero get_llm_provider() or get_image_provider() calls remain in service files |
| 6 | Advance on non-review status returns 400 | VERIFIED | ugc_router.py:106-110 — checks `if job.status not in _STAGE_ADVANCE_MAP` returns HTTP 400 |
| 7 | Celery worker autodiscovers ugc_tasks module | VERIFIED | app/worker.py:40 — `import app.ugc_tasks  # noqa: F401` |
| 8 | Main app mounts ugc_router | VERIFIED | app/main.py:13 — `from app import ugc_router`; line 93 — `app.include_router(ugc_router.router)` |
| 9 | All tasks use NullPool sessions (not module-level engine) | VERIFIED | Every task's async helper imports and calls get_task_session_factory() from app.database |

**Score:** 9/9 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `app/ugc_tasks.py` | Five per-stage Celery tasks | VERIFIED | 396 lines, 5 tasks registered, imports cleanly (.venv/bin/python confirms "All 5 tasks imported OK") |
| `app/services/ugc_pipeline/product_analyzer.py` | analyze_product with use_mock param | VERIFIED | use_mock: bool = False at line 16, direct MockLLMProvider/GeminiLLMProvider instantiation |
| `app/services/ugc_pipeline/script_engine.py` | generate_ugc_script with use_mock param | VERIFIED | use_mock: bool = False at line 15, same direct instantiation pattern |
| `app/services/ugc_pipeline/asset_generator.py` | generate_hero_image, generate_aroll_assets, generate_broll_assets with use_mock param | VERIFIED | All three functions + _get_veo_or_mock() accept use_mock; direct image provider instantiation |
| `app/ugc_router.py` | Submit, advance, status endpoints | VERIFIED | 179 lines, 3 routes confirmed, _STAGE_ADVANCE_MAP covers all 5 review states |
| `app/worker.py` | ugc_tasks autodiscovery | VERIFIED | Line 40: `import app.ugc_tasks  # noqa: F401` |
| `app/main.py` | ugc_router mounted on /ugc prefix | VERIFIED | Routes confirmed: ['/ugc/jobs', '/ugc/jobs/{job_id}/advance', '/ugc/jobs/{job_id}'] |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| app/ugc_tasks.py | app/services/ugc_pipeline/product_analyzer.py | analyze_product(use_mock=job.use_mock) | WIRED | 5 occurrences of use_mock=job.use_mock in ugc_tasks.py |
| app/ugc_tasks.py | app/state_machines/ugc_job.py | UGCJobStateMachine with model binding | WIRED | Every task instantiates UGCJobStateMachine, sends complete_X event, writes job.status = sm.current_state.id |
| app/ugc_tasks.py | app/database.py | get_task_session_factory() NullPool sessions | WIRED | All 5 tasks + _fail_job helper call get_task_session_factory() inside async helpers |
| app/ugc_router.py | app/ugc_tasks.py | task_fn.delay(job.id) in advance endpoint | WIRED | Lines 86 and 134 — delay(job.id) and delay(job_id) confirmed |
| app/ugc_router.py | app/state_machines/ugc_job.py | UGCJobStateMachine for advance transitions | WIRED | Line 21: direct import; used in both submit (line 77) and advance (line 117) endpoints |
| app/main.py | app/ugc_router.py | app.include_router(ugc_router.router) | WIRED | Line 13: import; line 93: include_router confirmed |
| app/worker.py | app/ugc_tasks.py | import app.ugc_tasks for task registration | WIRED | Line 40: confirmed |

### State Machine Walk

Full pipeline transition chain verified end-to-end in Python:
- pending -> (start) -> running
- running -> (complete_analysis) -> stage_analysis_review
- stage_analysis_review -> (approve_analysis) -> running
- running -> (complete_script) -> stage_script_review
- stage_script_review -> (approve_script) -> running
- running -> (complete_aroll) -> stage_aroll_review
- stage_aroll_review -> (approve_aroll) -> running
- running -> (complete_broll) -> stage_broll_review
- stage_broll_review -> (approve_broll) -> running
- running -> (complete_composition) -> stage_composition_review
- stage_composition_review -> (approve_final) -> approved

### Anti-Patterns Found

None. No TODO/FIXME/placeholder comments, no empty return stubs, no console.log-only implementations found in any phase 21 file.

### Human Verification Required

#### 1. End-to-end flow with real Celery worker

**Test:** Submit a job via POST /ugc/jobs with use_mock=true, check status via GET, advance through each review state, verify final video is produced.
**Expected:** Each stage completes, status advances through all review states, final_video_path is set.
**Why human:** Requires running Celery worker + Redis broker; cannot verify task execution from code alone.

#### 2. File upload persistence

**Test:** Submit job with 1-2 product images, check that product_image_paths column is populated and files exist on disk at output/ugc_uploads/{job_id}/.
**Expected:** Images saved, paths stored in DB.
**Why human:** Requires live HTTP request with multipart form data.

#### 3. Non-review-state 400 rejection

**Test:** Call POST /ugc/jobs/{id}/advance when job status is "running" or "pending".
**Expected:** HTTP 400 with "not a review state" message.
**Why human:** Requires live DB record; logic is verified by code inspection but needs integration test confirmation.

### Notes

- `compose_ugc_ad()` intentionally has no `use_mock` param — it does pure ffmpeg/moviepy composition with no AI calls. Stage 5 still correctly derives from `job.use_mock` for earlier stages.
- Stage 1 combines analysis + hero image into one task because the state machine has no `stage_hero_image_review` state — this is a documented design decision.
- The `approve_final` path sets `job.approved_at` and enqueues no next task (next_task_name=None), correctly terminating the pipeline at the `approved` final state.

---

_Verified: 2026-02-20T20:39:48Z_
_Verifier: Claude (gsd-verifier)_
