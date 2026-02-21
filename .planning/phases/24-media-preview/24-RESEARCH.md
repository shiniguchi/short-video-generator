# Phase 24: Media Preview - Research

**Researched:** 2026-02-21
**Domain:** HTTP range requests, Starlette StaticFiles/FileResponse, Jinja2 template media tags, path validation
**Confidence:** HIGH

## Summary

Phase 24 adds inline media preview to the UGC review grid: images render as `<img>` tags, video clips play as `<video>` tags with seek support, and the final composed video is watchable inline. All three success criteria for HTTP 206 support are already satisfied by the existing infrastructure — no new serving code is needed.

The key discovery: **Starlette 0.49.3 `FileResponse` fully handles HTTP 206 range requests** (single range, multi-range, `If-Range`, `Accept-Ranges` header). The existing `/output` StaticFiles mount in `main.py` uses `FileResponse` internally and therefore already serves `.mp4` files with working browser seek. The prior architectural note about needing a custom `StreamingResponse` with manual range parsing is **obsolete** for starlette >= 0.39.0.

All generated file paths (`hero_image_path`, `aroll_paths`, `broll_paths`, `final_video_path`) are stored as relative paths like `output/images/uuid.png` or `output/review/ugc_ad_1_abc.mp4`. Converting to a browser URL is a simple string operation: prepend `/`. No new API routes are required. Phase 24 is primarily **template changes + CSS**.

Path traversal protection is already handled by `StaticFiles.lookup_path()` using `os.commonpath()` to reject escapes. For any dedicated `/media` route, add `Path.resolve()` + `is_relative_to(output_dir)` validation.

**Primary recommendation:** Skip custom streaming route — use the existing `/output` static mount. Phase 24 = replace text path strings in `ugc_review.html` with `<img>`/`<video>` tags, add responsive CSS for media cards, add a Jinja2 filter or template macro to convert stored paths to URLs.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Starlette | 0.49.3 (pinned), 0.52.1 (installed) | `FileResponse` / `StaticFiles` HTTP 206 | Already in project; range support added in 0.39.0 |
| FastAPI | 0.128.8 | Router, TemplateResponse | Existing web framework |
| Jinja2 | 3.1.6 | Template `<img>` / `<video>` HTML | Existing template engine |
| HTMX | 2.0.8 (CDN) | Already loaded from Phase 23 | No change needed |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Python `pathlib.Path` | stdlib | Path traversal validation (`resolve()` + `is_relative_to()`) | Only if adding a dedicated `/media/{path}` route |
| `FileResponse` | starlette 0.49.3 | HTTP 206 partial content for video | Use directly if adding a dedicated route |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Existing `/output` static mount | Custom `StreamingResponse` with manual range parsing | StaticFiles already handles HTTP 206 via FileResponse; manual range parsing adds complexity for zero benefit |
| Jinja2 template path filter | Dedicated `/media` API route | A filter/macro handles path→URL conversion in the template without adding routes; use a route only if you need access logging or auth |
| `<video controls>` in cards | Custom video player JS | Native `<video>` supports seek, play/pause, full-screen; no library needed |

**Installation:** No new packages.

## Architecture Patterns

### File Structure

```
app/
├── main.py                          # UNCHANGED: /output StaticFiles mount already serves all media
├── ui/
│   ├── router.py                    # OPTIONAL: add a /media/{path:path} route for logged access
│   ├── static/
│   │   └── ui.css                   # EXTEND: add .media-card, .media-preview img/video CSS
│   └── templates/
│       ├── ugc_review.html          # EXTEND: replace text paths with <img> / <video> tags
│       └── partials/
│           └── (no changes needed to stage controls)
output/
├── images/             # hero images: output/images/uuid.png    -> /output/images/uuid.png
├── clips/              # aroll/broll: output/clips/uuid.mp4     -> /output/clips/uuid.mp4
└── review/             # final video: output/review/ugc_ad.mp4 -> /output/review/ugc_ad.mp4
```

### Pattern 1: Path-to-URL Conversion (Jinja2 Filter)

**What:** Stored paths are relative like `output/images/uuid.png`. The browser URL is `/output/images/uuid.png` — just prepend `/`.

**When to use:** In every `<img src>` and `<video src>` in the template.

**Example — add filter in `ui/router.py`:**
```python
# Source: Jinja2 docs — adding custom filters to Jinja2Environment
# In app/ui/router.py, after templates = Jinja2Templates(...)
def media_url(path: str) -> str:
    """Convert stored relative path to browser-accessible URL."""
    if not path:
        return ""
    # Stored as "output/foo/bar.mp4" -> "/output/foo/bar.mp4"
    return "/" + path.lstrip("/")

templates.env.filters["media_url"] = media_url
```

**Example — in template:**
```html
<!-- Hero image -->
<img src="{{ job.hero_image_path | media_url }}"
     alt="Hero image"
     class="media-preview">

<!-- A-Roll clip -->
{% for path in job.aroll_paths %}
<div class="stage-card media-card">
  <div class="card-label">A-Roll Clip {{ loop.index }}</div>
  <video class="media-preview" controls preload="metadata">
    <source src="{{ path | media_url }}" type="video/mp4">
  </video>
</div>
{% endfor %}

<!-- Final video -->
<video class="media-preview" controls preload="metadata">
  <source src="{{ job.final_video_path | media_url }}" type="video/mp4">
</video>
```

### Pattern 2: HTTP 206 via Existing StaticFiles Mount

**What:** The `/output` static mount in `main.py` uses `StaticFiles`, which internally calls `FileResponse` for every file. Starlette 0.49.3 `FileResponse.__call__()` reads the `Range` header and returns HTTP 206 for partial content requests. Browser video seek sends `Range: bytes=N-` — already handled.

**When to use:** Always. No additional code needed.

**Evidence (verified from starlette 0.49.3 source):**
```python
# starlette/responses.py — FileResponse.__call__
headers = Headers(scope=scope)
http_range = headers.get("range")
if http_range is None:
    await self._handle_simple(send, send_header_only, send_pathsend)
else:
    ranges = self._parse_range_header(http_range, stat_result.st_size)
    if len(ranges) == 1:
        start, end = ranges[0]
        await self._handle_single_range(send, start, end, stat_result.st_size, ...)
        # sends HTTP 206 with Content-Range: bytes {start}-{end-1}/{size}
    else:
        await self._handle_multiple_ranges(...)  # also sends 206
```

**StaticFiles path traversal protection (verified from source):**
```python
# starlette/staticfiles.py — StaticFiles.lookup_path
full_path = os.path.realpath(joined_path)
directory = os.path.realpath(directory)
if os.path.commonpath([full_path, directory]) != str(directory):
    continue  # Rejects path traversal silently
```

### Pattern 3: Dedicated Media Route (Optional — for auth/logging)

**What:** If you need per-job access control or request logging, add a route that validates and proxies via `FileResponse`. Only add this if the plain static mount is insufficient.

**When to use:** If success criteria 5 (path traversal validation) requires explicit validation in code (not just relying on StaticFiles). Adds defense-in-depth.

**Example:**
```python
# Source: app/ui/router.py — optional media route
from pathlib import Path
from fastapi.responses import FileResponse

_OUTPUT_DIR = Path(__file__).parent.parent.parent / "output"

@router.get("/media/{job_id}/{filename:path}")
async def serve_media(job_id: int, filename: str):
    """Serve media files with explicit path traversal validation."""
    # Validate path stays within output dir
    requested = (_OUTPUT_DIR / filename).resolve()
    if not requested.is_relative_to(_OUTPUT_DIR.resolve()):
        raise HTTPException(status_code=400, detail="Invalid path")
    if not requested.exists():
        raise HTTPException(status_code=404)
    return FileResponse(requested)
    # FileResponse handles HTTP 206 automatically
```

### Pattern 4: Responsive Media CSS

**What:** Media in the review grid cards needs size constraints. Images and videos should fill the card width without overflow.

**When to use:** Add to `ui.css` alongside existing `.stage-card` / `.card-grid` classes.

**Example:**
```css
/* Media card variant — taller to accommodate video/image */
.media-card {
  padding: 12px;
}

/* Responsive image and video preview */
.media-preview {
  width: 100%;
  max-width: 100%;
  border-radius: 4px;
  display: block;
  background: #000;  /* letterbox color for vertical video */
}

/* Constrain height for vertical (9:16) video clips */
.media-preview-video {
  max-height: 320px;  /* prevents giant 9:16 cards */
  object-fit: contain;
}
```

### Anti-Patterns to Avoid

- **Custom StreamingResponse with manual range parsing:** Starlette already handles this. Adding manual parsing duplicates functionality and introduces bugs (edge cases with open-ended `bytes=N-` ranges, multi-range).
- **Serving files outside `/output`:** All generated paths are relative to the `output/` directory. Never concatenate user input directly to form a file path in a route. Product image uploads go to `output/ugc_uploads/{job_id}/{filename}` — the `job_id` integer acts as a namespace, but `filename` comes from user upload.
- **`<video autoplay>` without `muted`:** Browsers block autoplay with audio. Use `controls preload="metadata"` — no autoplay.
- **`preload="auto"`:** Loads all video data on page load. Use `preload="metadata"` — loads only enough to display duration and first frame.
- **Jinja2 `| media_url` filter on a None value:** Some paths may be `None` (e.g., `hero_image_path` before Stage 1 completes). Always check `{% if job.hero_image_path %}` before applying the filter.
- **Hard-coding `/output/` prefix in template:** Use the filter — if the output dir ever changes, one change fixes all.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTTP 206 range handling | Custom `StreamingResponse` + range header parser | `FileResponse` via StaticFiles | Starlette 0.49.3 handles single-range, multi-range, `If-Range`, 416 out-of-range errors |
| Video player UI | JS-based video player (Video.js, Plyr) | Native HTML5 `<video controls>` | Browser-native is sufficient; no new dependency |
| Path validation | Regex or string matching | `Path.resolve()` + `Path.is_relative_to()` | stdlib, correct, handles symlinks |
| Media URL generation | Manual string concat in template | Jinja2 custom filter `media_url` | Centralized, testable, consistent |

**Key insight:** The only work in Phase 24 is replacing text path strings in the review template with HTML media tags. All serving, seeking, and security is already handled by existing infrastructure.

## Common Pitfalls

### Pitfall 1: Assuming `/output` Static Mount Does NOT Handle HTTP 206

**What goes wrong:** Developer adds a custom streaming endpoint with manual range parsing, duplicating starlette's built-in behavior.

**Why it happens:** The prior architectural note ("FileResponse alone does not handle Range headers") was written before starlette 0.39.0 added range support (September 2024). The repo uses starlette 0.49.3 (pinned) / 0.52.1 (installed) — both have full range support.

**How to avoid:** Test `Range: bytes=0-0` against `/output/review/some.mp4` in DevTools before adding any custom code. Expect HTTP 206 response.

**Warning signs:** Writing a custom `StreamingResponse` endpoint when `/output/xxx.mp4` already returns 206.

### Pitfall 2: Open-Ended Range `bytes=N-` Not Handled

**What goes wrong:** Browser sends `Range: bytes=N-` (open-ended, meaning "from N to EOF"). Custom manual parsers sometimes return the wrong byte count or 200 instead of 206.

**Why it happens:** The open-ended format is the most common browser seek pattern. Starlette handles it natively via `_parse_ranges()` which accepts `start-end` and `start-` forms.

**How to avoid:** Don't write a custom range parser. Use `FileResponse`. If you test manually, test `bytes=0-`, `bytes=1000-`, and `bytes=0-999` — all should return 206 with correct `Content-Range`.

**Warning signs:** Browser seek bar jumps back to 0 after scrubbing; network tab shows 200 instead of 206 for video requests.

### Pitfall 3: Product Upload Filename Path Traversal

**What goes wrong:** `product_image_paths` entries contain user-uploaded filenames. If a user uploads a file named `../../etc/passwd`, the path becomes `output/ugc_uploads/1/../../etc/passwd`.

**Why it happens:** `ugc_router.py` does `dest = upload_dir / (img.filename or ...)` — `img.filename` is user-controlled.

**How to avoid:** The `/output` StaticFiles mount already protects against serving these paths (uses `os.commonpath` check). However, if a dedicated `/media` route is added, always call `.resolve()` and `is_relative_to()`. For defense-in-depth, the upload handler should also sanitize filenames (`Path(img.filename).name` strips directory components).

**Warning signs:** `product_image_paths` entries contain `..` sequences.

### Pitfall 4: `<video>` Not Playing Due to Missing `type` Attribute

**What goes wrong:** `<video><source src="..."></video>` without `type="video/mp4"` causes some browsers to probe the content type before playing.

**Why it happens:** Without `type`, browsers must sniff content type via a network request. Starlette/FileResponse sets `Content-Type: video/mp4` correctly for `.mp4`, but specifying `type` avoids the probe round-trip.

**How to avoid:** Always include `type="video/mp4"` on `<source>` elements for `.mp4` files.

### Pitfall 5: Card Grid Overflow with Vertical (9:16) Video

**What goes wrong:** 9:16 video clips are 720×1280. Rendered in a `minmax(250px, 1fr)` card, they overflow vertically and make the page extremely long.

**Why it happens:** `<video>` preserves aspect ratio by default. A 250px wide card for 9:16 video renders ~444px tall — acceptable. But if `max-height` is not set, multiple clips on one row create very long cards.

**How to avoid:** Add `max-height: 320px` and `object-fit: contain` on `.media-preview-video`. Test with real video clips.

## Code Examples

### Verified: starlette 0.49.3 FileResponse sends HTTP 206

```python
# Source: starlette/responses.py (installed version 0.49.3 / 0.52.1)
# FileResponse.__call__ extracts Range header and calls _handle_single_range which does:

self.headers["content-range"] = f"bytes {start}-{end - 1}/{file_size}"
await send({"type": "http.response.start", "status": 206, "headers": self.raw_headers})
# Then streams only the requested byte range
```

### Template: Hero Image Card

```html
<!-- In ugc_review.html — Stage 1 section (already shows hero_image_path as text) -->
{% if job.hero_image_path %}
<div class="stage-card media-card">
  <div class="card-label">Hero Image</div>
  <img src="{{ job.hero_image_path | media_url }}"
       alt="Hero image"
       class="media-preview"
       loading="lazy">
</div>
{% endif %}
```

### Template: A-Roll Video Cards

```html
<!-- In ugc_review.html — A-Roll section (currently shows path as text) -->
{% if job.aroll_paths is not none %}
<div class="stage-section">
  <h2>A-Roll</h2>
  <div class="card-grid">
    {% for path in job.aroll_paths %}
    <div class="stage-card media-card">
      <div class="card-label">A-Roll Clip {{ loop.index }}</div>
      <video class="media-preview media-preview-video" controls preload="metadata">
        <source src="{{ path | media_url }}" type="video/mp4">
      </video>
    </div>
    {% endfor %}
  </div>
</div>
{% endif %}
```

### Template: Final Video Card

```html
<!-- In ugc_review.html — Composition section (currently shows path as text) -->
{% if job.final_video_path is not none %}
<div class="stage-section">
  <h2>Composition</h2>
  <div class="card-grid">
    <div class="stage-card media-card">
      <div class="card-label">Final Video</div>
      <video class="media-preview media-preview-video" controls preload="metadata">
        <source src="{{ job.final_video_path | media_url }}" type="video/mp4">
      </video>
    </div>
  </div>
</div>
{% endif %}
```

### Jinja2 Filter Registration

```python
# Source: app/ui/router.py — add after templates = Jinja2Templates(...)
def _media_url(path: str | None) -> str:
    """Convert stored relative path 'output/foo/bar.mp4' to URL '/output/foo/bar.mp4'."""
    if not path:
        return ""
    return "/" + path.lstrip("/")

templates.env.filters["media_url"] = _media_url
```

### Path Traversal Validation (if adding a dedicated route)

```python
# Source: Python stdlib pathlib docs
from pathlib import Path

_OUTPUT_DIR = (Path(__file__).parent.parent.parent / "output").resolve()

def validate_media_path(relative_path: str) -> Path:
    """Raise ValueError if path escapes output directory."""
    candidate = (_OUTPUT_DIR / relative_path).resolve()
    if not candidate.is_relative_to(_OUTPUT_DIR):
        raise ValueError(f"Path traversal detected: {relative_path}")
    return candidate
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Manual `StreamingResponse` + range parser | `FileResponse` (built-in range support) | starlette 0.39.0, Sep 2024 | HTTP 206 for video seek is free; no custom code |
| starlette had no range support | `FileResponse` handles single-range, multi-range, `If-Range`, 416 | starlette 0.39.0 | Phase 24-01 requires no new serving infrastructure |

**Outdated architectural decision:**
- Prior note: "Use `StreamingResponse` with manual range parsing for `.mp4`. `FileResponse` alone does not handle Range headers." This was true before starlette 0.39.0 (Sep 2024). The repo uses starlette 0.49.3, so `FileResponse` is the correct tool.

## Open Questions

1. **Does Phase 24-01 still need a dedicated route?**
   - What we know: The `/output` StaticFiles mount in `main.py` already serves all media files (images, clips, review videos) with HTTP 206 via starlette's `FileResponse`.
   - What's unclear: The plan description says "Static image serving route + video streaming endpoint with HTTP 206 range handling." If this was planned assuming starlette lacked range support, the route may be unnecessary.
   - Recommendation: Verify with a real browser test (`Range: bytes=0-0` against `/output/review/some.mp4`) first. If it returns 206, skip the custom route entirely and use the existing mount. If a route is added, use `FileResponse` (not `StreamingResponse`).

2. **Success criterion 5: Path traversal validation**
   - What we know: `StaticFiles` already protects against path traversal via `os.commonpath`. Product upload filenames (`img.filename`) are user-controlled but scoped to `output/ugc_uploads/{job_id}/`.
   - What's unclear: Does the criterion require explicit validation in a new route, or is StaticFiles protection sufficient?
   - Recommendation: If adding a dedicated `/media` route, add `Path.resolve() + is_relative_to()` validation. Also sanitize upload filenames in `ugc_router.py` with `Path(img.filename).name` to strip any `../` components at write time.

3. **`preload` value for final video**
   - What we know: Final video may be 30+ seconds and several MB. `preload="auto"` would load the whole video on page load, slowing the review page.
   - What's unclear: Is `preload="metadata"` enough for a good UX (user sees thumbnail/duration but must wait on play), or should `preload="none"` be used?
   - Recommendation: Use `preload="metadata"` — loads first frame as poster image and duration. This is the standard balance between UX and bandwidth.

## Sources

### Primary (HIGH confidence)

- Codebase: `app/main.py:88-90` — `/output` StaticFiles mount confirmed, serves `output/` directory
- Codebase: `app/config.py:58` — `composition_output_dir = "output/review"` confirms final video paths
- Codebase: `app/services/image_provider/mock.py:65` — mock stores images as `output/images/mock_uuid.png` (relative)
- Codebase: `app/services/video_generator/mock.py` (verified via REPL) — clips stored as `output/clips/mock_uuid.mp4`
- Codebase: `app/ugc_tasks.py:367-370` — final video path: `output/review/ugc_ad_{id}_{uuid}.mp4`
- Codebase: `app/ui/templates/ugc_review.html` — current template shows paths as text; Phase 24 replaces with media tags
- Starlette source (installed 0.49.3/0.52.1): `FileResponse.__call__` reads `Range` header, calls `_handle_single_range` returning HTTP 206 — verified via `.venv/bin/python` REPL
- Starlette source: `StaticFiles.file_response` passes `scope` (including request headers) to `FileResponse` — verified
- Starlette source: `StaticFiles.lookup_path` uses `os.commonpath` for path traversal protection — verified

### Secondary (MEDIUM confidence)

- WebSearch + WebFetch: starlette `FileResponse` range support added in version 0.39.0 (September 2024) via PR #2697; CVE fix in 0.49.1 for range parsing DoS
- Phase 23 RESEARCH.md open question 4 — explicitly deferred media preview to Phase 24 and noted paths are under `output/`

### Tertiary (LOW confidence)

- Browser behavior: `preload="metadata"` vs `preload="auto"` — based on MDN knowledge, not verified against this specific browser environment
- Multi-range `bytes=0-499,1000-1499` handling — starlette source shows it handles this, but browser video seek typically only uses single-range; untested edge case

## Metadata

**Confidence breakdown:**
- HTTP 206 via FileResponse: HIGH — verified from installed starlette source code
- Path-to-URL conversion: HIGH — verified from actual stored file paths in REPL
- Template patterns: HIGH — derived from existing `ugc_review.html` structure
- CSS sizing: MEDIUM — reasonable estimates for 9:16 video; needs visual verification
- Prior "custom StreamingResponse" decision being obsolete: HIGH — starlette 0.39.0 changelog confirmed

**Research date:** 2026-02-21
**Valid until:** 2026-03-23 (starlette is stable; FileResponse API unlikely to change)
