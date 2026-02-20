---
phase: 21-per-stage-celery-tasks
plan: "02"
subsystem: ugc-pipeline
tags: [fastapi, router, celery, state-machine, ugc-pipeline]
dependency_graph:
  requires: [21-01]
  provides: [ugc-http-endpoints]
  affects: [app/ugc_router.py, app/worker.py, app/main.py]
tech_stack:
  added: []
  patterns: [form-upload, lazy-import-tasks, state-machine-advance-map]
key_files:
  created:
    - app/ugc_router.py
  modified:
    - app/worker.py
    - app/main.py
decisions:
  - "Lazy import app.ugc_tasks inside endpoints to avoid circular import at module load"
  - "_STAGE_ADVANCE_MAP dict maps each review status to (approve_event, next_task_name) — single source of truth for advance logic"
  - "approve_final maps to next_task_name=None — no task enqueued, job transitions to approved"
metrics:
  duration: "~2 min"
  completed: "2026-02-20"
  tasks: 2
  files: 3
---

# Phase 21 Plan 02: UGC Router and Worker Wiring Summary

**One-liner:** FastAPI UGC router with form-upload submit, state-machine advance, and status endpoints — wired into Celery worker and main app.

## Tasks Completed

| # | Name | Commit | Files |
|---|------|--------|-------|
| 1 | Create UGC router with submit, advance, and status endpoints | 8c65e22 | app/ugc_router.py (new) |
| 2 | Register ugc_tasks in worker and mount ugc_router in main | c26e38a | app/worker.py, app/main.py |

## What Was Built

**Task 1: app/ugc_router.py (179 lines)**

Three endpoints on `APIRouter(prefix="/ugc", tags=["ugc"])`:

| Endpoint | Action |
|----------|--------|
| `POST /ugc/jobs` | Accept form fields + file uploads, create UGCJob, transition `pending->running`, enqueue `ugc_stage_1_analyze` |
| `POST /ugc/jobs/{id}/advance` | Lookup job, validate review state via `_STAGE_ADVANCE_MAP`, send approve event, enqueue next task |
| `GET /ugc/jobs/{id}` | Return all stage output columns via `jsonable_encoder` |

`_STAGE_ADVANCE_MAP` covers all 5 review states:
- `stage_analysis_review` → `approve_analysis` → `ugc_stage_2_script`
- `stage_script_review` → `approve_script` → `ugc_stage_3_aroll`
- `stage_aroll_review` → `approve_aroll` → `ugc_stage_4_broll`
- `stage_broll_review` → `approve_broll` → `ugc_stage_5_compose`
- `stage_composition_review` → `approve_final` → None (sets `approved_at`)

**Task 2: worker.py + main.py**

- `app/worker.py`: Added `import app.ugc_tasks` after `import app.pipeline` — Celery worker now autodiscovers all 5 UGC tasks on startup.
- `app/main.py`: Added `from app import ugc_router` import and `app.include_router(ugc_router.router)` after `routes.router`.

## Deviations from Plan

**[Rule 3 - Blocking] python-multipart not installed in venv**
- Found during: Task 1 verification
- Issue: `python-multipart` is in `requirements.txt` but not installed, causing `RuntimeError` on import of Form-based endpoints
- Fix: `pip install python-multipart` in venv (package was already declared in requirements)
- Files modified: None (environment-only fix)
- Commit: N/A — dev environment fix only

## Self-Check

Files created/modified:
- `app/ugc_router.py` — created, 179 lines
- `app/worker.py` — modified (1 line added)
- `app/main.py` — modified (2 lines added)

Commits:
- `8c65e22` feat(21-02): create UGC router with submit, advance, and status endpoints
- `c26e38a` feat(21-02): register ugc_tasks in worker and mount ugc_router in main

## Self-Check: PASSED
