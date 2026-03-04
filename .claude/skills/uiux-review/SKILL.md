---
name: uiux-review
description: "Holistic UI/UX review with Chrome MCP. Walks every page, screenshots, rates, suggests fixes with visual references, then implements. Usage: /uiux-review [url-or-page] [--fix]"
allowed-tools: mcp__claude-in-chrome__tabs_context_mcp, mcp__claude-in-chrome__tabs_create_mcp, mcp__claude-in-chrome__navigate, mcp__claude-in-chrome__computer, mcp__claude-in-chrome__read_page, mcp__claude-in-chrome__find, mcp__claude-in-chrome__get_page_text, mcp__claude-in-chrome__javascript_tool, mcp__claude-in-chrome__resize_window, mcp__claude-in-chrome__read_console_messages, mcp__claude-in-chrome__read_network_requests, mcp__claude-in-chrome__form_input, Read, Edit, Write, Grep, Glob, Bash, WebSearch, WebFetch
context: fork
---

# UI/UX Review & Fix

## Objective

Walk through the app like a user, review every page for UI/UX issues, rate holistically, suggest improvements with visual references from top-tier products, then fix issues on command.

## Input

`$ARGUMENTS` determines behavior:

- **Empty** → full app walkthrough starting at `http://localhost:8000/ui/`
- **URL** → review that specific page
- **Page name** (e.g. "dashboard", "ugc/new") → append to `http://localhost:8000/ui/`
- **`--fix`** flag anywhere → after review, implement all High+ fixes automatically

## Before Starting

Read the checklist at `.claude/skills/uiux-review/checklist.md` — it has all review criteria with thresholds.

Read the benchmarks at `.claude/skills/uiux-review/benchmarks.md` — it has visual patterns from top-tier apps to compare against.

---

## Phase 0: Setup

1. `tabs_context_mcp` with `createIfEmpty: true`
2. `tabs_create_mcp` for a fresh tab
3. Navigate to target URL
4. `computer` action `wait` 3 seconds
5. `computer` action `screenshot` — confirm page loaded

## Phase 1: Page Discovery & Walkthrough

If reviewing the full app, discover all pages dynamically:

1. Use `Grep` to find all `@router.get` routes with `response_class=HTMLResponse` in the UI router file (search for the pattern in `app/ui/router.py` or similar)
2. Extract the GET routes — these are the visitable pages
3. Navigate to the app root first, then walk pages in logical user-journey order:
   - Start with the home/index page
   - Follow primary navigation links
   - Open list pages, then detail/review pages (use the first available record)
   - Cover creation flows (new/generate forms)
4. If a page needs a record ID, check the list page for an existing item to use

For each page:
- `resize_window` 1440x900 → screenshot
- `resize_window` 375x812 → screenshot
- `resize_window` back to 1440x900
- Note issues against checklist

## Phase 2: Comparative Analysis

For each page, mentally compare against benchmarks (from `benchmarks.md`):

- **Dashboard** → compare to Linear, Notion, Vercel dashboard patterns
- **Form pages** → compare to Stripe, Clerk onboarding flows
- **Review/detail pages** → compare to Figma, GitHub PR review patterns
- **List pages** → compare to Linear, Notion table/list patterns
- **Landing pages** → compare to top Webflow/Framer showcases

Use `WebSearch` to find current screenshots of these products when needed for specific comparisons. Search for "[product] [page type] screenshot 2025" to get visual references.

## Phase 3: Deep Inspection (per page)

### 3a. Visual & Layout
- Spacing consistency (8px grid)
- Typography hierarchy (clear H1 > H2 > body)
- Color contrast
- Visual balance and whitespace
- Card/section alignment

### 3b. Interaction States
- `find` interactive elements
- Hover states (use `hover` action)
- Focus rings (Tab key navigation)
- Loading/empty states
- Error state handling
- Button feedback

### 3c. Responsiveness
- 1440px (desktop) — full layout
- 768px (tablet) — reflow check
- 375px (mobile) — stacking, readability

### 3d. Accessibility Quick-Check
```javascript
// Missing alt text
document.querySelectorAll('img:not([alt])').length
```
```javascript
// Unlabeled buttons
[...document.querySelectorAll('button, a')].filter(el =>
  !el.textContent.trim() && !el.getAttribute('aria-label')
).length
```
```javascript
// Orphaned inputs
[...document.querySelectorAll('input, select, textarea')].filter(el =>
  !el.getAttribute('aria-label') &&
  !document.querySelector(`label[for="${el.id}"]`)
).length
```

### 3e. Console & Network
- `read_console_messages` with `onlyErrors: true`
- `read_network_requests` — check for 4xx/5xx

---

## Phase 4: Holistic Rating

After reviewing all pages, produce the final report.

### Report Format

```markdown
## UI/UX Review Report

**App**: [name]
**Date**: [date]
**Pages reviewed**: [count]
**Viewports**: 1440px, 768px, 375px

---

### Overall Score: X/100

| Category | Score | Notes |
|----------|-------|-------|
| Visual Design & Polish | /20 | |
| Layout & Spacing | /15 | |
| Responsiveness | /15 | |
| Interaction & Feedback | /15 | |
| Accessibility | /15 | |
| Information Architecture | /10 | |
| Consistency | /10 | |

### Score Guide
- 90-100: Production-ready, competitive with top SaaS
- 75-89: Good, minor polish needed
- 60-74: Functional but noticeably rough
- 40-59: Needs significant work
- <40: Prototype-level

---

### Findings by Page

#### [Page Name] — [url]
**Page score**: X/100

**Issues:**
- [B1] **Blocker** — [description] — rule [ID]
- [H1] **High** — [description] — rule [ID]
- [M1] **Medium** — [description] — rule [ID]

**Benchmark comparison:**
- [What top-tier apps do differently here]
- [Specific visual pattern to adopt]

---

### Top 10 Improvements (Prioritized)

For each improvement:
1. **What**: [specific change]
2. **Why**: [impact on UX]
3. **Reference**: [which top-tier app does this well]
4. **Effort**: S/M/L
5. **Files to change**: [file paths]

---

### Generic Patterns to Adopt

[3-5 cross-cutting improvements that apply across all pages, e.g.:
- Add consistent hover transitions (150ms ease)
- Standardize card padding to 24px
- Add skeleton loading states]
```

---

## Phase 5: Fix Mode (when `--fix` flag is set)

After producing the report, implement fixes:

1. Read the relevant template/CSS/JS files
2. Fix all **Blocker** and **High** issues
3. Fix **Medium** issues if straightforward
4. After each fix batch:
   - Read MEMORY.md for build/deploy conventions (docker rebuild command, cache-bust version, etc.)
   - Rebuild and wait for the app to be ready
   - Navigate to the fixed page
   - Screenshot to verify the fix

**Fix priority**: accessibility > broken layouts > interaction states > visual polish

---

## Severity Rules

| Severity | Criteria |
|----------|----------|
| **Blocker** | Broken functionality, inaccessible content, JS errors blocking use |
| **High** | Failed accessibility, broken responsive, missing error/empty states |
| **Medium** | Inconsistent spacing/colors, missing hover states, alignment issues |
| **Low** | Animation timing, micro-interactions, icon consistency |
