# Pitfalls Research

**Domain:** Adding Cloudflare deployment, LP generation, analytics, and web UI to existing Python/FastAPI app
**Researched:** 2026-02-19
**Confidence:** HIGH

---

## Critical Pitfalls

### Pitfall 1: D1 Free Tier Daily Limits Hit Without Warning

**What goes wrong:**
Analytics collection stops working after hitting D1's daily limits (5 million rows read, 100,000 rows written per day). The D1 API returns errors, and all queries fail until midnight UTC. No graceful degradation, just hard failure.

**Why it happens:**
Developers underestimate analytics volume. A single page view might write 5-10 rows (visitor record, session, page view, referrer, device info). 100K writes = only 10K-20K page views per day before hitting the limit. Free tier has no warning system before limits are hit.

**How to avoid:**
- Design for aggregation at write time: one row per page view, not multiple normalized tables
- Implement client-side debouncing: don't track every scroll/click, only meaningful events
- Add fallback: when D1 returns limit errors, queue events in Durable Objects or log to console
- Monitor usage daily via D1 API to know how close you are to limits
- Consider event sampling: track 10% of traffic once you hit 50% of daily limit

**Warning signs:**
- Analytics Worker returns 500 errors
- D1 API responses contain "daily limits exceeded" messages
- Analytics dashboard shows gaps in data at specific times of day
- Error rate spikes around the same time daily (just before UTC midnight)

**Phase to address:**
Phase 2: Cloudflare Worker Analytics (implement with limits in mind from day 1)

---

### Pitfall 2: Wrangler Secrets Override Dashboard Changes

**What goes wrong:**
You set environment variables in the Cloudflare dashboard for production, then run `wrangler deploy`. Wrangler overwrites your dashboard-configured env vars with whatever is in `wrangler.toml`, breaking production.

**Why it happens:**
Wrangler's default behavior is to treat `wrangler.toml` as the source of truth. If you set `keep_vars = false` (the default), every deployment resets environment variables to what's defined in the config file. Developers forget that local config overwrites remote config.

**How to avoid:**
- Set `keep_vars = true` in `wrangler.toml` to prevent overwriting dashboard-configured vars
- Use `wrangler secret put` for all secrets (API keys, tokens) instead of putting them in `wrangler.toml` or the dashboard
- Create `.dev.vars` for local development secrets (git-ignored)
- Document in README: "Production secrets managed via `wrangler secret put`, never via dashboard or wrangler.toml"
- Use environment-specific configs: `[env.production]` with minimal vars, secrets handled separately

**Warning signs:**
- Production Workers suddenly can't authenticate to external APIs
- Environment variables you set in the dashboard disappear after deployment
- Local development works but production breaks after `wrangler deploy`
- Secrets appear in wrangler.toml (immediate red flag)

**Phase to address:**
Phase 1: LP Generation & Deployment (establish pattern before adding more Workers)

---

### Pitfall 3: FastAPI Jinja2 url_for Generates HTTP Links in HTTPS Production

**What goes wrong:**
Your FastAPI app behind a reverse proxy generates `http://` URLs for static assets and forms when using Jinja2's `url_for()`. Browsers block mixed content, CSS/JS fail to load, forms don't submit.

**Why it happens:**
Uvicorn sees the reverse proxy's HTTP request (proxy → app), not the client's HTTPS request (client → proxy). Without `--proxy-headers`, Uvicorn doesn't know the original request was HTTPS. `url_for()` generates URLs based on what Uvicorn sees: HTTP.

**How to avoid:**
- Run Uvicorn with `--proxy-headers` flag in production
- Configure reverse proxy (nginx, Traefik, Cloudflare Tunnel) to send `X-Forwarded-Proto: https` header
- In Docker Compose production override, set command: `uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers`
- Test with `curl -H "X-Forwarded-Proto: https" http://localhost:8000` to verify url_for generates https
- Use absolute URLs for critical links: `<link rel="stylesheet" href="https://{{ request.url.hostname }}/static/style.css">`

**Warning signs:**
- Browser console shows "Mixed Content" errors
- Static files load in local dev, fail in production
- Forms submit to `http://` and get redirected infinitely
- `request.url.scheme` shows "http" when you expect "https"

**Phase to address:**
Phase 3: Web UI (Jinja2 Templates) - test with production-like proxy setup from start

---

### Pitfall 4: Cloudflare Pages Build Limit Exhaustion (500 builds/month free tier)

**What goes wrong:**
You hit the 500 builds/month limit mid-month. Every git push triggers a build. Development stops because Pages won't build, deploys fail, preview deployments stop working.

**Why it happens:**
Every push to connected repo = 1 build. 500 builds / 30 days = ~16 builds/day. Active development with 5-10 commits/day on main branch + pull request previews = limit hit in 2-3 weeks. Developers don't realize preview deployments for PRs also count toward the build limit.

**How to avoid:**
- Use Direct Upload via `wrangler pages deploy` for development - doesn't count toward build limit
- Connect GitHub only for production branch (main/master)
- Develop locally, test via `wrangler pages dev`, only push when ready
- Use GitHub Actions with build caching to avoid rebuilding on doc-only changes
- Document: "Local development = wrangler, not git push"
- Monitor build count in Cloudflare dashboard weekly

**Warning signs:**
- Builds failing with "monthly limit exceeded" error
- Build queue stops processing
- Can't deploy even though code is ready
- Early in month but approaching 200+ builds already

**Phase to address:**
Phase 1: LP Generation & Deployment (establish Direct Upload workflow to avoid problem)

---

### Pitfall 5: D1 Asynchronous Replication Causes Stale Reads

**What goes wrong:**
User submits waitlist form. Worker writes to D1. User refreshes page to confirm. Admin dashboard shows they're not on the list yet. Replica lag means read replica hasn't received the write.

**Why it happens:**
D1 uses asynchronous replication. Writes go to primary, reads may hit any replica. Replica lag is "arbitrarily out of date" according to Cloudflare docs. Without Sessions API, requests route to different replicas, and newer replica might be behind the one you just wrote to.

**How to avoid:**
- Use D1 Sessions API for all read operations after writes
- Pattern: write to primary, use session bookmark for subsequent reads to ensure sequential consistency
- For waitlist form: redirect to success page (no database read needed)
- For admin dashboard: accept eventual consistency or use Sessions API
- Cache writes client-side: show "pending" state without re-querying database
- Document read-after-write latency expectations (typically <1 second, but not guaranteed)

**Warning signs:**
- Intermittent "record not found" errors right after creating records
- Admin dashboard shows inconsistent data on refresh
- Tests fail randomly when checking writes immediately after creation
- User reports "I just signed up but I'm not on the list"

**Phase to address:**
Phase 2: Cloudflare Worker Analytics (use Sessions API pattern from start)

---

### Pitfall 6: Single-File HTML Landing Pages Bloat Beyond Cloudflare Worker 1MB Script Limit

**What goes wrong:**
You inline all CSS, JavaScript, and base64-encoded images into a single HTML file for easy deployment. The file exceeds 1MB. Cloudflare Workers can't deploy it because script size limit is 1MB on free tier.

**Why it happens:**
Inline CSS frameworks (Tailwind CDN, Bootstrap), JavaScript libraries, hero images as base64, custom fonts embedded - everything adds up fast. A typical React-heavy SPA can easily hit 2-3MB minified. Free tier Workers have a 1MB script size limit.

**How to avoid:**
- Don't inline images: upload to R2 (free tier: 10GB storage) or use Cloudflare Images
- Use external CDN links for frameworks: `<script src="https://unpkg.com/htmx.org"></script>`
- Critical CSS only inline, rest load async: `<link rel="preload" href="/style.css" as="style">`
- Minify HTML/CSS/JS before deploying
- Test: `ls -lh landing-page.html` - keep under 500KB to have headroom
- If must be single-file: use Cloudflare Pages (25MB limit) instead of Workers

**Warning signs:**
- `wrangler deploy` fails with "script too large" error
- Build succeeds but deploy fails
- File size shown in wrangler output is >1000KB
- Bundle size grows every time you add a feature

**Phase to address:**
Phase 1: LP Generation & Deployment (design for size limits from start)

---

### Pitfall 7: Docker Compose Environment Switching Breaks Due to Hardcoded Container Names

**What goes wrong:**
You use `docker compose up` for local dev and want to deploy the same compose file to production server. Container names conflict because `container_name: viralforge-web` is hardcoded. Can't run staging and production on same host.

**Why it happens:**
`docker-compose.yml` has hardcoded `container_name` fields. Docker doesn't allow duplicate container names on the same host. When you try to run multiple environments (dev, staging, prod) or multiple instances, containers fail to start with "name already in use" error.

**How to avoid:**
- Remove `container_name` from docker-compose.yml - let Docker auto-generate names
- Use `docker compose -p <project-name>` to namespace containers: `-p viralforge-dev`, `-p viralforge-prod`
- Use docker contexts: `docker context create production --docker "host=ssh://user@prod-server"`
- Environment-specific compose files: `docker compose -f docker-compose.yml -f docker-compose.prod.yml up`
- Override for local dev only: `docker-compose.override.yml` with container names (git-ignored)
- Document context switching: `docker --context production compose up -d`

**Warning signs:**
- "Container name already in use" errors
- Can't run staging and production simultaneously
- Need to stop local dev to test prod deploy
- Container cleanup required between environment switches

**Phase to address:**
Phase 5: Deployment Flexibility (before any multi-environment usage)

---

### Pitfall 8: Cloudflare Workers Cold Start State Leakage

**What goes wrong:**
Worker sets a module-level variable during request 1. Request 2 from different user sees data from request 1. User A's analytics event includes User B's session ID. Data leak and privacy violation.

**Why it happens:**
Workers reuse isolates across requests for performance. Module-level variables persist between requests. Pattern: `let sessionData = {}` at module level, set during request, next request sees previous request's data. Cloudflare docs: "Variables set during one request are still present during the next."

**How to avoid:**
- NEVER use module-level variables for request state
- Pattern: pass state through function arguments or store on `env` bindings
- Use `export default { async fetch(request, env, ctx) }` - env/ctx are request-scoped
- For analytics: extract all data from current request, don't cache in module scope
- ESLint rule: ban module-level `let`/`var`, only `const` for truly immutable values
- Test: simulate concurrent requests, check for data bleeding

**Warning signs:**
- Analytics shows impossible correlations (one user's data in another's session)
- Intermittent data corruption that's hard to reproduce
- Tests pass individually, fail when run in parallel
- Error: "Cannot perform I/O on behalf of a different request"

**Phase to address:**
Phase 2: Cloudflare Worker Analytics (critical for multi-tenant analytics)

---

### Pitfall 9: Missing CSRF Protection in FastAPI Forms Allows Forgery

**What goes wrong:**
Malicious site hosts `<form action="https://yourapp.com/admin/delete-user" method="POST">`. Admin visits malicious site while logged in. Form auto-submits. Admin's session cookie is sent, action executes, data is deleted.

**Why it happens:**
FastAPI doesn't include CSRF protection by default (unlike Django). Developers familiar with frameworks that include CSRF assume FastAPI has it. HTML forms + session cookies = vulnerable to CSRF without tokens. Jinja2 templates don't auto-generate CSRF tokens.

**How to avoid:**
- Install: `pip install fastapi-csrf-protect`
- Configure CSRF middleware with secret key
- In Jinja2 templates: `<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">`
- For AJAX: send CSRF token in `X-CSRF-Token` header
- Use `CsrfProtect` dependency in route handlers that modify data
- Test: attempt form submission without token, should return 403
- Document: "All state-changing endpoints require CSRF token"

**Warning signs:**
- No CSRF tokens visible in form HTML
- Security audit flags CSRF vulnerability
- Forms work without any hidden fields
- Admin actions can be triggered from external sites

**Phase to address:**
Phase 3: Web UI (Jinja2 Templates) AND Phase 4: Admin Dashboard (before any forms)

---

### Pitfall 10: D1 Migrations Can't Be Rolled Back

**What goes wrong:**
You deploy a migration that adds a new column with a default value. Production breaks because app code expects different schema. You can't rollback - D1 has no rollback command. Must write and deploy reverse migration while app is broken.

**Why it happens:**
D1 doesn't support migration rollback - it's a one-way operation. Cloudflare docs: "D1 does not have built-in rollback support, so you need to create new migrations to undo changes." Automatic rollback only happens if migration SQL fails, not for logical errors. SQLite doesn't support `DROP COLUMN` in older versions, making reversals complex.

**How to avoid:**
- Manual backup before schema changes: `wrangler d1 backup create <db-name>`
- Test migrations on local D1 first: `wrangler d1 migrations apply <db-name> --local`
- Write reverse migration BEFORE applying forward migration
- Use additive changes: add nullable columns, deprecate old ones, remove in later migration
- Blue/green schema pattern: new code supports both old and new schema during transition
- Document rollback procedure: restore from backup, not reverse migration
- Feature flags: deploy code that works with both schemas, then migrate

**Warning signs:**
- No recent D1 backups before major schema change
- Migration applied without testing locally
- No reverse migration written
- Code deployed simultaneously with schema change (tight coupling)

**Phase to address:**
Phase 2: Cloudflare Worker Analytics (before first D1 schema change)

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Using Cloudflare dashboard to set secrets instead of `wrangler secret put` | Faster initial setup, visual interface | Secrets get overwritten on next deploy, not reproducible, not version controlled | Never - use `wrangler secret put` from day 1 |
| Skip D1 Sessions API, accept eventual consistency | Simpler code, fewer dependencies | Stale reads after writes, user confusion, support tickets | Acceptable for read-heavy analytics where staleness doesn't matter |
| Inline all assets in single HTML file instead of using R2/CDN | One-file deploy, no dependencies | Hits 1MB Worker limit, slow page loads, no caching benefits | Only for true micro-sites under 100KB total |
| Use `container_name` in docker-compose.yml | Predictable container names for debugging | Can't run multiple environments, conflicts on multi-instance deploy | Local dev only, never in versioned compose file |
| Store analytics events in module-level array instead of immediate D1 write | Batch writes, reduce D1 API calls | State leakage between requests, data loss on Worker restart | Never - Workers must be stateless |
| Skip CSRF protection "until we add auth" | Faster initial development | Vulnerable from day 1, easy to forget later, security debt | Never for forms - CSRF protection should be in base template |
| Use git-connected Cloudflare Pages for all deploys | Automatic deploys on push | Burns through 500 build/month limit, no control over build timing | Production branch only, use `wrangler pages deploy` for dev |
| Hardcode API URLs in landing page instead of environment variables | Simple to understand, no build step | Must edit HTML to change environments, can't A/B test backends | Static demo sites only, never for production |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| FastAPI → Cloudflare Pages | Trying to deploy FastAPI backend to Pages (Pages is static-only) | Deploy static LPs to Pages, FastAPI backend to separate server, Worker for analytics |
| D1 → FastAPI | Expecting to query D1 from FastAPI backend | D1 bindings only work in Workers, not external apps. Use Workers D1 HTTP API or deploy FastAPI to Workers (Python support in beta) |
| Docker Compose → Production | Using dev compose file in production with hardcoded secrets | Use env_file, separate prod compose override, never commit secrets |
| Wrangler → Multiple environments | Trying to use same `wrangler.toml` for dev/staging/prod | Use `[env.staging]` and `[env.production]` sections with environment-specific bindings |
| Jinja2 → Static assets | Hardcoding `/static/` paths that break when app is behind path prefix | Use `url_for('static', path='style.css')` for all static asset URLs |
| Cloudflare Worker → FastAPI backend | Worker makes direct HTTP calls to backend with API keys in code | Use secrets via `wrangler secret put`, access via `env.API_KEY` binding |
| Single HTML file → Form submission | Form action points to localhost during development | Use relative URLs or environment-injected variables: `action="${API_URL}/submit"` |
| D1 writes → Immediate reads | Writing to D1 then immediately reading, expecting data to be there | Use Sessions API bookmarks for read-after-write consistency |
| Cloudflare Workers free tier → High traffic | Assuming 100K requests/day is 100K unique users | 100K requests = ~1,157 requests/hour. One page view = multiple requests (HTML, CSS, JS, images, analytics). Budget 5-10 requests per page view. |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| N+1 D1 queries in analytics Worker | Analytics endpoint times out, slow dashboard loads | Batch queries, use JOINs, implement pagination at database level | >1000 analytics events queried per request |
| Synchronous D1 writes blocking Worker response | Analytics collection adds 200-500ms to page load | Use `ctx.waitUntil()` for background writes, return response immediately | Any production traffic - impacts UX from day 1 |
| No caching of frequently-accessed D1 data | Every dashboard refresh hits D1, burns read quota | Use Workers KV for frequently-read data, 60s TTL for dashboard stats | >1000 dashboard page views per day |
| Large HTML landing pages served from Workers | First byte time >500ms, poor Core Web Vitals | Use Cloudflare Pages (edge cached) instead of Workers for static HTML | Landing page >100KB |
| Full table scans in D1 without indexes | Analytics queries take >10s, Workers CPU limit exceeded | Add indexes on commonly queried columns: timestamp, user_id, event_type | >10,000 rows in analytics table |
| FastAPI Jinja2 template compilation on every request | Slow page renders, high CPU | Enable template caching in production: `Jinja2Templates(auto_reload=False)` | >100 requests/minute |
| Loading entire dataset into Worker memory | Worker crashes with "memory limit exceeded" | Stream data, paginate, use cursor-based iteration for large datasets | >10MB result set |
| Uncompressed responses from FastAPI | Slow page loads, high bandwidth | Enable gzip middleware: `app.add_middleware(GZipMiddleware, minimum_size=1000)` | Any HTML response >10KB |

---

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Storing Cloudflare API tokens in wrangler.toml | Tokens committed to git, leaked in repository | Use `wrangler secret put` for all secrets, add wrangler.toml to .gitignore if it contains tokens |
| No rate limiting on waitlist form submission endpoint | Spam signups, database bloat, email list poisoning | Implement Cloudflare Workers rate limiting: 5 submissions per IP per hour |
| Missing email validation on waitlist form | Invalid emails in database, bounce rate kills email reputation | Server-side validation: regex + DNS MX lookup for email domain |
| Admin dashboard accessible without authentication | Anyone can view/delete waitlist entries, download user data | Require auth on all `/admin/*` routes, use FastAPI dependencies for auth checks |
| CSRF token not validated on admin actions | Admin session hijacking via CSRF attacks | Use `fastapi-csrf-protect`, validate token on all POST/PUT/DELETE endpoints |
| D1 database accessible without authentication | Public can query/modify analytics data | Use Wrangler auth, never expose D1 binding to public routes, validate requests in Worker |
| Secrets in `.dev.vars` committed to git | Development secrets leaked, can be used to access dev environment | Add `.dev.vars` to .gitignore, document in README to create from example |
| No input sanitization on landing page form | XSS via stored form submissions shown in admin dashboard | Sanitize all user input, escape HTML in Jinja2 templates (auto-escaped by default) |
| Landing page hosted on different origin than API | CORS misconfiguration allows any origin, CSRF vulnerability | Whitelist specific origins in CORS headers, don't use `Access-Control-Allow-Origin: *` |
| Session cookies without `Secure` and `SameSite` flags | Session hijacking, CSRF vulnerability | Set cookie flags: `session_cookie="__Secure-session"; Secure; HttpOnly; SameSite=Lax` |

---

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| No loading state during form submission | User clicks submit, nothing happens, clicks again, double submission | Show spinner, disable submit button immediately, clear on response |
| Landing page shows "Error 500" when Worker hits limits | Users see generic error, no context, assume site is broken | Implement error boundaries, show friendly message: "High traffic, please try again" |
| No email confirmation after waitlist signup | User unsure if signup worked, submits again, creates duplicates | Show success message + send confirmation email immediately |
| Admin dashboard takes >5s to load analytics | Admin abandons page, assumes it's broken | Implement pagination (50 events per page), lazy load charts, show loading skeleton |
| Mobile landing page not responsive | 60% of traffic is mobile, form is unusable, high bounce rate | Mobile-first design, test on real devices, use CSS media queries |
| Form error messages generic: "Invalid input" | User doesn't know what to fix, abandons form | Specific errors inline: "Email format invalid" next to email field |
| No "Back to top" button on long landing page | User scrolls down, can't easily navigate back to signup form | Add sticky CTA button or floating "Sign Up" button visible on scroll |
| Analytics dashboard shows raw timestamps instead of relative time | Admin has to calculate "3 hours ago" mentally, slow to understand trends | Use relative time: "3 hours ago", "Today", "This week" |
| Waitlist confirmation page has no next steps | User confirmed but doesn't know what happens next, sends support emails | Show clear next steps: "We'll email you in 2 weeks when we launch" |

---

## "Looks Done But Isn't" Checklist

- [ ] **Landing Page Deployment:** Often missing environment-specific API endpoint configuration - verify form submission works in production, not just dev
- [ ] **Cloudflare Worker Analytics:** Often missing error handling for D1 limit exhaustion - verify Worker doesn't crash when limits hit, fails gracefully
- [ ] **Admin Dashboard Auth:** Often missing CSRF protection on delete/edit actions - verify all state-changing actions require CSRF token
- [ ] **Docker Compose Production:** Often missing `restart: unless-stopped` policy - verify containers restart after host reboot
- [ ] **D1 Schema Migrations:** Often missing backup before migration - verify backup exists and is restorable before applying schema changes
- [ ] **FastAPI Static Files:** Often missing HTTPS url generation in production - verify all `url_for()` calls generate https:// links behind reverse proxy
- [ ] **Wrangler Secrets Management:** Often missing `.dev.vars` in .gitignore - verify secrets file not committed, documented in README
- [ ] **Waitlist Email Validation:** Often missing server-side validation - verify regex + domain validation, not just client-side HTML5 validation
- [ ] **Cloudflare Workers Environment Vars:** Often missing environment-specific bindings - verify staging Worker uses staging D1, prod uses prod D1
- [ ] **Landing Page Mobile Responsiveness:** Often missing viewport meta tag - verify `<meta name="viewport" content="width=device-width, initial-scale=1">` present
- [ ] **Form Submission Error Handling:** Often missing network error handling - verify form shows error if Worker is down or returns 500
- [ ] **Analytics Session Tracking:** Often missing Sessions API usage - verify read-after-write scenarios don't show stale data

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Hit D1 daily limit mid-day | LOW | 1. Wait until midnight UTC for reset, 2. Implement sampling/debouncing for tomorrow, 3. Consider upgrading to paid plan |
| Deployed migration that broke schema | HIGH | 1. Restore from D1 backup, 2. Write reverse migration, 3. Test locally, 4. Deploy hotfix code that works with old schema |
| Wrangler overwrote production secrets | MEDIUM | 1. Set `keep_vars = true` in wrangler.toml, 2. Re-run `wrangler secret put` for each secret, 3. Redeploy |
| Exceeded Cloudflare Pages build limit | LOW | 1. Use `wrangler pages deploy dist/` for manual deploys, 2. Disconnect GitHub temporarily, 3. Wait until next month for limit reset |
| CSRF vulnerability discovered in production | MEDIUM | 1. Add CSRF protection middleware, 2. Update all forms with tokens, 3. Deploy hotfix, 4. Monitor for abuse |
| Landing page exceeds 1MB Worker limit | MEDIUM | 1. Move images to R2, 2. Use external CDN for libraries, 3. Minify all assets, 4. Or migrate to Pages (25MB limit) |
| Worker state leakage between requests | HIGH | 1. Identify all module-level state, 2. Refactor to request-scoped state, 3. Test concurrency, 4. Deploy fix ASAP |
| Docker container name conflicts in production | LOW | 1. Stop containers, 2. Remove `container_name` from compose file, 3. Use `docker compose -p <project>`, 4. Restart |
| FastAPI generates HTTP URLs in HTTPS prod | MEDIUM | 1. Add `--proxy-headers` to Uvicorn command, 2. Configure proxy to send X-Forwarded-Proto, 3. Restart app |
| D1 replica lag causing stale reads | MEDIUM | 1. Implement D1 Sessions API with bookmarks, 2. Use sequential consistency for critical reads, 3. Accept staleness for non-critical reads |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| D1 Free Tier Daily Limits | Phase 2: Cloudflare Worker Analytics | Load test with 100K writes in <24h, verify graceful degradation |
| Wrangler Secrets Override | Phase 1: LP Generation & Deployment | Deploy twice, verify secrets persist across deploys |
| FastAPI url_for HTTP in HTTPS | Phase 3: Web UI (Jinja2 Templates) | Test behind nginx with X-Forwarded-Proto, verify https:// URLs |
| Pages Build Limit Exhaustion | Phase 1: LP Generation & Deployment | Use Direct Upload for 30 days, verify build count stays <20 |
| D1 Asynchronous Replication | Phase 2: Cloudflare Worker Analytics | Write then immediately read, verify Sessions API returns fresh data |
| Single-File HTML >1MB Limit | Phase 1: LP Generation & Deployment | Build LP, check file size <500KB before deploy |
| Docker Compose Container Names | Phase 5: Deployment Flexibility | Run same compose file on 2 hosts simultaneously, verify no conflicts |
| Workers Cold Start State Leakage | Phase 2: Cloudflare Worker Analytics | Send 100 concurrent requests with different data, verify no cross-contamination |
| Missing CSRF Protection | Phase 3: Web UI + Phase 4: Admin Dashboard | Attempt form POST without CSRF token, verify 403 response |
| D1 Migrations No Rollback | Phase 2: Cloudflare Worker Analytics | Create backup, apply migration, restore backup, verify data intact |

---

## Sources

**Cloudflare Workers & Wrangler:**
- [Wrangler Commands Documentation](https://developers.cloudflare.com/workers/wrangler/commands/)
- [Wrangler Configuration](https://developers.cloudflare.com/workers/wrangler/configuration/)
- [Workers Best Practices](https://developers.cloudflare.com/workers/best-practices/workers-best-practices/)
- [Wrangler Deploy Issues - GitHub](https://github.com/cloudflare/workers-sdk/issues/11368)
- [Workers Platform Limits](https://developers.cloudflare.com/workers/platform/limits/)
- [Workers Pricing](https://developers.cloudflare.com/workers/platform/pricing/)

**Cloudflare Pages:**
- [Pages Platform Limits](https://developers.cloudflare.com/pages/platform/limits/)
- [Cloudflare Pages Free Tier Analysis](https://www.oreateai.com/blog/cloudflare-pages-pricing-2025-unpacking-the-free-plans-limits/c971beb3590767270a7adb31e97eb0d7)
- [Pages Functions CORS Headers](https://developers.cloudflare.com/pages/functions/examples/cors-headers/)

**Cloudflare D1:**
- [D1 Platform Limits](https://developers.cloudflare.com/d1/platform/limits/)
- [D1 Pricing](https://developers.cloudflare.com/d1/platform/pricing/)
- [D1 Global Read Replication](https://developers.cloudflare.com/d1/best-practices/read-replication/)
- [D1 Sequential Consistency Blog](https://blog.cloudflare.com/d1-read-replication-beta/)
- [D1 Migrations](https://developers.cloudflare.com/d1/reference/migrations/)
- [D1 Environments](https://developers.cloudflare.com/d1/configuration/environments/)

**Cloudflare Workers Analytics & Rate Limiting:**
- [Workers Analytics Engine](https://developers.cloudflare.com/analytics/analytics-engine/)
- [Workers Rate Limiting](https://developers.cloudflare.com/workers/runtime-apis/bindings/rate-limit/)
- [Rate Limiting Best Practices](https://developers.cloudflare.com/waf/rate-limiting-rules/best-practices/)

**Cloudflare Secrets & Environment Variables:**
- [Workers Environment Variables](https://developers.cloudflare.com/workers/configuration/environment-variables/)
- [Workers Secrets](https://developers.cloudflare.com/workers/configuration/secrets/)
- [Workers Environments](https://developers.cloudflare.com/workers/wrangler/environments/)

**FastAPI & Jinja2:**
- [FastAPI Templates Documentation](https://fastapi.tiangolo.com/advanced/templates/)
- [FastAPI Static Files](https://fastapi.tiangolo.com/tutorial/static-files/)
- [FastAPI url_for HTTPS Issue - GitHub](https://github.com/fastapi/fastapi/issues/5899)
- [FastAPI CSRF Protection](https://github.com/aekasitt/fastapi-csrf-protect)
- [FastAPI CSRF Implementation Guide](https://community.latenode.com/t/how-to-properly-implement-csrf-protection-in-fastapi-with-jinja2-templates/20568)
- [FastAPI Best Practices 2026](https://fastlaunchapi.dev/blog/fastapi-best-practices-production-2026)
- [FastAPI JWT Authentication](https://testdriven.io/blog/fastapi-jwt-auth/)

**Docker Compose:**
- [Docker Compose Production Guide](https://docs.docker.com/compose/how-tos/production/)
- [Docker Compose Environment Files](https://oneuptime.com/blog/post/2026-01-25-docker-compose-environment-files/view)
- [Docker Context Multi-Host Management](https://oneuptime.com/blog/post/2026-02-08-how-to-use-docker-context-for-multi-host-management/view)
- [Docker Compose Best Practices](https://release.com/blog/6-docker-compose-best-practices-for-dev-and-prod)

**HTML Forms & Validation:**
- [MDN Client-Side Form Validation](https://developer.mozilla.org/en-US/docs/Learn_web_development/Extensions/Forms/Form_validation)
- [HTML Constraint Validation API](https://developer.mozilla.org/en-US/docs/Web/HTML/Guides/Constraint_validation)
- [MDN Sending Forms via JavaScript](https://developer.mozilla.org/en-US/docs/Learn_web_development/Extensions/Forms/Sending_forms_through_JavaScript)
- [Responsive Web Design 2026 Trends](https://www.keelis.com/blog/responsive-web-design-in-2026:-trends-and-best-practices)
- [Waitlist Form Best Practices](https://www.feathery.io/blog/waitlist-forms)

---

*Pitfalls research for: ViralForge Milestone - Adding LP Generation, Cloudflare Deployment, Analytics, and Web UI*
*Researched: 2026-02-19*
*Focus: Integration pitfalls when adding these features to existing Python/FastAPI app with Docker Compose*
