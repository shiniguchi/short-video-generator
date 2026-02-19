# Architecture Research: LP Generation + Cloudflare Integration

**Domain:** Adding LP generation, Cloudflare deployment, Worker + D1 analytics, and web UI to existing ViralForge
**Researched:** 2026-02-19
**Confidence:** HIGH

## Executive Summary

This architecture integrates four new capabilities into ViralForge's existing FastAPI + Celery stack:

1. **LP (Landing Page) Generation** — Single-file HTML pages created via Jinja2 templates
2. **Cloudflare Pages Deployment** — Automated deployment of generated LPs via Python SDK
3. **Cloudflare Worker + D1 Analytics** — Edge-based analytics stored in D1, accessed via HTTP proxy
4. **Web UI** — Jinja2-based admin interface in the same FastAPI app

**Key Decision:** Keep everything Python-first. Cloudflare Workers exist as separate deployment units (TypeScript/JavaScript) but are accessed via HTTP from Python. No hybrid Python Worker architecture needed.

---

## Current Architecture Overview

```
┌────────────────────────────────────────────────────────────────┐
│                         Docker Compose                         │
├────────────────────────────────────────────────────────────────┤
│  ┌──────────┐  ┌───────────┐  ┌──────────┐  ┌──────────────┐  │
│  │ FastAPI  │  │  Celery   │  │PostgreSQL│  │    Redis     │  │
│  │   Web    │  │  Worker   │  │    DB    │  │    Broker    │  │
│  └────┬─────┘  └─────┬─────┘  └─────┬────┘  └──────┬───────┘  │
│       │              │              │               │          │
├───────┴──────────────┴──────────────┴───────────────┴──────────┤
│                    Persistent Volumes                          │
│       ┌───────────────┐    ┌────────────────────┐              │
│       │ postgres_data │    │ output/ (file-based│              │
│       └───────────────┘    │  video artifacts)  │              │
│                            └────────────────────┘              │
└────────────────────────────────────────────────────────────────┘
```

**Current Component Responsibilities:**

| Component | Responsibility | Implementation |
|-----------|----------------|----------------|
| FastAPI Web | REST API endpoints, request handling | Uvicorn ASGI server, SQLAlchemy async |
| Celery Worker | Async task execution (trend collection, video gen) | Celery with thread pool, Redis broker |
| PostgreSQL | Job/Video/Script/Trend storage | Async SQLAlchemy, Alembic migrations |
| Redis | Task queue broker + result backend | Redis 7 Alpine |
| Provider Abstraction | Swappable AI services (mock/real) | ABC base classes + factory functions |

**Existing Patterns:**
- **Service Layer:** `app/services/` (video_generator, voiceover_generator, etc.)
- **Provider Pattern:** `base.py` (ABC) + `mock.py` + real providers (HeyGen, Gemini, etc.)
- **Factory Functions:** `get_video_generator()`, `get_voiceover_generator()` select provider from settings
- **Async DB:** All database access via `async with get_session()` context manager
- **File Output:** Generated videos → `output/review/`, approved → `output/approved/`

---

## New Architecture: Integration Points

```
┌──────────────────────────────────────────────────────────────────────────┐
│                          Existing FastAPI App                            │
├──────────────────────────────────────────────────────────────────────────┤
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │                     NEW: Jinja2 Web UI Layer                       │  │
│  │  /ui/dashboard  /ui/videos  /ui/jobs  /ui/landing-pages            │  │
│  │  (Jinja2 templates + StaticFiles for CSS/JS)                       │  │
│  └────────────────────────────────────────────────────────────────────┘  │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │                   Existing REST API Layer                          │  │
│  │  /api/generate  /api/videos  /api/jobs  /api/trends               │  │
│  └────────────────────────────────────────────────────────────────────┘  │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │                     NEW: LP + Deployment API                       │  │
│  │  /api/landing-pages  /api/lp-generate  /api/lp-deploy             │  │
│  └────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    ▼                               ▼
    ┌────────────────────────────┐    ┌────────────────────────────┐
    │   NEW: LP Generator Task   │    │  NEW: LP Deployment Task   │
    │    (Celery, sync task)     │    │   (Celery, sync task)      │
    │  - Load LandingPage record │    │  - Upload to CF Pages via  │
    │  - Render Jinja2 template  │    │    cloudflare-python SDK   │
    │  - Inline CSS, save HTML   │    │  - Update deployment_url   │
    └────────────┬───────────────┘    └────────────┬───────────────┘
                 │                                  │
                 ▼                                  ▼
      output/landing-pages/              Cloudflare Pages
         (single-file HTML)              (https://{slug}.pages.dev)
                                                   │
                                                   ▼
                                         ┌──────────────────────┐
                                         │  Cloudflare Worker   │
                                         │  (JavaScript/TS)     │
                                         │  - Track page views  │
                                         │  - Write to D1       │
                                         └──────────────────────┘
                                                   │
                                                   ▼
                                         ┌──────────────────────┐
                                         │   D1 Database        │
                                         │  (SQLite @ edge)     │
                                         │  Table: page_views   │
                                         └──────────────────────┘
                                                   │
                                                   ▼
                                         ┌──────────────────────┐
                                         │  Worker HTTP Proxy   │
                                         │  (exposes /analytics)│
                                         └──────────┬───────────┘
                                                    │
                            ┌───────────────────────┘
                            ▼
              ┌──────────────────────────────┐
              │  FastAPI /api/analytics      │
              │  - HTTP GET to Worker proxy  │
              │  - Fetch D1 data from edge   │
              └──────────────────────────────┘
```

---

## Component Integration Design

### 1. LP Generation Service

**Integration Approach:** New service following existing provider pattern

**Files:**
- `app/services/landing_page_generator/generator.py` — Jinja2 template rendering
- `app/services/landing_page_generator/base.py` — ABC for future template engines
- `app/templates/landing_pages/base.html.jinja2` — Base template with inline CSS
- `app/models.py` — Add `LandingPage` model

**Why This Approach:**
- Follows existing `app/services/` pattern
- Jinja2 already used for FastAPI templates
- Single-file HTML with inline CSS = portable, self-contained
- Can swap template engines later (ABC pattern)

**Database Schema:**
```python
class LandingPage(Base):
    __tablename__ = "landing_pages"

    id = Column(Integer, primary_key=True)
    video_id = Column(Integer, ForeignKey("videos.id"))
    slug = Column(String(255), unique=True)  # URL slug
    title = Column(String(500))
    description = Column(Text)
    html_path = Column(String(1000))  # output/landing-pages/{slug}.html
    deployment_url = Column(String(1000))  # https://{slug}.pages.dev
    status = Column(String(50), default="generated")  # generated, deployed, archived
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    deployed_at = Column(DateTime(timezone=True))
    extra_data = Column(JSON)  # Template variables, analytics summary
```

**Implementation:**
```python
# app/services/landing_page_generator/generator.py
from jinja2 import Environment, FileSystemLoader
from pathlib import Path
from uuid import uuid4

class LandingPageGenerator:
    def __init__(self, templates_dir: str = "app/templates/landing_pages"):
        self.env = Environment(loader=FileSystemLoader(templates_dir))

    def generate(
        self,
        video_path: str,
        title: str,
        description: str,
        cta_text: str = "Watch Now",
        output_dir: str = "output/landing-pages"
    ) -> str:
        """Generate single-file HTML landing page.

        Returns:
            Path to generated HTML file
        """
        template = self.env.get_template("base.html.jinja2")

        slug = str(uuid4())[:8]
        html = template.render(
            title=title,
            description=description,
            video_path=video_path,
            cta_text=cta_text,
            slug=slug
        )

        output_path = Path(output_dir) / f"{slug}.html"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html)

        return str(output_path)
```

**Celery Task:**
```python
# app/tasks.py
@celery_app.task(bind=True, name='app.tasks.generate_landing_page_task')
def generate_landing_page_task(self, video_id: int):
    """Generate landing page for approved video (SYNC task)."""
    from app.services.landing_page_generator.generator import LandingPageGenerator
    # ... load video, generate LP, save LandingPage record
```

**Why Sync Not Async:**
- LP generation is I/O-light (template rendering + file write)
- No external API calls, no network latency
- Celery task = already async from API perspective
- Keep simple, avoid async complexity for file operations

---

### 2. Cloudflare Pages Deployment

**Integration Approach:** New Celery task using `cloudflare-python` SDK

**Dependencies:**
```txt
# requirements.txt
cloudflare>=5.0.0-beta.1  # Official Python SDK
```

**Configuration:**
```python
# app/config.py
class Settings(BaseSettings):
    # ... existing settings

    # Cloudflare
    cloudflare_api_token: str = ""
    cloudflare_account_id: str = ""
    cloudflare_pages_project: str = "viralforge-lps"
```

**Implementation:**
```python
# app/services/cloudflare_deployer.py
from cloudflare import Cloudflare
from pathlib import Path

class CloudflareDeployer:
    def __init__(self, api_token: str, account_id: str, project_name: str):
        self.client = Cloudflare(api_token=api_token)
        self.account_id = account_id
        self.project_name = project_name

    def deploy_landing_page(self, html_path: str, slug: str) -> str:
        """Deploy single HTML file to Cloudflare Pages.

        Returns:
            Deployment URL (e.g., https://{slug}.pages.dev)
        """
        # Read HTML file
        html_content = Path(html_path).read_text()

        # Create deployment via Direct Upload
        # Note: CF Pages API expects a tarball or zip, OR use Wrangler CLI
        # For single HTML, easier to use wrangler publish via subprocess
        # OR use Pages Direct Upload API with files dict

        deployment = self.client.pages.projects.deployments.create(
            project_name=self.project_name,
            # ... deployment config
        )

        return deployment.url
```

**Alternative: Wrangler CLI via subprocess**
```python
# More reliable for file uploads
import subprocess

def deploy_via_wrangler(html_path: str, slug: str) -> str:
    """Deploy using Wrangler CLI (must be installed in Docker image)."""
    result = subprocess.run(
        ["wrangler", "pages", "deploy", html_path, "--project-name", f"lp-{slug}"],
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        raise Exception(f"Wrangler deploy failed: {result.stderr}")
    # Parse deployment URL from stdout
    return f"https://lp-{slug}.pages.dev"
```

**Celery Task:**
```python
# app/tasks.py
@celery_app.task(bind=True, name='app.tasks.deploy_landing_page_task')
def deploy_landing_page_task(self, landing_page_id: int):
    """Deploy landing page to Cloudflare Pages (SYNC task)."""
    from app.services.cloudflare_deployer import CloudflareDeployer
    # ... load LandingPage, deploy, update deployment_url + deployed_at
```

**Why Separate Task:**
- Deployment can fail (network, CF API rate limits)
- Want retry + backoff logic
- User can generate LP locally, deploy later
- Decouples generation from hosting

---

### 3. Cloudflare Worker + D1 Analytics

**Architecture Decision:** Workers are SEPARATE deployment units (JavaScript/TypeScript), NOT Python Workers

**Why Not Python Workers:**
- Python Workers are beta, limited ecosystem
- D1 binding from Python Workers is experimental
- JavaScript/TypeScript Workers are mature, battle-tested
- FastAPI backend doesn't need to run at edge

**Worker Structure:**
```
cloudflare-worker/           # NEW: Separate directory at project root
├── wrangler.toml            # Worker configuration
├── src/
│   └── index.ts             # Worker entry point
├── schema.sql               # D1 database schema
└── package.json             # TypeScript dependencies
```

**Worker Implementation:**
```typescript
// cloudflare-worker/src/index.ts
export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);

    // Track page view
    if (url.pathname.startsWith('/track')) {
      const slug = url.searchParams.get('slug');
      if (!slug) return new Response('Missing slug', { status: 400 });

      await env.DB.prepare(
        'INSERT INTO page_views (slug, ip, user_agent, created_at) VALUES (?, ?, ?, ?)'
      ).bind(slug, request.headers.get('CF-Connecting-IP'), request.headers.get('User-Agent'), Date.now()).run();

      return new Response('OK', { status: 200 });
    }

    // Analytics proxy endpoint (for Python backend)
    if (url.pathname === '/analytics') {
      const slug = url.searchParams.get('slug');
      const { results } = await env.DB.prepare(
        'SELECT COUNT(*) as views FROM page_views WHERE slug = ?'
      ).bind(slug).all();

      return new Response(JSON.stringify(results), {
        headers: { 'Content-Type': 'application/json' }
      });
    }

    return new Response('Not Found', { status: 404 });
  }
};
```

**D1 Schema:**
```sql
-- cloudflare-worker/schema.sql
CREATE TABLE page_views (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  slug TEXT NOT NULL,
  ip TEXT,
  user_agent TEXT,
  created_at INTEGER NOT NULL
);

CREATE INDEX idx_slug ON page_views(slug);
```

**Wrangler Configuration:**
```toml
# cloudflare-worker/wrangler.toml
name = "viralforge-analytics"
main = "src/index.ts"
compatibility_date = "2026-02-19"

[[d1_databases]]
binding = "DB"
database_name = "viralforge_analytics"
database_id = "<D1_DATABASE_ID>"

[observability]
enabled = true
```

**Deployment:**
```bash
# From project root
cd cloudflare-worker
npm install
wrangler d1 create viralforge_analytics  # First time only
wrangler d1 execute viralforge_analytics --file=schema.sql  # Create tables
wrangler deploy  # Deploy Worker
```

**Python Backend Integration:**
```python
# app/services/analytics_fetcher.py
import httpx
from app.config import get_settings

class AnalyticsFetcher:
    def __init__(self):
        self.worker_url = "https://viralforge-analytics.{your-subdomain}.workers.dev"

    async def get_page_views(self, slug: str) -> int:
        """Fetch page view count from Cloudflare Worker."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.worker_url}/analytics",
                params={"slug": slug}
            )
            response.raise_for_status()
            data = response.json()
            return data[0]["views"] if data else 0

# app/api/routes.py
@router.get("/landing-pages/{slug}/analytics")
async def get_landing_page_analytics(slug: str, _: str = Depends(require_api_key)):
    """Fetch analytics for landing page from Cloudflare D1 via Worker proxy."""
    from app.services.analytics_fetcher import AnalyticsFetcher

    fetcher = AnalyticsFetcher()
    views = await fetcher.get_page_views(slug)

    return {"slug": slug, "page_views": views}
```

**Why HTTP Proxy Pattern:**
- D1 has no direct Python client (Workers-only binding)
- Worker exposes `/analytics` HTTP endpoint
- Python backend calls HTTP endpoint like any API
- Simple, reliable, well-understood pattern
- Worker handles authentication via API tokens if needed

---

### 4. Web UI Layer

**Integration Approach:** Jinja2 templates in same FastAPI app, separate route prefix

**Project Structure:**
```
app/
├── api/
│   └── routes.py          # Existing: /api/* (JSON responses)
├── ui/                    # NEW: Web UI routes
│   ├── __init__.py
│   └── pages.py           # /ui/* (HTML responses via Jinja2)
├── templates/             # NEW: Jinja2 templates
│   ├── base.html.jinja2   # Base layout with nav
│   ├── dashboard.html.jinja2
│   ├── videos.html.jinja2
│   ├── jobs.html.jinja2
│   └── landing_pages.html.jinja2
├── static/                # NEW: CSS, JS, images
│   ├── css/
│   │   └── main.css
│   └── js/
│       └── app.js
└── main.py                # Mount UI routes + static files
```

**Implementation:**
```python
# app/ui/pages.py
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_session
from app.models import Video, Job, LandingPage

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, session: AsyncSession = Depends(get_session)):
    """Render dashboard with job/video stats."""
    # Query stats
    jobs_total = await session.scalar(select(func.count(Job.id)))
    videos_total = await session.scalar(select(func.count(Video.id)))

    return templates.TemplateResponse("dashboard.html.jinja2", {
        "request": request,
        "jobs_total": jobs_total,
        "videos_total": videos_total
    })

@router.get("/videos", response_class=HTMLResponse)
async def videos_list(request: Request, session: AsyncSession = Depends(get_session)):
    """Render video gallery with approve/reject actions."""
    query = select(Video).order_by(Video.created_at.desc()).limit(50)
    result = await session.execute(query)
    videos = result.scalars().all()

    return templates.TemplateResponse("videos.html.jinja2", {
        "request": request,
        "videos": videos
    })

@router.get("/landing-pages", response_class=HTMLResponse)
async def landing_pages_list(request: Request, session: AsyncSession = Depends(get_session)):
    """Render landing page manager."""
    query = select(LandingPage).order_by(LandingPage.created_at.desc())
    result = await session.execute(query)
    lps = result.scalars().all()

    return templates.TemplateResponse("landing_pages.html.jinja2", {
        "request": request,
        "landing_pages": lps
    })
```

```python
# app/main.py
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.api.routes import router as api_router
from app.ui.pages import router as ui_router

app = FastAPI(title="ViralForge")

# Mount API routes (existing)
app.include_router(api_router, prefix="/api", tags=["API"])

# Mount UI routes (new)
app.include_router(ui_router, prefix="/ui", tags=["Web UI"])

# Mount static files (new)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
```

**Base Template:**
```html
<!-- app/templates/base.html.jinja2 -->
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}ViralForge{% endblock %}</title>
    <link rel="stylesheet" href="/static/css/main.css">
    {% block extra_head %}{% endblock %}
</head>
<body>
    <nav>
        <a href="/ui/dashboard">Dashboard</a>
        <a href="/ui/videos">Videos</a>
        <a href="/ui/jobs">Jobs</a>
        <a href="/ui/landing-pages">Landing Pages</a>
    </nav>

    <main>
        {% block content %}{% endblock %}
    </main>

    <script src="/static/js/app.js"></script>
    {% block extra_js %}{% endblock %}
</body>
</html>
```

**Why This Approach:**
- Follows FastAPI + Jinja2 standard pattern
- No separate frontend build step
- Server-side rendering = fast initial load
- Can add HTMX for dynamic updates later
- Keeps everything in one deployment unit

**Alternative Considered: Separate React SPA**
- Pros: Richer interactions, client-side state
- Cons: Separate build pipeline, CORS config, more complexity
- Verdict: Overkill for admin UI, save for future if needed

---

## Data Flow Diagrams

### LP Generation + Deployment Flow

```
[User clicks "Create LP" in Web UI]
    │
    ▼
[POST /api/lp-generate with video_id]
    │
    ▼
[API creates LandingPage record, queues generate_landing_page_task]
    │
    ▼
[Celery Worker: generate_landing_page_task]
    │
    ├─→ Load Video record
    ├─→ Render Jinja2 template (title, description, video embed)
    ├─→ Inline CSS for self-contained HTML
    ├─→ Save to output/landing-pages/{slug}.html
    └─→ Update LandingPage.html_path, status="generated"
    │
    ▼
[User clicks "Deploy" in Web UI]
    │
    ▼
[POST /api/lp-deploy with landing_page_id]
    │
    ▼
[API queues deploy_landing_page_task]
    │
    ▼
[Celery Worker: deploy_landing_page_task]
    │
    ├─→ Load LandingPage record
    ├─→ Upload HTML to Cloudflare Pages (via SDK or Wrangler CLI)
    ├─→ Receive deployment URL
    └─→ Update LandingPage.deployment_url, deployed_at, status="deployed"
    │
    ▼
[Landing Page live at https://{slug}.pages.dev]
```

### Analytics Tracking Flow

```
[User visits https://{slug}.pages.dev]
    │
    ▼
[Cloudflare Pages serves static HTML]
    │
    ▼
[HTML includes <script> that calls Worker /track endpoint]
    │
    ▼
[Cloudflare Worker receives /track?slug={slug}]
    │
    ├─→ Extract IP, User-Agent from request headers
    ├─→ INSERT INTO page_views (slug, ip, user_agent, created_at)
    └─→ Return 200 OK
    │
    ▼
[D1 Database stores page view]
    │
    │
    ▼
[Admin visits /ui/landing-pages in Web UI]
    │
    ▼
[GET /api/landing-pages/{slug}/analytics]
    │
    ├─→ HTTP GET to Worker /analytics?slug={slug}
    ├─→ Worker queries D1: SELECT COUNT(*) FROM page_views WHERE slug=?
    ├─→ Worker returns JSON: {"views": 123}
    └─→ API returns analytics to Web UI
    │
    ▼
[Web UI displays page view count]
```

---

## File Organization

### New Files to Create

```
app/
├── models.py                           # MODIFY: Add LandingPage model
├── config.py                           # MODIFY: Add cloudflare_* settings
├── tasks.py                            # MODIFY: Add LP generation/deployment tasks
├── api/
│   └── routes.py                       # MODIFY: Add /api/lp-*, /api/analytics
├── ui/                                 # NEW: Web UI routes
│   ├── __init__.py
│   └── pages.py
├── templates/                          # NEW: Jinja2 templates
│   ├── base.html.jinja2
│   ├── dashboard.html.jinja2
│   ├── videos.html.jinja2
│   ├── jobs.html.jinja2
│   ├── landing_pages.html.jinja2
│   └── landing_pages/                  # LP generation templates
│       └── base.html.jinja2
├── static/                             # NEW: Static assets
│   ├── css/
│   │   └── main.css
│   └── js/
│       └── app.js
├── services/
│   ├── landing_page_generator/         # NEW: LP generation service
│   │   ├── __init__.py
│   │   ├── base.py                     # ABC for template engines
│   │   └── generator.py                # Jinja2 implementation
│   ├── cloudflare_deployer.py          # NEW: CF Pages deployment
│   └── analytics_fetcher.py            # NEW: Fetch D1 analytics via Worker

cloudflare-worker/                      # NEW: Separate directory at root
├── wrangler.toml
├── src/
│   └── index.ts
├── schema.sql
├── package.json
└── tsconfig.json

output/
└── landing-pages/                      # NEW: Generated HTML files
    └── {slug}.html
```

### Modified Files

| File | Modification |
|------|--------------|
| `app/models.py` | Add `LandingPage` model |
| `app/config.py` | Add `cloudflare_api_token`, `cloudflare_account_id`, `cloudflare_pages_project` |
| `app/tasks.py` | Add `generate_landing_page_task`, `deploy_landing_page_task` |
| `app/api/routes.py` | Add `/api/lp-generate`, `/api/lp-deploy`, `/api/landing-pages/{slug}/analytics` |
| `app/main.py` | Mount UI router, mount static files |
| `requirements.txt` | Add `cloudflare>=5.0.0-beta.1`, `jinja2` (already present) |
| `Dockerfile` | Install Node.js + Wrangler CLI (for deployment task) |
| `alembic/` | Migration to add `landing_pages` table |

---

## Build Order (Integration Sequence)

### Phase 1: LP Generation (Standalone)
**Goal:** Generate single-file HTML landing pages locally

1. Add `LandingPage` model to `app/models.py`
2. Create Alembic migration for `landing_pages` table
3. Create `app/services/landing_page_generator/` (base + generator)
4. Create `app/templates/landing_pages/base.html.jinja2`
5. Add `generate_landing_page_task` to `app/tasks.py`
6. Add `/api/lp-generate` endpoint to `app/api/routes.py`
7. Test: Generate LP for existing video, verify HTML in `output/landing-pages/`

**Why First:** No external dependencies, can be tested locally immediately

### Phase 2: Web UI
**Goal:** View/manage videos, jobs, LPs in browser

1. Create `app/ui/pages.py` with routes
2. Create `app/templates/` (base, dashboard, videos, jobs, landing_pages)
3. Create `app/static/` (CSS, JS)
4. Mount UI router in `app/main.py`
5. Add StaticFiles mount for `/static`
6. Test: Browse to `/ui/dashboard`, see job stats

**Why Second:** Visual interface for testing LP generation, no Cloudflare account needed yet

### Phase 3: Cloudflare Worker + D1 Analytics
**Goal:** Track page views at edge

1. Create `cloudflare-worker/` directory at root
2. Write `src/index.ts` with `/track` and `/analytics` endpoints
3. Write `schema.sql` for `page_views` table
4. Configure `wrangler.toml` with D1 binding
5. Deploy Worker + D1 database to Cloudflare
6. Update LP template to include analytics `<script>` tag
7. Add `app/services/analytics_fetcher.py`
8. Add `/api/landing-pages/{slug}/analytics` endpoint
9. Test: Open generated HTML locally, verify `/track` call (will fail until deployed)

**Why Third:** Can develop Worker independently, test locally with `wrangler dev`

### Phase 4: Cloudflare Pages Deployment
**Goal:** Deploy LPs to public URLs

1. Add `cloudflare_*` settings to `app/config.py`
2. Create `app/services/cloudflare_deployer.py`
3. Add `deploy_landing_page_task` to `app/tasks.py`
4. Add `/api/lp-deploy` endpoint
5. Update Dockerfile to install Node.js + Wrangler CLI
6. Add "Deploy" button to `/ui/landing-pages` UI
7. Test: Deploy LP, verify live at `https://{slug}.pages.dev`

**Why Last:** Requires Cloudflare account + API token, most complex integration

---

## Local-to-Hosted Switchability

### Configuration Strategy

```python
# app/config.py
class Settings(BaseSettings):
    # Deployment mode
    deployment_mode: str = "local"  # local, docker, hosted

    # Cloudflare (only needed for hosted mode)
    cloudflare_api_token: str = ""
    cloudflare_account_id: str = ""
    cloudflare_pages_project: str = "viralforge-lps"
    cloudflare_worker_url: str = ""

    # Local fallbacks
    local_lp_base_url: str = "http://localhost:8000/static/landing-pages"
```

### Conditional Logic

```python
# app/services/cloudflare_deployer.py
class CloudflareDeployer:
    def __init__(self):
        self.settings = get_settings()

    def deploy_landing_page(self, html_path: str, slug: str) -> str:
        if self.settings.deployment_mode == "local":
            # Local mode: Copy to static/ and return local URL
            shutil.copy(html_path, f"app/static/landing-pages/{slug}.html")
            return f"{self.settings.local_lp_base_url}/{slug}.html"

        elif self.settings.deployment_mode in ("docker", "hosted"):
            # Hosted mode: Deploy to Cloudflare Pages
            return self._deploy_to_cloudflare(html_path, slug)
```

### Analytics Fetcher Fallback

```python
# app/services/analytics_fetcher.py
class AnalyticsFetcher:
    async def get_page_views(self, slug: str) -> int:
        settings = get_settings()

        if settings.deployment_mode == "local":
            # No analytics in local mode
            return 0

        else:
            # Fetch from Cloudflare Worker
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{settings.cloudflare_worker_url}/analytics",
                    params={"slug": slug}
                )
                data = response.json()
                return data[0]["views"] if data else 0
```

### Environment Variables

**Local development (`.env`):**
```bash
DEPLOYMENT_MODE=local
LOCAL_LP_BASE_URL=http://localhost:8000/static/landing-pages
```

**Docker Compose (production-like):**
```yaml
# docker-compose.yml
environment:
  - DEPLOYMENT_MODE=docker
  - CLOUDFLARE_API_TOKEN=${CLOUDFLARE_API_TOKEN}
  - CLOUDFLARE_ACCOUNT_ID=${CLOUDFLARE_ACCOUNT_ID}
  - CLOUDFLARE_WORKER_URL=https://viralforge-analytics.your-subdomain.workers.dev
```

**Hosted (Cloud Run, Fly.io, etc.):**
```bash
DEPLOYMENT_MODE=hosted
CLOUDFLARE_API_TOKEN=<secret>
CLOUDFLARE_ACCOUNT_ID=<secret>
CLOUDFLARE_WORKER_URL=https://viralforge-analytics.your-subdomain.workers.dev
```

---

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| 0-1k LPs/month | Current design is fine. Single FastAPI instance, Celery worker handles LP gen/deploy sequentially. D1 free tier = 5M reads/day. |
| 1k-10k LPs/month | Add Celery worker concurrency (multiple containers). Use CF Pages batch upload API if available. D1 still within free tier. |
| 10k+ LPs/month | Move LP generation to dedicated worker queue. Consider CF Pages API rate limits (may need backoff/retry). Upgrade D1 to paid tier if >5M reads/day. |

### First Bottleneck: Cloudflare Pages API Rate Limits

**Problem:** CF Pages API has rate limits (exact limits not publicly documented, likely ~10-100 deploys/min)

**Solution:**
1. Add retry logic with exponential backoff to `deploy_landing_page_task`
2. Use Celery rate limiting: `@task(rate_limit='10/m')` to cap deploys
3. Batch deploy if CF Pages supports it (upload multiple files in one deployment)

### Second Bottleneck: D1 Read Performance

**Problem:** D1 free tier = 5M reads/day. At 10k LPs with 100 views each = 1M views/day. Admin checking analytics = 1 read per LP per check.

**Solution:**
1. Cache analytics in PostgreSQL (sync from D1 hourly via Celery Beat task)
2. Use D1 query result caching (built-in, configurable in Worker)
3. Aggregate analytics daily instead of real-time queries

---

## Anti-Patterns

### Anti-Pattern 1: Deploying Each LP to Separate CF Pages Project

**What people might do:** Create new Cloudflare Pages project for each landing page

**Why it's wrong:**
- CF Pages has project limits (100 projects per account on free tier)
- Each project needs separate DNS, SSL, config
- Deployment complexity scales linearly with LP count

**Do this instead:**
- Use **one CF Pages project** for all LPs
- Deploy LPs to different paths: `/{slug}/index.html`
- Or use custom domains with wildcard routing

### Anti-Pattern 2: Storing LP Analytics in PostgreSQL

**What people might do:** Skip Cloudflare Workers, track analytics in PostgreSQL

**Why it's wrong:**
- PostgreSQL is not at edge, high latency for global users
- Tracking pixel needs fast response (<100ms), PostgreSQL adds 200-500ms
- Wastes database connections for lightweight analytics

**Do this instead:**
- Use Cloudflare D1 for edge analytics (50ms response globally)
- Sync aggregated data to PostgreSQL hourly for reports
- Best of both worlds: fast tracking + rich querying

### Anti-Pattern 3: Generating LPs Synchronously in API Endpoint

**What people might do:** Render LP in `/api/lp-generate` endpoint, block until done

**Why it's wrong:**
- Template rendering + file I/O can take 500ms-2s
- Blocks API thread, reduces throughput
- No retry logic if generation fails

**Do this instead:**
- Queue `generate_landing_page_task` via Celery
- Return immediately with `task_id`
- Poll `/api/jobs/{task_id}` for completion
- Pattern already established in existing pipeline

### Anti-Pattern 4: Embedding Cloudflare Worker Code in Python

**What people might do:** Try to write Cloudflare Worker in Python using Python Workers beta

**Why it's wrong:**
- Python Workers are beta, limited library support
- D1 binding from Python Workers is experimental
- JavaScript/TypeScript Workers are mature, well-documented
- Mixing Python + Python Workers = confusing codebase

**Do this instead:**
- Keep Worker as separate TypeScript project
- Python backend calls Worker via HTTP
- Clear separation of concerns
- Use each tool for what it's good at

---

## Integration Points Summary

### Existing → New Connections

| Existing Component | New Component | Connection Type | Purpose |
|-------------------|---------------|-----------------|---------|
| Video model | LandingPage model | Foreign Key | Link LP to source video |
| FastAPI `/api/*` | FastAPI `/ui/*` | Same app, different router | Web UI for admin |
| Celery tasks | `generate_landing_page_task` | Same Celery app | Async LP generation |
| Celery tasks | `deploy_landing_page_task` | Same Celery app | Async CF deployment |
| FastAPI | Cloudflare Worker | HTTP (fetch) | Retrieve analytics from D1 |
| Cloudflare Pages | Cloudflare Worker | JavaScript `<script>` tag | Track page views |

### External Dependencies

| Service | Purpose | Python Integration | Configuration |
|---------|---------|-------------------|---------------|
| Cloudflare Pages | Host LPs | `cloudflare-python` SDK | `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID` |
| Cloudflare Workers | Edge analytics | HTTP API calls | `CLOUDFLARE_WORKER_URL` |
| Cloudflare D1 | Analytics storage | Via Worker proxy | Managed by Worker |

---

## Sources

### Landing Pages
- [40 best landing page examples of 2026](https://unbounce.com/landing-page-examples/best-landing-page-examples/)
- [Landing Page Best Practices for Creators (2026 Edition)](https://www.newzenler.com/blog/landing-page-best-practices-creators-2026)

### Cloudflare Integration
- [Query D1 from Python Workers](https://developers.cloudflare.com/d1/examples/query-d1-from-python-workers/)
- [Cloudflare Python SDK](https://github.com/cloudflare/cloudflare-python)
- [Build an API to access D1 using a proxy Worker](https://developers.cloudflare.com/d1/tutorials/build-an-api-to-access-d1/)
- [D1py - Python wrapper for D1 REST API](https://github.com/Suleman-Elahi/D1py)
- [Cloudflare Pages Deployment API](https://developers.cloudflare.com/api/python/resources/pages/subresources/projects/subresources/deployments/)
- [Fetch · Cloudflare Workers docs](https://developers.cloudflare.com/workers/runtime-apis/fetch/)

### FastAPI + Jinja2
- [FastAPI Templates](https://fastapi.tiangolo.com/advanced/templates/)
- [How to Serve a Website With FastAPI Using HTML and Jinja2 – Real Python](https://realpython.com/fastapi-jinja2-template/)
- [The Ultimate FastAPI Tutorial Part 6 - Serving HTML with Jinja Templates](https://christophergs.com/tutorials/ultimate-fastapi-tutorial-pt-6-jinja-templates/)

### Architecture Patterns
- [Developing a Single Page App with FastAPI and React](https://testdriven.io/blog/fastapi-react/)
- [FastAPI Static Files](https://fastapi.tiangolo.com/tutorial/static-files/)
- [Serving a React Frontend Application with FastAPI](https://davidmuraya.com/blog/serving-a-react-frontend-application-with-fastapi/)

---

*Architecture research for: ViralForge LP + Cloudflare Integration*
*Researched: 2026-02-19*
