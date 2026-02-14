---
phase: 06-pipeline-integration
plan: 02
subsystem: pipeline-api
tags: [fastapi, rest-api, celery, job-management, orchestration]

dependency_graph:
  requires:
    - Phase 06-01 (Pipeline Orchestration) - orchestrate_pipeline_task, PIPELINE_STAGES, Job helpers
    - Phase 01 (Foundation) - Job model, FastAPI setup, database session
  provides:
    - POST /generate - Pipeline trigger endpoint with Job creation
    - GET /jobs - Job listing with status filter and progress
    - GET /jobs/{id} - Real-time job status endpoint
    - POST /jobs/{id}/retry - Failed job retry with resume capability
  affects:
    - Future deployment (Cloud Run) - these are the user-facing pipeline control endpoints

tech_stack:
  added:
    - app/schemas.py - 5 new Pydantic schemas for pipeline API
    - app/api/routes.py - 4 new REST endpoints (Phase 6 section)
  patterns:
    - Lazy imports in endpoints to avoid circular dependencies
    - Non-blocking task triggering (task.delay() with immediate response)
    - Progress percentage computed from completed_stages
    - Resume-from-checkpoint via retry endpoint

key_files:
  created:
    - None (all modifications)
  modified:
    - app/schemas.py (47 lines added) - Pipeline request/response schemas
    - app/api/routes.py (189 lines added) - Pipeline control endpoints

decisions:
  - Lazy imports in endpoint functions avoid circular import issues between routes, pipeline, and models
  - Progress percentage computed on-the-fly from Job.extra_data["completed_stages"]
  - Retry endpoint preserves completed_stages to enable true resume-from-checkpoint
  - Poll URL pattern (/api/jobs/{id}) enables client-side status monitoring

metrics:
  duration_minutes: 2
  completed_date: 2026-02-14
  tasks_completed: 2
  files_created: 0
  files_modified: 2
  commits: 2
---

# Phase 6 Plan 2: Pipeline REST API Summary

REST API endpoints for triggering, monitoring, listing, and retrying pipeline runs with real-time progress tracking.

## What Was Built

Added 4 new endpoints to `app/api/routes.py` and 5 supporting Pydantic schemas to `app/schemas.py`, completing ORCH-04 (monitoring) and ORCH-05 (manual triggering).

### Key Components

1. **Pydantic Schemas (app/schemas.py)**
   - `PipelineTriggerRequest` - Optional theme/config_path for POST /generate
   - `PipelineTriggerResponse` - Job ID, task ID, poll URL for triggered pipeline
   - `JobStatusResponse` - Full job status with completed_stages, progress_pct, error details
   - `JobListResponse` - Paginated job list wrapper
   - `JobRetryResponse` - Retry confirmation with resume_from and skipping_stages info

2. **POST /generate Endpoint**
   - Accepts optional JSON body (theme, config_path)
   - Creates Job record with status="pending", stage="initialization"
   - Triggers orchestrate_pipeline_task.delay() asynchronously
   - Returns immediately with job_id and poll_url (non-blocking)
   - Default empty request supported for quick testing

3. **GET /jobs Endpoint**
   - Lists pipeline jobs ordered by created_at DESC
   - Optional status filter (pending, running, completed, failed)
   - Configurable limit (default 20)
   - Computes progress_pct for each job from completed_stages / total_stages
   - Returns JobListResponse with count and jobs array

4. **GET /jobs/{id} Endpoint**
   - Returns detailed status for single job
   - Includes completed_stages list for transparency
   - Computes progress_pct (e.g., 60% when 3/5 stages done)
   - ISO format timestamps for created_at and updated_at
   - Returns 404 if job not found

5. **POST /jobs/{id}/retry Endpoint**
   - Validates job.status == "failed" (400 error otherwise)
   - Resets status to "pending" and clears error_message
   - Preserves completed_stages for resume capability
   - Triggers orchestrate_pipeline_task with resume=True
   - Returns resume_from (first incomplete stage) and skipping_stages list

### Architecture Decisions

**Lazy Imports**: All model and schema imports happen inside endpoint functions to avoid circular dependencies. Pattern: `from app.models import Job` inside function body.

**Non-Blocking Trigger**: POST /generate uses `task.delay()` and returns immediately. No `.get()` or `.wait()` calls. Client polls GET /jobs/{id} for status updates.

**Progress Calculation**: Progress percentage computed on-the-fly from `len(completed_stages) / len(PIPELINE_STAGES) * 100`. Simple, accurate, no extra state management.

**Resume Pattern**: Retry endpoint keeps completed_stages intact. orchestrate_pipeline_task skips already-completed stages when resume=True. This enables fault-tolerant pipeline execution.

### Python 3.9 Compatibility

- Used `from typing import List, Optional` (not `list[str]` syntax)
- Used `datetime.now(timezone.utc)` (already imported in routes.py)
- All Pydantic schemas use Python 3.9 compatible annotations

## Implementation Details

### Endpoint Verification

All 4 new endpoints registered in FastAPI app:
- `/generate` - Pipeline trigger
- `/jobs` - Job listing
- `/jobs/{job_id}` - Job status
- `/jobs/{job_id}/retry` - Job retry

Existing endpoints (health, trends, videos, approve, reject) remain functional.

### Request/Response Flow

**Trigger Pipeline:**
```
POST /generate
{
  "theme": "tech-innovation",
  "config_path": "config/custom.yml"
}

→ Response:
{
  "job_id": 42,
  "task_id": "a1b2c3d4-...",
  "status": "queued",
  "poll_url": "/jobs/42",
  "message": "Pipeline execution started"
}
```

**Monitor Progress:**
```
GET /jobs/42

→ Response:
{
  "id": 42,
  "status": "running",
  "stage": "content_generation",
  "completed_stages": ["trend_collection", "trend_analysis"],
  "total_stages": 5,
  "progress_pct": 40.0,
  "theme": "tech-innovation",
  "created_at": "2026-02-14T10:55:00Z",
  "updated_at": "2026-02-14T10:56:30Z",
  "error_message": null
}
```

**Retry Failed Job:**
```
POST /jobs/42/retry

→ Response:
{
  "job_id": 42,
  "task_id": "e5f6g7h8-...",
  "status": "queued",
  "resume_from": "composition",
  "skipping_stages": ["trend_collection", "trend_analysis", "content_generation"],
  "message": "Pipeline retry started from composition"
}
```

## Testing & Verification

All verification checks passed:

1. All 5 pipeline schemas importable (PipelineTriggerRequest, PipelineTriggerResponse, JobStatusResponse, JobListResponse, JobRetryResponse)
2. All 4 new endpoints registered in FastAPI app routes
3. Existing endpoints (health, trends, videos, approve, reject) still functional
4. Phase 6 routes visible in router: /generate, /jobs, /jobs/{job_id}, /jobs/{job_id}/retry

## Deviations from Plan

None - plan executed exactly as written.

## What's Next

Phase 6 complete. All pipeline integration tasks finished:
- 06-01: Pipeline orchestration with checkpointing
- 06-02: REST API endpoints for control and monitoring

The full pipeline is now:
1. Triggerable via REST API (POST /generate)
2. Observable in real-time (GET /jobs/{id} with progress_pct)
3. Fault-tolerant with resume capability (POST /jobs/{id}/retry)
4. Fully integrated from trend collection through composition and review

Next step: Deploy to Cloud Run or continue with additional features (publishing, scheduling, etc).

## Commits

- `dd3ca2e`: feat(06-02): add Pydantic schemas for pipeline REST API
- `35b4e9e`: feat(06-02): add pipeline REST API endpoints

## Self-Check: PASSED

### Files Modified
- [x] `/Users/naokitsk/Documents/short-video-generator/app/schemas.py` - EXISTS
- [x] `/Users/naokitsk/Documents/short-video-generator/app/api/routes.py` - EXISTS

### Commits Verified
- [x] `dd3ca2e` - FOUND in git log
- [x] `35b4e9e` - FOUND in git log

All claimed files and commits verified successfully.
