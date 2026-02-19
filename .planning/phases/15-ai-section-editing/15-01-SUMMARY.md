---
phase: 15-ai-section-editing
plan: "01"
subsystem: landing-page
tags: [pydantic, jinja2, regex, section-editor, landing-page, copy-generation]

requires:
  - phase: 14-landing-page-generation
    provides: render_section(), optimize_html(), validate_html(), LLM provider, section templates with data-section attributes

provides:
  - edit_section() entry point for AI-powered single-section editing
  - 8 section-scoped Pydantic schemas (HeroEditCopy through FooterEditCopy)
  - list_sections() for data-section discovery from HTML
  - get_editable_sections() for listing valid edit targets
  - Regex-based section replacement with CSS re-consolidation

affects:
  - 15-02 (CLI for section editing will import edit_section, list_sections, get_editable_sections)
  - any future web UI for section editing

tech-stack:
  added: []
  patterns:
    - "Section-scoped Pydantic schemas: one small schema per section for generate_structured() vs. full LandingPageCopy"
    - "Regex section replacement: data-section attribute as targeting anchor, re.DOTALL for multi-line blocks"
    - "Re-optimize after replacement: optimize_html() consolidates <style> tags back into <head>"

key-files:
  created:
    - app/services/landing_page/section_editor.py
  modified:
    - app/schemas.py

key-decisions:
  - "Section-scoped schemas (8 small schemas) instead of full LandingPageCopy for targeted edits — smaller prompts, more accurate output"
  - "HTML file as source of truth — extract context from HTML via regex, no JSON sidecar state"
  - "gallery excluded from EDITABLE_SECTIONS — image paths not copy, clear error returned"
  - "Always call optimize_html() after replacement — prevents CSS duplication across multiple edits"
  - "video_url and hero_image set to None in hero context build — copy-only editing MVP, media preserved via section regex replacement"

patterns-established:
  - "edit_section() returns structured dict: {success, html_path, section, warnings} or {success, error}"
  - "_generate_section_copy() uses use_mock=True for dev; mirrors copy_generator.py get_mock_copy() pattern"

duration: 1min
completed: 2026-02-19
---

# Phase 15 Plan 01: AI Section Editing Core Summary

**section_editor.py with edit_section() that surgically replaces LP sections via AI-generated copy, Jinja2 re-render, and regex replacement, plus 8 section-scoped Pydantic schemas in schemas.py**

## Performance

- **Duration:** 1 min
- **Started:** 2026-02-19T20:38:25Z
- **Completed:** 2026-02-19T20:39:57Z
- **Tasks:** 1
- **Files modified:** 2

## Accomplishments

- Built `edit_section()` core loop: read HTML → validate → AI generate → re-render → regex replace → optimize → write back
- Added 8 section-scoped schemas to `schemas.py` for focused AI output (HeroEditCopy through FooterEditCopy)
- `list_sections()` extracts all `data-section` values from HTML for CLI discovery
- Gallery and missing sections return structured error dicts, not exceptions
- Mock mode works without any LLM API calls

## Task Commits

1. **Task 1: Add section-scoped Pydantic schemas and build section_editor.py** - `694a742` (feat)

**Plan metadata:** (pending)

## Files Created/Modified

- `app/services/landing_page/section_editor.py` - Core section editing module: edit_section(), list_sections(), get_editable_sections(), _replace_section(), _extract_section_context(), _generate_section_copy(), _build_template_context()
- `app/schemas.py` - Added 8 section-scoped edit schemas after LandingPageResult

## Decisions Made

- Section-scoped schemas (one per section) instead of full `LandingPageCopy` — smaller prompts, accurate edits scoped to only the fields that section uses
- HTML file is source of truth — no JSON sidecar, extract context from HTML via regex when needed
- `gallery` excluded from `EDITABLE_SECTIONS` — returns clear error message since gallery shows image paths not copy
- Always call `optimize_html()` after section replacement — prevents CSS duplication on repeated edits
- `video_url`/`hero_image` set to `None` in hero `_build_template_context()` — copy-only MVP; the section regex replaces the full block so media is not preserved between edits

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None — all Phase 14 infrastructure (render_section, optimize_html, validate_html, get_llm_provider) worked as expected. No new dependencies needed.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `edit_section()`, `list_sections()`, `get_editable_sections()` ready for CLI in Plan 02
- All 8 section types tested in mock mode
- Schemas exported from `app/schemas.py` for import in CLI and future web UI

## Self-Check: PASSED

- `app/services/landing_page/section_editor.py` — FOUND
- `app/schemas.py` — FOUND
- `.planning/phases/15-ai-section-editing/15-01-SUMMARY.md` — FOUND
- Commit `694a742` — FOUND

---
*Phase: 15-ai-section-editing*
*Completed: 2026-02-19*
