---
phase: 12-google-ai-provider-suite
plan: 02
subsystem: image-provider
tags:
  - image-generation
  - imagen
  - provider-abstraction
  - google-ai
dependency_graph:
  requires:
    - app/config.py (IMAGE_PROVIDER_TYPE, GOOGLE_API_KEY settings)
    - app/services/video_generator/base.py (provider abstraction pattern)
  provides:
    - app/services/image_provider/ (ImageProvider abstraction)
    - app/services/image_provider/get_image_provider() (factory function)
  affects:
    - Phase 13 (UGC Product Ad Pipeline uses image provider for hero images and B-Roll product shots)
tech_stack:
  added:
    - google.generativeai (Imagen 4 SDK - deprecated, needs migration to google.genai)
    - Pillow (PIL for mock image generation)
    - tenacity (retry logic for API calls)
  patterns:
    - Provider abstraction pattern (ABC base + mock + real providers)
    - Lazy mock provider initialization for fallback
    - Factory function with USE_MOCK_DATA and API key validation
    - Retry with exponential backoff for API resilience
key_files:
  created:
    - app/services/image_provider/base.py (ImageProvider ABC)
    - app/services/image_provider/mock.py (MockImageProvider)
    - app/services/image_provider/google_imagen.py (GoogleImagenProvider)
    - app/services/image_provider/__init__.py (factory + exports)
  modified: []
decisions:
  - Use google.generativeai SDK (deprecated) for Imagen 4 - needs migration to google.genai in future
  - Aspect ratio derived from width/height ratio (9:16 if height > width, 16:9 if width > height, 1:1 if equal)
  - Support reference_images parameter for style guidance (optional PIL Image list)
  - 512-2048 pixel range for resolution support validation
  - PNG output format for all generated images
  - Fixed type hint issue using Any instead of ImageGenerationModel when SDK unavailable
metrics:
  duration_seconds: 164
  duration_minutes: 2
  tasks_completed: 2
  files_created: 4
  commits: 2
  completed_date: 2026-02-15
---

# Phase 12 Plan 02: Image Provider Abstraction Summary

**One-liner:** Imagen 4 text-to-image generation with reference image support and mock fallback using provider abstraction pattern.

## What Was Built

Created a complete ImageProvider abstraction layer following the same pattern as VideoProvider and TTSProvider:

1. **ImageProvider ABC** (`base.py`):
   - `generate_image(prompt, width, height, num_images, reference_images)` - Generate images from text prompt
   - `supports_resolution(width, height)` - Validate resolution support
   - Returns list of file paths for batch generation support

2. **MockImageProvider** (`mock.py`):
   - Generates solid-color PNG placeholder images using Pillow
   - Color derived from prompt hash for consistency (same pattern as MockVideoProvider)
   - Creates images in `output/images/` directory
   - Supports any resolution (always returns True)

3. **GoogleImagenProvider** (`google_imagen.py`):
   - Uses google.generativeai SDK with ImageGenerationModel("imagen-4.0-generate-001")
   - Derives aspect_ratio from width/height: "9:16", "16:9", or "1:1"
   - Supports reference images for style guidance (loads PIL Images from paths)
   - Retry logic: 3 attempts with exponential backoff (2x multiplier, 4-30s wait)
   - Falls back to mock on API errors or when USE_MOCK_DATA=true
   - Validates resolution support: 512-2048 pixel range

4. **Factory Function** (`__init__.py`):
   - `get_image_provider()` returns configured provider based on IMAGE_PROVIDER_TYPE
   - Falls back to mock when GOOGLE_API_KEY is empty or USE_MOCK_DATA=true
   - Exports ImageProvider, MockImageProvider, GoogleImagenProvider, get_image_provider

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed NameError for ImageGenerationModel type hint**
- **Found during:** Task 2 verification
- **Issue:** When google.generativeai SDK is not installed, `ImageGenerationModel` is not defined but was used in type hint for `_generate_with_retry()` method, causing NameError at import time
- **Fix:** Changed type hint from `ImageGenerationModel` to `Any` (imported from typing) to support environments where SDK is unavailable
- **Files modified:** app/services/image_provider/google_imagen.py
- **Commit:** 9be0eac

## Verification Results

All verification checks passed:

1. Factory returns MockImageProvider by default: PASSED
2. ImageProvider ABC has generate_image and supports_resolution methods: PASSED
3. MockImageProvider generates valid PNG files: PASSED
4. GoogleImagenProvider imports without error: PASSED
5. Factory correctly falls back to mock when USE_MOCK_DATA=true: PASSED

## Known Limitations

1. **SDK Deprecation Warning**: google.generativeai package is deprecated. All support has ended. Need to migrate to google.genai package in future update.
2. **Resolution Granularity**: Aspect ratio is coarse-grained (9:16, 16:9, 1:1) - Imagen doesn't support arbitrary aspect ratios
3. **Reference Image Validation**: No validation of reference image format or size - relies on Imagen API to handle invalid inputs

## Integration Points

- **Phase 13 UGC Product Ad Pipeline**: Uses ImageProvider for hero images and B-Roll product shots
- **Config**: Reads IMAGE_PROVIDER_TYPE and GOOGLE_API_KEY from settings (added by Plan 01)
- **Pattern**: Follows exact same abstraction pattern as VideoProvider and TTSProvider

## Self-Check: PASSED

Created files verified:
```
FOUND: /Users/naokitsk/Documents/short-video-generator/app/services/image_provider/base.py
FOUND: /Users/naokitsk/Documents/short-video-generator/app/services/image_provider/mock.py
FOUND: /Users/naokitsk/Documents/short-video-generator/app/services/image_provider/google_imagen.py
FOUND: /Users/naokitsk/Documents/short-video-generator/app/services/image_provider/__init__.py
```

Commits verified:
```
FOUND: ce03a01 (Task 1 - ImageProvider abstraction with mock and Imagen)
FOUND: 9be0eac (Task 2 - Factory function)
```

All claimed artifacts exist and are committed to git.
