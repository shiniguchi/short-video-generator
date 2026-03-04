---
description: Generate executive branch summary for GitHub PR descriptions
---

# Branch Summary Generator

**AI Instructions**: Auto-generate executive branch summary for entire branch. Analyze ALL commits from main..HEAD, **output raw markdown text in a code block**.

---

## Auto-Context Gathering

1. **Analyze ALL branch changes**
   - `git log main..HEAD --oneline` - Show all commits in branch
   - `git diff main..HEAD --stat` - Show all files changed

2. **Detect current repository**
   - `basename "$(git rev-parse --show-toplevel)"`

---

## Summary Format

**Risk Level**: Red High | Yellow Medium | Green Low

### TL;DR
**Max 2 sentences - simple, direct summary using plain language**

### Problem & Root Cause
**What broke and why** (number each item, show actual observations)

### Solution
**What we changed to fix it** (number to match problems, show before/after)

### Impact
**Performance** — before/after numbers
**Watch After Deploy** — metrics to monitor

### Housekeeping
Files deleted, dead code removed, docs updated

---

## PR Title

- Under 70 characters
- Format: `<type>: <short description>` (feat, fix, refactor, docs, chore, perf, test)
- Imperative mood ("add X" not "added X")
- Output as a separate code block before the summary

---

## Output Instructions

1. Output PR title in its own code block first
2. Output summary markdown in a separate markdown code block
3. Do NOT render as HTML - output plain text markdown for copy-paste
4. Keep it concise (KISS)
