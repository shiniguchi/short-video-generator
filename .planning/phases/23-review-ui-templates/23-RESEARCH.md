# Phase 23: Review UI Templates - Research

**Researched:** 2026-02-21
**Domain:** FastAPI + Jinja2 + HTMX 2.0.8 + SSE Extension 2.2.4 — UGC review pipeline UI
**Confidence:** HIGH

## Summary

Phase 23 builds the browser UI for the UGC review pipeline. All API endpoints from Phase 22 are already implemented (`/ugc/jobs`, `/ugc/jobs/{id}`, `/ugc/jobs/{id}/events`, `/ugc/jobs/{id}/advance`, `/ugc/jobs/{id}/regenerate`). Phase 23 is purely UI work: new HTML templates + new routes in the existing `app/ui/router.py`.

The codebase already has a well-established UI pattern: `{% extends "base.html" %}`, `app/ui/router.py` for routes, `app/ui/static/ui.css` for styling, and vanilla-JS SSE in `ui.js`. Phase 23 introduces HTMX 2.0.8 for the first time — HTMX scripts must be added to `base.html` or a separate UGC-scoped base. All approve/reject actions use `hx-post` + `hx-swap="outerHTML"` on a partial template endpoint that returns only the replaced card/button HTML.

Two new templates are required: `ugc_new.html` (job creation form with mock toggle) and `ugc_review.html` (stage stepper + per-stage item grids + HTMX approve/reject). The stage stepper maps `job.status` to one of five review states. Locked stages are visually disabled via CSS. Approve/reject actions post to the existing API and swap the card in place — no page reload.

**Primary recommendation:** Add two UI routes to `app/ui/router.py`, two full-page templates, and one partial template for card swaps. Add HTMX CDN scripts to `base.html`. Use SSE extension for live status during `running` state, and plain `hx-post` for approve/reject during review states.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | 0.128.8 | `TemplateResponse` in UI routes | Existing web framework |
| Jinja2 | 3.1.6 | Server-side HTML templates with context variables | Existing template engine |
| HTMX | 2.0.8 (CDN) | Approve/reject via `hx-post` + partial swap, no JS | Prior locked decision |
| htmx-ext-sse | 2.2.4 (CDN) | `hx-ext="sse"` + `sse-connect` for live SSE progress | Prior locked decision |
| ui.css | (existing) | Existing class-based stylesheet — extend for new components | Project standard |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| SQLAlchemy (async) | 2.0.46 | Load `UGCJob` for template context | UI GET routes load job from DB |
| python-statemachine | 2.6.0 | NOT needed in UI layer | API handles state transitions |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Separate partial template file | jinja2-fragments block rendering | `jinja2-fragments` not installed; separate partials file is simpler, no new dependency |
| HTMX CDN in base.html | Bundle with build step | No build step in this project — CDN is the prior decision |
| HTMX for job creation form | Standard HTML form POST | Either works; HTMX adds no value for a simple one-time form — use standard form POST |

**Installation:** No new packages. HTMX added via CDN script tags in `base.html`.

## Architecture Patterns

### File Structure

```
app/
├── ui/
│   ├── router.py                    # EXTEND: add 3 new routes (ugc_new, ugc_list, ugc_review)
│   ├── static/
│   │   └── ui.css                   # EXTEND: add stepper, card-grid, stage-badge CSS
│   └── templates/
│       ├── base.html                # EXTEND: add HTMX + SSE CDN script tags
│       ├── ugc_new.html             # NEW: job creation form
│       ├── ugc_list.html            # NEW: list all UGC jobs
│       ├── ugc_review.html          # NEW: stage stepper + item grids + approve/reject
│       └── partials/
│           └── ugc_stage_controls.html  # NEW: approve/reject button partial (swapped by HTMX)
```

### Pattern 1: Stage Stepper (Visual Progress)

**What:** A horizontal ordered list of 5 stages. The active stage is highlighted. Completed stages show a check. Future stages are visually muted/disabled. The stepper is rendered server-side from `job.status`.

**When to use:** Top of `ugc_review.html`.

**Stage-to-status mapping:**
```python
# In ui/router.py context building
STAGE_ORDER = [
    ("stage_analysis_review", "Analysis"),
    ("stage_script_review", "Script"),
    ("stage_aroll_review", "A-Roll"),
    ("stage_broll_review", "B-Roll"),
    ("stage_composition_review", "Composition"),
]

# Derive stepper state from job.status
# "running" = between stages — stepper shows progress toward next review
# A stage is "complete" if its review state is past in the ordered list
# A stage is "active" if it's the current review state (or running toward it)
# A stage is "locked" if it's after the current active stage
```

**Example:**
```html
<!-- Source: HTMX docs + project CSS conventions -->
<ol class="stage-stepper">
  {% for status_key, label in stage_order %}
    {% if status_key == job.status %}
      <li class="step step-active">{{ label }}</li>
    {% elif status_key in completed_stages %}
      <li class="step step-done">{{ label }}</li>
    {% else %}
      <li class="step step-locked" aria-disabled="true">{{ label }}</li>
    {% endif %}
  {% endfor %}
</ol>
```

### Pattern 2: HTMX Approve/Reject with Partial Swap

**What:** Approve and Regenerate buttons each post to the API. The response is a partial HTML fragment (`ugc_stage_controls.html`) that replaces the button container. No page reload.

**When to use:** Shown only when `job.status` is a review state (not `running`).

**Critical:** The partial template endpoint in `ui/router.py` must render only `ugc_stage_controls.html` — not wrapped in `base.html`.

**Example:**
```html
<!-- In ugc_review.html — button container that gets swapped -->
<div id="stage-controls">
  <button
    hx-post="/ugc/jobs/{{ job.id }}/advance"
    hx-target="#stage-controls"
    hx-swap="outerHTML"
    hx-indicator="#spinner"
    class="btn btn-primary">
    Approve & Continue
  </button>
  {% if job.status != "stage_composition_review" %}
  <button
    hx-post="/ugc/jobs/{{ job.id }}/regenerate"
    hx-target="#stage-controls"
    hx-swap="outerHTML"
    class="btn btn-secondary">
    Regenerate
  </button>
  {% endif %}
</div>
```

**HTMX response:** The `/ugc/jobs/{id}/advance` API returns JSON (`{"job_id": ..., "status": ...}`). HTMX expects HTML for `hx-swap`. Two options:
1. **Add a UI wrapper endpoint** in `ui/router.py` (e.g., `POST /ui/ugc/{id}/advance`) that calls the API internally and returns `TemplateResponse("partials/ugc_stage_controls.html", ...)`.
2. **Have HTMX post directly to the API** and use `hx-on::after-request` JS to reload the page on success.

**Recommendation:** Option 1 — UI wrapper POST in `ui/router.py` that returns HTML partial. Keeps HTMX declarative and avoids JS. The wrapper calls `advance_ugc_job` logic directly (or just duplicates the DB write inline since it's 3 lines).

### Pattern 3: SSE Progress During Running State

**What:** When `job.status == "running"`, connect to SSE endpoint and display live status. When SSE stream closes (status hits a review state), reload the controls section via `hx-trigger="sse:message"`.

**When to use:** `ugc_review.html` — only when job is in `running` state.

**Example:**
```html
<!-- SSE live progress — shown only when status == "running" -->
{% if job.status == "running" %}
<div id="sse-progress"
     hx-ext="sse"
     sse-connect="/ugc/jobs/{{ job.id }}/events"
     sse-swap="message"
     hx-swap="innerHTML">
  <p class="status-msg">Running pipeline...</p>
</div>
{% endif %}
```

The SSE extension replaces `#sse-progress` innerHTML with each `data:` message from the server. When the stream closes (status hits a review state), the page needs a mechanism to show the review controls. Options:

- **Use `hx-trigger="sse:message"` on a sibling element** to trigger a GET of the review controls when a message arrives — but this fires on every message.
- **Use `sse-close="done"` with a named SSE event** — cleaner but requires the server to emit a named `event: done` line.
- **Simplest approach:** When the SSE stream closes naturally (server-side disconnect on terminal state), JavaScript can detect the `htmx:sseClose` event and reload the page section. OR just reload the full page.

**Simplest reliable approach:** Emit `data: {"status": "...", "reload": true}` when hitting a terminal state. The HTMX SSE `sse-swap` updates the progress div. Add a thin `<script>` listener on the `htmx:sseClose` event to do `window.location.reload()`.

```html
<script>
  document.body.addEventListener("htmx:sseClose", function() {
    window.location.reload();
  });
</script>
```

This keeps the template simple. On reload, the route reloads job from DB and renders review controls server-side.

### Pattern 4: Item Grid for Stage Review

**What:** A CSS grid of cards — one per reviewable item. Stage 1 (analysis) shows text fields. Stages 3-4 (aroll, broll) show media paths. Stage 5 (composition) shows final video.

**Content by stage:**
```
stage_analysis_review:
  - analysis_category, analysis_ugc_style, analysis_emotional_tone
  - analysis_key_features (list), analysis_visual_keywords (list)
  - analysis_target_audience
  - hero_image_path (image thumbnail)

stage_script_review:
  - master_script (dict — hook, scenes, CTA)
  - aroll_scenes (list — text per scene)
  - broll_shots (list — visual desc per shot)

stage_aroll_review:
  - aroll_paths (list of file paths — audio/video files)

stage_broll_review:
  - broll_paths (list of file paths — video clips)

stage_composition_review:
  - final_video_path (final composed video)
  - candidate_video_path (if regenerated)
```

**Note:** Per-item approve/reject (REVIEW-02) means each card shows Approve/Reject buttons. However, the current DB model has no per-item approval columns. The API `advance` endpoint advances the entire stage. REVIEW-02 as worded ("approve or reject each individual item") must be interpreted at stage level for this phase, OR per-item state is stored client-side only with a final "approve all" action. See Open Questions.

### Pattern 5: Locked Stage Visual State

**What:** Stages after the current review state are visually locked — buttons disabled, cards muted, with `aria-disabled="true"`. This is CSS-only; the API already enforces stage gates.

**Example CSS:**
```css
/* In ui.css */
.step-locked {
  color: #9ca3af;
  opacity: 0.5;
  cursor: not-allowed;
}
.step-active {
  color: #1a1a2e;
  font-weight: 700;
  border-bottom: 2px solid #1a1a2e;
}
.step-done {
  color: #15803d;
}
.step-done::after {
  content: " ✓";
}
```

### Pattern 6: UGC Job Creation Form

**What:** `ugc_new.html` — a form with: product name, description, product URL (optional), target duration, style preference, mock/real toggle checkbox, image upload. On submit, posts to `/ugc/jobs` API.

**Note:** The `/ugc/jobs` POST endpoint accepts `multipart/form-data`. The HTML form must have `enctype="multipart/form-data"` for image upload.

**Example:**
```html
<form method="POST" action="/ugc/jobs" enctype="multipart/form-data">
  <div class="form-group">
    <label for="product_name">Product Name</label>
    <input type="text" id="product_name" name="product_name" required>
  </div>
  <div class="form-group">
    <label for="description">Description</label>
    <textarea id="description" name="description" required></textarea>
  </div>
  <div class="form-group form-check">
    <input type="checkbox" id="use_mock" name="use_mock" checked value="true">
    <label for="use_mock">Use mock data (no API calls)</label>
  </div>
  <!-- ... more fields ... -->
  <button type="submit" class="btn btn-primary">Start Job</button>
</form>
```

**CRITICAL:** FastAPI's `use_mock: bool = Form(True)` expects the value `"true"` or `"false"` from form data. A checkbox sends its value when checked, and nothing when unchecked. This requires either: (a) hidden input with `value="false"` before the checkbox (overridden when checkbox is checked), or (b) JavaScript to set a hidden field. The simplest approach: use a `<select>` with `true`/`false` options instead of a checkbox, OR use JS.

Actually the existing `generate.html` uses a checkbox for `mock: bool = Form(False)`. FastAPI's form bool parsing: if the field name is present in the form data with any truthy value, it's `True`; if absent, it falls back to the default. A checked checkbox sends `name=value`; unchecked sends nothing. So `use_mock: bool = Form(True)` with a checkbox: unchecked → field absent → uses default `True` (wrong). Better: use `Form(False)` as default and send `"true"` when checked.

### Anti-Patterns to Avoid

- **Returning JSON from UI wrapper endpoints:** HTMX swap endpoints must return HTML, not JSON. Keep API (`ugc_router.py`) as JSON, UI wrapper (`ui/router.py`) as HTML.
- **Loading HTMX script after elements with `hx-ext="sse"`:** SSE extension must be loaded before DOM elements that use it. Load in `<head>` or early in `<body>`.
- **No `enctype="multipart/form-data"` on file upload form:** Without it, images are not sent. `ugc_new.html` must include this.
- **Checkbox bool quirk — unchecked = field absent:** FastAPI treats absent form field as the default value. Test checkbox behavior explicitly. Use `<select>` if ambiguous.
- **Treating `running` status as a review state:** The stepper must handle `running` specially — it's between two review stages. Derive the "active" stage from which review state was last passed (can be inferred from which columns are populated).
- **Using `Depends(get_session)` in SSE generator:** Already resolved in Phase 22 — `async_session_factory()` per iteration. UI SSE elements connect to the existing `/ugc/jobs/{id}/events` API endpoint, not a new one.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Per-item approve state | Custom JS state object | Stage-level approve via `hx-post` to `/ugc/jobs/{id}/advance` | Per-item columns don't exist in DB; stage gate is the unit of approval |
| SSE reconnect logic | Custom EventSource wrapper | HTMX SSE extension handles reconnect automatically | Extension has built-in reconnect; don't add JS |
| Partial template fragments | jinja2-fragments | Separate partial template files in `templates/partials/` | jinja2-fragments not installed; separate files are simpler |
| Status → stage label mapping | Complex conditional chain | Dict in route context: `STAGE_LABELS = {"stage_analysis_review": "Analysis", ...}` | Pass mapping to template, iterate in Jinja2 |
| HTMX response headers | Custom middleware | `HX-Redirect` response header for post-approve navigation | HTMX reads `HX-Redirect` header and navigates — no JS needed |

**Key insight:** The hardest parts (DB polling, SSE framing, state transitions) are already done. Phase 23 is template + CSS + route wiring.

## Common Pitfalls

### Pitfall 1: Checkbox `use_mock` Not Sending Boolean Correctly

**What goes wrong:** FastAPI receives `use_mock=True` (default) even when the user unchecked the box, because an unchecked checkbox sends no value — the form field is absent — so FastAPI uses the `Form(...)` default.

**Why it happens:** HTML spec: unchecked checkboxes are not included in form submission data.

**How to avoid:** Use one of:
1. A hidden input `<input type="hidden" name="use_mock" value="false">` placed BEFORE the checkbox. The checkbox value (`"true"`) overrides it when checked; the hidden value sends `"false"` when unchecked.
2. A `<select>` with `<option value="true">Mock</option><option value="false">Real</option>`.

FastAPI with `use_mock: bool = Form(...)`: it parses `"true"` → `True`, `"false"` → `False`. Both options work.

**Warning signs:** Jobs always created with `use_mock=True` (or always `False`) regardless of checkbox state.

### Pitfall 2: `running` State Has No Review Content to Show

**What goes wrong:** Template renders `ugc_review.html` when `job.status == "running"`. The template shows no stage output columns (they're None). The stepper shows a stage as "active" but there's nothing to approve.

**Why it happens:** `running` is a transient state between stages. The stage data columns are only populated when a stage completes and status transitions to a review state.

**How to avoid:** In `ugc_review.html`, gate the item grid on `job.status in review_states`. While `running`, show only the SSE progress area. Use Jinja2 conditionals: `{% if job.status == "running" %}...{% elif job.status in review_states %}...{% endif %}`.

**Warning signs:** Template renders empty grids, or Jinja2 errors from iterating `None` list values.

### Pitfall 3: HTMX Approve Button Returns JSON, Not HTML

**What goes wrong:** `hx-post="/ugc/jobs/{{ job.id }}/advance"` posts to the API endpoint which returns `{"job_id": ..., "status": ...}`. HTMX tries to swap this JSON string into `#stage-controls` — result is raw JSON text in the DOM.

**Why it happens:** HTMX expects HTML from any endpoint it targets with `hx-swap`. The existing API returns JSON.

**How to avoid:** Add UI wrapper endpoints in `ui/router.py`:
- `POST /ui/ugc/{id}/advance` → calls advance logic, returns `TemplateResponse("partials/ugc_stage_controls.html", {"job": job})`
- `POST /ui/ugc/{id}/regenerate` → same pattern

The HTMX buttons point to `/ui/ugc/{id}/advance`, not `/ugc/jobs/{id}/advance`.

**Warning signs:** DOM shows `{"job_id": 1, "status": "running"}` text inside the button area after clicking Approve.

### Pitfall 4: SSE Connection Stays Open on Review State

**What goes wrong:** SSE element `sse-connect="/ugc/jobs/{{ job.id }}/events"` stays connected even after the stream closes. The browser auto-reconnects to SSE endpoints when the connection drops. The server-side generator terminates when a terminal state is reached, but the browser will retry.

**Why it happens:** Browser EventSource auto-reconnect is built into the spec. HTMX SSE extension respects this.

**How to avoid:** Use `sse-close` attribute to close the connection on a specific named event, OR listen for `htmx:sseClose` and stop reconnect. The simplest approach: when status is a review state on page load, don't render the SSE div at all (gate on `job.status == "running"`). When the SSE stream closes and triggers a page reload, the reloaded page won't have the SSE div if status is now a review state.

**Warning signs:** Browser DevTools shows repeated GET requests to `/ugc/jobs/{id}/events` after the job reaches a review state.

### Pitfall 5: Stepper "Active" Stage Ambiguous During `running`

**What goes wrong:** When `job.status == "running"`, you don't know which review stage was last completed without inspecting data columns or tracking the transition sequence.

**Why it happens:** `running` is shared by all inter-stage transitions (stage 1→2, 2→3, etc.). The status field doesn't say "running toward stage 2."

**How to avoid:** Derive the "currently running toward" stage by checking which data columns are populated:
- `aroll_scenes is not None` → running toward stage_aroll_review (stage 3 completed)
- `aroll_paths is not None` → running toward stage_broll_review (stage 4 completed)
- etc.

Or simplify: just show the SSE progress div without a specific active stage highlighted when `running`. Highlight only when in a review state.

## Code Examples

### UI Route for Review Page
```python
# Source: app/ui/router.py — new route, follows existing TemplateResponse pattern
from sqlalchemy import select
from app.models import UGCJob

STAGE_ORDER = [
    ("stage_analysis_review", "Analysis"),
    ("stage_script_review", "Script"),
    ("stage_aroll_review", "A-Roll"),
    ("stage_broll_review", "B-Roll"),
    ("stage_composition_review", "Composition"),
]
REVIEW_STATES = {s for s, _ in STAGE_ORDER}

@router.get("/ugc/{job_id}/review", response_class=HTMLResponse)
async def ugc_review(request: Request, job_id: int, session: AsyncSession = Depends(get_session)):
    """Render stage stepper + item grid for a UGC job."""
    result = await session.execute(select(UGCJob).where(UGCJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail=f"UGCJob {job_id} not found")

    # Derive completed stages for stepper rendering
    stage_keys = [s for s, _ in STAGE_ORDER]
    current_idx = stage_keys.index(job.status) if job.status in stage_keys else -1
    completed_stages = set(stage_keys[:current_idx])

    return templates.TemplateResponse(
        request=request,
        name="ugc_review.html",
        context={
            "job": job,
            "stage_order": STAGE_ORDER,
            "completed_stages": completed_stages,
            "review_states": REVIEW_STATES,
        },
    )
```

### UI Wrapper POST for Approve (returns HTML partial)
```python
# Source: app/ui/router.py — new route for HTMX approve action
@router.post("/ugc/{job_id}/advance", response_class=HTMLResponse)
async def ugc_ui_advance(request: Request, job_id: int, session: AsyncSession = Depends(get_session)):
    """HTMX target: approve current stage. Returns updated stage-controls partial."""
    from app.ugc_router import advance_ugc_job  # reuse router logic

    # Call advance inline (or duplicate the 3-line DB write)
    result = await session.execute(select(UGCJob).where(UGCJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404)

    # Re-use advance logic inline
    from app.ugc_router import _STAGE_ADVANCE_MAP
    from app.state_machines.ugc_job import UGCJobStateMachine
    from statemachine.exceptions import TransitionNotAllowed

    if job.status not in _STAGE_ADVANCE_MAP:
        raise HTTPException(status_code=400, detail=f"Cannot advance from '{job.status}'")

    approve_event, next_task_name = _STAGE_ADVANCE_MAP[job.status]
    sm = UGCJobStateMachine(model=job, state_field="status", start_value=job.status)
    sm.send(approve_event)
    job.status = sm.current_state.id
    await session.commit()

    if next_task_name:
        import app.ugc_tasks as ugc_tasks_module
        getattr(ugc_tasks_module, next_task_name).delay(job_id)

    return templates.TemplateResponse(
        request=request,
        name="partials/ugc_stage_controls.html",
        context={"job": job, "review_states": REVIEW_STATES},
    )
```

### base.html HTMX CDN Addition
```html
<!-- Add to <head> in base.html — BEFORE any hx-ext="sse" elements -->
<script src="https://cdn.jsdelivr.net/npm/htmx.org@2.0.8/dist/htmx.min.js"
  integrity="sha384-/TgkGk7p307TH7EXJDuUlgG3Ce1UVolAOFopFekQkkXihi5u/6OCvVKyz1W+idaz"
  crossorigin="anonymous"></script>
<script src="https://cdn.jsdelivr.net/npm/htmx-ext-sse@2.2.4/sse.js"
  integrity="sha384-A986SAtodyH8eg8x8irJnYUk7i9inVQqYigD6qZ9evobksGNIXfeFvDwLSHcp31N"
  crossorigin="anonymous"></script>
```

### Stage Controls Partial Template
```html
<!-- Source: templates/partials/ugc_stage_controls.html -->
<!-- Returned by UI wrapper POST — swapped into #stage-controls via outerHTML -->
<div id="stage-controls">
  {% if job.status in review_states %}
    <button
      hx-post="/ui/ugc/{{ job.id }}/advance"
      hx-target="#stage-controls"
      hx-swap="outerHTML"
      class="btn btn-primary">
      Approve &amp; Continue
    </button>
    {% if job.status != "stage_composition_review" %}
    <button
      hx-post="/ui/ugc/{{ job.id }}/regenerate"
      hx-target="#stage-controls"
      hx-swap="outerHTML"
      class="btn btn-secondary">
      Regenerate
    </button>
    {% endif %}
  {% elif job.status == "approved" %}
    <p class="status-msg">Job approved and complete.</p>
  {% elif job.status == "running" %}
    <p class="status-msg">Pipeline running — waiting for stage to complete...</p>
  {% endif %}
</div>
```

### SSE Section in ugc_review.html
```html
<!-- Source: HTMX SSE extension docs + htmx.org/extensions/sse/ -->
{% if job.status == "running" %}
<div id="sse-progress"
     hx-ext="sse"
     sse-connect="/ugc/jobs/{{ job.id }}/events"
     sse-swap="message"
     hx-swap="innerHTML">
  <p class="status-msg">Connecting to pipeline...</p>
</div>
<script>
  /* Reload page when SSE stream closes — shows review controls */
  document.body.addEventListener("htmx:sseClose", function() {
    window.location.reload();
  });
</script>
{% endif %}
```

### Checkbox bool fix for `use_mock`
```html
<!-- Hidden field sends "false" when unchecked; checkbox value "true" overrides when checked -->
<input type="hidden" name="use_mock" value="false">
<input type="checkbox" id="use_mock" name="use_mock" value="true" checked>
<label for="use_mock">Use mock data (no API calls)</label>
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Vanilla JS SSE (`ui.js` `connectSSE`) | HTMX SSE extension (`hx-ext="sse"`) | Phase 23 (first use) | Declarative SSE — minimal JS for review page |
| Full page form POST + redirect | HTMX `hx-post` + `hx-swap="outerHTML"` | Phase 23 (first use) | Approve/reject in-place — no page reload |
| Plain Jinja2 templates (no HTMX) | HTMX-augmented templates | Phase 23 | base.html needs CDN scripts added |

**Not deprecated:**
- Existing vanilla JS in `ui.js` (used by LP generation `progress.html`) — leave it unchanged.
- Existing `connectSSE()` function in `ui.js` — keep it; it serves `progress.html` still.

## Open Questions

1. **REVIEW-02: Per-item approve/reject**
   - What we know: REVIEW-02 says "approve or reject each individual item (scene, image, clip)". The DB has no per-item approval columns. The API `advance` endpoint advances the whole stage.
   - What's unclear: Does the planner want per-item approval to actually gate the stage advance (require ALL items approved), or is it just visual UX (user clicks approve on each card, then clicks a final "approve stage" button)?
   - Recommendation: Implement as visual-only per-item state stored in browser memory (JS or hidden inputs), with a single "Approve Stage" button that posts to `/advance`. Per-item rejections are handled via the Regenerate button (regenerates the whole stage). This avoids DB schema changes in Phase 23.

2. **`running` state navigation**
   - What we know: A user might navigate to `/ui/ugc/{id}/review` while `job.status == "running"`. The SSE stream should auto-connect.
   - What's unclear: Should the page also work if the user navigates there after a stage completes (status = review state), without ever having seen the SSE stream?
   - Recommendation: Yes — the route always renders correctly for any status. SSE div only appears for `running`; review controls appear for review states. This is already handled by the Jinja2 conditional pattern above.

3. **Nav link for UGC section**
   - What we know: `base.html` nav has links to Dashboard, Waitlist, Generate.
   - What's unclear: Should a "UGC" link be added to nav pointing to `/ui/ugc` (job list)?
   - Recommendation: Yes — add "UGC" to nav in `base.html`. The ugc_list.html page is the UGC section entry point.

4. **Media serving for aroll/broll preview**
   - What we know: `aroll_paths` and `broll_paths` are local file paths. The `output/` directory is mounted as `/output` static files in `main.py`.
   - What's unclear: Are the aroll/broll file paths under `output/`? If so, they're already servable.
   - Recommendation: Phase 24 handles video/media preview (MEDIA-01 through MEDIA-03). For Phase 23, show file path strings as text in the grid cards — don't try to embed video players yet.

## Sources

### Primary (HIGH confidence)
- Codebase: `app/ui/router.py` — existing TemplateResponse pattern, route structure
- Codebase: `app/ui/templates/base.html` — current template structure, no HTMX yet
- Codebase: `app/ui/static/ui.css` — existing CSS classes and conventions
- Codebase: `app/ugc_router.py` — all API endpoints available for UI wrapper calls; `_STAGE_ADVANCE_MAP`, `_STAGE_REGEN_MAP` verified
- Codebase: `app/models.py:147-203` — UGCJob column layout; mapped stage outputs to stepper states
- Codebase: `app/state_machines/ugc_job.py` — 5 review states + running + approved + failed
- Codebase: `.planning/STATE.md` — confirmed locked decisions (HTMX 2.0.8 CDN, SSE Extension 2.2.4, hx-post + outerHTML)
- WebFetch: `https://htmx.org/extensions/sse/` — verified `hx-ext="sse"`, `sse-connect`, `sse-swap="message"`, `sse-close`, CDN script tags with integrity hashes
- WebFetch: `https://htmx.org/docs/#swapping` — verified `hx-swap="outerHTML"`, `hx-target`, `hx-post` behavior

### Secondary (MEDIUM confidence)
- WebSearch: jinja2-fragments not in requirements.txt (verified) — confirmed separate partial files are the correct approach
- WebSearch: HTMX SSE `htmx:sseClose` custom event — confirmed as the extension's close event name for JS listener

### Tertiary (LOW confidence)
- Checkbox `use_mock` bool behavior with FastAPI `Form(...)`: derived from HTML spec + FastAPI form parsing behavior; recommended to test manually during implementation.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries already installed; HTMX CDN URLs verified with integrity hashes
- Architecture patterns: HIGH — derived directly from existing codebase patterns + API endpoints
- HTMX hx-swap behavior: HIGH — verified from official HTMX docs
- SSE extension behavior: HIGH — verified from `htmx.org/extensions/sse/`
- Pitfalls: HIGH for JSON-vs-HTML swap and checkbox bool; MEDIUM for SSE reconnect behavior details
- Per-item approve approach: MEDIUM — recommendation is pragmatic but planner may choose differently

**Research date:** 2026-02-21
**Valid until:** 2026-03-23 (stable; HTMX 2.0.8 + Jinja2 3.1.6 are not fast-moving)
