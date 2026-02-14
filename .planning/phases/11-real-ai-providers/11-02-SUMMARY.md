---
phase: 11-real-ai-providers
plan: 02
subsystem: content-generation
tags: [tts, elevenlabs, fish-audio, providers, factory-pattern]
dependency_graph:
  requires:
    - 11-01-SUMMARY.md  # Real AI video providers via fal.ai
  provides:
    - ElevenLabs TTS provider with 12 marketing voices
    - Fish Audio TTS provider with reference_id system
    - Extended factory supporting 4 TTS provider types
  affects:
    - app/services/voiceover_generator/generator.py
    - app/config.py
tech_stack:
  added:
    - elevenlabs: Python SDK for ElevenLabs API
  patterns:
    - Provider abstraction with mock fallback (same as OpenAI TTS)
    - Factory pattern for provider selection
    - Lazy client initialization
key_files:
  created:
    - app/services/voiceover_generator/elevenlabs_tts.py
    - app/services/voiceover_generator/fish_audio_tts.py
  modified:
    - app/config.py
    - app/services/voiceover_generator/generator.py
    - app/services/voiceover_generator/__init__.py
    - requirements.txt
decisions:
  - decision: "ElevenLabs as premium TTS provider"
    rationale: "Market leader with 70+ languages, superior voice quality for marketing content, $99/mo pricing"
    alternatives: "Considered OpenAI TTS only, but ElevenLabs offers better marketing-specific voices"
  - decision: "Fish Audio as budget TTS provider"
    rationale: "50-70% cheaper than ElevenLabs, competitive quality in blind tests, good for high-volume testing"
    alternatives: "Considered Play.ht, but Fish Audio has simpler API and better pricing"
  - decision: "Use httpx for Fish Audio (no SDK)"
    rationale: "Fish Audio has simple REST API, no need for separate SDK dependency"
    alternatives: "Could wrap in custom client class, but direct httpx calls are clearer"
  - decision: "ElevenLabs model: eleven_turbo_v2_5"
    rationale: "Fast generation, good quality, cheaper credits than eleven_multilingual_v2"
    alternatives: "eleven_multilingual_v2 for better quality but slower and more expensive"
metrics:
  duration: 2
  completed: 2026-02-14
  tasks_completed: 2
  files_modified: 6
  commits: 2
---

# Phase 11 Plan 02: Real TTS Providers (ElevenLabs & Fish Audio) Summary

**One-liner:** Premium (ElevenLabs) and budget (Fish Audio) TTS providers with 12 preset marketing voices and mock fallback pattern

## Objective

Implement two real TTS providers (ElevenLabs and Fish Audio), extending the existing TTSProvider abstraction to produce natural voiceover audio. ElevenLabs provides premium quality for final videos, Fish Audio offers cost-effective option for high-volume testing and iterations.

## What Was Built

### Provider Implementations

**ElevenLabsTTSProvider:**
- 12 preset marketing voices (Rachel, Drew, Clyde, Paul, Domi, Bella, Antoni, Elli, Josh, Arnold, Adam, Sam)
- Voice name-to-ID mapping for ease of use
- Uses `eleven_turbo_v2_5` model (fast, quality, cost-efficient)
- MP3 output at 44.1kHz, 128kbps
- Lazy client initialization
- Mock fallback when `USE_MOCK_DATA=true` or API key empty

**FishAudioTTSProvider:**
- Reference_id system for voice selection
- 3 convenience aliases: default, english_female, english_male
- Direct httpx calls to Fish Audio REST API (no SDK needed)
- MP3 output format
- Same mock fallback pattern as ElevenLabs and OpenAI

### Factory Updates

Updated `get_voiceover_generator()` factory to support 4 provider types:
- `mock` (default) - Silent audio for local dev
- `openai` - OpenAI TTS (existing)
- `elevenlabs` - ElevenLabs TTS (new)
- `fish` - Fish Audio TTS (new)

Selection via `TTS_PROVIDER_TYPE` environment variable.

### Configuration

Added to Settings class:
- `elevenlabs_api_key: str = ""` (ELEVENLABS_API_KEY env var)
- `fish_audio_api_key: str = ""` (FISH_AUDIO_API_KEY env var)
- Updated `tts_provider_type` comment to include new options

### Dependencies

Added `elevenlabs>=1.0.0` to requirements.txt. Fish Audio uses existing httpx dependency.

## Deviations from Plan

None - plan executed exactly as written.

## Key Implementation Details

**ElevenLabs Voice Mappings:**
```python
VOICE_MAPPINGS = {
    "rachel": "21m00Tcm4TlvDq8ikWAM",  # Default marketing voice
    "drew": "29vD33N1CtxCmqQRPOHJ",
    # ... 10 more voices
}
```

**Fish Audio API Call Pattern:**
```python
response = client.post(
    "https://api.fish.audio/v1/tts",
    headers={
        "Authorization": f"Bearer {self.api_key}",
        "Content-Type": "application/json"
    },
    json={"text": text, "format": "mp3", "reference_id": voice_id}
)
```

**Mock Fallback Pattern (consistent across all providers):**
```python
if settings.use_mock_data or not self.api_key:
    return self.mock_provider.generate_speech(text, voice, output_path)
```

## Testing Evidence

All verification checks passed:
- ✓ ElevenLabsTTSProvider and FishAudioTTSProvider import cleanly
- ✓ Both classes implement TTSProvider ABC correctly
- ✓ Factory selects correct provider based on TTS_PROVIDER_TYPE
- ✓ Config includes elevenlabs_api_key and fish_audio_api_key settings
- ✓ elevenlabs dependency in requirements.txt
- ✓ Python 3.9 compatible (uses `from typing import List, Optional`)
- ✓ All existing providers still work (mock, openai)

## Task Breakdown

| Task | Name                                      | Commit  | Files                                                                                   |
| ---- | ----------------------------------------- | ------- | --------------------------------------------------------------------------------------- |
| 1    | Implement ElevenLabs and Fish Audio TTS   | b95117a | elevenlabs_tts.py, fish_audio_tts.py, config.py, requirements.txt                      |
| 2    | Update factory with new provider options  | 53ee469 | generator.py, __init__.py                                                               |

## User Setup Required

**ElevenLabs:**
1. Visit https://elevenlabs.io/app/settings/api-keys
2. Create API key
3. Add to `.env`: `ELEVENLABS_API_KEY=your-key-here`
4. Set `TTS_PROVIDER_TYPE=elevenlabs`

**Fish Audio:**
1. Visit https://fish.audio/account
2. Get API key from account settings
3. Add to `.env`: `FISH_AUDIO_API_KEY=your-key-here`
4. Set `TTS_PROVIDER_TYPE=fish`

**Note:** Both providers gracefully fall back to mock when API keys are empty or `USE_MOCK_DATA=true`.

## Success Criteria Met

- [x] TTS_PROVIDER_TYPE=elevenlabs instantiates ElevenLabsTTSProvider
- [x] TTS_PROVIDER_TYPE=fish instantiates FishAudioTTSProvider
- [x] TTS_PROVIDER_TYPE=openai still works (existing provider)
- [x] Both new providers fall back to mock when API keys are empty or USE_MOCK_DATA=true
- [x] Mock provider remains default (TTS_PROVIDER_TYPE=mock)
- [x] No import errors in any module

## Next Steps

Phase 11 Plan 03: Avatar video providers (HeyGen) for human presenter videos

## Self-Check: PASSED

**Created files verified:**
```
✓ app/services/voiceover_generator/elevenlabs_tts.py exists
✓ app/services/voiceover_generator/fish_audio_tts.py exists
```

**Commits verified:**
```
✓ b95117a: feat(11-02): implement ElevenLabs and Fish Audio TTS providers
✓ 53ee469: feat(11-02): update voiceover generator factory for new TTS providers
```

**Modified files verified:**
```
✓ app/config.py contains elevenlabs_api_key and fish_audio_api_key
✓ app/services/voiceover_generator/generator.py contains ElevenLabsTTSProvider and FishAudioTTSProvider imports
✓ app/services/voiceover_generator/__init__.py exports both new providers
✓ requirements.txt contains elevenlabs>=1.0.0
```
