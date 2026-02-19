# Phase 16: Waitlist Collection - Research

**Researched:** 2026-02-19
**Domain:** FastAPI endpoint + SQLAlchemy model + email validation + Alembic migration + HTML form wiring
**Confidence:** HIGH

## Summary

This phase wires the existing LP waitlist form to a real backend. The form already has honeypot spam prevention and a client-side timestamp check built in Phase 14. The JavaScript comment in the template explicitly says "Phase 16 will add backend processing." No new libraries are needed — email-validator is the only addition, but Python's built-in `re` or Pydantic's `EmailStr` (already indirectly available via pydantic) can handle format validation without a new install.

The project uses FastAPI + SQLAlchemy async + Alembic migrations + SQLite. All patterns are established across phases 1-15. This phase follows the exact same pattern as other models in `app/models.py` and routes in `app/api/routes.py`.

The key design question is: what identifies which LP a signup came from? The LP lives at `output/{run_id}/landing-page.html`. The `run_id` (8-char hex UUID prefix) is the natural source identifier. It should be embedded in the form (as a hidden input or in the endpoint URL) so the backend can record it.

**Primary recommendation:** Add a `WaitlistEntry` model, a `POST /waitlist` endpoint (no API key required — it's public), a `004` Alembic migration, and update the waitlist Jinja2 template to POST via `fetch()` to the backend.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| SQLAlchemy | 2.0.46 (installed) | ORM model for WaitlistEntry | Already in use for all models |
| Alembic | 1.16.5 (installed) | Migration `004_waitlist_schema` | Same pattern as 001-003 |
| FastAPI | 0.128.8 (installed) | `POST /waitlist` route | Already used for all API routes |
| Pydantic | 2.12.5 (installed) | Request schema + EmailStr validation | Already used for all schemas |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `email-validator` | any | Enables Pydantic `EmailStr` | If using `EmailStr`; else use `re` pattern |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Pydantic EmailStr | `re` regex check | `re` is zero-dependency but weaker; EmailStr validates MX-resolvable format |
| Embedded `lp_source` hidden field | URL path param `/waitlist/{lp_slug}` | URL param is cleaner; hidden field simpler for static HTML |

**Installation (if using EmailStr):**
```bash
pip install email-validator
```

Note: `email-validator` enables Pydantic's `EmailStr` type, which does RFC-compliant format validation. It does NOT do live MX/DNS checks by default — that matches WAIT-02 ("basic domain check" = domain portion present and syntactically valid, not live DNS query).

## Architecture Patterns

### Recommended Project Structure
```
app/
├── models.py           # Add WaitlistEntry model here
├── schemas.py          # Add WaitlistSubmit + WaitlistResponse schemas
├── api/routes.py       # Add POST /waitlist route (no auth)
alembic/versions/
└── 004_waitlist_schema.py   # New migration
app/services/landing_page/templates/sections/
└── waitlist.html.j2    # Update JS fetch() call + add hidden lp_source input
```

### Pattern 1: Model Addition (follow existing pattern)
**What:** Add `WaitlistEntry` to `app/models.py` with UniqueConstraint on email.
**When to use:** Any new persisted entity.
**Example:**
```python
# Source: existing models.py pattern (e.g. Trend model)
class WaitlistEntry(Base):
    """Visitor waitlist signups from landing pages."""
    __tablename__ = "waitlist_entries"

    id = Column(Integer, primary_key=True)
    email = Column(String(255), nullable=False)
    lp_source = Column(String(50), nullable=True)  # run_id of the LP, e.g. "52166684"
    signed_up_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint('email', name='uq_waitlist_email'),
    )
```

### Pattern 2: Public Endpoint (no API key)
**What:** `POST /waitlist` route without `require_api_key` dependency — this endpoint is hit by LP visitors.
**When to use:** Any publicly accessible endpoint (no Bearer token from browser).
**Example:**
```python
# Source: routes.py pattern adapted for public access
@router.post("/waitlist")
async def submit_waitlist(
    request: WaitlistSubmit,
    session: AsyncSession = Depends(get_session),
):
    """Public endpoint for LP waitlist form submissions."""
    from app.models import WaitlistEntry
    from sqlalchemy.exc import IntegrityError

    # Check duplicate
    existing = await session.execute(
        select(WaitlistEntry).where(WaitlistEntry.email == request.email)
    )
    if existing.scalars().first():
        raise HTTPException(status_code=409, detail="You're already on the waitlist!")

    entry = WaitlistEntry(email=request.email, lp_source=request.lp_source)
    session.add(entry)
    try:
        await session.commit()
    except IntegrityError:
        # Race condition: duplicate inserted between check and commit
        raise HTTPException(status_code=409, detail="You're already on the waitlist!")

    return {"message": "Thanks! You're on the list."}
```

### Pattern 3: Alembic Migration (follow 001-003 pattern)
**What:** `004_waitlist_schema.py` creating `waitlist_entries` table.
**Example:**
```python
# Source: alembic/versions/003_content_generation_schema.py pattern
revision: str = '004'
down_revision: Union[str, None] = '003'

def upgrade() -> None:
    op.create_table(
        'waitlist_entries',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('lp_source', sa.String(50), nullable=True),
        sa.Column('signed_up_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email', name='uq_waitlist_email'),
    )

def downgrade() -> None:
    op.drop_table('waitlist_entries')
```

### Pattern 4: CORS for Public Form Submission
**What:** The LP is a static HTML file opened from `file://` or served from Cloudflare Pages (Phase 18-19). The current CORS config in `app/main.py` only allows `http://localhost:3000`. For the form to POST to the FastAPI backend from LP pages, CORS must allow the LP's origin.
**Critical decision:** During local dev the LP is opened as a file (`file://`), which some browsers treat as null origin. For local dev, CORS needs `allow_origins=["*"]` or the form must be served from localhost. For production (Phase 18-19), origins come from Cloudflare Pages domain.
**Recommended approach:** Add a `CORS_ALLOWED_ORIGINS` env var with default `*` for dev; tighten in production. OR configure the LP form to submit to the same origin (requires LP to be served, not file://).

### Pattern 5: Waitlist Template Update
**What:** Update `waitlist.html.j2` JavaScript to POST to backend instead of just showing success message locally.
**Example:**
```javascript
// Replace the "Valid submission" block in waitlist.html.j2
const payload = {
    email: document.getElementById('email').value,
    lp_source: '{{ lp_source | default("") }}'  // Jinja2 variable
};

fetch('/waitlist', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
})
.then(res => res.json())
.then(data => {
    if (data.detail) {
        // Show duplicate/error message
        errorEl.textContent = data.detail;
        errorEl.style.display = 'block';
    } else {
        form.style.display = 'none';
        successMessage.style.display = 'block';
    }
})
.catch(() => {
    // Fallback: show success anyway (offline/network error)
    form.style.display = 'none';
    successMessage.style.display = 'block';
});
```

The `lp_source` Jinja2 variable needs to be passed from `build_landing_page()` in `template_builder.py` — currently the `run_id` is known in `generator.py` but not forwarded to section templates.

### Anti-Patterns to Avoid
- **Form `action=""` attribute:** The current form has no `action` — it uses JS. Keep it JS-only fetch() for SPA-style UX (no page reload on submit).
- **Storing honeypot state server-side:** Honeypot is client-side only. The server should NOT try to validate `website_url` field — bots that bypass client-side checks are caught by server-side email validation.
- **Live MX lookup:** Do not do live DNS/MX verification in the endpoint. It's slow, blocks the async loop, and fails for valid new domains.
- **Using `require_api_key` on the waitlist endpoint:** Visitors don't have API keys. This endpoint must be fully public.
- **IntegrityError as primary duplicate check:** Check first with SELECT, then handle IntegrityError as a safety net (race condition). Don't rely solely on the DB exception — it leaks internal details.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Email format validation | Custom regex | Pydantic `EmailStr` (with email-validator) | Handles RFC 5321/5322 edge cases |
| Duplicate detection | Custom logic | UniqueConstraint + IntegrityError catch | DB-level guarantee, race-condition safe |
| Rate limiting | New middleware | Existing `_RateLimiter` in `main.py` | Already built, just ensure waitlist route is covered |

**Key insight:** Everything needed already exists in the project. This is a wiring task, not a library task.

## Common Pitfalls

### Pitfall 1: CORS blocks form submission
**What goes wrong:** Browser blocks the `fetch()` POST from LP origin to FastAPI.
**Why it happens:** Current `main.py` CORS is locked to `http://localhost:3000`. LP files are served from `file://` or `output/` subdirectory.
**How to avoid:** Add `CORS_ALLOWED_ORIGINS` env var, default to `["*"]` for dev. Update `main.py` to read it.
**Warning signs:** Browser console shows "CORS policy" error; form never reaches server.

### Pitfall 2: Duplicate check race condition
**What goes wrong:** Two concurrent submissions with same email both pass SELECT check, then one fails on INSERT.
**Why it happens:** Async gap between SELECT and INSERT.
**How to avoid:** Catch `IntegrityError` on commit and return 409. The UniqueConstraint makes this safe.

### Pitfall 3: `lp_source` not available in section template
**What goes wrong:** Jinja2 template can't render `{{ lp_source }}` because `build_landing_page()` doesn't pass it.
**Why it happens:** `run_id` is generated in `generator.py` but `build_landing_page()` only accepts `copy`, `color_scheme`, `video_url`, `hero_image`, `product_images`.
**How to avoid:** Either (a) pass `lp_source` as a new param to `build_landing_page()` and thread it into waitlist section context, or (b) make the form read `lp_source` from a `<meta>` tag or `data-*` attribute set in the base template. Option (b) is cleaner.
**Warning signs:** Template renders `{{ lp_source }}` as empty string.

### Pitfall 4: `email-validator` not installed
**What goes wrong:** Pydantic raises `ImportError` when `EmailStr` is used.
**Why it happens:** `EmailStr` requires `email-validator` package; it's not in `requirements.txt`.
**How to avoid:** Either add `email-validator` to requirements.txt, or use a simple regex check in the endpoint body instead of `EmailStr`.

### Pitfall 5: Endpoint path conflicts with API router prefix
**What goes wrong:** The route is registered as `/waitlist` but the LP submits to `/api/waitlist` or vice versa.
**Why it happens:** The existing router in `routes.py` has no prefix set — routes are registered as `/health`, `/trends`, etc. directly (no `/api/` prefix in the router itself; prefix comes from `app.include_router(routes.router)`).
**How to avoid:** Check `main.py` — `app.include_router(routes.router)` has no `prefix=` argument, so routes are at root level. The LP JS must POST to `/waitlist` (not `/api/waitlist`).

### Pitfall 6: `server_default=func.now()` vs `default=datetime.now`
**What goes wrong:** `default=datetime.now` is evaluated at model class definition time (Python side), not per-row (DB side).
**Why it happens:** SQLAlchemy distinction between Python-side default and server-side default.
**How to avoid:** Use `server_default=func.now()` for timestamps — same pattern as all other models.

## Code Examples

Verified patterns from existing codebase:

### WaitlistSubmit Pydantic Schema
```python
# Add to app/schemas.py (follow existing pattern)
from pydantic import BaseModel, EmailStr
from typing import Optional

class WaitlistSubmit(BaseModel):
    """Waitlist form submission from LP visitor."""
    email: EmailStr  # Requires email-validator package
    lp_source: Optional[str] = None  # run_id of LP, e.g. "52166684"

class WaitlistResponse(BaseModel):
    """Response for waitlist submission."""
    message: str
```

### Duplicate check pattern (from routes.py approach)
```python
# Source: routes.py select pattern
from sqlalchemy import select
result = await session.execute(
    select(WaitlistEntry).where(WaitlistEntry.email == request.email)
)
if result.scalars().first():
    raise HTTPException(status_code=409, detail="You're already on the waitlist!")
```

### CORS update pattern
```python
# app/main.py — update to support configurable origins
import os
allowed_origins = os.getenv("CORS_ALLOWED_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],  # No Authorization needed for public endpoint
    allow_credentials=False,
)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Form action= page reload | fetch() async submit | Standard since ~2018 | No page navigation; SPA-like UX |
| Separate validation library | Pydantic EmailStr | Pydantic v2 (2023) | Single dependency handles schema + validation |
| Manual IntegrityError import | `from sqlalchemy.exc import IntegrityError` | SQLAlchemy 2.0 | Same as before, still needed |

**Deprecated/outdated:**
- `declarative_base()` from `sqlalchemy.ext.declarative`: Already in use in this project (not breaking, just older style — don't change it, match existing models.py).

## Open Questions

1. **CORS origin for production (Phase 18-19)**
   - What we know: Phase 18-19 deploys to Cloudflare Pages. The LP origin will be a `.pages.dev` domain.
   - What's unclear: Whether the FastAPI server will be behind a reverse proxy with the same origin, or a separate domain.
   - Recommendation: Use `*` for dev; add `CORS_ALLOWED_ORIGINS` env var for later tightening. Flag for Phase 18-19.

2. **LP `run_id` availability in the form**
   - What we know: `run_id` is created in `generator.py` and used to name the output folder.
   - What's unclear: Whether to embed `run_id` as a Jinja2 variable in the template (requires passing it to `build_landing_page`) or derive it at runtime (from the URL path the LP is served at).
   - Recommendation: Pass `lp_source=run_id` to `build_landing_page()` as an optional param; inject it into a `<meta name="lp-source">` tag in the base template; read it in JS via `document.querySelector('meta[name="lp-source"]').content`.

3. **`email-validator` vs regex**
   - What we know: `email-validator` is not in requirements.txt. Using `EmailStr` without it causes a runtime error.
   - What's unclear: Whether the team prefers zero-dependency simplicity or full RFC compliance.
   - Recommendation: Add `email-validator` to requirements.txt. It's small (~50KB), well-maintained, and unlocks `EmailStr` cleanly.

## Sources

### Primary (HIGH confidence)
- Codebase: `app/models.py` — UniqueConstraint, Column, server_default patterns verified directly
- Codebase: `app/api/routes.py` — route structure, Depends(get_session), HTTPException patterns verified
- Codebase: `app/main.py` — CORS config, rate limiter, include_router verified
- Codebase: `app/services/landing_page/templates/sections/waitlist.html.j2` — form structure, JS, honeypot verified
- Codebase: `alembic/versions/003_content_generation_schema.py` — migration pattern verified
- Codebase: `app/schemas.py` — Pydantic model patterns verified
- Codebase: `requirements.txt` — email-validator NOT present (confirmed gap)

### Secondary (MEDIUM confidence)
- SQLAlchemy 2.0 docs: `IntegrityError` imported from `sqlalchemy.exc` (standard, stable)
- Pydantic v2 docs: `EmailStr` requires `email-validator` package (confirmed standard requirement)

### Tertiary (LOW confidence)
- CORS `file://` origin behavior: varies by browser; some send `null` origin, some block entirely

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries already installed and verified in codebase
- Architecture: HIGH — all patterns directly observed in existing routes.py, models.py
- Pitfalls: HIGH — CORS gap, lp_source threading, email-validator missing confirmed from codebase inspection
- CORS production behavior: LOW — depends on Phase 18-19 decisions not yet made

**Research date:** 2026-02-19
**Valid until:** 2026-03-19 (stable domain; no fast-moving libraries involved)
