---
phase: 20-ugcjob-data-model
plan: "01"
subsystem: data-model
tags: [ugcjob, postgresql, alembic, state-machine, python-statemachine]
dependency_graph:
  requires: []
  provides: [UGCJob model, migration-006, UGCJobStateMachine]
  affects: [phases 21-25 — all pipeline stages read/write UGCJob rows]
tech_stack:
  added: [python-statemachine==2.6.0]
  patterns: [SQLAlchemy declarative model with typed per-stage columns, state machine as guard layer only]
key_files:
  created:
    - alembic/versions/006_ugcjob_schema.py
    - app/state_machines/__init__.py
    - app/state_machines/ugc_job.py
  modified:
    - app/models.py
    - requirements.txt
key_decisions:
  - "python-statemachine is a guard layer only — DB column is source of truth. Instantiate with start_value=job.status for existing rows."
  - "use_mock stored per UGCJob row, not read from get_settings() singleton, so each job can toggle independently."
  - "Migration 006 uses down_revision=039d14368a2d (not '005') matching migration 005's actual revision ID."
metrics:
  duration: "~3 minutes"
  completed: "2026-02-20"
  tasks_completed: 2
  files_changed: 5
---

# Phase 20 Plan 01: UGCJob Data Model Summary

UGCJob SQLAlchemy model with 28 typed per-stage columns, Alembic migration 006, and python-statemachine 2.6.0 guard layer for all status transitions.

## What Was Built

### UGCJob model (app/models.py)
28-column model covering the full UGC pipeline:
- Input: product_name, description, product_url, product_image_paths, target_duration, style_preference, use_mock
- State: status (String 50, default pending), error_message
- Stage 1 Analysis: analysis_category, analysis_ugc_style, analysis_emotional_tone, analysis_key_features, analysis_visual_keywords, analysis_target_audience
- Stage 2 Hero Image: hero_image_path
- Stage 3 Script: master_script, aroll_scenes, broll_shots
- Stage 4 A-Roll: aroll_paths
- Stage 5 B-Roll: broll_paths
- Stage 6 Composition: final_video_path, cost_usd
- Candidate: candidate_video_path
- Timestamps: created_at, updated_at, approved_at

### Migration 006 (alembic/versions/006_ugcjob_schema.py)
Hand-crafted migration, revision=006, down_revision=039d14368a2d. Creates ugc_jobs table with all columns. Applied cleanly to running Docker Postgres instance.

### UGCJobStateMachine (app/state_machines/ugc_job.py)
9 states, 12 transitions. `fail` reachable from all 7 non-final states via `|` OR syntax. Model binding writes job.status on every transition. Invalid transitions raise `TransitionNotAllowed`.

## Verification Results

- `UGCJob.__tablename__` = `ugc_jobs` — OK
- All 28 columns present in model and migration — OK
- `alembic current` shows revision 006 — OK
- `statemachine.__version__` = 2.6.0 — OK
- Full happy path (pending -> approved) — OK
- fail from all 7 non-final states — OK
- Invalid transition (pending -> approve_final) raises TransitionNotAllowed — OK

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Docker container lacked asyncpg and python-statemachine**
- **Found during:** Task 1 migration verification
- **Issue:** The venv and Docker container didn't have asyncpg or python-statemachine installed
- **Fix:** Installed asyncpg in venv; installed python-statemachine in Docker container via `docker exec pip install`; copied migration file via `docker cp` since only `app/` is bind-mounted
- **Files modified:** None (runtime installs only)
- **Commit:** N/A (runtime environment setup)

## Commits

| Hash | Task | Message |
|------|------|---------|
| ddb0590 | Task 1 | feat(20-01): add UGCJob model, migration 006, python-statemachine dependency |
| 21d096f | Task 2 | feat(20-01): add UGCJobStateMachine guard layer |

## Self-Check: PASSED
