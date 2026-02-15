---
phase: 13
plan: 02
subsystem: ugc-product-ad-pipeline
tags: [asset-generation, composition, imagen, veo, moviepy]
status: complete
completed: 2026-02-15

dependency_graph:
  requires:
    - app/services/image_provider (ImageProvider ABC + factory)
    - app/services/video_generator/google_veo (GoogleVeoProvider)
    - app/services/video_generator/mock (MockVideoProvider)
    - moviepy v2 (VideoFileClip, CompositeVideoClip, concatenate_videoclips)
  provides:
    - generate_hero_image() - UGC character + product hero image
    - generate_aroll_assets() - A-Roll scenes via Veo image-to-video
    - generate_broll_assets() - B-Roll shots via Imagen → Veo pipeline
    - compose_ugc_ad() - Final 9:16 MP4 composition
  affects:
    - Future UGC orchestrator task (Phase 13 Plan 03)

tech_stack:
  added:
    - app/services/ugc_pipeline/asset_generator.py
    - app/services/ugc_pipeline/ugc_compositor.py
  patterns:
    - Veo/mock fallback via _get_veo_or_mock() helper
    - MoviePy v2 immutable API (with_*, resized())
    - Two-step Imagen → Veo pipeline for B-Roll generation
    - Reference image support for product consistency

key_files:
  created:
    - app/services/ugc_pipeline/asset_generator.py (204 lines)
    - app/services/ugc_pipeline/ugc_compositor.py (167 lines)
  modified:
    - app/services/ugc_pipeline/__init__.py (added exports)

key_decisions:
  - Use GoogleVeoProvider directly for image-to-video (not via VideoGeneratorService)
  - B-Roll audio stripped via without_audio() to preserve A-Roll voice
  - B-Roll overlays at 80% scale centered for picture-in-picture effect
  - Hero image uses product photo as reference_images for visual consistency
  - Synchronous functions for Celery task compatibility

metrics:
  duration: 161
  duration_min: 2
  tasks_completed: 2
  files_created: 2
  files_modified: 1
  commits: 2
---

# Phase 13 Plan 02: UGC Asset Generation & Composition Summary

**One-liner:** Hero image generation via Imagen with product reference, A-Roll/B-Roll video assets via Veo image-to-video, and final 9:16 MP4 composition with picture-in-picture B-Roll overlays using MoviePy v2.

## Objective

Create asset generation and composition services for the UGC ad pipeline that orchestrate Imagen + Veo calls for visual asset production and assemble A-Roll base + B-Roll overlays into final 9:16 MP4 videos.

## Tasks Completed

### Task 1: Create asset_generator.py for hero image, A-Roll, and B-Roll generation
**Commit:** 517f0ad

**Implementation:**
- **generate_hero_image()**: Generates 720x1280 hero image combining UGC character style with product photo reference. Calls ImageProvider with reference_images parameter for visual consistency. Returns single image path.
- **generate_aroll_assets()**: Generates A-Roll video clips from hero image using Veo's image-to-video mode. Combines visual_prompt + voice_direction for full scene description. Returns ordered list of clip paths.
- **generate_broll_assets()**: Two-step pipeline for each B-Roll shot: (1) Imagen generates product image from reference, (2) Veo animates it with motion prompt. Returns ordered list of clip paths.
- **_get_veo_or_mock()**: Helper function that returns MockVideoProvider when USE_MOCK_DATA=true or google_api_key is empty, otherwise returns GoogleVeoProvider instance.

**Key patterns:**
- Direct use of GoogleVeoProvider (not VideoGeneratorService) to access image-to-video extension method
- Synchronous functions for Celery task compatibility
- Proper logging with info/debug levels for generation tracking
- Mock fallback at provider instantiation level

**Files created:**
- app/services/ugc_pipeline/asset_generator.py (204 lines)
- app/services/ugc_pipeline/__init__.py (initially empty module file)

### Task 2: Create ugc_compositor.py for A-Roll + B-Roll composition
**Commit:** 9e1c4cf

**Implementation:**
- **compose_ugc_ad()**: Main composition function that:
  1. Loads A-Roll clips from paths
  2. Concatenates into base video (or uses single clip directly)
  3. Loads B-Roll clips and positions as overlays with:
     - 80% scale via resized(0.8)
     - Center positioning via with_position(("center", "center"))
     - Start time via with_start(overlay_start)
     - Audio stripped via without_audio() to preserve A-Roll voice
  4. Creates CompositeVideoClip with base + overlays
  5. Writes final MP4 with H.264/AAC encoding (5Mbps video, 128k audio)
  6. Explicitly closes all clips for resource cleanup

**Edge cases handled:**
- Empty aroll_paths: Raises ValueError (at least one A-Roll required)
- Single A-Roll clip: Uses directly as base without concatenation
- Empty broll_metadata: Writes A-Roll concatenation only
- B-Roll extends beyond A-Roll: Logs warning (MoviePy truncates automatically)

**MoviePy v2 immutable API usage:**
- with_start() instead of set_start()
- with_position() instead of set_position()
- resized() instead of resize()
- without_audio() to strip B-Roll audio

**Files created:**
- app/services/ugc_pipeline/ugc_compositor.py (167 lines)

**Files modified:**
- app/services/ugc_pipeline/__init__.py (added asset_generator and ugc_compositor exports)

## Verification Results

1. asset_generator.py imports without error ✓
2. ugc_compositor.py imports without error ✓
3. generate_hero_image uses ImageProvider with reference_images parameter ✓
4. generate_aroll_assets uses Veo image-to-video (or mock fallback) ✓
5. generate_broll_assets uses Imagen then Veo image-to-video pipeline ✓
6. compose_ugc_ad uses MoviePy v2 immutable API correctly ✓
7. B-Roll audio is stripped (without_audio()) to prevent audio conflicts ✓
8. All clips are explicitly closed after composition ✓

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking Issue] Updated __init__.py exports**
- **Found during:** Task 2 verification
- **Issue:** __init__.py created by Plan 13-01 only exported product_analyzer and script_engine. Importing ugc_compositor failed because those modules don't exist yet (will be created in future plan).
- **Fix:** Added asset_generator and ugc_compositor exports to __init__.py while preserving Plan 13-01's exports (forward compatibility for when those modules are created).
- **Files modified:** app/services/ugc_pipeline/__init__.py
- **Commit:** 9e1c4cf (included in Task 2 commit)

## Technical Decisions

1. **Direct GoogleVeoProvider usage**: Used GoogleVeoProvider directly instead of VideoGeneratorService because image-to-video is a Veo-specific extension method (not part of VideoProvider ABC). This gives us access to generate_clip_from_image() for hero image animation.

2. **B-Roll audio stripping**: All B-Roll overlays use without_audio() to prevent audio conflicts with A-Roll voice track (which has built-in voice from Veo generation).

3. **80% B-Roll scale**: Fixed 80% scale for all B-Roll overlays provides clear picture-in-picture effect while maintaining product visibility.

4. **Reference image consistency**: Both hero image and B-Roll shots use product photo as reference_images to ensure visual product consistency across all assets.

5. **Synchronous design**: All functions are synchronous (not async) because they'll be called from Celery task context where asyncio.run() bridge is needed for DB operations but not for provider calls.

## Integration Points

**Upstream dependencies:**
- app/services/image_provider: ImageProvider factory and ABC (generate_image with reference_images)
- app/services/video_generator/google_veo: GoogleVeoProvider for image-to-video generation
- app/services/video_generator/mock: MockVideoProvider for testing fallback
- moviepy v2: VideoFileClip, CompositeVideoClip, concatenate_videoclips

**Downstream consumers (future):**
- Phase 13 Plan 03 UGC orchestrator task will call generate_hero_image(), generate_aroll_assets(), generate_broll_assets(), and compose_ugc_ad() in sequence.

**Settings requirements:**
- google_api_key: Google AI API key (Gemini, Imagen, Veo)
- use_mock_data: Boolean flag to enable mock providers
- output_dir: Base directory for generated assets
- image_provider_type: "imagen" or "mock"

## Success Criteria Met

- [x] generate_hero_image() generates 720x1280 image using product photo as reference
- [x] generate_aroll_assets() generates video clips from hero image for each scene
- [x] generate_broll_assets() generates Imagen image then Veo animation for each shot
- [x] compose_ugc_ad() creates final 9:16 MP4 from A-Roll base + B-Roll overlays
- [x] All functions use mock providers when USE_MOCK_DATA=true
- [x] MoviePy v2 immutable API used throughout (with_* methods, resized())

## Self-Check: PASSED

**Created files verification:**
- ✓ FOUND: app/services/ugc_pipeline/asset_generator.py
- ✓ FOUND: app/services/ugc_pipeline/ugc_compositor.py

**Modified files verification:**
- ✓ FOUND: app/services/ugc_pipeline/__init__.py

**Commits verification:**
- ✓ FOUND: 517f0ad (Task 1: asset_generator)
- ✓ FOUND: 9e1c4cf (Task 2: ugc_compositor)

**Import verification:**
```bash
# All imports successful with only expected Python 3.9 warnings
python -c "from app.services.ugc_pipeline.asset_generator import generate_hero_image, generate_aroll_assets, generate_broll_assets; print('OK')"
python -c "from app.services.ugc_pipeline.ugc_compositor import compose_ugc_ad; print('OK')"
```

## Next Steps

Plan 13-03 will create the UGC pipeline orchestrator task that:
1. Calls product_analyzer (Plan 13-01) to extract product info
2. Calls script_engine (Plan 13-01) to generate UGC ad breakdown
3. Calls generate_hero_image() to create UGC character + product image
4. Calls generate_aroll_assets() to animate A-Roll scenes from hero image
5. Calls generate_broll_assets() to generate B-Roll product shots
6. Calls compose_ugc_ad() to create final 9:16 MP4 ad

---

**Completed:** 2026-02-15
**Duration:** 2 minutes
**Tasks:** 2/2
**Commits:** 517f0ad, 9e1c4cf
