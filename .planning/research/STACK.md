# Technology Stack

**Project:** ViralForge - AI-Powered Short-Form Video Generation Pipeline
**Milestone:** Landing Page Generation, Cloudflare Deployment & Web UI
**Researched:** 2026-02-19
**Confidence:** HIGH

---

## MILESTONE UPDATE: New Features Stack

This document has been updated to include stack additions for the **Landing Page Generation & Deployment** milestone. The original stack (Python 3.11+, FastAPI, Celery, Redis, PostgreSQL, AI providers) remains unchanged. See below for NEW dependencies only.

---

## NEW Stack Additions (Milestone: Landing Pages & Web UI)

### Core Technologies (NEW for this milestone)

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| **Jinja2** | 3.1.6 | HTML template engine for LP generation | Already FastAPI's default templating engine. Compiles to optimized Python code (JIT or AOT). Async support. Security: auto-escaping enabled by default. |
| **python-multipart** | 0.0.14+ | Form data parsing | **Required** by FastAPI for `Form()` and `UploadFile`. No alternative. Used for waitlist form submission and product idea input. |
| **SQLAdmin** | 0.23.0 | Admin dashboard UI | Native FastAPI + SQLAlchemy integration. Auto-generates CRUD UI for models. Zero custom frontend code. Supports async engines. Python 3.9+ compatible. |
| **Wrangler CLI** | 4.66.0+ | Cloudflare deployment | Official Cloudflare CLI for Pages, Workers, D1. Handles auth (`wrangler login`), static site deployment, preview deployments. Node.js 18+ required. |

### Supporting Libraries (NEW)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **httpx** | Already installed (0.28.1) | HTTP client for Cloudflare SQL API | Query analytics from Cloudflare D1 via SQL API. Async support. Already in requirements.txt for AI provider calls. |
| **StaticFiles** | Part of Starlette | Serve static assets (CSS/JS) | Imported from `fastapi.staticfiles`. No separate install. Used for web UI static assets. |
| **Jinja2Templates** | Part of Starlette | Template rendering in routes | Imported from `fastapi.templating`. No separate install. Used for web UI and LP rendering. |

### Development Tools (NEW)

| Tool | Purpose | Notes |
|------|---------|-------|
| **Node.js 18+** | Runtime for Wrangler CLI | LTS version recommended. Check: `node --version`. Wrangler requires 18+ (v16 EOL). |
| **npx** | Execute Wrangler without global install | Comes with npm. Preferred over global install for version consistency. Command: `npx wrangler`. |

---

## Installation (NEW dependencies only)

### Python Dependencies

Add to `requirements.txt`:

```
# Landing Page & Web UI (NEW)
python-multipart==0.0.14  # FastAPI form handling (REQUIRED for Form())
sqladmin==0.23.0          # Admin dashboard

# Update existing (specify version)
Jinja2==3.1.6             # Currently unspecified in requirements.txt
```

Install:

```bash
pip install python-multipart==0.0.14 sqladmin==0.23.0
pip install --upgrade Jinja2==3.1.6
```

### Node.js Tools (for deployment only)

```bash
# Check Node.js version (must be 18+)
node --version

# If needed (macOS)
brew install node

# Or (Ubuntu/Debian)
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs

# Wrangler usage (no global install needed)
npx wrangler login
npx wrangler pages project create
npx wrangler pages deploy output/lp/{project_id}.html
```

---

## Integration Points with Existing FastAPI App

### 1. Landing Page Generation

**NEW module**: `app/services/landing_page/generator.py`

**Uses**:
- Jinja2Templates (via `from fastapi.templating import Jinja2Templates`)
- Existing LLM provider (`app/services/llm_provider/`) for AI-generated copy
- Template file: `templates/landing_page.html.jinja2`

**Flow**:
```python
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="templates")

# Step 1: Generate copy via existing LLM provider
llm = get_llm_provider()  # Uses existing gemini.py or mock.py
copy = await llm.generate_landing_page_copy(product_idea)

# Step 2: Render template
template = templates.get_template("landing_page.html.jinja2")
html = template.render(
    title=copy.title,
    hero=copy.hero_text,
    features=copy.features,
    analytics_script=get_analytics_beacon()
)

# Step 3: Write static HTML
output_path = f"output/lp/{project_id}.html"
with open(output_path, "w", encoding="utf-8") as f:
    f.write(html)

return {"html_path": output_path}
```

**Key insight**: Single-file static HTML. No server-side rendering needed after generation.

---

### 2. Cloudflare Deployment

**NEW script**: `scripts/deploy_landing_page.py` (Python wrapper) or manual CLI

**Uses**:
- Wrangler CLI (Node.js tool, **not** Python)
- subprocess (Python standard library) for calling Wrangler

**Deployment options**:

**Option A: Python wrapper (recommended)**

```python
import subprocess
from pathlib import Path

def deploy_to_cloudflare(html_path: str, project_id: str) -> str:
    """Deploy static HTML to Cloudflare Pages."""

    # Wrangler command
    cmd = [
        "npx", "wrangler", "pages", "deploy",
        html_path,
        f"--project-name=viralforge-lp-{project_id}",
        "--branch=main"
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise Exception(f"Deployment failed: {result.stderr}")

    # Extract URL from output
    url = f"https://viralforge-lp-{project_id}.pages.dev"
    return url
```

**Option B: Manual CLI (for testing)**

```bash
npx wrangler pages deploy output/lp/{project_id}.html \
    --project-name=viralforge-lp-{project_id} \
    --branch=main
```

**Output**: `https://viralforge-lp-{project_id}.pages.dev`

**Limits** (Cloudflare free tier):
- 500 deployments/month
- 20,000 files/deployment (single HTML file: OK)
- 25 MiB/file (typical LP: <500 KB)

---

### 3. Analytics Collection (Cloudflare Worker + D1)

**Architecture**:
```
Landing Page (JS beacon)
    → Cloudflare Worker (JavaScript)
    → D1 Database (SQLite-based)
    → Cloudflare SQL API
    → Python Admin Dashboard
```

**NEW file**: `cloudflare/analytics-worker.js` (JavaScript, **not** Python)

```javascript
// Cloudflare Worker for analytics
export default {
  async fetch(request, env) {
    // Parse event from landing page
    const { event, page_id, referrer } = await request.json();

    // Write to Analytics Engine
    await env.ANALYTICS.writeDataPoint({
      blobs: [page_id, event, referrer],      // Dimensions (strings)
      doubles: [1],                           // Values (numbers)
      indexes: [page_id]                      // Sampling key
    });

    return new Response("OK", { status: 200, headers: {
      "Access-Control-Allow-Origin": "*"
    }});
  }
}
```

**Landing page beacon** (injected into HTML template):

```html
<script>
  // Track page view
  fetch('https://analytics.YOUR_WORKER.workers.dev/track', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      event: 'page_view',
      page_id: '{{ page_id }}',
      referrer: document.referrer
    })
  });

  // Track form submission
  document.getElementById('waitlist-form').addEventListener('submit', () => {
    fetch('https://analytics.YOUR_WORKER.workers.dev/track', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        event: 'form_submit',
        page_id: '{{ page_id }}',
        referrer: document.referrer
      })
    });
  });
</script>
```

**Query analytics from Python** (admin dashboard):

```python
import httpx
from app.config import get_settings

settings = get_settings()

async def get_analytics(page_id: str):
    """Query Cloudflare Analytics via SQL API."""

    url = f"https://api.cloudflare.com/client/v4/accounts/{settings.cloudflare_account_id}/analytics_engine/sql"

    headers = {
        "Authorization": f"Bearer {settings.cloudflare_api_token}"
    }

    query = f"""
    SELECT
        blob1 AS page_id,
        blob2 AS event_type,
        COUNT(*) AS event_count,
        timestamp
    FROM ANALYTICS
    WHERE blob1 = '{page_id}'
    GROUP BY blob1, blob2, timestamp
    ORDER BY timestamp DESC
    """

    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, data=query)
        response.raise_for_status()
        return response.json()
```

**Why JavaScript Worker, not Python Worker?**
- Python Workers in **beta** (as of Feb 2026)
- JavaScript Workers: production-ready, simpler for analytics
- No advantage to Python for simple `writeDataPoint()` call

---

### 4. Waitlist Form Handling

**NEW route**: `app/api/waitlist.py`

**Uses**:
- FastAPI `Form()` (requires `python-multipart`)
- SQLAlchemy (existing)
- Pydantic validation (existing)

**NEW model** (`app/models.py`):

```python
from sqlalchemy import Column, Integer, String, DateTime
from app.database import Base
from datetime import datetime

class WaitlistEntry(Base):
    __tablename__ = "waitlist"

    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, nullable=False)
    product_idea = Column(String(500), nullable=False)
    source_page = Column(String)  # Which LP they came from
    created_at = Column(DateTime, default=datetime.utcnow)
```

**NEW schema** (`app/schemas.py`):

```python
from pydantic import BaseModel, EmailStr, Field

class WaitlistSubmit(BaseModel):
    email: EmailStr
    product_idea: str = Field(..., max_length=500, min_length=10)
    source_page: str | None = None
```

**NEW route** (`app/api/waitlist.py`):

```python
from fastapi import APIRouter, Form, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import WaitlistEntry
from app.schemas import WaitlistSubmit

router = APIRouter(prefix="/waitlist", tags=["waitlist"])

@router.post("/submit")
async def submit_waitlist(
    email: str = Form(...),
    product_idea: str = Form(..., max_length=500),
    source_page: str = Form(None),
    db: AsyncSession = Depends(get_db)
):
    # Validate with Pydantic
    try:
        data = WaitlistSubmit(
            email=email,
            product_idea=product_idea,
            source_page=source_page
        )
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))

    # Check duplicate
    existing = await db.execute(
        select(WaitlistEntry).where(WaitlistEntry.email == data.email)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already registered")

    # Save
    entry = WaitlistEntry(**data.model_dump())
    db.add(entry)
    await db.commit()

    return {"status": "success", "message": "Added to waitlist"}
```

**Form HTML** (in LP template):

```html
<form id="waitlist-form" method="POST" action="/waitlist/submit">
  <input type="email" name="email" required placeholder="your@email.com">
  <textarea name="product_idea" required maxlength="500" placeholder="Your product idea..."></textarea>
  <input type="hidden" name="source_page" value="{{ page_id }}">
  <button type="submit">Join Waitlist</button>
</form>
```

**Critical**: `python-multipart` **must** be installed or FastAPI raises:
```
RuntimeError: Form data requires "python-multipart" to be installed.
```

---

### 5. Admin Dashboard

**NEW integration** (add to `app/main.py`):

```python
from fastapi import FastAPI
from sqladmin import Admin, ModelView
from app.database import engine
from app.models import WaitlistEntry, LandingPage

app = FastAPI(...)

# Initialize SQLAdmin
admin = Admin(app, engine)

# Define admin views
class WaitlistAdmin(ModelView, model=WaitlistEntry):
    column_list = [WaitlistEntry.id, WaitlistEntry.email, WaitlistEntry.created_at]
    column_searchable_list = [WaitlistEntry.email]
    column_sortable_list = [WaitlistEntry.created_at]
    column_default_sort = [(WaitlistEntry.created_at, True)]  # Newest first

class LandingPageAdmin(ModelView, model=LandingPage):
    column_list = [LandingPage.id, LandingPage.url, LandingPage.views, LandingPage.conversions]
    column_sortable_list = [LandingPage.views, LandingPage.conversions]

# Register views
admin.add_view(WaitlistAdmin)
admin.add_view(LandingPageAdmin)
```

**Access**: `http://localhost:8000/admin`

**Features** (auto-generated by SQLAdmin):
- List view with pagination, sorting, search
- Create/edit forms (auto-generated from SQLAlchemy models)
- CSV/JSON export
- Filtering by column values

**Custom analytics view** (add to admin):

```python
from sqladmin import BaseView, expose

class AnalyticsView(BaseView):
    name = "Analytics"
    icon = "fa-solid fa-chart-line"

    @expose("/analytics", methods=["GET"])
    async def analytics_page(self, request):
        # Fetch from Cloudflare SQL API
        analytics_data = await get_analytics(page_id=None)  # All pages

        return await self.templates.TemplateResponse(
            "admin/analytics.html",
            {"request": request, "data": analytics_data}
        )

admin.add_view(AnalyticsView)
```

**Why SQLAdmin over alternatives?**
- **Flask-Admin**: Designed for Flask, not FastAPI (workarounds needed)
- **Starlette Admin**: Similar, but SQLAdmin has better SQLAlchemy 2.0 support
- **Custom admin**: 10x more code, reinventing wheel

---

### 6. Web UI (Product Idea Input)

**NEW routes**: `app/api/ui.py`

**Uses**:
- Jinja2Templates (via FastAPI)
- StaticFiles for CSS/JS
- Existing form handling

**Static files setup** (`app/main.py`):

```python
from fastapi.staticfiles import StaticFiles

app.mount("/static", StaticFiles(directory="static"), name="static")
```

**Directory structure**:

```
static/
├── css/
│   └── style.css
├── js/
│   └── app.js
└── images/
    └── logo.png

templates/
├── base.html.jinja2           # Base layout
├── product_form.html.jinja2   # Product idea input
└── landing_page.html.jinja2   # Generated LP template
```

**NEW route** (`app/api/ui.py`):

```python
from fastapi import APIRouter, Request, Form, Depends
from fastapi.templating import Jinja2Templates
from app.services.landing_page.generator import generate_landing_page

router = APIRouter(prefix="/ui", tags=["ui"])
templates = Jinja2Templates(directory="templates")

@router.get("/")
async def product_input_ui(request: Request):
    """Render product idea input form."""
    return templates.TemplateResponse(
        "product_form.html.jinja2",
        {"request": request}
    )

@router.post("/generate")
async def generate_lp(
    request: Request,
    product_idea: str = Form(..., max_length=500)
):
    """Generate landing page from product idea."""

    # Call LP generation service
    result = await generate_landing_page(product_idea)

    return templates.TemplateResponse(
        "generation_result.html.jinja2",
        {
            "request": request,
            "html_path": result.html_path,
            "preview_url": result.preview_url
        }
    )
```

**Template example** (`templates/product_form.html.jinja2`):

```html
{% extends "base.html.jinja2" %}

{% block content %}
<h1>Generate Landing Page</h1>
<form method="POST" action="/ui/generate">
  <label for="product_idea">Product Idea</label>
  <textarea
    id="product_idea"
    name="product_idea"
    required
    maxlength="500"
    placeholder="Describe your product idea..."
  ></textarea>

  <button type="submit">Generate Landing Page</button>
</form>
{% endblock %}
```

**CSS** (`static/css/style.css`):

```css
/* Minimal styling - no framework needed */
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  max-width: 800px;
  margin: 0 auto;
  padding: 2rem;
}

textarea {
  width: 100%;
  min-height: 150px;
  padding: 1rem;
  border: 1px solid #ddd;
  border-radius: 4px;
}

button {
  background: #0070f3;
  color: white;
  padding: 0.75rem 1.5rem;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}
```

**No JavaScript framework needed**. Plain HTML forms + optional vanilla JS for UX enhancements.

---

## Alternatives Considered

| Category | Recommended | Alternative | When to Use Alternative |
|----------|-------------|-------------|-------------------------|
| **Template Engine** | Jinja2 | Mako, Chevron, Mustache | **Never**. Jinja2 is FastAPI default, ecosystem standard. |
| **Admin Dashboard** | SQLAdmin | Flask-Admin, Starlette Admin | Flask-Admin: if migrating from Flask. Starlette Admin: if need MongoDB. |
| **Form Handling** | python-multipart | None | **No alternative**. FastAPI requires it for `Form()` and `UploadFile`. |
| **LP Deployment** | Cloudflare Pages | Vercel, Netlify, AWS S3 | Vercel/Netlify: if need serverless functions in LP. S3: if already on AWS. Cloudflare chosen for free D1 analytics integration. |
| **Analytics** | Cloudflare Workers + D1 | Google Analytics, Plausible, PostHog | GA: if need funnel analysis, attribution. Plausible/PostHog: privacy-first. D1 chosen for free tier + custom events + full control. |
| **Static Files** | FastAPI StaticFiles | WhiteNoise, nginx | WhiteNoise: if Django. nginx: if high traffic (serve directly). StaticFiles fine for dev/low-traffic. |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| **Separate React/Vue frontend** | Adds build step, npm dependencies, deployment complexity. Request specifies "Python ecosystem only, no separate frontend build." | Jinja2 templates + HTMX (if interactivity needed) |
| **Flask-Admin** | Designed for Flask, not FastAPI. Requires workarounds, not maintained for async. | SQLAdmin (native FastAPI support) |
| **multipart** package | Conflicts with `python-multipart`. Same import name causes errors. | `python-multipart` (official FastAPI requirement) |
| **Wrangler v1** (`@cloudflare/wrangler`) | Deprecated in 2022. No longer supported. | `wrangler` (v4.66.0+, npm package) |
| **Python Workers for analytics** | Beta, limited ecosystem, overkill for simple event tracking. | JavaScript Worker (production-ready, simpler) |
| **Custom analytics backend** | Reinventing wheel, requires hosting, database, maintenance. | Cloudflare Workers + D1 (free tier, zero infra) |
| **Django templates** | Requires Django framework. Incompatible with FastAPI. | Jinja2 (FastAPI default) |

---

## Stack Patterns by Use Case

### Pattern 1: Landing Page Generation (AI → HTML → Deploy)

```
User Input (Product Idea)
  → FastAPI Form Endpoint
  → LLM Provider (Gemini/Claude)
  → Jinja2 Template Rendering
  → Static HTML File
  → Wrangler Deploy
  → Cloudflare Pages URL
```

**Stack**:
- `app/services/llm_provider/gemini.py` (existing)
- Jinja2Templates (FastAPI, no separate install)
- `templates/landing_page.html.jinja2` (NEW)
- subprocess + `npx wrangler pages deploy`

### Pattern 2: Analytics Collection (Event → Store → Query → Display)

```
JS Beacon (Landing Page)
  → Cloudflare Worker (JavaScript)
  → D1 Database (writeDataPoint)
  → Cloudflare SQL API (query)
  → Python Admin Dashboard (httpx)
  → SQLAdmin UI
```

**Stack**:
- Client: `<script>` in LP HTML (vanilla JS)
- Worker: `cloudflare/analytics-worker.js` (JavaScript)
- Query: `httpx` (Python, already installed)
- Display: SQLAdmin (new install)

### Pattern 3: Web UI (Input → Validate → Generate → Deploy)

```
Browser
  → FastAPI Jinja2 Template (form)
  → Form Submission (python-multipart)
  → Pydantic Validation
  → LP Generation Service
  → Deployment Service
  → Success Page (Jinja2)
```

**Stack**:
- Frontend: Jinja2 templates + plain HTML forms
- Backend: FastAPI + python-multipart + Pydantic (existing)
- Storage: SQLAlchemy (existing)

---

## Version Compatibility

| Package | Version | Compatible With | Notes |
|---------|---------|-----------------|-------|
| Jinja2 | 3.1.6 | Python 3.7+ | Works with 3.11-3.14 (ViralForge uses 3.11+) |
| python-multipart | 0.0.14+ | FastAPI 0.128.8+ | **Breaking change** in 0.0.14: import as `python_multipart` (not `multipart`). FastAPI handles this internally. |
| SQLAdmin | 0.23.0 | FastAPI (any), SQLAlchemy 2.0.46+ | Requires Python 3.9+. ViralForge uses 3.11+. ✓ Compatible. |
| Wrangler | 4.66.0+ | Node.js 18+ | Node.js 16 EOL, not supported. Check: `node --version`. |
| StaticFiles | N/A | FastAPI 0.128.8+ | Part of Starlette, re-exported by FastAPI. No separate install. |
| Jinja2Templates | N/A | FastAPI 0.128.8+ | Part of Starlette, re-exported by FastAPI. No separate install. |

**Critical compatibility note**: `python-multipart` 0.0.14+ changed internal import from `multipart` to `python_multipart`. If directly importing (not via FastAPI), update:

```python
# Old (pre-0.0.14)
from multipart import parse_options_header

# New (0.0.14+)
from python_multipart import parse_options_header
```

FastAPI's `Form()` and `UploadFile` handle this internally → **no user code changes needed** unless directly importing multipart internals.

---

## Deployment Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                  ViralForge FastAPI App (Local/Docker)          │
│  ┌──────────────┐  ┌────────────────┐  ┌──────────────────┐   │
│  │ Web UI       │  │ LP Generator   │  │ Admin Dashboard  │   │
│  │ (Jinja2)     │  │ (Jinja2 + LLM) │  │ (SQLAdmin)       │   │
│  │ /ui          │  │ /api/generate  │  │ /admin           │   │
│  └──────┬───────┘  └───────┬────────┘  └────────┬─────────┘   │
│         │                  │                     │              │
│         └──────────────────┴─────────────────────┘              │
│                            │                                    │
│                   ┌────────▼─────────┐                          │
│                   │  PostgreSQL      │                          │
│                   │  (SQLAlchemy)    │                          │
│                   └──────────────────┘                          │
└─────────────────────────────────────────────────────────────────┘
                            │
                            │ (writes static HTML)
                            ▼
                  ┌──────────────────┐
                  │  output/lp/      │
                  │  *.html files    │
                  └──────────────────┘
                            │
                            │ (npx wrangler pages deploy)
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Cloudflare Pages                             │
│  ┌───────────────────────────────────────────────────────┐     │
│  │  Static Landing Pages (HTML)                          │     │
│  │  https://{project-id}.pages.dev                       │     │
│  │  ┌────────────────────────────────────────────────┐   │     │
│  │  │ <script> Analytics Beacon (vanilla JS)        │   │     │
│  │  └────────────────────────────────────────────────┘   │     │
│  └───────────────────────────────────────────────────────┘     │
│         │                                                        │
│         │ (POST /track)                                         │
│         ▼                                                        │
│  ┌───────────────────────────────────────────────────────┐     │
│  │  Cloudflare Worker (analytics-worker.js)              │     │
│  │  - Receives events from landing pages                 │     │
│  │  - Writes to Analytics Engine via writeDataPoint()   │     │
│  └───────────────────────────────────────────────────────┘     │
│         │                                                        │
│         ▼                                                        │
│  ┌───────────────────────────────────────────────────────┐     │
│  │  D1 Database (Analytics Events)                       │     │
│  │  - Stores: page_id, event_type, timestamp            │     │
│  │  - Queryable via SQL API                             │     │
│  └───────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────┘
         │
         │ (HTTP POST to SQL API)
         ▼
┌─────────────────────────────────────────────────────────────────┐
│  FastAPI Admin Dashboard                                         │
│  ┌───────────────────────────────────────────────────────┐     │
│  │  Analytics View (Custom SQLAdmin View)                │     │
│  │  - Queries Cloudflare SQL API via httpx              │     │
│  │  - Renders metrics: views, conversions, CVR          │     │
│  └───────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────┘
```

**Key insights**:

1. **Two separate deployment surfaces**:
   - **Python app**: Runs locally/Docker. Generates LPs, serves web UI, admin.
   - **Cloudflare**: Hosts static LPs, collects analytics via Worker.

2. **No direct connection**: FastAPI doesn't host landing pages. Flow:
   - FastAPI generates HTML → writes to `output/lp/`
   - Wrangler deploys HTML to Cloudflare Pages
   - Analytics flow back via SQL API

3. **JavaScript Worker, not Python**: Analytics Worker is JavaScript (production-ready). Python Workers in beta, unnecessary for simple event tracking.

---

## Configuration Updates

Add to `app/config.py` (`Settings` class):

```python
class Settings(BaseSettings):
    # ... existing settings ...

    # Landing Page Generation (NEW)
    cloudflare_account_id: str = ""
    cloudflare_api_token: str = ""  # For SQL API analytics queries
    cloudflare_pages_project: str = "viralforge-lp"
    lp_template_path: str = "templates/landing_page.html.jinja2"
    lp_output_dir: str = "output/lp"
    analytics_worker_url: str = ""  # https://analytics.YOUR_WORKER.workers.dev

    # Admin Dashboard (NEW)
    admin_enabled: bool = True
    admin_auth_enabled: bool = False  # Set True for production
```

Add to `.env`:

```bash
# Cloudflare
CLOUDFLARE_ACCOUNT_ID=your_account_id_here
CLOUDFLARE_API_TOKEN=your_api_token_here
CLOUDFLARE_PAGES_PROJECT=viralforge-lp
ANALYTICS_WORKER_URL=https://analytics.YOUR_WORKER.workers.dev

# Admin Dashboard
ADMIN_ENABLED=true
ADMIN_AUTH_ENABLED=false  # Set true in production
```

---

## Sources

### HIGH Confidence (Official Docs, Current Versions Verified)

- [Jinja2 · PyPI](https://pypi.org/project/Jinja2/) — Version 3.1.6, released March 5, 2025, Python 3.7+ requirement
- [FastAPI Templates Documentation](https://fastapi.tiangolo.com/advanced/templates/) — Jinja2Templates usage, integration patterns
- [FastAPI Static Files Documentation](https://fastapi.tiangolo.com/tutorial/static-files/) — StaticFiles from `fastapi.staticfiles`, mounting
- [SQLAdmin PyPI](https://pypi.org/project/sqladmin/) — Version 0.23.0, released Feb 4, 2026, Python 3.9+, FastAPI integration
- [SQLAdmin Documentation](https://aminalaee.github.io/sqladmin/) — FastAPI setup, ModelView configuration
- [Cloudflare Pages Direct Upload](https://developers.cloudflare.com/pages/get-started/direct-upload/) — Wrangler CLI commands, deployment workflow
- [Cloudflare D1 Python Workers](https://developers.cloudflare.com/d1/examples/query-d1-from-python-workers/) — Python Workers beta status, limitations
- [Cloudflare Analytics Engine Get Started](https://developers.cloudflare.com/analytics/analytics-engine/get-started/) — `writeDataPoint()` API, SQL query method, binding configuration
- [Wrangler npm package](https://www.npmjs.com/package/wrangler) — Latest version, Node.js requirements
- [FastAPI Form Handling](https://fastapi.tiangolo.com/tutorial/request-forms-and-files/) — python-multipart requirement, Form() usage

### MEDIUM Confidence (Multiple Sources, Verified)

- [Real Python: FastAPI Jinja2 Tutorial](https://realpython.com/fastapi-jinja2-template/) — Integration patterns, template rendering
- [FastAPI and Pydantic Settings](https://fastapi.tiangolo.com/advanced/settings/) — Pydantic Settings with .env support
- [Jinja2 Best Practices 2026](https://betterstack.com/community/guides/scaling-python/jinja-templating/) — Security, performance, organization
- [Cloudflare Workers Analytics](https://developers.cloudflare.com/analytics/analytics-engine/) — Analytics Engine overview, use cases
- [python-multipart GitHub Discussion](https://github.com/fastapi/fastapi/discussions/5144) — Import changes in 0.0.14+, compatibility issues

### LOW Confidence (WebSearch Only, Flagged for Validation)

- **Cloudflare Pages deprecation claim** (April 2025): Appears **incorrect**. Official docs remain active as of Feb 2026. One source claimed deprecation, but official Cloudflare docs show no deprecation notice.
- **Python Workers production-ready**: Marked as **beta** in official Cloudflare docs. Recommend JavaScript Workers for analytics (production-ready).

---

## Recommended Development Workflow

```bash
# 1. Start FastAPI app
docker compose up

# 2. Access web UI
open http://localhost:8000/ui

# 3. Input product idea → generates LP
# Output: output/lp/{project_id}.html

# 4. Preview locally
open output/lp/{project_id}.html

# 5. Deploy to Cloudflare
npx wrangler pages deploy output/lp/{project_id}.html \
    --project-name=viralforge-lp-{project_id}

# 6. View deployed LP
# URL: https://viralforge-lp-{project_id}.pages.dev

# 7. Monitor analytics in admin dashboard
open http://localhost:8000/admin
```

**No CI/CD needed initially**. Manual deployment via Wrangler CLI. Add CI/CD later if needed (GitHub Actions + Wrangler action).

---

## Key Takeaways

1. **Minimal new dependencies**: Only 2 new Python packages (`python-multipart`, `sqladmin`)
2. **Use existing stack**: Jinja2, Pydantic, SQLAlchemy already in place
3. **Separate concerns**: Python for generation/admin, JavaScript for analytics Worker
4. **Free tier optimizations**: Cloudflare Pages (unlimited), D1 (5GB free), Workers (100k req/day)
5. **No frontend build**: Plain HTML/CSS/JS, no React/Vue/npm build step
6. **Production-ready choices**: SQLAdmin (Feb 2026), Wrangler v4 (Feb 2026), Jinja2 3.1.6 (Mar 2025)

---

*Technology Stack for ViralForge Landing Page & Deployment Milestone*
*Researched: 2026-02-19*
*Confidence: HIGH (all components verified with official sources)*

---

## Original Stack (Unchanged)

See sections below for original ViralForge stack (Python, FastAPI, Celery, AI providers, video generation). **No changes** to original stack. New milestone adds landing page, deployment, analytics, web UI capabilities on top of existing foundation.

---

### Core Framework

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| **Python** | 3.11+ | Runtime environment | Industry standard for ML/AI pipelines. Python 3.11 offers 10-60% performance improvements over 3.10. Most AI libraries require 3.9+ minimum. |
| **FastAPI** | 0.129.0+ | API framework & orchestration | Async-first design, automatic OpenAPI docs, Pydantic integration, exceptional performance. Requires Python 3.10+. Industry standard for ML APIs in 2026. |
| **Celery** | 5.6.2+ | Async task queue | Battle-tested distributed task queue. Handles long-running video generation jobs. Supports retries, rate limiting, task prioritization. Requires Python 3.9+. |
| **Docker Compose** | v2 (latest) | Container orchestration | Go-based v2 is production-ready for single-server deployments. Manages 6 microservices + PostgreSQL + Redis with one command. v1 reached EOL July 2023. |

### Database & Cache

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| **PostgreSQL** | 15+ | Primary database | ACID compliance for critical video metadata and workflow state. JSON support for flexible schema. Best async driver support via asyncpg. |
| **Redis** | 7.2+ | Message broker & cache | Dual role: Celery message broker + result backend. In-memory speed for task queue. Supports pub/sub for real-time updates. |
| **SQLAlchemy** | 2.0.46+ | ORM | Async support via `create_async_engine`. Type-safe queries. Migration support via Alembic. PostgreSQL dialect optimized for asyncpg driver. |
| **asyncpg** | 0.30+ | PostgreSQL driver | 5x faster than psycopg3. Native async/await. Binary protocol for PostgreSQL. Required for SQLAlchemy async. Supports PostgreSQL 9.5-18. |
| **redis-py** | 7.1.0+ (Feb 2026) | Redis client | Official Redis client. Native async support via `redis.asyncio`. Supports Redis 7.2-8.2. |

### AI & Video Generation

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| **diffusers** | 0.36.0+ | Stable Video Diffusion | Hugging Face library for running SVD locally. Pre-built pipelines, interchangeable schedulers, battle-tested. Apache 2.0 license. Requires Python 3.8+. |
| **huggingface-hub** | 1.4.1+ | Model download & management | Official client for downloading SVD models. Caching, resume support, authentication. Requires Python 3.9+. |
| **OpenAI SDK** | 2.20.0+ | Sora API integration | Official Python SDK for Sora 2 video generation (paid tier). Async support. Supports sora-2 (fast) and sora-2-pro (quality). |
| **google-genai** | Latest | Veo 3.1 API integration | Official Python SDK for Google Veo video generation (paid tier). 8-second 720p/1080p/4k output with native audio. |
| **torch** | 2.x + CUDA | GPU acceleration | Required for local Stable Video Diffusion. CUDA support for NVIDIA GPUs. CPU fallback available but 10-50x slower. |

### LLM Integration

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| **langchain** | 0.3+ | LLM orchestration | Industry standard for LLM pipelines. Unified interface for OpenAI, Anthropic, local models. Prompt templates, chain composition, output parsing. |
| **langchain-openai** | Latest | OpenAI integration | Official LangChain package for GPT-4. Streaming support. Function calling for structured outputs. |
| **langchain-anthropic** | Latest | Claude integration | Official LangChain package for Claude Opus/Sonnet. Extended context for long-form analysis. |
| **anthropic** | 0.79.0+ | Claude SDK (direct) | Alternative to LangChain for Claude-only workflows. Requires Python 3.9+. Lower latency than LangChain wrapper. |

### Text-to-Speech

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| **elevenlabs** | Latest | Premium TTS (paid) | Studio-quality voices (32 languages, 100+ accents). Flash v2.5 model: 75ms latency. Turbo v2.5: 250-300ms, production quality. Official Python SDK. |
| **Coqui TTS** | 0.22+ | Open-source TTS (free) | XTTS model supports 13 languages. Runs locally, no API costs. Quality lower than ElevenLabs but sufficient for MVP. Apache 2.0 license. |
| **pyttsx3** | 2.90+ | Fallback offline TTS | Pure offline TTS, no dependencies. Useful for testing without API calls. Lower quality, limited voices. |

### Video Processing

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| **ffmpeg-python** | 0.2.0+ | FFmpeg wrapper | Pythonic FFmpeg interface. Supports complex filter graphs. Industry standard, well-maintained. Better than moviepy for production pipelines. |
| **moviepy** | 2.0+ | High-level video editing | Compositing, text overlays, transitions. Built on FFmpeg. v2.0 (2025) introduced breaking changes but better async support. Python 3.9+. |
| **Pillow (PIL)** | 10.x+ | Image processing | Thumbnail generation, image preprocessing for video generation. Lightweight, fast. Required by many video libraries. |

### Data & Integration

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| **gspread** | 6.1.4+ | Google Sheets API | Official Python API for Sheets. OAuth2/service account auth. Batch updates, read/write ranges. Released May 2025. Requires Python 3.8+. |
| **pydantic** | 2.12.5+ | Data validation | FastAPI's core validator. v2 is 5-50x faster (Rust core). Type-safe schemas, automatic JSON serialization. Field validators, computed fields. |
| **python-dotenv** | 1.0+ | Environment variables | Load .env files into os.environ. Essential for API keys, secrets. Never commit .env to git (use .env.example template). |

### Social Media Scraping

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| **httpx** | 0.27+ | HTTP client | Async HTTP client. Better than requests for async workflows. HTTP/2 support. Used by many modern scraping tools. |
| **BeautifulSoup4** | 4.12+ | HTML parsing | Industry standard for web scraping. Parser-agnostic. Simple API for navigating DOM. |
| **Playwright** | 1.47+ | Browser automation | Headless browser for JavaScript-heavy sites (TikTok, Instagram). Stealth mode, anti-detection features. More reliable than Selenium for 2026 social platforms. |

**WARNING:** Social media scraping in 2026 is legally and technically complex. TikTok/Instagram employ advanced anti-bot measures (TLS fingerprinting, behavioral analysis, IP quality detection). Official APIs are expensive or unavailable. Consider third-party APIs like Bright Data, ScrapeCreators, or EnsembleData for legal/reliable access.

### Development Tools

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| **Poetry** | 1.8+ | Dependency management | Modern Python packaging. Lock file for deterministic builds. Dependency groups (dev/test/prod). Replaces requirements.txt/setup.py. Python 3.9+. Released Feb 2026. |
| **Flower** | 2.0+ | Celery monitoring | Real-time web dashboard for Celery workers/tasks. Port 5555. Task history, worker stats, remote control. Essential for debugging async pipelines. |
| **pytest** | 8.x+ | Testing framework | Industry standard. Async test support via pytest-asyncio. Fixtures, parametrization, coverage reports. |
| **black** | 24.x+ | Code formatter | Opinionated, zero-config. Industry standard. Integrates with pre-commit hooks. |
| **ruff** | 0.8+ | Linter | 10-100x faster than flake8/pylint. Rust-based. Auto-fix support. Replaces flake8, isort, pydocstyle. |

