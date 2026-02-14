---
phase: 06-pipeline-integration
plan: 01
subsystem: pipeline-orchestration
tags: [celery, orchestration, fault-tolerance, checkpointing]

dependency_graph:
  requires:
    - Phase 02 (Trend Intelligence) - collect_trends_task, analyze_trends_task
    - Phase 03 (Content Generation) - generate_content_task
    - Phase 04 (Video Composition) - compose_video_task
    - Phase 01 (Foundation) - Job model, database helpers
  provides:
    - orchestrate_pipeline_task - Full pipeline orchestration with checkpointing
    - PIPELINE_STAGES - Stage constants for pipeline execution
    - Job status helpers - Database update utilities
  affects:
    - app/worker.py - Added pipeline module registration

tech_stack:
  added:
    - app/pipeline.py - Pipeline orchestration module
  patterns:
    - Database-backed checkpointing via Job.extra_data["completed_stages"]
    - Resume-from-checkpoint capability
    - Celery task chaining with composition
    - asyncio.run() bridge pattern for async DB operations in sync tasks

key_files:
  created:
    - app/pipeline.py (275 lines) - Pipeline orchestration with 5 stages
  modified:
    - app/worker.py (3 lines added) - Explicit pipeline module import

decisions:
  - orchestrator has max_retries=0 - individual stages handle their own retries
  - composition chained from content generation - extracted compose_task_id and waited
  - completed_stages list in Job.extra_data - enables resume capability
  - review stage marked complete by orchestrator - manual review happens via API endpoints

metrics:
  duration_minutes: 1
  completed_date: 2026-02-14
  tasks_completed: 2
  files_created: 1
  files_modified: 1
  commits: 2
---

# Phase 6 Plan 1: Pipeline Orchestration Summary

Pipeline orchestration task that sequences all 5 stages with database-backed checkpointing and resume capability.

## What Was Built

Created `app/pipeline.py` with the core orchestration layer (ORCH-01, ORCH-02, ORCH-03) that transforms independent Celery tasks into a cohesive pipeline with fault tolerance.

### Key Components

1. **Stage Constants**
   - Single source of truth for 5 pipeline stages
   - trend_collection, trend_analysis, content_generation, composition, review
   - Exported as PIPELINE_STAGES list

2. **Async Job Helpers**
   - `_load_job(job_id)` - Loads Job record with all fields
   - `_update_job_status(job_id, stage, status, error_msg)` - Updates Job row
   - `_mark_stage_complete(job_id, stage)` - Appends to completed_stages list
   - `_mark_job_complete(job_id)` - Sets final completion status
   - `_mark_job_failed(job_id, stage, error_msg)` - Records failure details
   - All use asyncio.run() pattern consistent with existing tasks

3. **orchestrate_pipeline_task**
   - Celery task with name 'app.tasks.orchestrate_pipeline_task'
   - max_retries=0 - orchestrator doesn't retry, stages handle own retries
   - Sequences: collect_trends -> analyze_trends -> generate_content -> (composition chained) -> review
   - Loads completed_stages from Job.extra_data to enable resume
   - Waits for composition task after content generation completes
   - Logs all stage transitions for Docker container visibility
   - Updates Job status after each stage transition

4. **Worker Registration**
   - Added explicit `import app.pipeline` in worker.py
   - Ensures orchestrate_pipeline_task is discovered by Celery
   - Task callable via celery_app

### Architecture Decisions

**Checkpointing Strategy**: Store completed_stages as list in Job.extra_data JSON column. When resuming, skip stages already in the list. This enables fault tolerance without external state management.

**Retry Strategy**: Individual stage tasks have autoretry_for=(Exception,) with retry_backoff=True and max_retries=3. Orchestrator has max_retries=0 to prevent double-retry scenarios. If stage fails after 3 retries, orchestrator marks job failed and re-raises.

**Composition Chaining**: Content generation returns compose_task_id. Orchestrator extracts this, waits for composition to complete, then marks both STAGE_CONTENT_GENERATION and STAGE_COMPOSITION complete. This maintains end-to-end pipeline flow while respecting Phase 4's deferred composition design.

**Review Stage**: Marked complete by orchestrator, but actual review happens asynchronously via Phase 5 API endpoints (/videos/{id}/approve, /videos/{id}/reject). This allows pipeline to complete while video awaits human review.

## Implementation Details

### Error Handling

All stage execution wrapped in try/except. On exception:
1. Log error with stage name
2. Call `_mark_job_failed(job_id, stage, str(exc))`
3. Re-raise exception to fail the orchestrator task

Individual stage tasks retry transient failures automatically before bubbling up to orchestrator.

### Stage Execution Pattern

```python
for stage_name, task_func, args in stage_tasks:
    if stage_name in completed_stages:
        logger.info(f"Skipping stage {stage_name} (already completed)")
        continue

    logger.info(f"Starting stage: {stage_name}")
    asyncio.run(_update_job_status(job_id, stage_name, "running"))

    result = task_func.apply_async(args=args)
    task_result = result.get(timeout=1800)  # 30 min timeout

    logger.info(f"Stage {stage_name} completed: {task_result}")
    asyncio.run(_mark_stage_complete(job_id, stage_name))
```

### Python 3.9 Compatibility

- Used `from typing import Optional, List, Dict, Any` (not `list[str]` syntax)
- asyncio.run() pattern consistent with existing codebase
- All imports and syntax compatible with Python 3.9.6

## Testing & Verification

All verification checks passed:

1. PIPELINE_STAGES contains 5 stages in correct order
2. All helper functions importable (_load_job, _update_job_status, etc.)
3. orchestrate_pipeline_task registered in celery_app.tasks
4. All existing tasks still importable (collect_trends_task, analyze_trends_task, generate_content_task, compose_video_task)

## Deviations from Plan

None - plan executed exactly as written.

## What's Next

Phase 6 Plan 2 will add API endpoint integration to trigger orchestrate_pipeline_task from REST API, create Job records, and expose pipeline status/progress to users.

## Commits

- `5c6f99f`: feat(06-01): add pipeline orchestration module with stage constants and Job helpers
- `9b6fb1c`: feat(06-01): register pipeline module with Celery autodiscovery

## Self-Check: PASSED

### Files Created
- [x] `/Users/naokitsk/Documents/short-video-generator/app/pipeline.py` - EXISTS

### Files Modified
- [x] `/Users/naokitsk/Documents/short-video-generator/app/worker.py` - EXISTS

### Commits Verified
- [x] `5c6f99f` - FOUND in git log
- [x] `9b6fb1c` - FOUND in git log

All claimed files and commits verified successfully.
