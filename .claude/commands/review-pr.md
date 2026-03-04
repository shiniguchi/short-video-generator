---
description: Holistic PR alignment - fix cross-file inconsistencies, delete abandoned code, refactor docs to KISS
---

# PR Holistic Alignment

**Objective**: Analyze PR, fix all misalignments, delete dead code, refactor docs to KISS. Make production-ready.

---

## Core Operations

### 1. Detect PR Changes

```bash
git diff $(git merge-base origin/main HEAD)...HEAD
```

### 2. Align Cross-File References

For each changed pattern, grep entire repo, fix mismatches:

- Function renamed: Find old name usages, update all
- Import path changed: Find old imports, update all
- Type signature changed: Find old usages, update all
- Env var added: Update all config files (`.env.example`, `docker-compose.yml`)

### 3. Find and Delete Unused Files & Code

**Step 3A**: List all source files, check if imported/referenced anywhere. 0 references = potentially unused.

**Step 3B**: Verify flagged files:
- Entry points (main.py, index.ts) = KEEP
- Test files testing active code = KEEP
- Truly orphaned = DELETE

**Step 3C**: Delete dead code within files:
- Unused exports with 0 usages
- Commented blocks (>5 lines)
- Legacy code paths replaced by new implementation
- Unreferenced functions

### 4. Verify and Update All Documentation

**Step 4A**: Cross-reference doc claims with actual code. Flag outdated sections.
**Step 4B**: Fix wrong references, remove documented features that no longer exist.
**Step 4C**: Refactor to KISS — paragraphs to bullets, complex explanations to tables.

---

## Commit & Output

```bash
git add .
git commit -m "refactor: align cross-file references, delete abandoned code, update docs to KISS"
```

**Summary format:**
```
Alignment: Fixed [N] files, [M] imports, [K] configs
Cleanup: Deleted [X] unused files, [Y] dead exports, [Z] comment blocks
Docs: Verified [P] files, updated [Q] outdated sections
Net: -[total] lines removed
```

---

## Success Criteria

- Zero cross-file inconsistencies
- Zero unused files (verified and deleted)
- Zero dead code (0-reference exports/functions/comments)
- All docs accurate and in KISS format
- Changes committed
