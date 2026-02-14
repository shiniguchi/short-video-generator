---
phase: 11-real-ai-providers
plan: 03
subsystem: avatar_generator
tags: [heygen, avatar, talking-head, provider-pattern]
dependency_graph:
  requires:
    - Phase 11 Plan 01 (fal.ai video providers)
    - Phase 11 Plan 02 (TTS providers)
    - Phase 3 provider pattern
  provides:
    - HeyGen avatar video generation
    - Avatar provider factory
    - Mock avatar provider for local dev
  affects:
    - app/tasks.py (avatar step in pipeline)
    - .env.example (all Phase 11 provider settings)
tech_stack:
  added:
    - HeyGen API v2 (talking-head video generation)
    - httpx (HTTP client for HeyGen API polling)
  patterns:
    - Provider abstraction (ABC + mock + real + factory)
    - Mock fallback (when USE_MOCK_DATA=true or no API key)
    - Conditional pipeline branching (avatar replaces video+voiceover)
key_files:
  created:
    - app/services/avatar_generator/__init__.py
    - app/services/avatar_generator/base.py
    - app/services/avatar_generator/mock.py
    - app/services/avatar_generator/heygen.py
    - app/services/avatar_generator/generator.py
  modified:
    - app/config.py (avatar provider settings)
    - app/tasks.py (avatar integration)
    - .env.example (all provider settings)
decisions:
  - choice: "HeyGen avatar video replaces both video + voiceover"
    rationale: "HeyGen produces complete talking-head with embedded speech audio"
  - choice: "Avatar generation as Step 6b (after voiceover generation)"
    rationale: "Allows pipeline to still generate voiceover separately for non-avatar paths"
  - choice: "Only activate avatar when AVATAR_PROVIDER_TYPE in ('heygen',)"
    rationale: "Mock mode stays default, avatar is opt-in feature"
metrics:
  duration_minutes: 2
  tasks_completed: 2
  files_created: 5
  files_modified: 3
  commits: 2
  completed_date: 2026-02-14
---

# Phase 11 Plan 03: HeyGen Avatar Provider Summary

**One-liner:** HeyGen talking-head avatar generation with API v2 integration, replacing separate video+voiceover in pipeline when enabled

## What Was Built

Created a complete avatar_generator subsystem following the established provider pattern:

1. **AvatarProvider ABC** - Abstract base class defining talking-head generation interface
2. **MockAvatarProvider** - Placeholder generator using moviepy ColorClip (purple, duration from script length)
3. **HeyGenAvatarProvider** - Full HeyGen API v2 integration with video creation, polling, and download
4. **AvatarGeneratorService** - Wrapper service with factory function for provider selection
5. **Pipeline integration** - Step 6b conditionally generates avatar video when configured
6. **Complete .env.example** - All Phase 11 provider settings documented

## Key Implementation Details

### HeyGen API Integration

**Video Creation Flow:**
1. POST to `https://api.heygen.com/v2/video/generate` with script text + avatar ID + voice ID
2. Poll `https://api.heygen.com/v1/video_status.get` every 10 seconds (10 minute timeout)
3. Download completed video URL to local `output/avatars/` directory
4. Return local file path

**Fallback Logic:**
- If `USE_MOCK_DATA=true` → use MockAvatarProvider
- If `heygen_api_key` is empty → use MockAvatarProvider
- Otherwise → use HeyGen API

### Pipeline Integration Strategy

**Key insight:** Avatar video is fundamentally different from standard video generation:
- **Input:** Script text (not visual prompts)
- **Output:** Complete talking-head video with embedded speech audio
- **Replacement:** Avatar replaces BOTH video AND voiceover (not just video)

**Implementation:**
```python
# Step 6b: Generate avatar video if avatar provider is configured
if settings.avatar_provider_type in ("heygen",):
    avatar_path = avatar_gen.generate_avatar_video(script_text=plan['voiceover_script'])
    video_path = avatar_path  # Avatar replaces video
    audio_path = avatar_path  # Avatar has embedded audio
```

**When Step 6b runs:**
- `AVATAR_PROVIDER_TYPE=heygen` → Avatar video generated, replaces video+voiceover
- `AVATAR_PROVIDER_TYPE=mock` (default) → Pipeline works as before (separate video + voiceover)

### .env.example Consolidation

Updated .env.example to include ALL Phase 11 provider settings:

**Video Providers (Plan 01):**
- `FAL_KEY` - fal.ai API key for Kling/Minimax
- `VIDEO_PROVIDER_TYPE` - mock/svd/kling/minimax

**TTS Providers (Plan 02):**
- `ELEVENLABS_API_KEY` - ElevenLabs TTS API key
- `FISH_AUDIO_API_KEY` - Fish Audio TTS API key
- `TTS_PROVIDER_TYPE` - mock/openai/elevenlabs/fish

**Avatar Providers (Plan 03):**
- `HEYGEN_API_KEY` - HeyGen API key
- `HEYGEN_AVATAR_ID` - Default avatar ID from HeyGen dashboard
- `AVATAR_PROVIDER_TYPE` - mock/heygen

## Deviations from Plan

None - plan executed exactly as written.

## Verification Results

All success criteria met:

✓ `AVATAR_PROVIDER_TYPE=heygen` instantiates HeyGenAvatarProvider
✓ HeyGen provider falls back to mock when `HEYGEN_API_KEY` is empty or `USE_MOCK_DATA=true`
✓ Pipeline generates content end-to-end with all-mock defaults
✓ .env.example contains all provider configuration keys
✓ No import errors or pipeline breakage with default settings

**Import verification:**
```
python -c "from app.services.avatar_generator import AvatarProvider, MockAvatarProvider, HeyGenAvatarProvider, get_avatar_generator; print('Avatar OK')"
```
→ Avatar OK

**Config verification:**
```
python -c "from app.config import get_settings; s = get_settings(); print(f'avatar_provider_type: {s.avatar_provider_type}')"
```
→ avatar_provider_type: mock

**Tasks verification:**
```
python -c "from app.tasks import generate_content_task; print('Tasks OK')"
```
→ Tasks OK

## Task Breakdown

| Task | Description | Commit | Key Changes |
|------|-------------|--------|-------------|
| 1 | Create avatar generator subsystem with HeyGen provider | c9e934a | AvatarProvider ABC, MockAvatarProvider, HeyGenAvatarProvider, factory, config settings |
| 2 | Wire avatar provider into pipeline and update env documentation | 4067eed | Step 6b in generate_content_task, complete .env.example |

## Files Changed

**Created (5 files):**
- `app/services/avatar_generator/__init__.py` - Package exports
- `app/services/avatar_generator/base.py` - AvatarProvider ABC
- `app/services/avatar_generator/mock.py` - MockAvatarProvider with moviepy
- `app/services/avatar_generator/heygen.py` - HeyGenAvatarProvider with API v2
- `app/services/avatar_generator/generator.py` - AvatarGeneratorService + factory

**Modified (3 files):**
- `app/config.py` - Added heygen_api_key, avatar_provider_type, heygen_avatar_id
- `app/tasks.py` - Added Step 6b for avatar video generation
- `.env.example` - Added all Phase 11 provider settings with section comments

## Impact on Codebase

**New Capabilities:**
- HeyGen talking-head avatar generation as alternative to standard video+voiceover
- Unified provider configuration in .env for all AI services (video, TTS, avatar)
- Complete mock-mode operation without any API keys (default behavior)

**Pipeline Flow:**
- **Default (mock):** config → script → video → voiceover → compose
- **With avatar:** config → script → avatar (replaces video+voiceover) → compose

**Dependencies:**
- Requires `httpx` (already in requirements.txt from Plan 02)
- Requires `moviepy` (already in requirements.txt from Phase 3)

## Next Steps

Phase 11 complete! All 3 plans executed:
- 11-01: fal.ai video providers (Kling, Minimax)
- 11-02: TTS providers (ElevenLabs, Fish Audio)
- 11-03: Avatar provider (HeyGen)

**Ready for milestone v1.0 audit.**

## Self-Check: PASSED

**Files exist:**
```bash
[ -f "app/services/avatar_generator/base.py" ] && echo "FOUND"
[ -f "app/services/avatar_generator/mock.py" ] && echo "FOUND"
[ -f "app/services/avatar_generator/heygen.py" ] && echo "FOUND"
[ -f "app/services/avatar_generator/generator.py" ] && echo "FOUND"
[ -f "app/services/avatar_generator/__init__.py" ] && echo "FOUND"
```
→ All 5 files FOUND

**Commits exist:**
```bash
git log --oneline --all | grep -q "c9e934a" && echo "FOUND: c9e934a"
git log --oneline --all | grep -q "4067eed" && echo "FOUND: 4067eed"
```
→ Both commits FOUND

**Imports resolve:**
```bash
python -c "from app.services.avatar_generator import get_avatar_generator; print('OK')"
python -c "from app.tasks import generate_content_task; print('OK')"
```
→ Both imports OK
