---
phase: 12-google-ai-provider-suite
plan: 03
subsystem: video-generation
tags: [veo, google-ai, video-provider, provider-pattern]

dependency_graph:
  requires:
    - "VideoProvider ABC (app/services/video_generator/base.py)"
    - "MockVideoProvider fallback pattern (app/services/video_generator/mock.py)"
    - "FalKlingProvider pattern reference (app/services/video_generator/fal_kling.py)"
    - "Video generator factory (app/services/video_generator/generator.py)"
  provides:
    - "GoogleVeoProvider class implementing VideoProvider ABC"
    - "Veo 3.1 text-to-video generation via Google Generative AI"
    - "Veo 3.1 image-to-video generation (extension method)"
    - "'veo' option in video generator factory"
  affects:
    - "app/services/video_generator/generator.py (factory function)"
    - "app/services/video_generator/__init__.py (package exports)"
    - "app/config.py (google_api_key field, video_provider_type comment)"

tech_stack:
  added:
    - name: "google-generativeai"
      version: ">=0.8.6"
      purpose: "Google Generative AI SDK for Veo 3.1 video generation"
    - name: "grpcio"
      version: "1.78.0"
      purpose: "gRPC support for Google AI API communication"
  patterns:
    - "Provider abstraction pattern with VideoProvider ABC"
    - "Lazy mock provider initialization for fallback"
    - "Duration clamping with warning logs"
    - "Aspect ratio and resolution detection from dimensions"
    - "Polling-based operation completion (Google AI async pattern)"
    - "Extension method for provider-specific capabilities (image-to-video)"

key_files:
  created:
    - path: "app/services/video_generator/google_veo.py"
      lines: 280
      purpose: "Veo 3.1 video provider with text-to-video and image-to-video modes"
  modified:
    - path: "app/services/video_generator/generator.py"
      purpose: "Added 'veo' case to factory function, updated docstring"
    - path: "app/services/video_generator/__init__.py"
      purpose: "Exported GoogleVeoProvider class"
    - path: "app/config.py"
      purpose: "Updated video_provider_type comment to include 'veo'"
    - path: "requirements.txt"
      purpose: "Added google-generativeai and dependencies"

decisions:
  - context: "Duration limit enforcement"
    choice: "Clamp to 8 seconds max with warning log"
    rationale: "Veo 3.1 API has hard 8-second limit per clip; clamping prevents API errors while preserving user intent visibility via warning"
    alternatives:
      - "Raise exception on >8s duration (breaks existing pipeline)"
      - "Silent clamping (hides issue from users)"

  - context: "Image-to-video mode implementation"
    choice: "Extension method generate_clip_from_image() not part of ABC"
    rationale: "Image-to-video is Veo-specific capability; other providers (Kling, Minimax) don't support it. Avoids forcing all providers to implement unused method"
    alternatives:
      - "Add to VideoProvider ABC with NotImplementedError (clutters interface)"
      - "Separate ImageToVideoProvider ABC (over-engineering for single use case)"

  - context: "SDK choice for Google AI"
    choice: "Use google-generativeai package despite deprecation warning"
    rationale: "Package still functional, official replacement (google.genai) may have different API. Migration can be deferred to Phase 13 refinement"
    alternatives:
      - "Switch to google.genai immediately (requires API research, delays delivery)"
      - "Wait for Phase 13 to evaluate and migrate if needed (chosen approach)"

metrics:
  duration_minutes: 2
  completed_at: "2026-02-15T12:06:11Z"
  tasks_completed: 2
  files_created: 1
  files_modified: 4
  commits: 2
  lines_added: ~350
---

# Phase 12 Plan 03: Veo Video Provider Summary

**One-liner:** Veo 3.1 video generation with 8-second max clips, text-to-video and image-to-video modes via Google Generative AI SDK.

## Overview

Implemented GoogleVeoProvider as a VideoProvider implementation, adding Veo 3.1 as a video generation option alongside existing Kling and Minimax providers. Veo generates video with built-in voice/audio support, eliminating separate TTS for talking-head content (critical for Phase 13 UGC Product Ad Pipeline). Provider enforces 8-second-per-clip limit, supports both 9:16 and 16:9 resolutions, and includes image-to-video mode for animating Imagen-generated images.

## What Was Built

### GoogleVeoProvider Class
- **Location:** `app/services/video_generator/google_veo.py`
- **Extends:** `VideoProvider` ABC
- **API:** Google Generative AI `veo-3.1-generate-preview` model
- **Features:**
  - Text-to-video generation via `generate_clip()`
  - Image-to-video generation via `generate_clip_from_image()` (extension method)
  - Duration clamping to 8 seconds max with warning log
  - Aspect ratio auto-detection (9:16 for height > width, else 16:9)
  - Resolution auto-detection (1080p if width >= 1080, else 720p)
  - Polling-based operation completion (10-second intervals)
  - Mock fallback when `USE_MOCK_DATA=true` or `google_api_key` empty
  - Error handling with automatic mock fallback on API failures

### Supported Resolutions
- **9:16 (vertical):** 720x1280 (HD), 1080x1920 (Full HD)
- **16:9 (horizontal):** 1280x720 (HD), 1920x1080 (Full HD)

### Factory Integration
- **Factory function:** `get_video_generator()` in `generator.py`
- **Provider type:** `VIDEO_PROVIDER_TYPE=veo`
- **Configuration:** Uses `google_api_key` from `Settings` class
- **Default behavior:** Factory still returns `MockVideoProvider` when type not specified

## Implementation Details

### Duration Clamping Logic
```python
original_duration = duration_seconds
duration_seconds = min(duration_seconds, 8)
if original_duration > 8:
    print(f"WARNING: Veo 3.1 max 8s/clip: clamped {original_duration}s to {duration_seconds}s")
```

### API Call Pattern
```python
model = genai.GenerativeModel("veo-3.1-generate-preview")
operation = model.generate_videos(
    prompt=prompt,
    config={
        "aspect_ratio": aspect_ratio,
        "resolution": resolution,
        "duration_seconds": str(duration_seconds)
    }
)

# Poll until done
while not operation.done:
    time.sleep(10)
    operation = operation.refresh()

# Save video
video = operation.response.generated_videos[0]
video.video.save(output_path)
```

### Image-to-Video Mode
```python
def generate_clip_from_image(self, prompt, image_path, duration_seconds, width, height):
    image = Image.open(image_path)
    operation = model.generate_videos(prompt=prompt, image=image, config={...})
    # Same polling and save logic as text-to-video
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking Issue] Missing google-generativeai SDK**
- **Found during:** Task 1 - Create Google Veo 3.1 video provider
- **Issue:** ModuleNotFoundError: No module named 'google.generativeai' on first import attempt
- **Fix:** Installed google-generativeai SDK and dependencies via pip
- **Command:** `pip install google-generativeai pillow tenacity`
- **Files modified:** requirements.txt (regenerated with pip freeze)
- **Commit:** e91f62d (included in Task 1 commit)
- **Rationale:** google-generativeai is a required dependency for Veo provider; plan referenced import but didn't explicitly call out dependency installation. Auto-fixed as blocking issue preventing task completion.

**2. [Rule 3 - Missing Field] google_api_key already in config.py**
- **Found during:** Task 2 - Update video generator factory and package exports
- **Context:** Plan instructed adding google_api_key to Settings, but field already existed (added in Plan 12-01 or 12-02)
- **Action:** Skipped duplicate addition, only updated video_provider_type comment
- **Rationale:** Field already present with correct type and comment; no changes needed beyond comment update

## Verification

All verification steps passed:

1. **Import test:**
   ```python
   from app.services.video_generator import GoogleVeoProvider
   # Result: OK
   ```

2. **Provider instantiation:**
   ```python
   provider = GoogleVeoProvider(google_api_key='', output_dir='output')
   # Result: GoogleVeoProvider instance created
   ```

3. **Resolution support:**
   ```python
   provider.supports_resolution(720, 1280)   # True (9:16 HD)
   provider.supports_resolution(1080, 1920)  # True (9:16 Full HD)
   provider.supports_resolution(500, 500)    # False (unsupported)
   ```

4. **Mock fallback:**
   ```python
   clip_path = provider.generate_clip('test', 5)
   # Result: Mock clip generated at output/clips/mock_412db52b.mp4
   ```

5. **Factory integration:**
   ```python
   from app.services.video_generator import get_video_generator
   gen = get_video_generator()
   # Result: Default provider is MockVideoProvider (correct)
   ```

## Success Criteria

- [x] GoogleVeoProvider is a valid VideoProvider implementation
- [x] Duration clamping to 8 seconds is enforced with logging
- [x] Image-to-video mode available via `generate_clip_from_image()` extension method
- [x] Factory function includes "veo" option
- [x] Mock fallback works when `USE_MOCK_DATA=true` or API key empty

## Known Limitations

1. **SDK Deprecation:** google-generativeai package shows deprecation warning pointing to google.genai. Migration deferred to Phase 13 refinement.
2. **Python 3.9 Warnings:** Multiple FutureWarning messages about Python 3.9 end-of-life. Expected and documented in project memory.
3. **No retry logic:** Unlike FalKlingProvider, Veo provider doesn't have tenacity decorators (imported but not used). Error handling relies on try/except with mock fallback.
4. **No cost estimation:** Unlike Kling provider, Veo provider doesn't log cost estimates. Google AI pricing structure may differ.

## Phase 13 Preparation

This plan specifically enables Phase 13 UGC Product Ad Pipeline by providing:
- **Image-to-video capability:** Animate Imagen-generated product images
- **Built-in audio:** Veo generates video with voice/audio, eliminating separate TTS step
- **Single API key:** Combined with Gemini (LLM) and Imagen (images), entire pipeline uses one GOOGLE_API_KEY

Next steps for Phase 13:
1. Test image-to-video mode with actual Imagen outputs
2. Evaluate audio quality from Veo-generated clips
3. Consider migrating to google.genai SDK if API is stable
4. Add retry logic with tenacity if needed

## Self-Check: PASSED

**Created files:**
- [x] FOUND: app/services/video_generator/google_veo.py

**Modified files:**
- [x] FOUND: app/services/video_generator/generator.py
- [x] FOUND: app/services/video_generator/__init__.py
- [x] FOUND: app/config.py
- [x] FOUND: requirements.txt

**Commits:**
- [x] FOUND: e91f62d (Task 1 - Google Veo 3.1 video provider)
- [x] FOUND: 601eb23 (Task 2 - Factory and exports)

All artifacts verified to exist on disk and in git history.
