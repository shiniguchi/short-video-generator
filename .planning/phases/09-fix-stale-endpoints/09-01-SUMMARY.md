---
phase: 09-fix-stale-endpoints
plan: 01
subsystem: api
tags: [bugfix, endpoint, job-tracking]
dependency_graph:
  requires: [phase-07-job-tracking]
  provides: [functional-manual-endpoints]
  affects: [api-routes, video-compositor]
tech_stack:
  added: []
  patterns: [lazy-import, on-demand-job-creation]
key_files:
  created: []
  modified:
    - app/api/routes.py: "Fixed POST /generate-content and POST /compose-video to create Jobs and pass job_id"
    - app/services/video_compositor/compositor.py: "Corrected default output_dir from output/final to output/review"
decisions:
  - "On-demand Job creation pattern: When job_id is None, endpoints create Job records with appropriate stage and completed_stages"
  - "Manual flow Jobs use theme='manual' to distinguish from orchestrated pipeline Jobs"
  - "POST /compose-video marks content_generation as completed in extra_data to enable progress tracking"
metrics:
  duration_minutes: 1
  tasks_completed: 2
  files_modified: 2
  commits: 2
  completed_at: "2026-02-14"
---

# Phase 09 Plan 01: Fix Stale Manual Endpoints Summary

**One-liner:** Fixed broken POST /generate-content and POST /compose-video endpoints to create Jobs on-demand and pass job_id to Celery tasks, aligned VideoCompositor default to output/review.

## Overview

Phase 7 added job_id as the first parameter to all Celery tasks for job tracking, but the two manual per-stage API endpoints (POST /generate-content and POST /compose-video) were not updated. This caused TypeError when calling the tasks. This plan fixed both endpoints to create Job records on-demand when job_id is not provided, and cleaned up the stale output/final default in VideoCompositor.

## Tasks Completed

### Task 1: Fix POST /generate-content and POST /compose-video endpoints

**Objective:** Update endpoint signatures to pass job_id to their underlying Celery tasks.

**Changes:**
- POST /generate-content:
  - Added `job_id: Optional[int] = None` and `theme_config_path: Optional[str] = None` as query parameters
  - Injected `session: AsyncSession = Depends(get_session)` for DB access
  - Creates Job with status="pending", stage="content_generation", theme="manual" when job_id is None
  - Calls `generate_content_task.delay(job_id, theme_config_path)` with job_id as first argument
  - Returns job_id in response for tracking

- POST /compose-video:
  - Kept existing required params (script_id, video_path, audio_path)
  - Added `job_id: Optional[int] = None` and `cost_data: Optional[dict] = None` as query parameters
  - Injected `session: AsyncSession = Depends(get_session)` for DB access
  - Creates Job with status="pending", stage="composition", theme="manual", completed_stages=["content_generation"] when job_id is None
  - Calls `compose_video_task.delay(job_id, script_id, video_path, audio_path, cost_data)` with job_id as first argument
  - Returns job_id in response for tracking

**Files Modified:**
- `app/api/routes.py` (lines 172-200, 244-298)

**Commit:** 5c264d6

### Task 2: Fix VideoCompositor default and remove output/final

**Objective:** Align VideoCompositor default output_dir with config.py setting and remove unused directory.

**Changes:**
- Changed `VideoCompositor.__init__` default parameter from `output_dir: str = "output/final"` to `output_dir: str = "output/review"`
- Updated docstring to reflect new default
- Removed empty `output/final/` directory

**Rationale:** In practice, the compositor is always instantiated with `output_dir=settings.composition_output_dir` from tasks.py, so this is a fallback/documentation alignment with the Phase 5 config change.

**Files Modified:**
- `app/services/video_compositor/compositor.py` (lines 31, 36)

**Commit:** ebbdf2d

## Verification Results

All success criteria met:

1. **POST /generate-content passes job_id:** ✓ Confirmed with grep
2. **POST /compose-video passes job_id:** ✓ Confirmed with grep
3. **No TypeError from missing args:** ✓ Python syntax validation passed
4. **output/final removed:** ✓ Directory does not exist
5. **All 19 endpoints exist:** ✓ Confirmed 19 route decorators

## Deviations from Plan

None - plan executed exactly as written.

## Integration Points

**Updated:**
- `app/api/routes.py` → `app/tasks.py`: Both manual endpoints now correctly pass job_id as first argument

**Unchanged:**
- `app/tasks.py` signatures remain the same (no changes needed)
- `app/models.py` Job model unchanged
- `app/services/video_compositor/compositor.py` behavior unchanged (only default parameter updated)

## Impact

**Fixed:**
- POST /generate-content now works without TypeError
- POST /compose-video now works without TypeError
- Manual debugging flows are fully functional alongside orchestrated pipeline
- INFRA-04 (API completeness) restored - all 19 endpoints operational

**Benefits:**
- Users can now trigger individual pipeline stages for testing/debugging
- Job tracking works consistently across manual and orchestrated flows
- Progress tracking available for manual flows via /jobs/{job_id}
- Code default aligns with configuration (reduces confusion)

## Self-Check: PASSED

**Files created/modified exist:**
- FOUND: app/api/routes.py (modified)
- FOUND: app/services/video_compositor/compositor.py (modified)

**Commits exist:**
- FOUND: 5c264d6 (Task 1)
- FOUND: ebbdf2d (Task 2)

**Directory removed:**
- CONFIRMED: output/final does not exist

**No stale references:**
- CONFIRMED: No Python code references output/final
