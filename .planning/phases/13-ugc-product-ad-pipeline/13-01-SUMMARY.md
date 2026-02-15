---
phase: 13-ugc-product-ad-pipeline
plan: 01
subsystem: ugc-pipeline-core
tags: [schemas, llm-services, product-analysis, script-generation]

dependency_graph:
  requires: [phase-12-llm-provider]
  provides: [ugc-schemas, product-analyzer-service, script-engine-service]
  affects: [phase-13-plan-02-imagen-service, phase-13-plan-03-ugc-orchestrator]

tech_stack:
  added: []
  patterns: [two-call-llm-pattern, category-aware-prompts, nested-schema-mocking]

key_files:
  created:
    - app/services/ugc_pipeline/__init__.py
    - app/services/ugc_pipeline/product_analyzer.py
    - app/services/ugc_pipeline/script_engine.py
  modified:
    - app/schemas.py
    - app/services/llm_provider/mock.py

decisions:
  - decision: Use two-call LLM pattern (generate_text + generate_structured) for script generation
    rationale: Follows established pattern from script_generator.py, separates freeform creativity (master script) from structured breakdown (A-Roll/B-Roll)
    alternatives: [single-call-with-complex-schema]
    chosen: two-call-pattern
  - decision: Category-aware prompts via CATEGORY_PROMPTS dict lookup
    rationale: Adapts to any product category via prompt engineering, not code branches. Easy to extend with new categories.
    alternatives: [hardcoded-category-logic, single-generic-prompt]
    chosen: category-prompt-dict
  - decision: A-Roll scenes constrained to 4-8 seconds (Veo limit), B-Roll shots default 5 seconds
    rationale: Veo 3.1 has 8-second max per generation. 4s minimum ensures meaningful content. B-Roll 5s is optimal for product showcases.
    alternatives: [flexible-duration, longer-clips-with-splitting]
    chosen: veo-duration-constraints

metrics:
  duration_seconds: 284
  tasks_completed: 2
  files_created: 3
  files_modified: 2
  commits: 3
  completed_date: "2026-02-15"
---

# Phase 13 Plan 01: UGC Pipeline Schemas & Services Summary

**One-liner:** Pydantic schemas for UGC product ad pipeline + LLM-powered product analysis and Hook-Problem-Proof-CTA script generation with A-Roll/B-Roll breakdown.

## Tasks Completed

### Task 1: Add UGC pipeline Pydantic schemas to app/schemas.py
- **Status:** ✅ Complete
- **Commit:** 1a86a1c
- **Duration:** ~2 minutes

Added 7 Pydantic v2 schemas to app/schemas.py:

1. **ProductInput**: Product name, description, URL, target duration, style preference
2. **ProductAnalysis**: Category, key features, target audience, UGC style, emotional tone, visual keywords
3. **MasterScript**: Hook-Problem-Proof-CTA structure with full script and total duration
4. **ArollScene**: UGC creator talking scenes (4-8s Veo constraint) with visual prompt, voice direction, script text
5. **BrollShot**: Product close-up/lifestyle shots (5s default) with image prompt, animation prompt, overlay timing
6. **AdBreakdown**: Complete breakdown with master script, A-Roll scenes, B-Roll shots, total duration
7. **UGCAdResponse**: API response schema for ad generation requests

All schemas validate correctly with Pydantic v2. ArollScene enforces ge=4, le=8 duration constraint (Veo limit).

### Task 2: Create product_analyzer.py and script_engine.py services
- **Status:** ✅ Complete
- **Commits:** bc1d01d (mock fix), c97e16f (services)
- **Duration:** ~2 minutes

**app/services/ugc_pipeline/product_analyzer.py:**
- `analyze_product()` function using `LLMProvider.generate_structured()` with ProductAnalysis schema
- Temperature: 0.7 for balanced creativity
- System prompt: "You are a UGC marketing strategist analyzing products for viral ad campaigns."
- Logs category and ugc_style results

**app/services/ugc_pipeline/script_engine.py:**
- `generate_ugc_script()` function using two-call pattern:
  - **Call 1**: `llm.generate_text()` — Generate Hook-Problem-Proof-CTA master script with category-specific guidance
  - **Call 2**: `llm.generate_structured()` with AdBreakdown schema — Break script into A-Roll/B-Roll
- **CATEGORY_PROMPTS** dict with 6 entries: cosmetics, tech, food, fashion, saas, default
- Logs scene count, shot count, total duration

**app/services/ugc_pipeline/__init__.py:**
- Exports `analyze_product` and `generate_ugc_script`

Both services work seamlessly with MockLLMProvider (USE_MOCK_DATA=true default).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed MockLLMProvider nested Pydantic model handling**
- **Found during:** Task 2 verification
- **Issue:** MockLLMProvider failed when generating schemas with nested BaseModel fields (e.g., AdBreakdown.master_script: MasterScript). It returned empty string for nested models, causing Pydantic validation error: "Input should be a valid dictionary or instance of MasterScript [type=model_type, input_value='', input_type=str]"
- **Fix:** Updated MockLLMProvider.generate_structured() to detect nested models via $ref in JSON schema, extract Pydantic class from schema.model_fields[field_name].annotation, and recursively call generate_structured() for nested models
- **Files modified:** app/services/llm_provider/mock.py
- **Commit:** bc1d01d

This was a blocking issue (Rule 3) that also constituted a bug (Rule 1) — the mock provider didn't work correctly with nested schemas, which are common in complex data structures. The fix makes MockLLMProvider universally compatible with any Pydantic schema structure.

## Verification Results

✅ **All 7 UGC schemas import successfully**
- ProductInput, ProductAnalysis, MasterScript, ArollScene, BrollShot, AdBreakdown, UGCAdResponse

✅ **analyze_product() returns valid ProductAnalysis via MockLLMProvider**
- Tested with 'Test Serum' product, returns ProductAnalysis instance with correct field types

✅ **generate_ugc_script() returns valid AdBreakdown via MockLLMProvider**
- Tested with tech product, returns AdBreakdown with nested MasterScript, aroll_scenes, broll_shots

✅ **No list[str] syntax (Python 3.9 compatible)**
- All services use `from typing import List, Optional` pattern

✅ **CATEGORY_PROMPTS dict has 6 entries**
- cosmetics, tech, food, fashion, saas, default

## Key Implementation Details

### Two-Call LLM Pattern (Established in Phase 3, Phase 12)
```python
# Call 1: Generate master script text with category guidance
master_script_text = llm.generate_text(
    prompt=master_script_prompt,
    system_prompt="You are a viral UGC ad script writer...",
    temperature=0.8
)

# Call 2: Generate structured breakdown with A-Roll/B-Roll
breakdown = llm.generate_structured(
    prompt=breakdown_prompt,  # Includes master_script_text
    schema=AdBreakdown,
    temperature=0.7
)
```

### Category-Aware Prompt Engineering
```python
CATEGORY_PROMPTS = {
    "cosmetics": "Focus on beauty transformation, before/after...",
    "tech": "Focus on problem scenario, feature demo...",
    "food": "Focus on taste reaction, cooking process...",
    "fashion": "Focus on style transformation, try-on...",
    "saas": "Focus on productivity pain, ROI stats...",
    "default": "Follow Hook-Problem-Proof-CTA structure..."
}

category_guidance = CATEGORY_PROMPTS.get(
    analysis.category.lower(),
    CATEGORY_PROMPTS["default"]
)
```

### Veo Duration Constraints
- **A-Roll scenes:** 4-8 seconds (Veo 3.1 max 8s per generation, 4s minimum for meaningful content)
- **B-Roll shots:** 5 seconds (optimal for product showcases, overlaid during A-Roll)
- **Pydantic validation:** `duration_seconds: int = Field(ge=4, le=8)` enforces constraint

## Links to Downstream Plans

- **Plan 02 (Imagen B-Roll):** Will use BrollShot.image_prompt for Imagen generation
- **Plan 03 (UGC Orchestrator):** Will chain analyze_product() → generate_ugc_script() → Imagen → Veo → FFmpeg composition

## Self-Check

**Created files:**
```bash
✓ app/services/ugc_pipeline/__init__.py exists
✓ app/services/ugc_pipeline/product_analyzer.py exists
✓ app/services/ugc_pipeline/script_engine.py exists
```

**Modified files:**
```bash
✓ app/schemas.py modified (7 new schemas)
✓ app/services/llm_provider/mock.py modified (nested model handling)
```

**Commits:**
```bash
✓ 1a86a1c exists: feat(13-01): add UGC pipeline Pydantic schemas
✓ bc1d01d exists: fix(13-01): handle nested Pydantic models in MockLLMProvider
✓ c97e16f exists: feat(13-01): create UGC pipeline services
```

## Self-Check: PASSED

All files created, all commits exist, all verifications passed.
