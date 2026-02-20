# Technology Stack

**Project:** ViralForge — v3.0 Linear Review Workflow UI
**Milestone:** Per-frame script/image/video review, approval state machine, AI regeneration, mock/real toggle
**Researched:** 2026-02-20
**Confidence:** HIGH

---

## Milestone Context

v2.0 shipped FastAPI + Jinja2 + SSE + Celery + Redis + SQLAlchemy. This document covers NEW stack additions only for v3.0's linear review pipeline UI. Zero frontend framework is in scope — stay in the Jinja2 + vanilla JS pattern already established.

---

## NEW Stack Additions (v3.0 Review Workflow)

### Core Technologies

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **HTMX** | 2.0.8 (CDN) | Inline approve/reject/regenerate actions without page reload | No build step. `hx-post` swaps HTML fragments. `hx-trigger="every 2s"` for Celery poll. SSE extension for streaming. Pairs perfectly with Jinja2 fragments. 2.0.x stable since June 2024, 2.0.8 current. |
| **python-statemachine** | 2.6.0 | Review state machine (pending → approved/rejected/regenerating) | Released 2026-02-13. Full async support. `States.from_enum()` maps directly to SQLAlchemy String column. Validates transitions — rejects illegal state jumps. Cleaner than manual `if status == "approved"` guards. |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **FastAPI FileResponse** | (Starlette, already installed) | Serve local video/image files at `/media/{path}` | Return `.mp4` or `.jpg` from `output/` directory. Starlette auto-sets `Content-Length`, `ETag`, `Last-Modified`. No new install. |
| **FastAPI StreamingResponse** | (Starlette, already installed) | HTTP Range requests for video seeking | Required when browser sends `Range: bytes=N-M` header. Enables scrub-to-position in `<video>` tag. No new install. |
| **HTMX SSE Extension** | 2.2.4 (CDN) | Push Celery regeneration progress to review page | `hx-ext="sse"` + `sse-swap="stage"` updates individual frame cards as AI regenerates them. Reuses existing SSE pattern from v2.0. No install. |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| **Alembic** | DB migration for new review state columns | Already installed. Add `review_state`, `reviewed_at`, `reviewer_note` to existing `Video` model via migration. |
| **Jinja2 `{% block %}` fragments** | Partial template rendering for HTMX swaps | Already installed. Render individual frame card HTML fragment in response to HTMX `hx-post`. No new install, pattern change only. |

---

## Installation (New for v3.0)

### Python

```bash
pip install python-statemachine==2.6.0
```

Add to `requirements.txt`:
```
python-statemachine==2.6.0
```

### CDN (add to `app/ui/templates/base.html`)

```html
<!-- Core HTMX -->
<script src="https://cdn.jsdelivr.net/npm/htmx.org@2.0.8/dist/htmx.min.js"></script>
<!-- SSE Extension (for regeneration progress) -->
<script src="https://cdn.jsdelivr.net/npm/htmx-ext-sse@2.2.4/sse.js"></script>
```

**No npm/node required.** CDN-only, no build step.

---

## Integration Points

### 1. Approval State Machine

Use `python-statemachine` with `States.from_enum()` to mirror the existing `Video.status` string column:

```python
from python_statemachine import StateMachine, State
from enum import Enum

class ReviewStatus(str, Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    regenerating = "regenerating"

class ReviewMachine(StateMachine):
    # States from enum — matches Video.status values directly
    pending      = State(initial=True)
    regenerating = State()
    approved     = State(final=True)
    rejected     = State(final=True)

    approve      = pending.to(approved)
    reject       = pending.to(rejected)
    regenerate   = pending.to(regenerating)
    finish_regen = regenerating.to(pending)  # back to review after regen
```

**Integration with SQLAlchemy**: State machine is a Python-only guard. It does not own the DB column. Pattern:

```python
async def approve_frame(frame_id: int, session: AsyncSession):
    frame = await session.get(VideoFrame, frame_id)
    machine = ReviewMachine(initial_state=frame.status)
    machine.approve()                           # raises InvalidDefinition if illegal
    frame.status = machine.current_state.id     # write string back to DB column
    frame.reviewed_at = datetime.now(timezone.utc)
    await session.commit()
```

**Why not `transitions` (0.9.3)?** Both work. `python-statemachine` 2.6.0 has cleaner async support and was released Feb 2026 (more recent). Either is valid — pick one and commit.

### 2. Video/Image Preview Serving

`FileResponse` for images. `StreamingResponse` with range-request handling for videos (enables browser seek bar):

```python
from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, StreamingResponse
from pathlib import Path

@router.get("/media/image/{frame_id}")
async def serve_image(frame_id: int, session: AsyncSession = Depends(get_session)):
    frame = await session.get(VideoFrame, frame_id)
    path = Path(frame.image_path)
    if not path.exists():
        raise HTTPException(404)
    # Security: must be inside output/ dir
    if not path.resolve().is_relative_to(Path("output").resolve()):
        raise HTTPException(403)
    return FileResponse(path, media_type="image/jpeg")

@router.get("/media/video/{frame_id}")
async def serve_video(frame_id: int, request: Request, session: AsyncSession = Depends(get_session)):
    frame = await session.get(VideoFrame, frame_id)
    path = Path(frame.video_path)
    if not path.resolve().is_relative_to(Path("output").resolve()):
        raise HTTPException(403)

    file_size = path.stat().st_size
    range_header = request.headers.get("range")

    if range_header:
        # Parse "bytes=START-END"
        start, end = range_header.replace("bytes=", "").split("-")
        start = int(start)
        end = int(end) if end else file_size - 1
        chunk_size = end - start + 1

        def iter_range():
            with open(path, "rb") as f:
                f.seek(start)
                remaining = chunk_size
                while remaining > 0:
                    chunk = f.read(min(65536, remaining))
                    if not chunk:
                        break
                    remaining -= len(chunk)
                    yield chunk

        return StreamingResponse(
            iter_range(),
            status_code=206,
            media_type="video/mp4",
            headers={
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Accept-Ranges": "bytes",
                "Content-Length": str(chunk_size),
            }
        )

    return FileResponse(path, media_type="video/mp4")
```

**Template usage:**
```html
<!-- Image frame preview -->
<img src="/media/image/{{ frame.id }}" loading="lazy" style="max-width:100%">

<!-- Video frame preview with seek support -->
<video controls style="max-width:100%">
  <source src="/media/video/{{ frame.id }}" type="video/mp4">
</video>
```

### 3. HTMX for Review Actions

Per-frame approve/reject buttons swap only that card's HTML fragment — no page reload:

```html
<!-- Frame review card (Jinja2 fragment) -->
<div id="frame-{{ frame.id }}" class="frame-card status-{{ frame.status }}">
  <img src="/media/image/{{ frame.id }}">
  <p>{{ frame.script_text }}</p>

  {% if frame.status == "pending" %}
  <button hx-post="/ui/review/{{ frame.id }}/approve"
          hx-target="#frame-{{ frame.id }}"
          hx-swap="outerHTML">
    Approve
  </button>
  <button hx-post="/ui/review/{{ frame.id }}/reject"
          hx-target="#frame-{{ frame.id }}"
          hx-swap="outerHTML">
    Reject
  </button>
  <button hx-post="/ui/review/{{ frame.id }}/regenerate"
          hx-target="#frame-{{ frame.id }}"
          hx-swap="outerHTML">
    Regenerate
  </button>
  {% endif %}
</div>
```

**FastAPI route returns an HTML fragment**, not a full page:

```python
@router.post("/ui/review/{frame_id}/approve")
async def approve_frame_htmx(frame_id: int, request: Request, session: AsyncSession = Depends(get_session)):
    await approve_frame(frame_id, session)
    frame = await session.get(VideoFrame, frame_id)
    # Return only the updated card fragment
    return templates.TemplateResponse(
        "partials/frame_card.html",
        {"request": request, "frame": frame}
    )
```

### 4. Celery Regeneration + SSE Progress

Regeneration triggers a Celery task. SSE streams progress back to the specific frame card using HTMX SSE extension. Reuses the existing SSE pattern from Phase 17.

```html
<!-- After clicking Regenerate, card polls for updates -->
<div id="frame-{{ frame.id }}" hx-ext="sse"
     sse-connect="/ui/review/{{ frame.id }}/events"
     sse-swap="frame_update"
     sse-close="done">
  <p>Regenerating...</p>
</div>
```

```python
from fastapi.responses import StreamingResponse as SSEResponse
import asyncio, json

@router.get("/ui/review/{frame_id}/events")
async def frame_sse(frame_id: int, session: AsyncSession = Depends(get_session)):
    async def event_stream():
        # Poll Celery task state from Redis
        while True:
            frame = await session.get(VideoFrame, frame_id)
            if frame.status != "regenerating":
                # Emit final HTML fragment
                html = render_frame_card(frame)
                yield f"event: frame_update\ndata: {html}\n\n"
                yield f"event: done\ndata: done\n\n"
                break
            yield f"event: frame_update\ndata: <p>Regenerating...</p>\n\n"
            await asyncio.sleep(1)

    return SSEResponse(event_stream(), media_type="text/event-stream")
```

### 5. Mock/Real AI Toggle

The existing `USE_MOCK_AI` env var pattern already works. No new stack required. Review workflow just passes the flag through to existing `get_llm_provider()`, `get_video_generator()`, etc. calls. The regeneration Celery task reads from settings at call time.

```python
# In regeneration task — no changes needed
from app.config import get_settings
settings = get_settings()
provider = get_video_generator(mock=settings.use_mock_ai)
```

---

## Alternatives Considered

| Recommended | Alternative | Why Not |
|-------------|-------------|---------|
| HTMX 2.0.8 (CDN) | Alpine.js, Vue, React | HTMX = HTML attributes, no build step, zero config. Matches existing Jinja2 pattern. Alpine.js is close second but HTMX SSE extension is needed anyway. |
| `python-statemachine` 2.6.0 | `transitions` 0.9.3 | Both valid. `python-statemachine` has async-native design and was released Feb 2026. `transitions` supports Python 2.7 (legacy baggage). Either works for this use case. |
| `FileResponse` + `StreamingResponse` (Starlette) | nginx to serve `output/` | nginx requires Docker config changes. Starlette works now with zero additions. Use nginx only if video load becomes a bottleneck (unlikely for internal review tool). |
| SSE (existing pattern) | WebSockets | SSE is one-directional (server → client) which is all regeneration needs. WebSockets add bidirectional overhead. SSE already works in the codebase. |
| Jinja2 partial templates | JSON API + client-side render | JSON API requires JS to render HTML. Partial templates return ready HTML — simpler, fewer moving parts, no JS templating. |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| React / Vue / Svelte | Build step, separate server, breaks "Jinja2 only" constraint. | HTMX CDN script tag. |
| WebSockets for progress | Bidirectional overhead. Regeneration only needs server→client. | SSE (existing pattern, already proven). |
| SQLAlchemy `Enum` column type | Migration pain — changing enum values requires `ALTER TYPE` in PostgreSQL. | `String(50)` column (existing pattern) with `python-statemachine` as guard layer. |
| Celery `chord`/`group` for per-frame regen | Complex error recovery. One frame at a time is simpler, cheaper to retry. | Single Celery task per frame regeneration request. |
| Global state refresh on every action | Reloading full review page on approve/reject kills UX. | HTMX `hx-target="#frame-{id}" hx-swap="outerHTML"` — swap only the affected card. |

---

## Stack Patterns by Variant

**If regeneration is fast (< 2s, mock mode):**
- Skip SSE entirely. Return updated card HTML directly from the `POST /regenerate` endpoint.
- Simpler: no SSE connection management.

**If regeneration is slow (> 5s, real AI providers):**
- Fire Celery task, return "regenerating" card immediately.
- SSE stream polls Celery result via `AsyncResult(task_id).state`.
- On completion, swap card with final content.

**If running all-mock (smoke test):**
- Mock providers return instantly. No SSE needed for regeneration.
- FileResponse still serves mock-generated images/videos from `output/`.

---

## Version Compatibility

| Package | Version | Compatible With | Notes |
|---------|---------|-----------------|-------|
| python-statemachine | 2.6.0 | Python 3.7–3.14 | Confirmed compatible with Python 3.13 (project uses 3.13 per venv). |
| HTMX | 2.0.8 | All modern browsers, no IE | SSE extension 2.2.4 required separately if using `hx-ext="sse"`. |
| HTMX SSE ext | 2.2.4 | HTMX 2.0.x | Must match HTMX major version (2.x). Do not mix with HTMX 1.x. |
| FastAPI FileResponse | Starlette 0.49.3 | FastAPI 0.128.8 | Already installed. Range request (206) requires manual `StreamingResponse` — `FileResponse` does not handle Range headers automatically. |

**Critical note on FileResponse + Range requests:** `FileResponse` does NOT implement HTTP 206 partial content. Browsers request video ranges for seeking. If you return `FileResponse` for video, seek will not work. Use `StreamingResponse` with manual range parsing (see Integration section above).

---

## Database Changes Required

New columns on `Video` model (via Alembic migration):

```python
# New columns — add to existing Video model
reviewed_at = Column(DateTime(timezone=True), nullable=True)
reviewer_note = Column(Text, nullable=True)  # Optional reject reason
```

New model for per-frame review state (if UGC pipeline frames are tracked individually):

```python
class VideoFrame(Base):
    """Per-frame review state for UGC pipeline."""
    __tablename__ = "video_frames"

    id = Column(Integer, primary_key=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False)
    frame_type = Column(String(50))  # "script", "hero_image", "a_roll", "b_roll", "composite"
    status = Column(String(50), default="pending")  # pending, approved, rejected, regenerating
    image_path = Column(String(1000), nullable=True)
    video_path = Column(String(1000), nullable=True)
    script_text = Column(Text, nullable=True)
    generation_params = Column(JSON, nullable=True)  # Prompt/config used to generate
    celery_task_id = Column(String(255), nullable=True)  # For polling regen status
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    reviewer_note = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
```

---

## Sources

### HIGH Confidence (Official Docs / PyPI / Verified)

- [python-statemachine PyPI](https://pypi.org/project/python-statemachine/) — Version 2.6.0, released 2026-02-13, Python 3.7–3.14
- [python-statemachine docs: States from Enum](https://python-statemachine.readthedocs.io/en/latest/api.html) — `States.from_enum()` usage
- [HTMX 2.0.8 CDN](https://cdn.jsdelivr.net/npm/htmx.org@2.0.8/dist/htmx.min.js) — Stable, confirmed via jsDelivr
- [HTMX SSE Extension](https://htmx.org/extensions/sse/) — Version 2.2.4, `hx-ext="sse"`, `sse-swap`, `sse-close` attributes
- [FastAPI Custom Responses Docs](https://fastapi.tiangolo.com/advanced/custom-response/) — `FileResponse`, `StreamingResponse`, parameters
- [FastAPI StreamingResponse Range Discussion](https://github.com/fastapi/fastapi/discussions/7718) — Range request pattern, 206 status, why FileResponse doesn't handle Range
- [transitions PyPI](https://pypi.org/project/transitions/) — Version 0.9.3, released 2025-07-02 (alternative considered)

### MEDIUM Confidence (Multiple Sources, Verified)

- [Streaming Video with FastAPI](https://stribny.name/posts/fastapi-video/) — Range request implementation pattern, chunk size guidance
- [HTMX FastAPI patterns 2025](https://testdriven.io/blog/fastapi-htmx/) — Partial template rendering for HTMX swaps, `hx-target`/`hx-swap` patterns
- [HTMX 2.0.0 release notes](https://htmx.org/posts/2024-06-17-htmx-2-0-0-is-released/) — Confirmed stable since June 2024, IE dropped

---

## Key Takeaways

1. **Two new installs only**: `python-statemachine==2.6.0` (Python) + HTMX CDN (no npm).
2. **SSE already works**: Phase 17 built the pattern. Review workflow reuses it per-frame.
3. **No React/Vue**: HTMX swaps Jinja2 fragments. Simpler than JSON API + client render.
4. **Range requests matter**: `FileResponse` breaks video seeking. Use `StreamingResponse` + manual range parsing for `.mp4` files.
5. **State machine as guard only**: `python-statemachine` validates transitions. SQLAlchemy `String(50)` column stays as the source of truth.
6. **Mock/real toggle is free**: Existing `use_mock_ai` setting propagates through existing provider pattern. No new code needed.

---

*v3.0 Review Workflow Stack — ViralForge*
*Researched: 2026-02-20*
*Confidence: HIGH (all components verified with official sources)*
