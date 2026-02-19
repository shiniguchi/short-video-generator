---
phase: 15-ai-section-editing
plan: "02"
subsystem: landing-page
tags: [argparse, cli, json-sidecar, section-editor, landing-page, python]

requires:
  - phase: 15-ai-section-editing-01
    provides: edit_section(), list_sections(), get_editable_sections() from section_editor.py

provides:
  - scripts/edit_lp_section.py CLI with --lp, --section, --prompt, --product, --list, --mock, --no-open flags
  - JSON sidecar persistence (landing-page.json) for product context across edits
  - app.services.landing_page public API exports: edit_section, list_sections

affects:
  - 17-web-ui (will use edit_section programmatically via updated __init__.py exports)

tech-stack:
  added: []
  patterns:
    - "Sidecar file pattern: write landing-page.json next to HTML on first edit; read on subsequent edits to skip --product flag"
    - "Lazy import pattern: heavy module imports inside main() to avoid loading at --help time"

key-files:
  created:
    - scripts/edit_lp_section.py
  modified:
    - app/services/landing_page/__init__.py

key-decisions:
  - "Sidecar written by CLI on first edit (not by generator) — keeps generator simple, CLI owns persistence"
  - "Product fallback order: --product flag > sidecar file > error with helpful tip message"

patterns-established:
  - "edit_lp_section.py follows generate_landing_page.py pattern: sys.path setup, DATABASE_URL override, logging, argparse, lazy imports"

duration: 3min
completed: 2026-02-19
---

# Phase 15 Plan 02: CLI for LP Section Editing Summary

**argparse CLI (edit_lp_section.py) wrapping section_editor.py with sidecar persistence so --product is only needed once per LP**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-19T20:42:02Z
- **Completed:** 2026-02-19T20:45:00Z
- **Tasks:** 1
- **Files modified:** 2

## Accomplishments

- Built `scripts/edit_lp_section.py` CLI matching the style of `generate_landing_page.py`
- `--list` mode discovers all sections in an LP and shows editability status
- Edit mode resolves product context from `--product` flag or sidecar fallback, with clear error if neither exists
- Sidecar (`landing-page.json`) written on first edit when `--product` is provided — subsequent edits need no flag
- Updated `app/services/landing_page/__init__.py` to export `edit_section` and `list_sections` for programmatic use

## Task Commits

1. **Task 1: Create CLI command and update module exports** - `8901da2` (feat)

**Plan metadata:** (pending)

## Files Created/Modified

- `scripts/edit_lp_section.py` - CLI: argparse setup, --list mode, edit mode, sidecar read/write helpers
- `app/services/landing_page/__init__.py` - Added edit_section and list_sections to public exports

## Decisions Made

- Sidecar written by CLI on first edit (not by generator) — generator stays clean, CLI owns the persistence concern
- `--product` fallback order: explicit flag > sidecar file > error with tip message explaining how to save it
- Lazy import of heavy modules inside `main()` to keep `--help` fast

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None — section_editor.py from Plan 01 worked as expected. No new dependencies needed.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- CLI fully functional: generate LP (mock) → edit any section (mock) → sidecar persists product context
- `edit_section` and `list_sections` exported from `app.services.landing_page` for Phase 17 Web UI
- Phase 15 complete — all section editing functionality (core + CLI) shipped

## Self-Check: PASSED

- `scripts/edit_lp_section.py` — FOUND
- `app/services/landing_page/__init__.py` — FOUND (exports edit_section, list_sections)
- `.planning/phases/15-ai-section-editing/15-02-SUMMARY.md` — FOUND
- Commit `8901da2` — FOUND

---
*Phase: 15-ai-section-editing*
*Completed: 2026-02-19*
