# Phase 25: LP Integration - Research

**Researched:** 2026-02-21
**Domain:** LP module review UI, video frame extraction, UGCJob-to-LP pipeline bridge
**Confidence:** HIGH

## Summary

Phase 25 bridges two existing pipelines: the UGC video pipeline (Phases 20-24, `UGCJob` model, `ugc_review.html`) and the LP generation pipeline (Phases 14-15, `LandingPage` model, `generate_landing_page()`). The LP generation code already exists and works. This phase adds (1) per-module review cards for LP content, (2) a stage gate that locks LP review until the UGC job reaches `approved`, and (3) video frame extraction to pre-populate the LP hero image from the approved video.

The biggest architectural decision is **where LP review state lives**. The existing `LandingPage` model has no concept of per-module approval status and no link to a `UGCJob`. Two options: (a) add columns to `LandingPage`, or (b) store per-module approval in a new `JSON` column. Option (b) is simpler and consistent with how `UGCJob` stores stage data in JSON columns.

Frame extraction is already solved by the existing `generate_thumbnail()` function in `app/services/video_compositor/thumbnail.py`. It uses `moviepy.VideoFileClip.get_frame()` + `PIL.Image.save()`. The same approach extracts a frame at e.g. `t=2.0` and saves a JPEG — usable directly as the LP hero image.

LP-specific image regeneration (LP-10) needs a new Celery task and API endpoint that calls the existing image provider, stores the new path, and does not mutate the approved hero. Per the project decision "Regeneration produces candidates: Never mutate approved content in place", new images should go to a candidate column.

**Primary recommendation:** Add `ugc_job_id` FK + `lp_module_approvals` JSON + `lp_hero_image_path` + `lp_hero_candidate_path` columns to `LandingPage`. Reuse `ugc_review.html` card pattern for LP module cards. Reuse `generate_thumbnail()` for frame extraction. Add one Celery task for LP image regeneration.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| moviepy | 2.2.1 | Video frame extraction via `VideoFileClip.get_frame()` | Already in project; used in `thumbnail.py` and `ugc_compositor.py` |
| Pillow | 11.3.0 | Save extracted frame as JPEG | Already in project; used in `thumbnail.py` |
| SQLAlchemy | 2.0.46 | ORM for new columns on `LandingPage` | Existing ORM |
| Alembic | 1.16.5 | DB migration for new columns | Existing migration toolchain |
| Jinja2 | 3.1.6 | Template for LP module review cards | Existing template engine |
| HTMX | 2.0.8 (CDN) | Approve/reject buttons, outerHTML swap | Already loaded in `base.html` |
| python-statemachine | 2.6.0 | Guard LP stage gate (locked until video approved) | Existing pattern; `UGCJobStateMachine` is the reference |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Celery | 5.6.2 | LP image regeneration task | Reuse existing `celery_app` from `worker.py` |
| image_provider | existing | Generate new LP hero images | Reuse `app/services/image_provider/` pattern |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| JSON `lp_module_approvals` column | Separate `LPModuleApproval` table | JSON column is simpler; module count is fixed (4 modules); no relational queries needed |
| Separate `LPJob` model | Extend `LandingPage` | LP generation already writes to `LandingPage`; adding columns avoids a new model and migration complexity |
| New image provider call for regen | Re-run full LP generation | Full regen is too heavy; only the hero image needs replacing |

**Installation:** No new packages.

## Architecture Patterns

### Recommended Project Structure

```
app/
├── models.py                        # ADD: ugc_job_id, lp_module_approvals, lp_hero_image_path, lp_hero_candidate_path to LandingPage
├── ugc_router.py                    # ADD: POST /ugc/jobs/{id}/lp-review endpoint to trigger LP generation after approval
├── ui/
│   ├── router.py                    # ADD: GET /ui/lp/{run_id}/review, POST /ui/lp/{run_id}/module/{module}/approve
│   └── templates/
│       ├── lp_review.html           # NEW: LP module review page (mirrors ugc_review.html structure)
│       └── partials/
│           └── lp_stage_controls.html  # NEW: LP approve/regen buttons partial
alembic/
└── versions/
    └── 007_lp_integration_schema.py # NEW: migration adding columns to landing_pages
```

### Pattern 1: LP Module Approval via JSON Column

**What:** Store per-module approval status in a JSON dict `{"headline": "approved", "hero": "pending", "cta": "pending", "benefits": "pending"}`. Gate the "LP complete" action on all modules being `approved`.

**When to use:** On every module approve/reject button click.

**Example — model change:**
```python
# app/models.py — LandingPage additions
ugc_job_id = Column(Integer, ForeignKey("ugc_jobs.id"), nullable=True)
lp_module_approvals = Column(JSON, nullable=True)  # {"headline": "approved", ...}
lp_hero_image_path = Column(String(1000), nullable=True)  # frame from approved video
lp_hero_candidate_path = Column(String(1000), nullable=True)  # regenerated candidate
lp_review_locked = Column(Boolean, default=True)  # unlocked when UGCJob.status == "approved"
```

**Example — approve endpoint in ui/router.py:**
```python
# POST /ui/lp/{run_id}/module/{module}/approve
LP_MODULES = ["headline", "hero", "cta", "benefits"]

@router.post("/lp/{run_id}/module/{module}/approve")
async def lp_module_approve(run_id: str, module: str, session: AsyncSession = Depends(get_session)):
    if module not in LP_MODULES:
        raise HTTPException(status_code=400, detail=f"Unknown module: {module}")
    result = await session.execute(select(LandingPage).where(LandingPage.run_id == run_id))
    lp = result.scalar_one_or_none()
    if not lp:
        raise HTTPException(status_code=404)
    approvals = dict(lp.lp_module_approvals or {})
    approvals[module] = "approved"
    lp.lp_module_approvals = approvals
    await session.commit()
    return templates.TemplateResponse(request=request, name="partials/lp_stage_controls.html",
                                      context={"lp": lp, "modules": LP_MODULES})
```

### Pattern 2: Stage Gate — LP Locked Until Video Approved

**What:** The LP review page checks `UGCJob.status == "approved"`. If not approved, render a "locked" state instead of the approve/reject buttons.

**When to use:** In the LP review router GET handler and template.

**Example — router.py:**
```python
@router.get("/lp/{run_id}/review", response_class=HTMLResponse)
async def lp_review(request: Request, run_id: str, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(LandingPage).where(LandingPage.run_id == run_id))
    lp = result.scalar_one_or_none()
    if not lp:
        raise HTTPException(status_code=404)

    ugc_job = None
    video_approved = False
    if lp.ugc_job_id:
        ugc_result = await session.execute(select(UGCJob).where(UGCJob.id == lp.ugc_job_id))
        ugc_job = ugc_result.scalar_one_or_none()
        video_approved = (ugc_job and ugc_job.status == "approved")

    return templates.TemplateResponse(request=request, name="lp_review.html",
        context={"lp": lp, "video_approved": video_approved, "modules": LP_MODULES})
```

**Example — lp_review.html gate:**
```html
{% if not video_approved %}
<div class="status-msg">LP review is locked. Approve the video pipeline first.</div>
{% else %}
  <!-- module cards here -->
{% endif %}
```

### Pattern 3: Video Frame Extraction (reuse generate_thumbnail)

**What:** After `UGCJob` reaches `approved`, extract a frame from `final_video_path` using the existing `generate_thumbnail()` function and store the JPEG path as `lp.lp_hero_image_path`.

**When to use:** When advancing UGCJob to `approved` status (in `ugc_router.py` advance endpoint) OR lazily when LP review is first opened.

**Example — trigger in advance endpoint:**
```python
# In ugc_router.py advance handler, after approve_final:
if approve_event == "approve_final" and job.final_video_path:
    from app.services.video_compositor.thumbnail import generate_thumbnail
    # Extract frame at 2 seconds into the approved video
    frame_path = generate_thumbnail(
        video_path=job.final_video_path,
        timestamp=2.0,
        output_dir="output/lp_frames"
    )
    # Link to any LandingPage rows that reference this job
    lp_result = await session.execute(
        select(LandingPage).where(LandingPage.ugc_job_id == job_id)
    )
    for lp in lp_result.scalars().all():
        lp.lp_hero_image_path = frame_path
        lp.lp_review_locked = False
    await session.commit()
```

**Note:** `generate_thumbnail()` uses `moviepy.VideoFileClip` synchronously. Run it outside an async context (e.g., in a thread via `asyncio.to_thread()`) or in the Celery task to avoid blocking the event loop.

### Pattern 4: LP Hero Image Regeneration (Celery Task)

**What:** User triggers LP-specific image regeneration. A Celery task calls the image provider with an LP-appropriate prompt, stores the result in `lp_hero_candidate_path` (never overwrites `lp_hero_image_path`).

**When to use:** POST `/ugc/jobs/{id}/lp-regenerate-hero` from the LP review page.

**Example — new Celery task:**
```python
# In app/ugc_tasks.py — new task
@celery_app.task(bind=True, name='app.ugc_tasks.lp_hero_regen', max_retries=1, time_limit=300)
def lp_hero_regen(self, lp_run_id: str):
    """Regenerate LP hero image, store as candidate (never overwrites approved)."""
    async def _run():
        from app.database import get_task_session_factory
        from app.models import LandingPage
        from app.services.image_provider import get_image_provider
        from sqlalchemy import select

        session_factory = get_task_session_factory()
        async with session_factory() as session:
            result = await session.execute(select(LandingPage).where(LandingPage.run_id == lp_run_id))
            lp = result.scalar_one_or_none()
            if not lp:
                raise ValueError(f"LandingPage {lp_run_id} not found")
            provider = get_image_provider(use_mock=False)  # use_mock from UGCJob.use_mock ideally
            candidate_path = provider.generate(prompt=f"Product hero image for {lp.product_idea}")
            lp.lp_hero_candidate_path = candidate_path
            await session.commit()
    asyncio.run(_run())
```

### Pattern 5: LP Module Cards (reuse stage-card / card-grid CSS)

**What:** Four LP modules (headline, hero, CTA, benefits) each render as a `stage-card` with an approve/reject button. Uses identical CSS and HTMX patterns to the UGC review grid.

**Example — lp_review.html module card:**
```html
{% for module in modules %}
<div class="stage-card">
  <div class="card-label">{{ module | title }}</div>
  <div class="card-value">{{ lp_module_content[module] }}</div>
  <div class="action-row">
    {% set approval = lp.lp_module_approvals.get(module, "pending") if lp.lp_module_approvals else "pending" %}
    {% if approval == "approved" %}
      <span class="status-badge status-approved">Approved</span>
    {% else %}
      <button hx-post="/ui/lp/{{ lp.run_id }}/module/{{ module }}/approve"
              hx-target="#lp-stage-controls"
              hx-swap="outerHTML"
              class="btn btn-primary">Approve</button>
    {% endif %}
  </div>
</div>
{% endfor %}
```

### Anti-Patterns to Avoid

- **Mutating `lp_hero_image_path` on regen:** Per project decision, regeneration produces candidates. Store new image in `lp_hero_candidate_path`. Only swap on explicit "accept candidate" action.
- **Running moviepy `generate_thumbnail()` in async route handler directly:** `VideoFileClip` is blocking IO. Use `asyncio.to_thread()` or run it in a Celery task.
- **Generating LP before video is approved:** LP review must be locked until `UGCJob.status == "approved"`. Don't let partial or failed video state populate LP hero.
- **Storing module approvals in a separate table:** JSON column on `LandingPage` is sufficient for 4 fixed modules. A separate table adds join complexity for no benefit.
- **Hardcoding module list in templates and router separately:** Define `LP_MODULES = ["headline", "hero", "cta", "benefits"]` once in `ui/router.py` and pass to all templates via context.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Video frame extraction | Custom `ffmpeg` subprocess | `generate_thumbnail()` in `thumbnail.py` | Already exists; uses moviepy + PIL; handles edge cases (timestamp > duration) |
| Module approval storage | `LPModuleApproval` ORM table | JSON column on `LandingPage` | 4 fixed modules, no relational queries; JSON column is idiomatic for this pattern |
| LP image generation | New image provider wrapper | Existing `app/services/image_provider/` | `get_image_provider()` dispatcher already handles mock/real switching |
| HTMX partial swap for approval | Full-page reload | `hx-target` + `hx-swap="outerHTML"` on controls partial | Established pattern in `ugc_stage_controls.html`; reuse it |

**Key insight:** Most of Phase 25 is wiring — the frame extractor, image provider, Celery task pattern, and card UI all exist. The main new code is the `lp_review.html` template, two new routes, one new Celery task, and the DB migration.

## Common Pitfalls

### Pitfall 1: No Link Between LandingPage and UGCJob

**What goes wrong:** LP is generated independently of the UGC job. There is no `ugc_job_id` on `LandingPage`. Phase 25 cannot know which video to extract a frame from.

**Why it happens:** The LP pipeline (Phase 14) predates the UGC pipeline. They were independent.

**How to avoid:** The migration must add `ugc_job_id` as a nullable FK to `landing_pages`. The LP creation flow (in `ui/router.py` `_run_generation`) must be updated to accept and store `ugc_job_id` when LP is created from the UGC review flow.

**Warning signs:** `lp.ugc_job_id is None` when trying to extract a frame.

### Pitfall 2: LP Linked but UGCJob Not Yet Approved

**What goes wrong:** User creates LP while video is still in `stage_composition_review`. LP review shows module cards but no video frame in hero (or stale frame from an earlier run).

**Why it happens:** Timing — LP is created before video is approved.

**How to avoid:** Lock LP review UI when `ugc_job.status != "approved"`. Only extract and store the frame when `approve_final` transition completes. Set `lp_review_locked = True` by default; set `False` only on `approve_final`.

**Warning signs:** `lp.lp_hero_image_path` is None even though video composition completed.

### Pitfall 3: moviepy Blocking the Event Loop

**What goes wrong:** `generate_thumbnail()` calls `VideoFileClip(path)` which is blocking disk IO. Called directly in an `async def` FastAPI handler, it blocks the event loop and freezes all concurrent requests.

**Why it happens:** moviepy is synchronous.

**How to avoid:** Run frame extraction in a Celery task (preferred, follows existing pattern) or wrap with `await asyncio.to_thread(generate_thumbnail, ...)` if running inline.

**Warning signs:** Server hangs for several seconds on approve_final click; other requests time out.

### Pitfall 4: LP Module Content Not Available for Display

**What goes wrong:** `lp_review.html` needs to show the content of each LP module (headline text, hero image, CTA text, benefits list) but `LandingPage` model stores only `html_path` and a `sections` JSON of section names — not the copy content.

**Why it happens:** `LandingPage` was designed to track status and paths, not store copy content. Copy lives only in the generated HTML file.

**How to avoid (two options):**
- **Option A:** Parse the HTML file to extract copy at render time (fragile, not recommended).
- **Option B:** Re-generate LP copy from `product_idea` + `target_audience` via the LLM (expensive, slow).
- **Option C (recommended):** Store `LandingPageCopy` as JSON in a new `lp_copy` column on `LandingPage` at generation time, then display from DB.

**Warning signs:** Template cannot display module content without reading HTML files.

**Decision needed:** The planner must resolve whether to add `lp_copy` column or parse HTML. This is the biggest open question.

### Pitfall 5: Alembic Migration Breaks Existing LandingPage Rows

**What goes wrong:** Adding `ugc_job_id` as a non-nullable FK breaks existing `landing_pages` rows that have no UGC job.

**Why it happens:** All existing LPs were created via the standalone LP generator, not via UGC flow.

**How to avoid:** Make `ugc_job_id` nullable (FK with `nullable=True`). Add `lp_review_locked` with a server default of `True` but also `nullable=True` to avoid migration failures.

## Code Examples

### Frame Extraction — Reuse generate_thumbnail

```python
# Source: app/services/video_compositor/thumbnail.py (existing)
from app.services.video_compositor.thumbnail import generate_thumbnail

# Extract frame at 2.0 seconds from the approved final video
frame_path = generate_thumbnail(
    video_path=job.final_video_path,  # e.g. "output/review/ugc_ad_1_abc123.mp4"
    timestamp=2.0,
    output_dir="output/lp_frames",   # new subdirectory for LP frames
    quality=85
)
# Returns: "output/lp_frames/ugc_ad_1_abc123_thumb.jpg"
# URL: "/output/lp_frames/ugc_ad_1_abc123_thumb.jpg" (via existing /output mount)
```

### LP Review Stage Gate Check

```python
# In ui/router.py GET /ui/lp/{run_id}/review
video_approved = (
    lp.ugc_job_id is not None
    and ugc_job is not None
    and ugc_job.status == "approved"
)
# Pass to template: context={"video_approved": video_approved}
```

### Alembic Migration Skeleton

```python
# alembic/versions/007_lp_integration_schema.py
def upgrade() -> None:
    op.add_column('landing_pages', sa.Column('ugc_job_id', sa.Integer(), sa.ForeignKey('ugc_jobs.id'), nullable=True))
    op.add_column('landing_pages', sa.Column('lp_module_approvals', sa.JSON(), nullable=True))
    op.add_column('landing_pages', sa.Column('lp_hero_image_path', sa.String(1000), nullable=True))
    op.add_column('landing_pages', sa.Column('lp_hero_candidate_path', sa.String(1000), nullable=True))
    op.add_column('landing_pages', sa.Column('lp_review_locked', sa.Boolean(), nullable=True, server_default='true'))
    op.add_column('landing_pages', sa.Column('lp_copy', sa.JSON(), nullable=True))  # if Option C chosen

def downgrade() -> None:
    op.drop_column('landing_pages', 'lp_copy')
    op.drop_column('landing_pages', 'lp_review_locked')
    op.drop_column('landing_pages', 'lp_hero_candidate_path')
    op.drop_column('landing_pages', 'lp_hero_image_path')
    op.drop_column('landing_pages', 'lp_module_approvals')
    op.drop_column('landing_pages', 'ugc_job_id')
```

### LP Module List (single source of truth)

```python
# In app/ui/router.py
LP_MODULES = ["headline", "hero", "cta", "benefits"]
```

### LP Review Trigger — After UGCJob Approve Final

```python
# In app/ugc_router.py advance endpoint, after approve_final transition:
if approve_event == "approve_final" and job.final_video_path:
    import asyncio
    from app.services.video_compositor.thumbnail import generate_thumbnail
    frame_path = await asyncio.to_thread(
        generate_thumbnail,
        job.final_video_path,
        2.0,
        "output/lp_frames"
    )
    # Unlock any LP linked to this job
    lp_result = await session.execute(
        select(LandingPage).where(LandingPage.ugc_job_id == job_id)
    )
    for lp_row in lp_result.scalars().all():
        lp_row.lp_hero_image_path = frame_path
        lp_row.lp_review_locked = False
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| LP generated standalone, no UGC link | LP linked to UGCJob via FK | Phase 25 | Enables hero frame sourcing and stage gate |
| LP review = none (not implemented) | Per-module approve/reject cards | Phase 25 | LP-08 requirement |
| LP hero image = `hero_image_path` in `LandingPageRequest` | LP hero defaults to video frame | Phase 25 | LP-09 requirement |

**Not yet in codebase:**
- `ugc_job_id` on `LandingPage` — must be added
- `lp_module_approvals` JSON column — must be added
- LP review template — must be created
- LP hero regeneration task — must be created

## Open Questions

1. **Where is LP copy stored for module display? (CRITICAL)**
   - What we know: `LandingPage.sections` contains only a list of section name strings. `html_path` points to the generated HTML. `LandingPageCopy` fields (headline, benefits, CTA) exist only during generation.
   - What's unclear: Should a new `lp_copy` JSON column store the full `LandingPageCopy.model_dump()` at generation time? Or parse the HTML at review time?
   - Recommendation: Add `lp_copy = Column(JSON)` to `LandingPage` and serialize `LandingPageCopy.model_dump()` into it during `_run_generation()`. This is the cleanest approach — no HTML parsing, data is queryable.

2. **How is LP created in the UGC-linked flow? (CRITICAL)**
   - What we know: Current LP creation is standalone via `/ui/generate` form. Phase 25 needs LP to be created after video approval and linked to the `UGCJob`.
   - What's unclear: Is there a new "Generate LP from this video" button on the UGC review page? Or does `approve_final` automatically trigger LP generation?
   - Recommendation: Add a "Generate LP" button on the UGC review page (status == "approved"). User clicks it → LP generation runs → LP is linked to job. Do not auto-trigger — keeps user in control.

3. **Which frame timestamp for hero extraction?**
   - What we know: `generate_thumbnail()` defaults to `t=2.0` seconds. The video is typically 25-30 seconds.
   - What's unclear: Is `t=2.0` the right frame (past the hook/intro)? Should the user pick?
   - Recommendation: Default to `t=2.0` (established existing default). Expose no UI for this in Phase 25.

4. **`use_mock` for LP hero regen task**
   - What we know: Project decision: `use_mock` is stored per `UGCJob` row. LP hero regen needs to respect mock mode.
   - What's unclear: Should regen task read `use_mock` from the linked `UGCJob` row?
   - Recommendation: Yes — load `ugc_job.use_mock` in the Celery task and pass it to the image provider. If no linked job, default to `False`.

5. **Nav link for LP review**
   - What we know: The LP review page is new. The nav in `base.html` has links for Dashboard, Waitlist, Generate, UGC.
   - What's unclear: Should LP review be accessible from the UGC review page (approved state) or from the LP list?
   - Recommendation: Add "View LP" link on the UGC review page when `status == "approved"` and a linked LP exists. Also accessible from the LP list dashboard.

## Sources

### Primary (HIGH confidence)
- Codebase: `app/models.py` — `LandingPage` and `UGCJob` schemas confirmed; no existing link between them
- Codebase: `app/services/video_compositor/thumbnail.py` — `generate_thumbnail()` uses moviepy + PIL; reusable directly
- Codebase: `app/services/landing_page/generator.py` — `generate_landing_page()` pipeline; `LandingPageCopy` not persisted
- Codebase: `app/services/landing_page/section_editor.py` — `LP_MODULES` analog: `EDITABLE_SECTIONS` keys = `["hero", "benefits", "features", "how_it_works", "cta_repeat", "faq", "waitlist", "footer"]`
- Codebase: `app/ugc_router.py` — `_STAGE_ADVANCE_MAP`, advance endpoint pattern, `approve_final` transition
- Codebase: `app/ui/router.py` — `STAGE_ORDER`, `_REVIEW_STATES`, HTMX partial return pattern for ugc advance/regenerate
- Codebase: `app/ui/templates/ugc_review.html` — card-grid + stage-card + media-card pattern to replicate for LP modules
- Codebase: `app/ui/templates/partials/ugc_stage_controls.html` — outerHTML HTMX swap pattern to replicate
- Codebase: `alembic/versions/006_ugcjob_schema.py` — migration pattern (add_column with nullable=True)
- Codebase: `requirements.txt` — moviepy 2.2.1, Pillow 11.3.0, Celery 5.6.2 confirmed present

### Secondary (MEDIUM confidence)
- Phase 24 RESEARCH.md — `media_url` Jinja2 filter and `/output` StaticFiles mount confirmed available for LP hero image display
- Project decisions list — "Regeneration produces candidates: Never mutate approved content in place" constrains LP hero regen design

### Tertiary (LOW confidence)
- LP module definition (headline, hero, CTA, benefits) — derived from `LandingPageCopy` schema fields and LP-08 requirement text; not explicitly enumerated in codebase as a list

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries already in project, versions confirmed
- Architecture: HIGH — patterns directly derived from existing code; UGCJob advance pattern is the exact template
- Frame extraction: HIGH — `generate_thumbnail()` exists and is tested
- LP copy storage: MEDIUM — `lp_copy` column is recommended but not yet decided; open question 1 must be resolved in planning
- LP module list definition: MEDIUM — derived from requirements + `EDITABLE_SECTIONS`, not from explicit project config

**Research date:** 2026-02-21
**Valid until:** 2026-03-23 (stable stack; LP and UGC pipelines are not changing)
