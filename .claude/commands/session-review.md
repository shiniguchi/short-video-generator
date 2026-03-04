---
description: Session review with change tracking and optimization
---

# Session Review & Code Optimization

Execute a comprehensive session review: track changes, validate functionality, optimize code.

---

## 1. Change Analysis & Impact Assessment

1. **Identify changes**
   - `git status --porcelain` and `git diff --stat`
   - `basename "$(git rev-parse --show-toplevel)"`

2. **Impact analysis**
   - Map changed files to affected modules
   - Check for broken imports or references

---

## 2. Code Optimization & Quality

1. **Code simplification**
   - `git diff --numstat` to calculate lines added/removed
   - Find debug logging, typing issues, duplications
   - Recommend consolidation if net code increase detected

---

## 3. Workflow & Deployment Safety

1. **Deployment readiness**
   - Run appropriate linting/testing commands
   - Prepare rollback commands with current commit hash

---

## 4. Update Documentation

1. **Compare actual code logic with docs**
   - Delete irrelevant content from markdown docs
   - Add minimal relevant updates

---

## 5. Output

Generate standardized session report with:
- Code complexity changes (optimization opportunities)
- Production safety requirements
- Architecture compliance

**Tool Priority:**
1. Git CLI for change detection
2. Grep/search for code pattern analysis
3. Bash for workflow enforcement
