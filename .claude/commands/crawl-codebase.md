---
description: Crawl the entire codebase to gain full app context
---

**CRITICAL: DO NOT use Task tool (sub-agents). Do everything sequentially in the main thread.**

Crawl this codebase to build complete project context.

**Step 1:** Discover the file tree dynamically:

```bash
find . -type f \
  -not -path '*/.git/*' \
  -not -path '*/node_modules/*' \
  -not -path '*/__pycache__/*' \
  -not -path '*/.claude/*' \
  -not -path '*/.planning/*' \
  -not -path '*/dist/*' \
  -not -path '*/build/*' \
  -not -path '*/.next/*' \
  -not -path '*/outputs/*' \
  -not -path '*/.venv/*' \
  -not -path '*/venv/*' \
  -not -name '*.pyc' \
  -not -name '*.lock' \
  -not -name '*.min.js' \
  -not -name '*.min.css' \
  -not -name '*.map' \
  | sort
```

**Step 2:** From the tree, identify and read files in this priority:

1. **Project root** — README, config files, Dockerfile, docker-compose, Makefile, package.json, pyproject.toml, etc.
2. **Entry points** — main app file, server setup, route definitions
3. **Data models** — schemas, DB models, migrations (latest 2-3 only)
4. **Core logic** — services, controllers, state machines, task queues
5. **Templates & frontend** — HTML, JS, CSS (skip vendored/minified)
6. **Tests** — scan for test structure, read a few representative tests

Skip generated code, lock files, and binary assets. Read files ONE AT A TIME using the Read tool.

**Step 3:** After reading, provide a structured summary:

- **Architecture**: tech stack, project structure, key patterns
- **Data flow**: how requests move through the system end-to-end
- **Models & state**: DB schema, state machines, key data structures
- **External integrations**: APIs, services, queues
- **Endpoints**: all routes/endpoints grouped by domain
- **Frontend**: UI patterns, client-server interaction model

End with a random specific detail (e.g. an endpoint, a function, a config value) to prove full context.

**DO NOT create any files. DO NOT skip files — read everything relevant.**
