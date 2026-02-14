---
phase: 03-content-generation
plan: 01
subsystem: api
tags: [pydantic, yaml, alembic, sqlalchemy, config-reader, schemas]

# Dependency graph
requires:
  - phase: 02-trend-intelligence
    provides: TrendReport model and Claude structured output pattern
provides:
  - ThemeConfig reader from sample-data.yml with Pydantic validation
  - ContentReference reader for product/topic talking points
  - VideoProductionPlanCreate schema with 11 required fields for Claude tool-use
  - Script model extended with Phase 3 content generation fields
  - Alembic migration 003 adding content generation schema
affects: [03-02-script-generator, 03-03-content-pipeline]

# Tech tracking
tech-stack:
  added: [pyyaml]
  patterns: [YAML config with Pydantic validation, Theme config snapshot in JSON column]

key-files:
  created:
    - app/services/config_reader.py
    - alembic/versions/003_content_generation_schema.py
  modified:
    - app/config.py
    - app/schemas.py
    - app/models.py
    - config/sample-data.yml

key-decisions:
  - "Store theme_config as JSON snapshot in Script model for reproducibility"
  - "Add trend_report_id FK to Script model to link generated scripts with trend analysis"
  - "Extended sample-data.yml with product_name, tagline, target_audience, tone for script prompts"
  - "Added second content reference for testing variety in content pipeline"

patterns-established:
  - "Config reader pattern: Optional path parameter with settings.local_config_path default"
  - "Pydantic validation pattern: Load YAML → validate with model → return typed object"
  - "Provider type pattern: video_provider_type and tts_provider_type with mock/real options"

# Metrics
duration: 3min
completed: 2026-02-13
---

# Phase 03 Plan 01: Config Reader & Production Plan Schemas Summary

**Theme config reader with YAML validation and complete VideoProductionPlan schema with 11 fields for Claude structured outputs**

## Performance

- **Duration:** 3 minutes
- **Started:** 2026-02-13T22:58:22Z
- **Completed:** 2026-02-13T23:01:29Z
- **Tasks:** 2
- **Files modified:** 5
- **Files created:** 2

## Accomplishments

- ThemeConfig and ContentReference Pydantic models load and validate from sample-data.yml
- VideoProductionPlanCreate schema with all 11 required fields (video_prompt, duration_target, aspect_ratio, scenes, voiceover_script, hook_text, cta_text, text_overlays, hashtags, title, description)
- Script model extended with duration_target, aspect_ratio, hook_text, cta_text, theme_config (JSON snapshot), and trend_report_id FK
- Alembic migration 003 successfully adds content generation columns to scripts table
- Settings extended with openai_api_key, video_provider_type, tts_provider_type, output_dir for Phase 3 providers

## Task Commits

Each task was committed atomically:

1. **Task 1: Theme config reader service with local YAML fallback** - `d2f7433` (feat)
   - Created app/services/config_reader.py with ThemeConfig and ContentReference models
   - Extended sample-data.yml with product_name, tagline, target_audience, tone
   - Added second content reference entry for testing
   - Extended app/config.py with Phase 3 provider settings

2. **Task 2: Production Plan Pydantic schemas and Alembic migration** - `87e74bc` (feat)
   - Added SceneSchema, TextOverlaySchema, VideoProductionPlanCreate to app/schemas.py
   - Extended Script model with 6 new columns
   - Created migration 003 with foreign key to trend_reports

## Files Created/Modified

Created:
- `/Users/naokitsk/Documents/short-video-generator/app/services/config_reader.py` - Reads theme config and content references from YAML with Pydantic validation
- `/Users/naokitsk/Documents/short-video-generator/alembic/versions/003_content_generation_schema.py` - Migration adding content generation fields to scripts table

Modified:
- `/Users/naokitsk/Documents/short-video-generator/app/config.py` - Added openai_api_key, video_provider_type, tts_provider_type, output_dir settings
- `/Users/naokitsk/Documents/short-video-generator/app/schemas.py` - Added SceneSchema, TextOverlaySchema, VideoProductionPlanCreate, VideoProductionPlanResponse
- `/Users/naokitsk/Documents/short-video-generator/app/models.py` - Extended Script model with duration_target, aspect_ratio, hook_text, cta_text, theme_config, trend_report_id
- `/Users/naokitsk/Documents/short-video-generator/config/sample-data.yml` - Added product_name, tagline, target_audience, tone; added second content reference

## Decisions Made

1. **Theme config snapshot in Script model** - Store theme_config as JSON column to preserve exact configuration used for each script generation (enables reproducibility and debugging)

2. **Link scripts to trend analysis** - Added trend_report_id FK to Script model so generated scripts can reference the trend analysis that informed them

3. **Extended sample data for script prompts** - Added product_name, tagline, target_audience, tone fields to theme config to provide richer context for Claude script generation in Plan 02

4. **Provider type abstraction** - Added video_provider_type and tts_provider_type settings to enable swapping between mock and real providers (SVD/Veo for video, OpenAI/ElevenLabs for TTS)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None - all tasks completed smoothly. Config reader loaded YAML successfully, schemas validated correctly, migration ran without errors.

## User Setup Required

None - no external service configuration required. This plan uses local YAML config file and database schema changes only.

## Next Phase Readiness

**Ready for Plan 02 (Script Generator):**
- ThemeConfig available via read_theme_config() with product details
- ContentReference list available via read_content_references() with talking points
- VideoProductionPlanCreate schema ready for Claude tool-use pattern
- Script model has all required columns for storing generated production plans
- Settings have provider type configuration for TTS and video generation

**No blockers.** Script generator can now:
1. Load theme config with read_theme_config()
2. Load content references with read_content_references()
3. Call Claude with VideoProductionPlanCreate as tool schema
4. Store result in Script model with all Phase 3 fields

## Self-Check

Verifying all claims:

### Files Created
- app/services/config_reader.py: FOUND
- alembic/versions/003_content_generation_schema.py: FOUND

### Files Modified
- app/config.py: FOUND (openai_api_key, video_provider_type, tts_provider_type, output_dir present)
- app/schemas.py: FOUND (VideoProductionPlanCreate with 11 fields present)
- app/models.py: FOUND (Script model has 6 new columns)
- config/sample-data.yml: FOUND (product_name, tagline, target_audience, tone present)

### Commits
- d2f7433: FOUND (feat(03-01): add theme config reader with local YAML fallback)
- 87e74bc: FOUND (feat(03-01): add production plan schemas and migration)

### Runtime Verification
- read_theme_config() returns ThemeConfig with theme="Product Demo": PASSED
- read_content_references() returns 2 ContentReference objects: PASSED
- VideoProductionPlanCreate schema has 11 properties: PASSED
- Script model has duration_target, aspect_ratio, hook_text, cta_text, theme_config, trend_report_id: PASSED
- Alembic migration 003 runs successfully: PASSED

## Self-Check: PASSED

All files created, all commits present, all verifications successful.

---
*Phase: 03-content-generation*
*Completed: 2026-02-13*
