---
phase: 21-per-stage-celery-tasks
plan: "01"
subsystem: ugc-pipeline
tags: [celery, use-mock, state-machine, ugc-pipeline]
dependency_graph:
  requires: [20-01]
  provides: [ugc-stage-tasks]
  affects: [app/ugc_tasks.py, ugc-pipeline-services]
tech_stack:
  added: []
  patterns: [per-stage-celery, nullpool-sessions, direct-provider-instantiation]
key_files:
  created:
    - app/ugc_tasks.py
  modified:
    - app/services/ugc_pipeline/product_analyzer.py
    - app/services/ugc_pipeline/script_engine.py
    - app/services/ugc_pipeline/asset_generator.py
decisions:
  - "use_mock as explicit function parameter, not read from settings singleton — allows per-job mock toggle"
  - "Stages 1+2 (analysis + hero image) combined into ugc_stage_1_analyze — state machine has no intermediate stage_hero_image_review state"
  - "Direct provider instantiation inside service functions — removes dependency on global factory (get_llm_provider, get_image_provider)"
metrics:
  duration: "~4 min"
  completed: "2026-02-20"
  tasks: 2
  files: 4
---

# Phase 21 Plan 01: Per-Stage Celery Tasks Summary

**One-liner:** Five per-stage Celery tasks using NullPool DB sessions, use_mock threading through all UGC service functions, and state machine transitions to review states.

## Tasks Completed

| # | Name | Commit | Files |
|---|------|--------|-------|
| 1 | Thread use_mock through UGC service functions | 6097c93 | product_analyzer.py, script_engine.py, asset_generator.py |
| 2 | Create five per-stage Celery tasks | ec88d5c | app/ugc_tasks.py (new) |

## What Was Built

**Task 1: use_mock threading**

Added `use_mock: bool = False` to all five UGC service functions. Replaced global factory calls with direct provider instantiation:
- `analyze_product()` and `generate_ugc_script()` — instantiate `MockLLMProvider` or `GeminiLLMProvider` based on flag
- `generate_hero_image()` and `generate_broll_assets()` — instantiate `MockImageProvider` or `GoogleImagenProvider` based on flag
- `generate_aroll_assets()` — passes `use_mock` to `_get_veo_or_mock(use_mock=use_mock)`
- `_get_veo_or_mock()` updated to accept `use_mock` param instead of reading `settings.use_mock_data`

**Task 2: Five per-stage Celery tasks**

`app/ugc_tasks.py` with five registered tasks:

| Task | Stage | Service Call | State Transition |
|------|-------|-------------|-----------------|
| `ugc_stage_1_analyze` | Analysis + Hero Image | `analyze_product()` + `generate_hero_image()` | `running -> stage_analysis_review` |
| `ugc_stage_2_script` | Script | `generate_ugc_script()` | `running -> stage_script_review` |
| `ugc_stage_3_aroll` | A-Roll | `generate_aroll_assets()` | `running -> stage_aroll_review` |
| `ugc_stage_4_broll` | B-Roll | `generate_broll_assets()` | `running -> stage_broll_review` |
| `ugc_stage_5_compose` | Composition | `compose_ugc_ad()` | `running -> stage_composition_review` |

All tasks:
- Use `get_task_session_factory()` with NullPool (not module-level engine)
- Pass `use_mock=job.use_mock` to all service calls
- On error: transition to `failed`, write `error_message`, re-raise
- Use lazy imports inside async helpers to avoid circular imports

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check

Files created/modified:
- `app/ugc_tasks.py` — created, 396 lines
- `app/services/ugc_pipeline/product_analyzer.py` — modified
- `app/services/ugc_pipeline/script_engine.py` — modified
- `app/services/ugc_pipeline/asset_generator.py` — modified

Commits:
- `6097c93` feat(21-01): thread use_mock through UGC service functions
- `ec88d5c` feat(21-01): create five per-stage Celery tasks in app/ugc_tasks.py

## Self-Check: PASSED
