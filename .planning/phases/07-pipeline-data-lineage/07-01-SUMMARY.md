---
phase: 07-pipeline-data-lineage
plan: 01
subsystem: pipeline-orchestration
tags: [data-lineage, foreign-keys, job-tracking, gap-closure]

dependency_graph:
  requires:
    - "06-02: Pipeline REST API endpoints"
    - "Phase 4: Video composition with database persistence"
    - "Phase 3: Script generation with database persistence"
  provides:
    - "Job-to-Script foreign key population"
    - "Job-to-Video foreign key population"
    - "Full data lineage from orchestrator to outputs"
  affects:
    - app/pipeline.py
    - app/tasks.py
    - app/services/script_generator.py

tech_stack:
  added: []
  patterns:
    - "Parameter threading through async task chain"
    - "Foreign key population via optional parameters"

key_files:
  created: []
  modified:
    - path: app/pipeline.py
      summary: "Pass job_id to generate_content_task in stage_tasks list"
    - path: app/tasks.py
      summary: "Thread job_id from generate_content_task through save_production_plan and compose_video_task"
    - path: app/services/script_generator.py
      summary: "Accept job_id parameter and populate Script.job_id foreign key"
    - path: .planning/REQUIREMENTS.md
      summary: "Update ORCH-01 from 8-stage to 5-stage pipeline description"

decisions:
  - decision: "Use optional job_id parameter instead of required"
    rationale: "Allows backward compatibility for standalone script/video generation"
    alternatives: ["Make job_id required", "Add separate job-aware functions"]
    outcome: "Optional parameter chosen for flexibility"

metrics:
  duration_minutes: 2
  tasks_completed: 2
  files_modified: 4
  commits: 2
  completed_at: "2026-02-14"
---

# Phase 07 Plan 01: Pipeline Data Lineage Summary

Job ID threading through pipeline task chain to restore Script/Video foreign key population.

## Objective Achieved

Threaded `job_id` from `orchestrate_pipeline_task` through the entire content generation and composition chain, ensuring Script and Video database records link back to their originating Job via foreign keys. This restores full data lineage and checkpoint auditability.

## Tasks Completed

### Task 1: Thread job_id through pipeline orchestrator, content task, and composition task

**Status:** Complete
**Commit:** 1d95a79
**Files:** app/pipeline.py, app/tasks.py, app/services/script_generator.py

Made four coordinated changes to thread job_id:

1. **app/pipeline.py**: Updated `stage_tasks` list to pass `job_id` as first argument to `generate_content_task`
2. **app/tasks.py (generate_content_task)**:
   - Updated function signature to accept `job_id: int` as first parameter
   - Passed `job_id` to `save_production_plan()` call
   - Passed `job_id` as first argument to `compose_video_task.delay()` call
3. **app/tasks.py (compose_video_task)**:
   - Updated function signature to accept `job_id: int` as first parameter
   - Updated inner `_save_video_record()` function to accept `job_id`
   - Populated `Video.job_id` in Video() constructor
4. **app/services/script_generator.py (save_production_plan)**:
   - Added `job_id: Optional[int] = None` parameter
   - Populated `Script.job_id` in Script() constructor
   - Updated log message to include job_id

All 6 verification grep checks passed:
- Orchestrator passes job_id
- Content task accepts job_id
- save_production_plan populates Script.job_id
- Compose task accepts job_id
- Content task passes job_id to compose
- Compose task populates Video.job_id

### Task 2: Update REQUIREMENTS.md ORCH-01 to reflect 5 orchestration stages

**Status:** Complete
**Commit:** a46e2c5
**Files:** .planning/REQUIREMENTS.md

Updated ORCH-01 requirement text from "Full 8-stage pipeline" to "Full 5-stage pipeline executes sequentially: trend_collection → trend_analysis → content_generation (script + video + voiceover) → composition → review".

This accurately reflects the actual implementation where script generation, video generation, and voiceover synthesis are combined into a single `content_generation` Celery task, and composition is chained automatically.

## Deviations from Plan

None - plan executed exactly as written.

## Verification Results

All verification criteria passed:

1. Import check: All imports work without errors
2. job_id parameter chain complete (all 6 grep checks match)
3. No `relationship()` objects added to models.py (verified - only foreign key columns exist)
4. ORCH-01 text updated from "8-stage" to "5-stage"
5. No new dependencies added to requirements.txt
6. Python 3.9 compatible syntax used (typing imports, Optional)

## Impact

**Before this plan:**
- Job records created by orchestrator had no way to query their Script/Video outputs
- Script.job_id and Video.job_id columns existed in schema but were never populated (always NULL)
- Data lineage broken - couldn't trace which Job produced which outputs

**After this plan:**
- Full pipeline runs now populate Script.job_id and Video.job_id foreign keys
- Job records can query their associated Script and Video via relationships
- Complete data lineage from orchestrator through all stages
- Enables future features: job progress tracking, output retrieval, checkpoint resume by Job ID

## Key Files Modified

| File | Lines Changed | Purpose |
|------|---------------|---------|
| app/pipeline.py | 1 | Pass job_id to generate_content_task |
| app/tasks.py | 7 | Thread job_id through content and composition tasks |
| app/services/script_generator.py | 3 | Accept job_id and populate Script.job_id |
| .planning/REQUIREMENTS.md | 1 | Update ORCH-01 pipeline stage count |

## Technical Notes

- Used `Optional[int] = None` for job_id parameters to maintain backward compatibility
- No changes to models.py required (foreign key columns already existed from Phase 1)
- Log messages updated to include job_id for better traceability
- All changes follow existing asyncio.run() pattern for Celery tasks

## Next Steps

This plan closes the data lineage gap. Future plans can now:
- Query Job.scripts relationship to find all scripts generated by a job
- Query Job.videos relationship to find all videos generated by a job
- Build job-centric APIs (GET /jobs/{id}/outputs)
- Implement smart checkpoint resume based on job_id foreign keys

## Self-Check: PASSED

Verified all claims:

**Created files:** None (as expected)

**Modified files exist:**
```
FOUND: app/pipeline.py
FOUND: app/tasks.py
FOUND: app/services/script_generator.py
FOUND: .planning/REQUIREMENTS.md
```

**Commits exist:**
```
FOUND: 1d95a79 (Task 1 - feat(07-01): thread job_id through pipeline for data lineage)
FOUND: a46e2c5 (Task 2 - docs(07-01): update ORCH-01 to reflect 5-stage pipeline)
```

All files and commits verified successfully.
