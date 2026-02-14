---
phase: 05-review-output
plan: 01
subsystem: video-composition
tags: [review-workflow, cost-tracking, approval-api, file-management]
dependency_graph:
  requires: [04-01, 04-02]
  provides: [review-workflow, cost-tracking, approval-endpoints]
  affects: [video-compositor, api]
tech_stack:
  added: []
  patterns: [file-move-operations, status-validation, generation-metadata-logging]
key_files:
  created: []
  modified:
    - app/config.py
    - app/tasks.py
    - app/api/routes.py
decisions:
  - Changed composition_output_dir from output/final to output/review for review workflow
  - Mock providers return 0.0 cost, real providers will populate cost_data when swapped in
  - Generation metadata stored in Video.extra_data includes gen_id, timestamp, theme, trend_pattern, prompts, model, cost, path, status
  - File move operations handle missing files gracefully with warnings in API response
metrics:
  duration_seconds: 152
  tasks_completed: 2
  files_modified: 3
  commits: 2
  completed_at: "2026-02-14T10:20:18Z"
---

# Phase 05 Plan 01: Review Workflow with Cost Tracking Summary

**One-liner:** Review workflow with cost tracking and approve/reject endpoints — videos land in output/review/, track per-video costs and generation metadata, support approval/rejection with file moves.

## What Was Built

Implemented human review workflow for generated videos with comprehensive cost tracking and generation metadata logging:

1. **Review Directory Structure** (REVIEW-01)
   - Changed `composition_output_dir` from `output/final` to `output/review`
   - Added `approved_output_dir` = `output/approved`
   - Added `rejected_output_dir` = `output/rejected`
   - Videos now land in review/ after composition, awaiting approval/rejection

2. **Cost Tracking** (REVIEW-05)
   - Added `cost_data` parameter to both `generate_content_task` and `compose_video_task`
   - `cost_data` dict contains: `claude_cost`, `tts_cost`, `video_gen_cost`
   - Total cost calculated as sum of all cost components
   - Stored in `Video.cost_usd` field
   - Mock providers return 0.0 cost (ready for real provider integration)

3. **Generation Metadata Logging** (REVIEW-02)
   - Build comprehensive `generation_metadata` dict in `compose_video_task`
   - Fields: `gen_id` (UUID), `timestamp`, `theme`, `trend_pattern` (trend_report_id), `prompts` (video_prompt + voiceover_script), `model` (script_model, video_model, tts_model), `cost_usd`, `output_path`, `status`
   - Stored in `Video.extra_data` JSON field for queryability
   - Provides full audit trail for each generated video

4. **Approve/Reject API Endpoints** (REVIEW-03, REVIEW-04)
   - `POST /videos/{video_id}/approve`: moves files from review/ to approved/, sets status="approved", sets approved_at timestamp
   - `POST /videos/{video_id}/reject`: moves files from review/ to rejected/, sets status="rejected"
   - Both validate status (only "generated" videos can be approved/rejected)
   - Both move video file and thumbnail file
   - Both update `extra_data.status` for consistency
   - File-not-found errors handled gracefully with warnings array in response

## Tasks Completed

| Task | Description | Commit | Files Modified |
|------|-------------|--------|----------------|
| 1 | Update composition output to review directory with cost tracking and generation logging | f58959a | app/config.py, app/tasks.py |
| 2 | Add approve and reject REST API endpoints with file move operations | b2f764d | app/api/routes.py |

## Deviations from Plan

None — plan executed exactly as written.

## Technical Details

### Config Changes
- `composition_output_dir`: `"output/final"` → `"output/review"`
- New: `approved_output_dir = "output/approved"`
- New: `rejected_output_dir = "output/rejected"`

### Task Signature Updates
**Before:**
```python
def compose_video_task(self, script_id: int, video_path: str, audio_path: str)
```

**After:**
```python
def compose_video_task(self, script_id: int, video_path: str, audio_path: str, cost_data: dict = None)
```

### Generation Metadata Structure
```json
{
  "gen_id": "a1b2c3d4e5f6...",
  "timestamp": "2026-02-14T10:15:30Z",
  "theme": "AI-powered productivity",
  "trend_pattern": 42,
  "prompts": {
    "video_prompt": "...",
    "voiceover_script": "..."
  },
  "model": {
    "script_model": "claude",
    "video_model": "mock",
    "tts_model": "mock"
  },
  "cost_usd": 0.0,
  "output_path": "output/review/video_20260214_101530.mp4",
  "status": "generated"
}
```

### API Response Examples

**Approve Success:**
```json
{
  "id": 5,
  "status": "approved",
  "file_path": "output/approved/video_20260214_101530.mp4",
  "thumbnail_path": "output/approved/video_20260214_101530_thumb.jpg",
  "cost_usd": 0.0,
  "approved_at": "2026-02-14T10:18:45Z",
  "message": "Video approved and moved to output/approved/"
}
```

**Reject with Warning:**
```json
{
  "id": 6,
  "status": "rejected",
  "file_path": "output/rejected/video_20260214_101545.mp4",
  "thumbnail_path": "output/rejected/video_20260214_101545_thumb.jpg",
  "cost_usd": 0.0,
  "message": "Video rejected and moved to output/rejected/",
  "warnings": ["Thumbnail file not found: output/review/video_20260214_101545_thumb.jpg"]
}
```

### Status Validation
Both approve and reject endpoints validate that `video.status == "generated"` before operating. Invalid status transitions return 400:
```json
{
  "detail": "Cannot approve video with status 'approved'. Only 'generated' videos can be approved."
}
```

## Testing Notes

1. **Cost Tracking**: Currently returns 0.0 for all mock providers. When real providers are swapped in (OpenAI TTS, Stable Diffusion, Claude API), they should populate their respective cost fields in cost_data dict.

2. **File Operations**: Both approve and reject endpoints create target directories if they don't exist (`mkdir(parents=True, exist_ok=True)`).

3. **Graceful Degradation**: If video/thumbnail files are missing, endpoints still update the database status and return warnings in response array.

4. **Metadata Consistency**: `extra_data.status` is updated to match `Video.status` when approving/rejecting, maintaining consistency in generation logs.

## Verification Results

All verification checks passed:
- ✅ `composition_output_dir` = "output/review"
- ✅ `approved_output_dir` = "output/approved"
- ✅ `rejected_output_dir` = "output/rejected"
- ✅ `compose_video_task` saves videos to output/review/
- ✅ `Video.cost_usd` populated with total cost
- ✅ `Video.extra_data` contains full generation metadata
- ✅ `POST /videos/{id}/approve` endpoint registered
- ✅ `POST /videos/{id}/reject` endpoint registered
- ✅ All imports resolve without errors

## Self-Check: PASSED

**Created files exist:**
✅ No new files created (only modifications)

**Modified files exist:**
✅ app/config.py (modified)
✅ app/tasks.py (modified)
✅ app/api/routes.py (modified)

**Commits exist:**
✅ f58959a: feat(05-01): add review workflow with cost tracking and generation logging
✅ b2f764d: feat(05-01): add approve and reject REST API endpoints

## Next Steps

Phase 5 Plan 01 complete. Ready for Phase 5 Plan 02 (if any) or Phase 6.

**Suggested next actions:**
1. Test review workflow end-to-end: generate content → compose → approve/reject
2. Verify output directories are created correctly on first use
3. Validate cost tracking when real providers are integrated
4. Consider adding GET endpoint to list videos by status (generated/approved/rejected)
