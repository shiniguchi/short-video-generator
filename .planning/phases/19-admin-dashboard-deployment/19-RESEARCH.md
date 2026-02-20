# Phase 19: Admin Dashboard & Deployment - Research

**Researched:** 2026-02-20
**Domain:** FastAPI Jinja2 dashboard UI + Cloudflare Pages deployment API + CSV export + date-range filtering
**Confidence:** HIGH (dashboard + export + filtering), MEDIUM (Cloudflare Pages direct deploy via REST API)

## Summary

Phase 19 has two distinct halves: (1) an admin dashboard with waitlist management, analytics, CSV export, and date filtering — all pure FastAPI + Jinja2 + SQLAlchemy; and (2) one-click deployment of generated LP HTML files to Cloudflare Pages.

The dashboard half is straightforward. All data exists in the database: `WaitlistEntry` for signups, `LandingPage` for LP metadata, and `CloudflareAnalyticsClient` for per-LP traffic stats (built in Phase 18). The dashboard just needs new Jinja2 templates, SQL queries, and a StreamingResponse CSV export endpoint. No new Python packages are required.

The deployment half is the hard part. Cloudflare's officially documented approach for non-git deployments is `wrangler pages deploy <dir>`, a Node.js CLI tool. There is an undocumented REST API (reverse-engineered from wrangler source) that allows pure Python deployment via 5 HTTP steps: get upload token, hash files, upload file buckets, upsert hashes, then create deployment. The REST API approach works but is fragile since it is undocumented. The recommended approach for this project is to shell out to `npx wrangler pages deploy` via `asyncio.create_subprocess_exec`, which is officially supported and requires only Node.js on the host.

The deploy flow from Phase 18 is: read HTML from `lp.html_path`, call `inject_analytics_beacon()`, write to a temp dir, shell out to wrangler, update `LandingPage.status` to `"deployed"` and `deployed_url` in DB.

**Primary recommendation:** Use `asyncio.create_subprocess_exec("npx", "wrangler", "pages", "deploy", ...)` for Cloudflare Pages deployment. This is the officially supported path. Add two new config settings (`cf_account_id`, `cf_pages_project_name`) and one new env var (`CLOUDFLARE_API_TOKEN`). Dashboard pages are pure Jinja2 + SQLAlchemy with no new libraries.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI + Jinja2 | 0.128.8 + 3.1.6 (installed) | Dashboard HTML pages | Already used for all web UI (Phase 17 decision) |
| SQLAlchemy async | 2.0.46 (installed) | DB queries for signups, LP list, date filtering | Already in use for all models |
| asyncio stdlib | stdlib | `create_subprocess_exec` for wrangler shell call | Standard library, no deps |
| httpx | 0.28.1 (installed) | CloudflareAnalyticsClient calls (Phase 18, already exists) | Already in use |
| StreamingResponse | bundled with FastAPI | CSV export without loading all rows in memory | Standard Starlette pattern |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `csv` stdlib | stdlib | Write CSV rows to StringIO buffer for export | No external library needed |
| `io.StringIO` | stdlib | In-memory CSV buffer for streaming response | Avoids writing CSV to disk |
| `tempfile.TemporaryDirectory` | stdlib | Temp dir for wrangler deploy (one HTML file) | Wrangler needs a directory, not a file |
| Node.js + wrangler (system) | wrangler v3+ | Deploy HTML dir to Cloudflare Pages | Official Cloudflare deployment tool |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `npx wrangler pages deploy` subprocess | Undocumented REST API | REST API is reverse-engineered (blake3 hashing, upload JWTs, multipart finicky); subprocess is officially supported and stable |
| `npx wrangler pages deploy` subprocess | `cloudflare-python` SDK | SDK's `deployments.create()` only triggers git-connected builds — not direct file upload |
| StreamingResponse for CSV | Write CSV to file + FileResponse | StreamingResponse avoids disk I/O; fine for expected dataset size (<100K rows) |
| Full dashboard page for analytics | AJAX polling from preview page | Dashboard page loads all data server-side; simpler and consistent with Jinja2-only UI pattern |

**Installation:**
```bash
# No new Python packages needed
# Host must have Node.js + npx available (for wrangler)
# To verify: npx wrangler --version
```

## Architecture Patterns

### Recommended Project Structure
```
app/
├── ui/
│   ├── router.py            # Add: /dashboard, /waitlist, /export-csv, /deploy/{run_id}
│   └── templates/
│       ├── dashboard.html   # New: analytics + signups summary per LP
│       └── waitlist.html    # New: full waitlist table with date filter + export button
├── services/
│   └── landing_page/
│       └── deployer.py      # New: deploy_to_cloudflare_pages() using wrangler subprocess
└── config.py                # Add: cf_account_id, cf_pages_project_name
```

### Pattern 1: Dashboard Query — Per-LP Stats
**What:** Join `LandingPage` + `WaitlistEntry` in SQLAlchemy to compute signup counts per LP. Fetch analytics from CF Worker for pageviews. Calculate CVR = signups / pageviews.
**When to use:** DASH-02, DASH-05 — per-LP traffic, signup count, conversion rate.

```python
# Source: SQLAlchemy 2.0 async pattern (existing in routes.py)
from sqlalchemy import select, func
from app.models import LandingPage, WaitlistEntry

async def get_dashboard_data(session, start_date=None, end_date=None):
    # Signups per LP source
    signup_q = select(
        WaitlistEntry.lp_source,
        func.count(WaitlistEntry.id).label("signups")
    ).group_by(WaitlistEntry.lp_source)

    if start_date:
        signup_q = signup_q.where(WaitlistEntry.signed_up_at >= start_date)
    if end_date:
        signup_q = signup_q.where(WaitlistEntry.signed_up_at <= end_date)

    signups_by_lp = {row.lp_source: row.signups for row in (await session.execute(signup_q)).all()}

    lps = (await session.execute(
        select(LandingPage).order_by(LandingPage.created_at.desc())
    )).scalars().all()

    return lps, signups_by_lp
```

### Pattern 2: CSV Export via StreamingResponse
**What:** Export `WaitlistEntry` rows as CSV. Use `StreamingResponse` with `text/csv` content type. Stream rows to avoid loading all into memory.
**When to use:** DASH-03 — export waitlist emails to CSV.

```python
# Source: FastAPI StreamingResponse pattern (already used in router.py for SSE)
import csv
import io
from fastapi.responses import StreamingResponse

@router.get("/export-csv")
async def export_waitlist_csv(session: AsyncSession = Depends(get_session)):
    """Export all waitlist entries as CSV download."""
    result = await session.execute(
        select(WaitlistEntry).order_by(WaitlistEntry.signed_up_at.desc())
    )
    entries = result.scalars().all()

    def generate():
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["email", "signed_up_at", "lp_source"])
        for e in entries:
            writer.writerow([e.email, e.signed_up_at.isoformat(), e.lp_source or ""])
            yield buf.getvalue()
            buf.truncate(0)
            buf.seek(0)

    return StreamingResponse(
        generate(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=waitlist.csv"}
    )
```

### Pattern 3: Date Range Filter via Query Params
**What:** Accept `start` and `end` query params (ISO date strings), parse in Python, pass to SQLAlchemy `where` clauses. Preserve filter state in template via form GET.
**When to use:** DASH-04 — filter dashboard data by date range.

```python
from datetime import datetime, timezone
from typing import Optional

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    start: Optional[str] = None,
    end: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
):
    start_dt = datetime.fromisoformat(start).replace(tzinfo=timezone.utc) if start else None
    end_dt = datetime.fromisoformat(end).replace(tzinfo=timezone.utc) if end else None
    # pass start_dt, end_dt into query helpers
```

### Pattern 4: Cloudflare Pages Deploy via Wrangler Subprocess
**What:** Write LP HTML (with beacon injected) to a temp dir, then call `wrangler pages deploy` via `asyncio.create_subprocess_exec`. Parse URL from stdout.
**When to use:** DEPLOY-01, DEPLOY-02 — one-action deploy to publicly accessible CF Pages URL.

```python
# Source: asyncio subprocess docs + wrangler CLI docs
import asyncio
import tempfile
import shutil
from pathlib import Path

async def deploy_to_cloudflare_pages(lp: LandingPage, settings) -> str:
    """Deploy LP HTML to Cloudflare Pages. Returns deployed URL."""
    # Read and inject beacon
    html = Path(lp.html_path).read_text()
    html = inject_analytics_beacon(html, settings.cf_worker_url, lp.run_id)

    with tempfile.TemporaryDirectory() as tmpdir:
        # Write HTML as index.html (CF Pages serves index.html at root)
        out = Path(tmpdir) / "index.html"
        out.write_text(html)

        # wrangler needs CLOUDFLARE_API_TOKEN in env
        env = {
            "CLOUDFLARE_API_TOKEN": settings.cf_api_token,
            "PATH": "/usr/local/bin:/usr/bin:/bin",  # ensure npx is findable
        }

        proc = await asyncio.create_subprocess_exec(
            "npx", "wrangler", "pages", "deploy", tmpdir,
            "--project-name", settings.cf_pages_project_name,
            "--branch", "main",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)

        if proc.returncode != 0:
            raise RuntimeError(f"wrangler deploy failed: {stderr.decode()}")

        # Parse deployed URL from wrangler stdout
        # wrangler outputs: "✨ Deployment complete! Take a peek over at https://xxx.pages.dev"
        output = stdout.decode()
        url = _extract_pages_url(output)
        return url
```

### Pattern 5: Deploy Route in router.py (replaces stub)
**What:** Replace the Phase 17 stub `POST /ui/deploy/{run_id}` with real deployment logic. Run deploy in background asyncio task (can take 10-30s). Return immediate 202 response, stream status via JSON polling or redirect on completion.
**When to use:** DEPLOY-01, DEPLOY-03.

```python
@router.post("/deploy/{run_id}")
async def deploy_lp(run_id: str, session: AsyncSession = Depends(get_session)):
    """Deploy LP to Cloudflare Pages. Updates status to 'deployed' on success."""
    result = await session.execute(select(LandingPage).where(LandingPage.run_id == run_id))
    lp = result.scalar_one_or_none()
    if not lp:
        raise HTTPException(404, f"LP {run_id} not found")
    if lp.status == "deployed":
        return {"status": "already_deployed", "url": lp.deployed_url}

    # Deploy (blocking — acceptable since deploy takes <30s and is user-initiated)
    settings = get_settings()
    url = await deploy_to_cloudflare_pages(lp, settings)

    # Update DB
    lp.status = "deployed"
    lp.deployed_at = datetime.now(timezone.utc)
    lp.deployed_url = url
    await session.commit()

    return {"status": "deployed", "url": url}
```

### Anti-Patterns to Avoid
- **Using `cloudflare-python` SDK `deployments.create()`:** This requires a git-connected project and only triggers a rebuild. It cannot upload files.
- **REST API direct upload (reverse-engineered):** The undocumented 5-step upload API (upload-token → bucket upload → upsert-hashes → create deployment) uses unstable internal endpoints. Avoid unless wrangler is unavailable.
- **Blocking the event loop with subprocess.run():** Use `asyncio.create_subprocess_exec` not `subprocess.run` — the latter blocks the entire async event loop during the 10-30s deploy.
- **Hardcoding `index.html` path assumption in the LP preview:** LP HTML is always at `output/{run_id}/landing-page.html`. The deploy copies it as `index.html` in the temp dir. Don't change the file path in the DB.
- **Loading all waitlist rows into memory for CSV:** Use a generator with `StreamingResponse` — for large datasets the generator pattern avoids OOM.
- **Forgetting `--branch main` in wrangler deploy:** Without `--branch`, wrangler may create a preview deployment instead of the production deployment. Pass `--branch main` explicitly.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Cloudflare Pages upload | Custom 5-step REST API (upload-token, bucket upload, upsert-hashes, create deployment) | `npx wrangler pages deploy` | REST API is undocumented, uses blake3 hashing — wrangler handles all of this |
| CSV serialization | Custom string concatenation | `csv.writer` stdlib | Handles quoting, escaping edge cases |
| Date parsing | Custom string split | `datetime.fromisoformat()` | stdlib, handles ISO 8601 correctly |
| Per-LP signup count | N+1 per-LP queries | SQLAlchemy `GROUP BY lp_source` aggregate query | Single query vs N queries for N LPs |
| Analytics CVR calculation | Client-side JS | Server-side in Jinja2 template: `{{ signups / pageviews if pageviews else 0 }}` | Keeps logic server-side, no JS needed |

**Key insight:** The only genuinely new infrastructure is wrangler CLI access on the host. Everything else is composition of existing components: Phase 17's Jinja2 UI, Phase 16's WaitlistEntry model, Phase 18's CloudflareAnalyticsClient.

## Common Pitfalls

### Pitfall 1: Wrangler Not Found in Subprocess PATH
**What goes wrong:** `asyncio.create_subprocess_exec("npx", "wrangler", ...)` raises FileNotFoundError or wrangler returns "command not found".
**Why it happens:** The subprocess inherits a restricted env; `npx` or `node` may not be in the default PATH.
**How to avoid:** Pass an explicit `env` dict to `create_subprocess_exec` that includes `PATH` with node binary locations. Add a startup check: `which npx` or `npx --version` in the deploy route before attempting deploy.
**Warning signs:** `FileNotFoundError: [Errno 2] No such file or directory: 'npx'`.

### Pitfall 2: Wrangler Interactive Prompt Hangs Subprocess
**What goes wrong:** First-time deploy prompts for project name or account selection. Subprocess hangs waiting for stdin.
**Why it happens:** Wrangler tries to be interactive when project name or account ID is not specified.
**How to avoid:** Always pass `--project-name` and set `CLOUDFLARE_ACCOUNT_ID` in env. Wrangler skips prompts when both are provided.
**Warning signs:** Deploy subprocess never completes; `asyncio.wait_for` timeout fires after 120s.

### Pitfall 3: Cloudflare Pages Project Must Exist First
**What goes wrong:** `wrangler pages deploy` fails if the Pages project doesn't exist in the Cloudflare account.
**Why it happens:** Wrangler tries to look up the project by name and cannot auto-create it without interactive confirmation.
**How to avoid:** Create the Pages project once manually via dashboard or `npx wrangler pages project create <name>` before first deployment. Document this as a one-time setup step.
**Warning signs:** `wrangler deploy` returns error "project not found" or "unauthorized".

### Pitfall 4: CVR Division By Zero
**What goes wrong:** LP has 0 pageviews (Worker not configured, or new LP) — CVR = signups / pageviews raises ZeroDivisionError in template.
**Why it happens:** Template tries to compute `{{ signups / pageviews }}` when pageviews = 0.
**How to avoid:** Use `{{ (signups / analytics.pageviews * 100) | round(1) if analytics.pageviews else 0 }}` in Jinja2 template.
**Warning signs:** Dashboard page throws 500 error for LPs with no analytics data.

### Pitfall 5: Beacon Injected Twice on Re-deploy
**What goes wrong:** Re-deploying an already-deployed LP injects the beacon a second time.
**Why it happens:** `inject_analytics_beacon` is called on the HTML at `lp.html_path` — which was saved at generation time without beacon (correct). But if the LP HTML somehow already has a beacon (e.g., generation code changes), re-deploy doubles it.
**How to avoid:** `inject_analytics_beacon` reads the file at `html_path` which never has a beacon (beacon injection is deploy-time only per Phase 18 design). Guard: check LP status before deploying — return early if already `"deployed"` unless re-deploy is explicitly requested.
**Warning signs:** LP HTML has two `<script>` blocks with identical beacon code.

### Pitfall 6: Date Filter Query Param Timezone Mismatch
**What goes wrong:** User picks a date in their local timezone; query compares against UTC timestamps in DB. Results are off by hours.
**Why it happens:** HTML `<input type="date">` returns `YYYY-MM-DD` without timezone. Python parses as UTC by default.
**How to avoid:** Accept `YYYY-MM-DD`, parse as date, convert start to UTC midnight and end to UTC 23:59:59. Or accept ISO datetime strings with timezone. Document behavior.
**Warning signs:** Dashboard shows "no results" for a date the user knows has signups.

## Code Examples

Verified patterns from official sources and existing codebase:

### SQLAlchemy Aggregate Query (signup count per LP)
```python
# Source: SQLAlchemy 2.0 docs — select with func.count and group_by
from sqlalchemy import select, func
from app.models import WaitlistEntry

result = await session.execute(
    select(
        WaitlistEntry.lp_source,
        func.count(WaitlistEntry.id).label("count")
    ).group_by(WaitlistEntry.lp_source)
)
signups_by_lp = {row.lp_source: row.count for row in result.all()}
```

### Date Range Filter
```python
# Source: SQLAlchemy 2.0 + Python stdlib datetime
from datetime import datetime, timezone, date

def parse_date_filter(date_str: Optional[str]) -> Optional[datetime]:
    """Parse YYYY-MM-DD to UTC datetime for DB comparison."""
    if not date_str:
        return None
    d = date.fromisoformat(date_str)
    return datetime(d.year, d.month, d.day, tzinfo=timezone.utc)

# In route:
start_dt = parse_date_filter(start)
end_dt = parse_date_filter(end)
query = select(WaitlistEntry).order_by(WaitlistEntry.signed_up_at.desc())
if start_dt:
    query = query.where(WaitlistEntry.signed_up_at >= start_dt)
if end_dt:
    # end of day
    from datetime import timedelta
    query = query.where(WaitlistEntry.signed_up_at < end_dt + timedelta(days=1))
```

### Wrangler Pages Deploy Subprocess
```python
# Source: asyncio subprocess docs + wrangler CLI --help
import asyncio, tempfile, os
from pathlib import Path

async def deploy_to_cloudflare_pages(html: str, run_id: str, settings) -> str:
    with tempfile.TemporaryDirectory() as tmpdir:
        Path(tmpdir, "index.html").write_text(html, encoding="utf-8")

        env = os.environ.copy()
        env["CLOUDFLARE_API_TOKEN"] = settings.cf_api_token
        env["CLOUDFLARE_ACCOUNT_ID"] = settings.cf_account_id

        proc = await asyncio.create_subprocess_exec(
            "npx", "wrangler", "pages", "deploy", tmpdir,
            "--project-name", settings.cf_pages_project_name,
            "--branch", "main",
            "--commit-dirty=true",   # skip git check
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            env=env,
        )
        try:
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=120)
        except asyncio.TimeoutError:
            proc.kill()
            raise RuntimeError("wrangler deploy timed out after 120s")

        output = stdout.decode()
        if proc.returncode != 0:
            raise RuntimeError(f"wrangler deploy failed:\n{output}")

        # Extract URL: wrangler outputs line like:
        # "✨ Deployment complete! Take a peek over at https://xxxxx.pages.dev"
        for line in output.splitlines():
            if "pages.dev" in line or "http" in line:
                import re
                m = re.search(r"https?://\S+", line)
                if m:
                    return m.group(0).rstrip(".")
        raise RuntimeError(f"Could not parse deployed URL from wrangler output:\n{output}")
```

### Config Settings to Add
```python
# app/config.py — add to Settings class
# Cloudflare Pages Deployment (Phase 19)
cf_api_token: str = ""            # CLOUDFLARE_API_TOKEN for wrangler
cf_account_id: str = ""           # Cloudflare Account ID
cf_pages_project_name: str = ""   # Pages project name (must exist in CF dashboard)
```

### CSV Export (StreamingResponse generator)
```python
# Source: FastAPI StreamingResponse + stdlib csv module
import csv, io
from fastapi.responses import StreamingResponse

@router.get("/ui/waitlist/export.csv")
async def export_csv(session: AsyncSession = Depends(get_session)):
    entries = (await session.execute(
        select(WaitlistEntry).order_by(WaitlistEntry.signed_up_at.desc())
    )).scalars().all()

    def generate():
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["email", "signed_up_at", "lp_source"])
        yield buf.getvalue()
        for e in entries:
            buf.truncate(0); buf.seek(0)
            w.writerow([e.email, e.signed_up_at.isoformat() if e.signed_up_at else "", e.lp_source or ""])
            yield buf.getvalue()

    return StreamingResponse(
        generate(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="waitlist.csv"'},
    )
```

### Jinja2 Dashboard Template (CVR + filter form)
```html
<!-- templates/dashboard.html — extends base.html -->
<!-- Date filter form — GET submits to same page with query params -->
<form method="GET" action="/ui/dashboard" class="filter-form">
  <input type="date" name="start" value="{{ start or '' }}">
  <input type="date" name="end" value="{{ end or '' }}">
  <button type="submit" class="btn btn-primary">Filter</button>
  <a href="/ui/dashboard" class="btn btn-secondary">Clear</a>
</form>

<!-- Per-LP stats table -->
{% for lp in lps %}
<tr>
  <td>{{ lp.product_idea[:50] }}</td>
  <td><span class="status-badge status-{{ lp.status }}">{{ lp.status }}</span></td>
  <td>{{ analytics[lp.run_id].pageviews if lp.run_id in analytics else 0 }}</td>
  <td>{{ signups_by_lp.get(lp.run_id, 0) }}</td>
  <td>
    {% set pv = analytics[lp.run_id].pageviews if lp.run_id in analytics else 0 %}
    {% set sg = signups_by_lp.get(lp.run_id, 0) %}
    {{ ((sg / pv * 100) | round(1))|string + "%" if pv > 0 else "—" }}
  </td>
  <td>{{ lp.deployed_url or "—" }}</td>
</tr>
{% endfor %}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `subprocess.run()` blocking | `asyncio.create_subprocess_exec()` | Python 3.5+ (asyncio) | Non-blocking; won't freeze FastAPI event loop during 30s deploy |
| Cloudflare Pages git-only deploys | `wrangler pages deploy <dir>` direct upload | Wrangler 2.x+ | No git repo needed; can deploy from any directory |
| Custom CSV writer | `csv.writer` stdlib | Python 2.7+ | Handles edge cases (quotes, commas in data) |
| `cloudflare-python` SDK for Pages | `npx wrangler` subprocess | 2024 SDK still doesn't support direct upload | SDK `deployments.create()` is for git-connected projects only |

**Deprecated/outdated:**
- `cloudflare/pages-action` GitHub Action: Deprecated in favor of `cloudflare/wrangler-action`.
- Undocumented REST API direct upload (5-step flow): Works but unstable; wrangler abstracts it correctly.

## Open Questions

1. **Wrangler availability on host**
   - What we know: `npx wrangler` requires Node.js on the host running the FastAPI server.
   - What's unclear: Is Node.js available in the project's Docker image?
   - Recommendation: Check `docker-compose.yml` and `Dockerfile` for Node.js install. If absent, add `RUN apt-get install -y nodejs npm` to Dockerfile. Alternatively, add a startup check in the deploy route that returns a clear error if wrangler is not available.

2. **Pages project must pre-exist**
   - What we know: `wrangler pages deploy` requires the project to already exist.
   - What's unclear: Should Phase 19 auto-create the project if it doesn't exist, or require a one-time manual setup?
   - Recommendation: Require one-time manual setup (`npx wrangler pages project create <name>`). Document it in the phase verification steps. Auto-creation adds complexity and only happens once.

3. **Wrangler stdout URL parsing reliability**
   - What we know: Wrangler outputs the deployed URL in stdout but the exact format may vary between versions.
   - What's unclear: Is the `"✨ Deployment complete! Take a peek over at https://..."` line stable across wrangler versions?
   - Recommendation: Parse with a broad regex `https?://\S+\.pages\.dev` from all stdout lines. If not found, still mark as deployed but set `deployed_url` to `None` and log the full output. Don't fail deployment if URL parsing fails.

4. **Multiple deploys per LP**
   - What we know: The `LandingPage.status` transitions: `generated` → `deployed`. There is no re-deploy path.
   - What's unclear: Should re-deploying an already-deployed LP be supported? (e.g., after editing sections)
   - Recommendation: Allow re-deploy. Don't gate on `status == "deployed"`. Each wrangler deploy creates a new deployment; Cloudflare keeps previous ones as previews. Update `deployed_url` and `deployed_at` on each deploy.

5. **Analytics loading performance on dashboard**
   - What we know: `CloudflareAnalyticsClient.get_lp_analytics()` makes one HTTP call per LP to the Worker. If there are 20 LPs, that is 20 sequential HTTP calls.
   - What's unclear: Will this be acceptable latency for the dashboard page load?
   - Recommendation: Fetch analytics concurrently with `asyncio.gather()` for all LPs at once. Use a 5s timeout per call. If a call fails, use the graceful fallback `{"pageviews": 0, "form_submissions": 0, "error": "..."}` that `CloudflareAnalyticsClient` already returns.

## Sources

### Primary (HIGH confidence)
- Codebase: `app/ui/router.py` — existing route structure, Jinja2Templates setup, asyncio.create_task pattern
- Codebase: `app/models.py` — `LandingPage` (status, deployed_url, deployed_at), `WaitlistEntry` (email, signed_up_at, lp_source) — all columns already exist
- Codebase: `app/services/analytics/client.py` — `CloudflareAnalyticsClient.get_lp_analytics()` — Phase 18 artifact
- Codebase: `app/services/landing_page/optimizer.py` — `inject_analytics_beacon()` — Phase 18 artifact
- Codebase: `app/config.py` — existing Settings pattern, `cf_worker_url`, `cf_worker_api_key` already added
- Codebase: `app/ui/templates/index.html` — LP list pattern, status-badge CSS classes
- Cloudflare docs: https://developers.cloudflare.com/pages/how-to/use-direct-upload-with-continuous-integration/ — wrangler CLI deployment pattern, `CLOUDFLARE_API_TOKEN` + `CLOUDFLARE_ACCOUNT_ID` env vars
- Cloudflare docs: https://developers.cloudflare.com/fundamentals/api/reference/permissions/ — "Cloudflare Pages:Edit" token permission
- Python docs: `asyncio.create_subprocess_exec` — non-blocking subprocess
- Python docs: `csv.writer` + `io.StringIO` — CSV generation

### Secondary (MEDIUM confidence)
- Cloudflare Pages REST API (verified): `POST /accounts/{account_id}/pages/projects/{project_name}/deployments` with multipart/form-data — verified from official API reference (HIGH for existence, MEDIUM for file upload details since git-connected behavior documented but direct upload less clear)
- Wrangler stdout URL format: Based on community reports and wrangler source review — parse with regex as fallback; MEDIUM confidence on exact format stability across wrangler versions
- WebSearch: Wrangler `--commit-dirty=true` flag suppresses git-related errors when deploying non-git directories — MEDIUM confidence; verify with `npx wrangler pages deploy --help`

### Tertiary (LOW confidence)
- Undocumented REST API (5-step flow): Reverse-engineered from https://hunterashaw.com/reverse-engineering-the-cloudflare-pages-deployment-api/ — documented here for completeness but NOT recommended over wrangler

## Metadata

**Confidence breakdown:**
- Dashboard UI (DASH-01 through DASH-05): HIGH — pure Jinja2 + SQLAlchemy, patterns already in codebase
- CSV export: HIGH — stdlib csv + StreamingResponse, standard pattern
- Date filtering: HIGH — SQLAlchemy where clauses, standard datetime handling
- Cloudflare Pages deploy via wrangler subprocess: MEDIUM — wrangler is officially supported, but subprocess approach and stdout parsing add uncertainty; verify with `npx wrangler pages deploy --help`
- Analytics concurrent fetch: HIGH — `asyncio.gather()` is well-established

**Research date:** 2026-02-20
**Valid until:** 2026-03-20 (Wrangler CLI changes infrequently; Jinja2/SQLAlchemy stable)
