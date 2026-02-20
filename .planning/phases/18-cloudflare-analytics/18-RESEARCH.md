# Phase 18: Cloudflare Analytics - Research

**Researched:** 2026-02-20
**Domain:** Cloudflare Workers + D1 + analytics beacon + Python HTTP proxy client
**Confidence:** HIGH

## Summary

Phase 18 builds analytics infrastructure for deployed LPs using three pieces: (1) a Cloudflare Worker that receives beacon pings from LP pages and stores them in D1, (2) a small `<script>` beacon injected into each LP's HTML before deployment, and (3) a Python service in the FastAPI backend that queries the Worker via HTTP to retrieve analytics.

The Worker is a standalone Cloudflare project — a separate directory outside the Python codebase. It is deployed with `wrangler deploy` and runs at a `*.workers.dev` URL. It has two public endpoints: `POST /track` (receives beacon pings from LP pages, writes to D1) and `GET /analytics/:lp_id` (returns aggregated stats, gated by an API key). The Python backend calls the second endpoint over HTTPS using `httpx`.

D1 is Cloudflare's managed SQLite-compatible database. It is free-tier friendly: 5 million rows read/day and 100,000 rows written/day — more than sufficient for a smoke-test platform. Schema migrations are managed with `wrangler d1 migrations`. The beacon script injected into LP HTML uses `navigator.sendBeacon` (with `fetch` fallback) to fire a POST to the Worker endpoint without blocking page load.

**Primary recommendation:** Build one Worker with two routes (`/track` POST for beacons, `/analytics/:lp_id` GET for Python queries), one D1 database with two tables (`pageviews`, `form_submissions`), inject a 10-line beacon script into LP HTML via `optimizer.py`, add a `CloudflareAnalyticsClient` class to the FastAPI app, expose a `GET /api/analytics/:lp_id` route on the Python side.

## Standard Stack

### Core
| Library/Tool | Version | Purpose | Why Standard |
|---|---|---|---|
| Cloudflare Workers (JavaScript) | Workers runtime | Receives beacons, writes to D1, serves analytics | Official Cloudflare Worker runtime; no external compute needed |
| Cloudflare D1 | GA (2024) | SQLite-compatible managed DB, bound to Worker | Phase 14 decision: Cloudflare Pages + Worker + D1 |
| Wrangler CLI | latest (v3+) | Create/deploy Worker and D1 migrations | Official Cloudflare toolchain |
| `httpx` (Python) | 0.27+ (already in project) | Python backend calls Worker HTTP API | Async HTTP, already in many Python projects; simpler than Cloudflare SDK |

### Supporting
| Library/Tool | Version | Purpose | When to Use |
|---|---|---|---|
| `navigator.sendBeacon` (browser API) | Standard | Fire-and-forget HTTP POST from LP page | For pageview/form beacons — does not block page or cancel on unload |
| Hono (optional) | v4.x | Lightweight router for the Worker | Use if Worker has ≥3 routes; skip for 2 routes — native `URL` routing is fine |
| `.dev.vars` file | wrangler convention | Local dev secrets (API_KEY) | Keep secrets out of `wrangler.toml` |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|---|---|---|
| Custom Worker + D1 | Workers Analytics Engine | WAE is free-tier queryable via SQL API but has no row-level storage — D1 is better for per-LP queries |
| Custom Worker + D1 | Cloudflare Web Analytics | Built-in CF analytics requires a CF zone — LPs on `*.pages.dev` work, but this phase must deliver queryable data from Python |
| `navigator.sendBeacon` | Plain `fetch` | `sendBeacon` survives page unload; `fetch` can be cancelled; sendBeacon is the right tool for analytics |
| `httpx` (Python) | `cloudflare-python` SDK | SDK wraps the REST API; httpx against a Worker endpoint is simpler and zero extra deps |
| JavaScript Worker | Python Worker | Python Workers are stable but cold starts are slower and Worker JS is idiomatic Cloudflare — use JS |

**Installation:**
```bash
# Inside the Worker project directory (workers/lp-analytics/)
npm install  # if using Hono
npx wrangler@latest d1 create lp-analytics-db

# Python side — httpx likely already installed; if not:
pip install httpx
```

## Architecture Patterns

### Recommended Project Structure
```
workers/
└── lp-analytics/            # Cloudflare Worker project (separate from Python app)
    ├── wrangler.toml         # Worker config + D1 binding
    ├── src/
    │   └── index.js          # Worker handler (track + analytics routes)
    ├── migrations/
    │   └── 0001_init.sql     # D1 schema: pageviews + form_submissions tables
    └── .dev.vars             # Local secrets (never commit)

app/
├── services/
│   └── analytics/
│       ├── __init__.py
│       └── client.py         # CloudflareAnalyticsClient (httpx calls to Worker)
├── api/
│   └── routers/
│       └── analytics.py      # FastAPI router: GET /api/analytics/{lp_id}
└── services/
    └── landing_page/
        └── optimizer.py      # Modified: inject beacon script before </body>
```

### Pattern 1: Worker with Two Routes (No Framework)
**What:** Single Worker file routing by method + pathname — no npm dependencies needed for 2 routes.
**When to use:** When the Worker has only 2-3 routes. Add Hono if routes grow.

```javascript
// Source: Cloudflare Workers docs + D1 tutorial
// workers/lp-analytics/src/index.js

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const { pathname, method } = { pathname: url.pathname, method: request.method };

    // CORS preflight
    if (method === 'OPTIONS') {
      return corsResponse(null, 204);
    }

    // POST /track — receives beacon from LP page
    if (pathname === '/track' && method === 'POST') {
      return handleTrack(request, env, ctx);
    }

    // GET /analytics/:lp_id — gated by API key, called by Python
    const analyticsMatch = pathname.match(/^\/analytics\/([^/]+)$/);
    if (analyticsMatch && method === 'GET') {
      return handleAnalytics(request, env, analyticsMatch[1]);
    }

    return new Response('Not Found', { status: 404 });
  }
};
```

### Pattern 2: D1 Schema (pageviews + form_submissions)
**What:** Two tables. `pageviews` records every LP visit with referrer. `form_submissions` records each form submit.
**When to use:** Exactly this schema satisfies ANLYT-01 through ANLYT-05.

```sql
-- Source: Official D1 docs pattern
-- migrations/0001_init.sql

CREATE TABLE IF NOT EXISTS pageviews (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  lp_id       TEXT    NOT NULL,           -- run_id of the LP
  referrer    TEXT    DEFAULT '',         -- document.referrer or 'direct'
  user_agent  TEXT    DEFAULT '',
  tracked_at  INTEGER NOT NULL            -- Unix timestamp (ms)
);

CREATE TABLE IF NOT EXISTS form_submissions (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  lp_id       TEXT    NOT NULL,
  tracked_at  INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_pageviews_lp_id ON pageviews(lp_id);
CREATE INDEX IF NOT EXISTS idx_submissions_lp_id ON form_submissions(lp_id);
```

### Pattern 3: Track Endpoint (fire-and-forget with waitUntil)
**What:** Use `ctx.waitUntil()` so the Worker returns 204 immediately and the D1 write continues in the background. This is critical for low-latency beacon responses.

```javascript
// Source: Cloudflare Workers docs — ctx.waitUntil pattern
async function handleTrack(request, env, ctx) {
  const body = await request.json().catch(() => ({}));
  const { lp_id, event, referrer } = body;

  if (!lp_id || !event) {
    return corsResponse(JSON.stringify({ error: 'missing lp_id or event' }), 400);
  }

  const now = Date.now();

  // Non-blocking D1 write — response returns before write completes
  ctx.waitUntil((async () => {
    if (event === 'pageview') {
      await env.DB.prepare(
        'INSERT INTO pageviews (lp_id, referrer, tracked_at) VALUES (?, ?, ?)'
      ).bind(lp_id, referrer || 'direct', now).run();
    } else if (event === 'form_submit') {
      await env.DB.prepare(
        'INSERT INTO form_submissions (lp_id, tracked_at) VALUES (?, ?)'
      ).bind(lp_id, now).run();
    }
  })());

  return corsResponse(null, 204);
}
```

### Pattern 4: Analytics Query Endpoint (API-key gated)
**What:** Python backend calls this endpoint to get per-LP stats. Bearer token gates access.

```javascript
// Source: D1 proxy tutorial pattern
async function handleAnalytics(request, env, lp_id) {
  // Gate with API key
  const auth = request.headers.get('Authorization') || '';
  if (auth !== `Bearer ${env.API_KEY}`) {
    return new Response('Unauthorized', { status: 401 });
  }

  const [pvResult, fsResult] = await env.DB.batch([
    env.DB.prepare('SELECT COUNT(*) as count FROM pageviews WHERE lp_id = ?').bind(lp_id),
    env.DB.prepare('SELECT COUNT(*) as count FROM form_submissions WHERE lp_id = ?').bind(lp_id),
  ]);

  const referrers = await env.DB.prepare(
    'SELECT referrer, COUNT(*) as count FROM pageviews WHERE lp_id = ? GROUP BY referrer ORDER BY count DESC LIMIT 10'
  ).bind(lp_id).all();

  return corsResponse(JSON.stringify({
    lp_id,
    pageviews: pvResult.results[0]?.count ?? 0,
    form_submissions: fsResult.results[0]?.count ?? 0,
    top_referrers: referrers.results,
  }), 200);
}
```

### Pattern 5: Beacon Script Injected into LP HTML
**What:** 10-line script appended before `</body>` in `optimizer.py`. Fires on page load and on form submit. Uses `sendBeacon` for reliability.

```javascript
// Injected by optimizer.py into LP HTML before </body>
// WORKER_URL and LP_ID are filled in by Python at injection time
(function() {
  var w = "WORKER_URL_PLACEHOLDER";
  var id = "LP_ID_PLACEHOLDER";
  // Track pageview
  navigator.sendBeacon(w + "/track", JSON.stringify({
    lp_id: id, event: "pageview",
    referrer: document.referrer || "direct"
  }));
  // Track form submit
  var f = document.querySelector("form");
  if (f) {
    f.addEventListener("submit", function() {
      navigator.sendBeacon(w + "/track", JSON.stringify({
        lp_id: id, event: "form_submit"
      }));
    });
  }
})();
```

### Pattern 6: Python Analytics Client
**What:** `CloudflareAnalyticsClient` wraps the Worker HTTP call. Called by the FastAPI analytics router.

```python
# Source: httpx async docs pattern
# app/services/analytics/client.py
import httpx
import logging
from app.config import get_settings

logger = logging.getLogger(__name__)


class CloudflareAnalyticsClient:
    """HTTP client for querying analytics from the Cloudflare Worker."""

    def __init__(self):
        settings = get_settings()
        self.worker_url = settings.cf_worker_url
        self.api_key = settings.cf_worker_api_key

    async def get_lp_analytics(self, lp_id: str) -> dict:
        """Fetch pageview + form submission counts for an LP."""
        headers = {"Authorization": f"Bearer {self.api_key}"}
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{self.worker_url}/analytics/{lp_id}",
                headers=headers,
            )
            resp.raise_for_status()
            return resp.json()
```

### Pattern 7: wrangler.toml Configuration
```toml
# workers/lp-analytics/wrangler.toml
name = "lp-analytics"
main = "src/index.js"
compatibility_date = "2025-01-01"

[[d1_databases]]
binding = "DB"
database_name = "lp-analytics-db"
database_id = "YOUR_DATABASE_UUID_HERE"
```

### Pattern 8: CORS Helper
**What:** All responses need CORS headers since the LP pages are on different origins than the Worker.

```javascript
// workers/lp-analytics/src/index.js
function corsResponse(body, status = 200) {
  const headers = {
    'Access-Control-Allow-Origin': '*',   // LPs can be on any domain
    'Access-Control-Allow-Methods': 'POST, GET, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type, Authorization',
    'Content-Type': body ? 'application/json' : 'text/plain',
  };
  return new Response(body, { status, headers });
}
```

### Anti-Patterns to Avoid
- **Blocking on D1 write before returning 204:** Adds latency to every pageview; use `ctx.waitUntil()` instead.
- **Hardcoding Worker URL in LP HTML at generation time without a config setting:** Makes it impossible to change the Worker URL without regenerating all LPs — use `settings.cf_worker_url`.
- **Wildcard CORS on the analytics endpoint:** The `/analytics/:lp_id` endpoint should require `Authorization` header, not open CORS — only the `/track` endpoint needs open CORS.
- **Using D1 REST API from Python instead of Worker proxy:** The REST API is slower (50-500ms extra) and requires Cloudflare account tokens; Worker proxy is faster and uses a simple API key.
- **Storing user emails or PII in analytics:** This phase tracks events only — `pageviews` and `form_submissions` store no PII.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---|---|---|---|
| D1 query execution | Custom SQL client | `env.DB.prepare().bind().run()` D1 API | Built into the Worker runtime, no deps needed |
| Migration versioning | Custom SQL runner | `wrangler d1 migrations apply` | Tracks applied migrations in `d1_migrations` table automatically |
| CORS preflight | Custom OPTIONS handler | Pattern above (3 lines) | Browser enforces preflight for cross-origin POST; must respond correctly |
| Secret management | Env vars in wrangler.toml | `wrangler secret put API_KEY` + `.dev.vars` | Secrets in `wrangler.toml` are committed to git and visible |
| Beacon reliability | Plain `fetch()` | `navigator.sendBeacon()` | `sendBeacon` queues the request even if the page unloads; `fetch` can be cancelled |

**Key insight:** The Worker runtime provides D1 bindings natively — no ORM, no connection pooling, no migration library beyond wrangler. Keep the Worker simple.

## Common Pitfalls

### Pitfall 1: CORS Misconfiguration Blocking Beacons
**What goes wrong:** LP pages fail to POST to the Worker; browser blocks the request with CORS error.
**Why it happens:** `navigator.sendBeacon` POSTs JSON — browser sends a CORS preflight OPTIONS request first. If the Worker doesn't handle OPTIONS, it returns 404 and the actual beacon never fires.
**How to avoid:** Always handle `OPTIONS` method and return CORS headers on every response, including 204s and errors.
**Warning signs:** Console error "CORS header 'Access-Control-Allow-Origin' missing"; network tab shows OPTIONS request returning non-2xx.

### Pitfall 2: sendBeacon Requires `Content-Type: text/plain` or Blob
**What goes wrong:** `sendBeacon(url, JSON.stringify(data))` works, but the Worker receives the body as a string. Calling `request.json()` fails if content-type is not set to application/json.
**Why it happens:** `sendBeacon` with a string payload sends `Content-Type: text/plain`. Some Workers throw on `.json()` if content-type is wrong.
**How to avoid:** Use `request.text()` then `JSON.parse()` in the Worker, or use `new Blob([JSON.stringify(data)], {type: 'application/json'})` in the beacon script.
**Warning signs:** Worker returns 500 on `/track`; D1 insert never happens.

### Pitfall 3: D1 Free Tier Write Limits
**What goes wrong:** D1 writes fail silently after hitting 100,000 rows written/day on the free plan.
**Why it happens:** Cloudflare enforces free tier limits as of February 2025.
**How to avoid:** For a smoke-test platform with a small number of LPs, 100K writes/day is generous. Log Worker errors. If hitting limits, upgrade to Workers Paid ($5/mo) or add request deduplication.
**Warning signs:** D1 `run()` returns an error result; no rows appearing in database despite traffic.

### Pitfall 4: Beacon Script Injected After HTML Minification
**What goes wrong:** `optimizer.py` minifies CSS and restructures `<head>` — if beacon injection runs before optimization, the beacon script may be lost.
**Why it happens:** Current `optimize_html()` strips and re-inserts style blocks. If the beacon is in a `<style>` tag or in an unexpected location, it could be affected.
**How to avoid:** Inject the beacon script as the last step in the optimization pipeline — after `optimize_html()` runs, append `<script>` before `</body>`. The beacon injection function should be called from `generate_landing_page()` after step 5 (optimize) and before step 6 (save).
**Warning signs:** LP HTML saved to disk has no beacon script; analytics never populate.

### Pitfall 5: Worker URL Not Configurable
**What goes wrong:** Worker URL is hardcoded in optimizer.py or in the beacon script template. After redeployment or Worker rename, all existing LPs stop tracking.
**Why it happens:** `*.workers.dev` subdomain is fixed by the Worker name, but environment matters (dev vs. prod).
**How to avoid:** Add `cf_worker_url` to `app/config.py` Settings. Pass it through `generate_landing_page()` → `optimizer.py`. Default to empty string for local dev (no tracking).
**Warning signs:** Changing Worker name requires editing source code.

### Pitfall 6: Missing `wrangler d1 migrations apply --remote` Before Deploy
**What goes wrong:** Worker deployed, D1 database created, but tables don't exist. Every `/track` request fails with SQL error.
**Why it happens:** `wrangler d1 migrations apply` defaults to `--local` as of wrangler 3.33.0. You must pass `--remote` to apply to the actual D1 database.
**How to avoid:** Deployment steps: (1) create D1 db, (2) apply migrations `--remote`, (3) deploy Worker.
**Warning signs:** Worker returns 500 on all `/track` requests; D1 console shows empty database.

## Code Examples

Verified patterns from official sources:

### D1 Batch Query (pageviews + submissions in one call)
```javascript
// Source: https://developers.cloudflare.com/d1/worker-api/d1-database/
const [pvResult, fsResult] = await env.DB.batch([
  env.DB.prepare('SELECT COUNT(*) as count FROM pageviews WHERE lp_id = ?').bind(lp_id),
  env.DB.prepare('SELECT COUNT(*) as count FROM form_submissions WHERE lp_id = ?').bind(lp_id),
]);
const pageviews = pvResult.results[0]?.count ?? 0;
const form_submissions = fsResult.results[0]?.count ?? 0;
```

### D1 Insert with waitUntil (non-blocking write)
```javascript
// Source: https://developers.cloudflare.com/workers/runtime-apis/context/
ctx.waitUntil(
  env.DB.prepare('INSERT INTO pageviews (lp_id, referrer, tracked_at) VALUES (?, ?, ?)')
    .bind(lp_id, referrer, Date.now())
    .run()
);
return new Response(null, { status: 204, headers: corsHeaders });
```

### Wrangler D1 Migration Commands
```bash
# Source: https://developers.cloudflare.com/d1/wrangler-commands/

# Create database
npx wrangler d1 create lp-analytics-db

# Create migration file
npx wrangler d1 migrations create lp-analytics-db init_schema

# Apply locally (dev)
npx wrangler d1 migrations apply lp-analytics-db --local

# Apply remotely (production)
npx wrangler d1 migrations apply lp-analytics-db --remote

# Set secret API key (never put in wrangler.toml)
npx wrangler secret put API_KEY
```

### Python Settings additions (app/config.py)
```python
# Source: existing config.py pattern
# Cloudflare Analytics Worker (Phase 18)
cf_worker_url: str = ""        # e.g. https://lp-analytics.yourname.workers.dev
cf_worker_api_key: str = ""    # Bearer token for /analytics/:lp_id endpoint
```

### Beacon Injection in optimizer.py
```python
# Appended to existing optimize_html() pipeline
BEACON_TEMPLATE = """<script>
(function(){{
  var w="{worker_url}";var id="{lp_id}";
  if(!w)return;
  navigator.sendBeacon(w+"/track",JSON.stringify({{lp_id:id,event:"pageview",referrer:document.referrer||"direct"}}));
  var f=document.querySelector("form");
  if(f)f.addEventListener("submit",function(){{navigator.sendBeacon(w+"/track",JSON.stringify({{lp_id:id,event:"form_submit"}}));}});
}})();
</script>"""

def inject_analytics_beacon(html: str, worker_url: str, lp_id: str) -> str:
    """Inject analytics beacon script before </body>. Call AFTER optimize_html()."""
    if not worker_url:
        return html  # skip in local dev
    beacon = BEACON_TEMPLATE.format(worker_url=worker_url, lp_id=lp_id)
    return html.replace('</body>', f'{beacon}</body>', 1)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|---|---|---|---|
| D1 beta (limited) | D1 GA with D1 Insights | 2024 | D1 is production-ready; use migrations, not manual schema files |
| `wrangler d1 execute --local` (old default) | `wrangler d1 migrations apply --local` (new default as of wrangler 3.33.0) | wrangler 3.33.0 | Must pass `--remote` explicitly for production |
| D1 REST API (slow) | Worker proxy pattern (fast) | 2025 (D1 REST API latency improvement) | Worker proxy still preferred — simpler auth, lower latency |
| `fetch()` for analytics beacons | `navigator.sendBeacon()` | Browser standard | `sendBeacon` is now supported in all major browsers and Workers runtime |

**Deprecated/outdated:**
- Manual `schema.sql` with `wrangler d1 execute --file`: Works but doesn't track applied versions. Use `wrangler d1 migrations` instead.
- Python Cloudflare SDK for D1 queries: More complex than a Worker HTTP proxy for this use case.

## Open Questions

1. **Worker subdomain naming**
   - What we know: Worker URL is `https://<name>.<account>.workers.dev` — set by `name` in `wrangler.toml`
   - What's unclear: Account subdomain — need actual Cloudflare account to know the full URL
   - Recommendation: Make Worker URL configurable via `cf_worker_url` env var; document that it must be filled in after first `wrangler deploy`

2. **Beacon CORS: wildcard vs. LP domain allowlist**
   - What we know: Wildcard `Access-Control-Allow-Origin: *` works but is permissive
   - What's unclear: Whether LPs will be on `*.pages.dev` or custom domains (Phase 19 decides this)
   - Recommendation: Start with `*` for `/track` only; the endpoint writes only anonymous event data so open CORS is acceptable. `/analytics/:lp_id` requires Auth header, so CORS scope matters less.

3. **Local dev testing of beacon injection**
   - What we know: `cf_worker_url = ""` means beacon is not injected locally — safe default
   - What's unclear: How to integration-test the full beacon → Worker → D1 flow locally
   - Recommendation: `wrangler dev` starts a local Worker server on `localhost:8787`. Set `CF_WORKER_URL=http://localhost:8787` in `.env` for local end-to-end testing.

## Sources

### Primary (HIGH confidence)
- [Cloudflare D1 Worker API](https://developers.cloudflare.com/d1/worker-api/d1-database/) — prepare, bind, run, batch, exec methods
- [Build an API to access D1](https://developers.cloudflare.com/d1/tutorials/build-an-api-to-access-d1/) — Worker HTTP proxy pattern with bearer auth
- [D1 Migrations docs](https://developers.cloudflare.com/d1/reference/migrations/) — migration workflow and wrangler commands
- [D1 Wrangler Commands](https://developers.cloudflare.com/d1/wrangler-commands/) — create, execute, migrations apply syntax
- [D1 Platform Limits](https://developers.cloudflare.com/d1/platform/limits/) — 50 queries/invocation, 500 MB/db, 10 databases free
- [Workers Free Tier Pricing](https://developers.cloudflare.com/workers/platform/pricing/) — 100K requests/day, D1: 5M reads/100K writes per day free
- [Workers Secrets](https://developers.cloudflare.com/workers/configuration/secrets/) — wrangler secret put, .dev.vars pattern
- [D1 Getting Started](https://developers.cloudflare.com/d1/get-started/) — wrangler.toml D1 binding configuration

### Secondary (MEDIUM confidence)
- [Page View Counter with Workers + D1](https://mrinalcs.github.io/cloudflare-workers-d1-view-counter) — complete working example with D1 insert/update pattern, CORS, and beacon script
- [counterscale GitHub](https://github.com/benvinegar/counterscale) — open-source self-hosted analytics on Cloudflare; reference for patterns

### Tertiary (LOW confidence)
- Community posts on sendBeacon + CORS with Workers — consistent with official behavior; not directly from Cloudflare docs

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — D1 GA, wrangler CLI, Worker JS are official and well-documented
- Architecture: HIGH — Worker proxy pattern is the official recommended approach for external D1 access
- Pitfalls: HIGH for CORS and sendBeacon (community-verified), MEDIUM for free-tier limits (official docs but enforcement behavior evolving)
- Code examples: HIGH — drawn from official D1 tutorial and docs

**Research date:** 2026-02-20
**Valid until:** 2026-03-20 (D1 is GA and stable; wrangler CLI changes infrequently)
