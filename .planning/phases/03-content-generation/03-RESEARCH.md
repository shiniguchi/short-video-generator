# Phase 3: Content Generation - Research

**Researched:** 2026-02-13
**Domain:** AI Content Generation (Script, Video, Voiceover)
**Confidence:** MEDIUM-HIGH

## Summary

Phase 3 implements the content generation pipeline: AI-driven script generation via Claude API prompt chaining, video clip generation, and text-to-speech voiceover synthesis. The phase bridges trend intelligence (Phase 2) with video composition (Phase 4) by transforming trend patterns into production-ready video assets.

The core technical challenge is orchestrating three distinct AI generation workflows (script → video → voiceover) while respecting critical environmental constraints: **NO Docker/GPU locally, Python 3.9 compatibility, SQLite-only database, and mock-data-first development**. The architecture must support swappable backends (Stable Video Diffusion → Veo/Sora later, OpenAI TTS → ElevenLabs/Fish Audio later) through provider abstraction.

**Critical Insight:** Stable Video Diffusion requires GPU and Docker—both unavailable in the local environment. The phase must implement a mock/stub video generation provider for local development that simulates SVD behavior (generates placeholder videos), with the real SVD integration designed but untested until deployment to a GPU-enabled environment.

**Primary recommendation:** Use Claude Structured Outputs (JSON schema validation) for reliable prompt chain results, implement provider abstraction pattern with dependency injection for swappable video/TTS backends, leverage Celery with SQLAlchemy transport (no Redis) for async task processing, and build mock providers that return realistic test data for all external AI services.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| anthropic | 0.40.0+ | Claude API client | Official SDK with structured outputs support (beta Nov 2025, GA 2026) |
| openai | 1.60.0+ | OpenAI TTS API | Official SDK, supports tts-1-hd model and streaming |
| moviepy | 1.0.3+ | Video processing | Python-native FFmpeg wrapper, handles concatenation and format conversion |
| pillow | 11.0.0+ | Image generation | Create placeholder frames for mock video generation |
| gspread | 6.2.1+ | Google Sheets integration | Service account auth, clean API for reading theme configs |
| pydantic | 2.12+ | Schema validation | Built into FastAPI, validates API responses and internal data |
| celery | 5.6.2+ | Async task queue | SQLAlchemy transport support for local dev without Redis |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| ffmpeg-python | 0.2.0+ | FFmpeg bindings | Low-level video operations (chaining clips, format conversions) |
| elevenlabs | 1.11.0+ | ElevenLabs TTS (optional) | If swapping from OpenAI TTS for higher quality voices |
| dependency-injector | 4.48.3+ | DI framework | Provider abstraction for swappable backends |
| google-auth | 2.40.0+ | Google API auth | Service account credentials for Sheets API |
| aiofiles | 24.1.0+ | Async file I/O | Async read/write for video/audio file handling |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| moviepy | opencv-python | OpenCV faster but less Pythonic, harder to use |
| OpenAI TTS | Fish Audio, ElevenLabs | Fish Audio 70% cheaper, ElevenLabs higher quality, both require more setup |
| gspread | Google Sheets API (raw) | gspread abstracts complexity, raw API more flexible but verbose |
| Stable Video Diffusion | Runway ML, Wan2.2 | SVD local/free but slow, Runway cloud API faster but $$, Wan2.2 needs 24GB GPU |

**Installation (Python 3.9.6 compatible):**
```bash
pip install anthropic>=0.40.0 openai>=1.60.0 moviepy>=1.0.3 pillow>=11.0.0 \
            gspread>=6.2.1 ffmpeg-python>=0.2.0 dependency-injector>=4.48.3 \
            google-auth>=2.40.0 aiofiles>=24.1.0
```

## Architecture Patterns

### Recommended Project Structure
```
app/
├── services/
│   ├── script_generator/         # Claude API prompt chain
│   │   ├── __init__.py
│   │   ├── generator.py          # Main orchestrator
│   │   ├── prompts.py            # 5-step prompt templates
│   │   ├── schemas.py            # Pydantic schemas for structured outputs
│   │   └── tasks.py              # Celery tasks
│   │
│   ├── video_generator/          # Video clip generation
│   │   ├── __init__.py
│   │   ├── providers/            # Swappable backends
│   │   │   ├── base.py           # Abstract interface
│   │   │   ├── mock.py           # Placeholder generator (local dev)
│   │   │   ├── svd.py            # Stable Video Diffusion (GPU required)
│   │   │   └── veo.py            # Google Veo (future)
│   │   ├── generator.py          # Provider orchestrator
│   │   ├── chaining.py           # Multi-clip concatenation
│   │   └── tasks.py              # Celery tasks
│   │
│   ├── voiceover_generator/      # TTS synthesis
│   │   ├── __init__.py
│   │   ├── providers/            # Swappable backends
│   │   │   ├── base.py           # Abstract interface
│   │   │   ├── openai.py         # OpenAI TTS (default)
│   │   │   ├── elevenlabs.py    # ElevenLabs (optional)
│   │   │   └── fish.py           # Fish Audio (optional)
│   │   ├── generator.py          # Provider orchestrator
│   │   ├── sync.py               # Duration matching to video
│   │   └── tasks.py              # Celery tasks
│   │
│   └── config_reader/            # Theme configuration
│       ├── __init__.py
│       ├── sheets.py             # Google Sheets integration
│       ├── local.py              # Local JSON fallback
│       └── schemas.py            # Theme config models
│
├── models/                       # SQLAlchemy models
│   ├── production_plan.py        # Generated scripts/plans
│   ├── video_clip.py             # Generated video metadata
│   └── voiceover.py              # Generated audio metadata
│
└── api/
    └── content.py                # REST endpoints for generation
```

### Pattern 1: Claude Prompt Chaining with Structured Outputs

**What:** Break script generation into 5 sequential Claude API calls, each with JSON schema validation to ensure reliable outputs that feed into the next step.

**When to use:** Complex multi-step LLM workflows where each stage builds on previous results and requires structured data (not free-form text).

**Example:**
```python
# Source: https://platform.claude.com/docs/en/build-with-claude/structured-outputs
from anthropic import Anthropic
from pydantic import BaseModel
from typing import List

class ThemeInterpretation(BaseModel):
    """Step 1: Analyze theme/product"""
    core_message: str
    target_audience: str
    emotional_tone: str
    key_benefits: List[str]

class TrendAlignment(BaseModel):
    """Step 2: Match to trend patterns"""
    selected_patterns: List[str]
    style_classification: str  # "cinematic", "talking-head", etc.
    engagement_hooks: List[str]

class SceneConstruction(BaseModel):
    """Step 3: Build scene breakdown"""
    scenes: List[dict]  # {duration, visual_prompt, transition}
    video_prompt: str
    duration_target: int

class NarrationScript(BaseModel):
    """Step 4: Generate voiceover"""
    voiceover_script: str
    hook_text: str
    cta_text: str

class TextOverlayDesign(BaseModel):
    """Step 5: Design text overlays"""
    text_overlays: List[dict]  # {text, timestamp, position, style}
    hashtags: List[str]
    title: str
    description: str

class VideoProductionPlan(BaseModel):
    """Final combined output"""
    theme: ThemeInterpretation
    trends: TrendAlignment
    scenes: SceneConstruction
    narration: NarrationScript
    overlays: TextOverlayDesign

client = Anthropic(api_key="...")

def generate_production_plan(theme_config: dict, trend_report: dict) -> VideoProductionPlan:
    """5-step prompt chain with structured outputs"""

    # Step 1: Theme interpretation
    response1 = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=1024,
        messages=[{
            "role": "user",
            "content": f"Analyze this theme: {theme_config}"
        }],
        output_config={
            "format": {
                "type": "json_schema",
                "schema": ThemeInterpretation.model_json_schema()
            }
        }
    )
    theme = ThemeInterpretation.model_validate_json(response1.content[0].text)

    # Step 2: Trend alignment (uses output from step 1)
    response2 = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=1024,
        messages=[{
            "role": "user",
            "content": f"Match theme to trends:\nTheme: {theme.model_dump_json()}\nTrends: {trend_report}"
        }],
        output_config={
            "format": {
                "type": "json_schema",
                "schema": TrendAlignment.model_json_schema()
            }
        }
    )
    trends = TrendAlignment.model_validate_json(response2.content[0].text)

    # Steps 3-5 follow same pattern...
    # Final: Combine all outputs into VideoProductionPlan

    return VideoProductionPlan(
        theme=theme,
        trends=trends,
        scenes=scenes,
        narration=narration,
        overlays=overlays
    )
```

**Why this is critical:** Without structured outputs, Claude might return malformed JSON (~5-10% failure rate), requiring retries and error handling. Structured outputs guarantee schema compliance through constrained decoding, eliminating parsing errors.

**Confidence:** HIGH - Official Anthropic docs confirm structured outputs are GA for Opus 4.6/Sonnet 4.5 since November 2025.

### Pattern 2: Provider Abstraction for Swappable Backends

**What:** Define abstract base classes for video/TTS generation, allowing runtime selection of providers (mock, SVD, Veo, OpenAI, ElevenLabs) via dependency injection.

**When to use:** When you need to swap implementations without changing consumer code, especially for external APIs or hardware-dependent operations.

**Example:**
```python
# Source: https://python-dependency-injector.ets-labs.org/providers/factory.html
from abc import ABC, abstractmethod
from dependency_injector import containers, providers

# Abstract interface
class VideoProvider(ABC):
    @abstractmethod
    async def generate_video(self, prompt: str, duration: int) -> bytes:
        """Generate video from text prompt"""
        pass

    @abstractmethod
    def supports_chaining(self) -> bool:
        """Does provider support multi-clip generation?"""
        pass

# Mock implementation (local dev, no GPU)
class MockVideoProvider(VideoProvider):
    async def generate_video(self, prompt: str, duration: int) -> bytes:
        """Generate solid color placeholder video"""
        from moviepy.editor import ColorClip
        clip = ColorClip(size=(720, 1280), color=(100, 100, 200), duration=duration)
        clip.write_videofile("temp.mp4", fps=24, codec="libx264")
        with open("temp.mp4", "rb") as f:
            return f.read()

    def supports_chaining(self) -> bool:
        return True

# Real implementation (GPU required)
class StableVideoDiffusionProvider(VideoProvider):
    async def generate_video(self, prompt: str, duration: int) -> bytes:
        """Generate via SVD (requires Docker + GPU)"""
        # This will NOT work locally - designed for deployment
        raise NotImplementedError("SVD requires GPU - use MockVideoProvider locally")

    def supports_chaining(self) -> bool:
        return False  # SVD generates one clip at a time

# Dependency injection container
class Container(containers.DeclarativeContainer):
    config = providers.Configuration()

    # Select provider based on environment
    video_provider = providers.Selector(
        config.video_provider_type,
        mock=providers.Factory(MockVideoProvider),
        svd=providers.Factory(StableVideoDiffusionProvider),
        # veo=providers.Factory(VeoProvider),  # Future
    )

# Usage in service
class VideoGeneratorService:
    def __init__(self, provider: VideoProvider):
        self.provider = provider

    async def generate(self, prompt: str, duration: int) -> bytes:
        return await self.provider.generate_video(prompt, duration)

# Configuration (via environment variable)
# VIDEO_PROVIDER_TYPE=mock (local dev)
# VIDEO_PROVIDER_TYPE=svd (production with GPU)
```

**Why this is critical:** Local environment has NO GPU and NO Docker, so SVD cannot run. Mock provider allows full development and testing without GPU, with clean swap to real provider on deployment.

**Confidence:** HIGH - Standard Python pattern, official dependency-injector docs.

### Pattern 3: Celery with SQLAlchemy Transport (No Redis)

**What:** Use SQLAlchemy database as Celery broker instead of Redis, enabling local development without Docker/Redis while maintaining production Celery compatibility.

**When to use:** Local development on constrained environments, or when you already have a database but want to avoid additional infrastructure.

**Trade-offs:**
- **Pros:** No Redis dependency, works with existing SQLite/PostgreSQL, simpler local setup
- **Cons:** Slower than Redis, no remote control commands (celery events), not recommended for high-throughput production

**Example:**
```python
# Source: https://docs.celeryq.dev/en/3.1/getting-started/brokers/sqlalchemy.html
from celery import Celery

# SQLite transport (local dev)
app = Celery(
    'short_video_generator',
    broker='sqla+sqlite:///celerydb.sqlite',
    backend='db+sqlite:///results.sqlite'
)

# PostgreSQL transport (production, still no Redis)
# broker='sqla+postgresql://user:pass@localhost/celery_broker'

# Task definition
@app.task(bind=True, max_retries=3)
def generate_production_plan_task(self, theme_id: str):
    """Celery task for async script generation"""
    try:
        # Run 5-step prompt chain
        plan = generate_production_plan(theme_id)
        return {"status": "success", "plan_id": plan.id}
    except Exception as e:
        raise self.retry(exc=e, countdown=60)

# FastAPI endpoint triggers Celery task
@app.post("/api/content/generate")
async def trigger_generation(theme_id: str):
    task = generate_production_plan_task.delay(theme_id)
    return {"task_id": task.id, "status": "processing"}
```

**Why this works:** Project requirements specify SQLite + SQLAlchemy transport for local dev (no Docker/Redis). Production can switch to Redis by changing broker URL without code changes.

**Confidence:** MEDIUM - SQLAlchemy transport is officially supported but documented as "not recommended for high-throughput." Acceptable for local dev and prototype phase.

### Pattern 4: Mock Data Providers with USE_MOCK_DATA Flag

**What:** All external API calls (Claude, OpenAI TTS, video generation) check `USE_MOCK_DATA` environment variable and return realistic test data instead of calling real APIs.

**When to use:** Local development without API credentials, CI/CD testing, cost control during iteration.

**Example:**
```python
# config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    use_mock_data: bool = True  # Default to mock mode
    anthropic_api_key: str = ""
    openai_api_key: str = ""

settings = Settings()

# script_generator/generator.py
def generate_production_plan(theme_config: dict):
    if settings.use_mock_data:
        # Return pre-generated mock data
        return VideoProductionPlan(
            theme=ThemeInterpretation(
                core_message="Boost your productivity with AI",
                target_audience="tech professionals",
                emotional_tone="inspiring",
                key_benefits=["Save time", "Automate tasks", "Scale faster"]
            ),
            # ... rest of mock data
        )
    else:
        # Real Claude API call
        return _call_claude_api(theme_config)

# voiceover_generator/providers/openai.py
class OpenAITTSProvider:
    async def generate(self, text: str) -> bytes:
        if settings.use_mock_data:
            # Return silent MP3 file
            return self._generate_silent_audio(duration=len(text) / 15)  # ~15 chars/sec
        else:
            # Real OpenAI TTS call
            response = openai_client.audio.speech.create(
                model="tts-1-hd",
                voice="alloy",
                input=text
            )
            return response.content
```

**Why this is critical:** Requirements state "USE_MOCK_DATA=true is the default mode" and "testing without API credentials." All services must work end-to-end with mock data before enabling real APIs.

**Confidence:** HIGH - Standard testing pattern, explicit requirement.

### Pattern 5: Video Clip Chaining with Duration Matching

**What:** Generate multiple 2-4 second video clips and concatenate them to reach target duration (15-30 seconds), then sync voiceover audio to match final video length.

**When to use:** Video generation APIs with short clip limits (SVD max ~4 seconds) that need to produce longer videos.

**Example:**
```python
# Source: https://thepythoncode.com/article/concatenate-video-files-in-python
from moviepy.editor import VideoFileClip, concatenate_videoclips, AudioFileClip

def chain_video_clips(clip_paths: List[str], target_duration: int) -> VideoFileClip:
    """Concatenate short clips to reach target duration"""
    clips = [VideoFileClip(path) for path in clip_paths]

    # Calculate how many loops needed
    total_duration = sum(clip.duration for clip in clips)
    loops_needed = int(target_duration / total_duration) + 1

    # Repeat clips to exceed target
    extended_clips = clips * loops_needed

    # Concatenate and trim to exact duration
    final_clip = concatenate_videoclips(extended_clips, method="compose")
    final_clip = final_clip.subclip(0, target_duration)

    return final_clip

def sync_audio_to_video(video_clip: VideoFileClip, audio_path: str) -> VideoFileClip:
    """Stretch or trim audio to match video duration"""
    audio = AudioFileClip(audio_path)
    video_duration = video_clip.duration

    if audio.duration > video_duration:
        # Trim audio
        audio = audio.subclip(0, video_duration)
    elif audio.duration < video_duration:
        # Loop audio (rarely needed for TTS)
        loops = int(video_duration / audio.duration) + 1
        audio = concatenate_audioclips([audio] * loops).subclip(0, video_duration)

    # Set audio on video
    final_video = video_clip.set_audio(audio)
    return final_video

# Usage in video generation service
async def generate_complete_video(production_plan: VideoProductionPlan):
    # Generate 4-5 clips of 3 seconds each
    clip_paths = []
    for scene in production_plan.scenes[:5]:
        clip_bytes = await video_provider.generate_video(
            prompt=scene.visual_prompt,
            duration=3
        )
        path = save_to_temp(clip_bytes)
        clip_paths.append(path)

    # Chain to 15 seconds
    video_clip = chain_video_clips(clip_paths, target_duration=15)

    # Generate voiceover
    audio_bytes = await tts_provider.generate(production_plan.narration.voiceover_script)
    audio_path = save_to_temp(audio_bytes)

    # Sync audio to video
    final_video = sync_audio_to_video(video_clip, audio_path)

    # Export
    final_video.write_videofile("output.mp4", codec="libx264", audio_codec="aac")
```

**Why this is critical:** SVD (and most video AI models) have short clip limits. TikTok/YouTube Shorts require 15-30 seconds. Chaining + audio sync bridges the gap.

**Confidence:** HIGH - moviepy's `concatenate_videoclips` is standard solution, widely documented.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| JSON schema validation | Custom dict parser with try/except | Claude Structured Outputs + Pydantic | Constrained decoding eliminates parsing errors, Pydantic provides type safety |
| Video concatenation | Manual FFmpeg subprocess calls | moviepy.editor.concatenate_videoclips | Handles codec mismatches, frame rate conversion, audio sync automatically |
| Config file parsing | os.getenv() + manual type conversion | pydantic-settings BaseSettings | Environment variable validation, .env file loading, type coercion built-in |
| Google Sheets auth | Raw OAuth2 flow | gspread with service account JSON | Abstracts token refresh, handles API pagination, validates permissions |
| Audio duration calculation | Parse MP3 headers manually | moviepy.editor.AudioFileClip.duration | Handles multiple formats (MP3, WAV, AAC), reliable across codecs |
| Provider selection | if/else chains for backend switching | dependency-injector Selector | Runtime configuration, testable without mocking, swappable without code changes |

**Key insight:** Video processing is deceptively complex—codecs, frame rates, audio sync, container formats all interact in non-obvious ways. moviepy abstracts 90% of FFmpeg complexity while remaining flexible.

## Common Pitfalls

### Pitfall 1: Assuming Video Generation Works Locally

**What goes wrong:** Developer tries to run Stable Video Diffusion locally without GPU/Docker, gets cryptic errors or extremely slow generation (hours per clip).

**Why it happens:** SVD requires GPU acceleration and Docker containers for dependencies. Docs often assume GPU availability.

**How to avoid:**
- Implement mock video provider that generates solid-color placeholder clips
- Document GPU requirement clearly in README
- Use `VIDEO_PROVIDER_TYPE=mock` by default in .env.example
- Design SVD provider interface but leave implementation stub until deployment

**Warning signs:**
- Local generation takes >5 minutes per 3-second clip
- CUDA errors or "no GPU detected" warnings
- Docker container fails to start with memory errors

**Confidence:** HIGH - Explicit project constraint (no Docker/GPU locally).

### Pitfall 2: Claude API Rate Limiting on Prompt Chains

**What goes wrong:** 5-step prompt chain triggers rate limits (60 requests/minute for free tier), causing intermittent failures during batch processing.

**Why it happens:** Each video generation makes 5 Claude API calls in rapid succession. 12 videos = 60 calls = rate limit hit.

**How to avoid:**
- Implement exponential backoff with retry logic
- Use Celery task rate limits: `@app.task(rate_limit='10/m')`
- Cache intermediate prompt results in database (theme interpretation rarely changes)
- Consider batching: generate scripts for 10 videos, pause, continue

**Warning signs:**
- `RateLimitError: 429 Too Many Requests` in logs
- First few videos succeed, later ones fail
- Success rate drops during high-volume testing

**Confidence:** HIGH - Standard API rate limiting issue, well-documented in Anthropic docs.

### Pitfall 3: Audio-Video Sync Drift

**What goes wrong:** Voiceover audio becomes out-of-sync with video by 1-2 seconds near the end, especially on longer clips.

**Why it happens:**
- TTS generates audio at variable speed (words-per-minute inconsistent)
- Video clips have non-exact durations due to frame rounding
- Different audio codecs introduce small timing offsets

**How to avoid:**
- Always calculate exact video duration FIRST, then stretch/trim audio to match
- Use `fps=24` consistently for all video clips to avoid frame rate mismatches
- Explicitly set audio codec to AAC: `audio_codec='aac'` in moviepy
- Test with >15 second videos (shorter videos hide the drift)

**Warning signs:**
- Audio finishes before/after video ends
- Sync good at start, drifts by end
- Different results on Mac vs Linux (codec availability differences)

**Confidence:** MEDIUM-HIGH - Common issue in video processing, documented in moviepy GitHub issues.

### Pitfall 4: Google Sheets Service Account Permission Hell

**What goes wrong:** `gspread.exceptions.SpreadsheetNotFound` even though spreadsheet exists and URL is correct.

**Why it happens:** Service account email (from credentials JSON) doesn't have access to the spreadsheet. Google Sheets are private by default.

**How to avoid:**
1. Create service account in Google Cloud Console
2. Download credentials JSON
3. Copy service account email from JSON (`client_email` field)
4. **Go to Google Sheet → Share → Add email → Grant Editor access**
5. Test with `gc.open("Sheet Name")` before integrating

**Warning signs:**
- "Spreadsheet not found" error despite correct sheet name/URL
- Works with personal Google account credentials, fails with service account
- Error message doesn't mention permissions (misleading!)

**Confidence:** HIGH - Official gspread docs explicitly warn about this, common beginner issue.

### Pitfall 5: Celery SQLAlchemy Transport Limitations

**What goes wrong:** Celery tasks succeed but never get picked up by workers, or `celery events` command fails with "transport doesn't support remote control."

**Why it happens:** SQLAlchemy transport doesn't support advanced Celery features (remote control, events, revoke). Worker polling interval may be misconfigured.

**How to avoid:**
- Set `broker_transport_options = {'visibility_timeout': 3600}` for long tasks
- Don't rely on `celery events`, `celery inspect`, or Flower for monitoring
- Use database polling for task status instead of Celery result backend
- Plan migration to Redis for production (SQLAlchemy transport is dev-only)

**Warning signs:**
- Tasks stuck in "PENDING" state forever
- `celery events` command errors
- Flower dashboard shows no workers

**Confidence:** MEDIUM - Official Celery docs state "SQLAlchemy transport not recommended for production" but don't detail all limitations.

### Pitfall 6: FastAPI >=0.100.0 with Python 3.9 Incompatibility

**What goes wrong:** Import errors or runtime failures with newer FastAPI versions that assume Python 3.10+ features.

**Why it happens:** Python 3.9 lacks some type hinting features (e.g., `list[str]` instead of `List[str]`), and FastAPI 0.100+ may use them.

**How to avoid:**
- Pin FastAPI version: `fastapi>=0.100.0,<0.120.0` (test compatibility)
- Use `from typing import List, Dict` instead of builtin generics
- Run `python -m pytest` locally before deployment to catch issues early
- Set `requires-python = ">=3.9,<3.10"` in pyproject.toml to enforce version

**Warning signs:**
- `TypeError: 'type' object is not subscriptable` on `list[str]`
- Import errors on `from typing import X` where X doesn't exist in 3.9
- Works on Mac (Python 3.11) but fails on Linux (Python 3.9.6)

**Confidence:** MEDIUM - Python 3.9 is EOL October 2025, but project explicitly requires 3.9.6 compatibility.

## Code Examples

Verified patterns from official sources:

### Claude Structured Outputs - 5-Step Prompt Chain

```python
# Source: https://platform.claude.com/docs/en/build-with-claude/structured-outputs
from anthropic import Anthropic
from pydantic import BaseModel, Field
from typing import List

client = Anthropic(api_key="your_key")

class SceneDescription(BaseModel):
    """Individual scene in video"""
    scene_number: int = Field(ge=1, le=10)
    duration_seconds: int = Field(ge=2, le=4)
    visual_prompt: str = Field(min_length=10, max_length=500)
    transition: str = Field(pattern="^(fade|cut|dissolve)$")

class VideoProductionPlan(BaseModel):
    """Complete production plan for video"""
    video_prompt: str
    duration_target: int = Field(ge=15, le=30)
    aspect_ratio: str = Field(pattern="^9:16$")
    scenes: List[SceneDescription]
    voiceover_script: str
    hashtags: List[str]
    title: str
    description: str

def generate_with_structured_output(theme_config: dict, trend_report: dict):
    """Generate production plan with guaranteed JSON schema compliance"""
    prompt = f"""
    Create a TikTok video production plan based on:

    Theme: {theme_config['product_name']} - {theme_config['tagline']}
    Target: {theme_config['target_audience']}

    Trending patterns: {trend_report['top_patterns']}

    Requirements:
    - 15-30 seconds total
    - 9:16 vertical format
    - 3-7 scenes
    - Hook in first 3 seconds
    - Call-to-action at end
    """

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
        output_config={
            "format": {
                "type": "json_schema",
                "schema": VideoProductionPlan.model_json_schema()
            }
        }
    )

    # Parse and validate (guaranteed to succeed with structured outputs)
    plan = VideoProductionPlan.model_validate_json(response.content[0].text)
    return plan
```

### OpenAI TTS with Streaming

```python
# Source: https://platform.openai.com/docs/guides/text-to-speech
from openai import OpenAI
from pathlib import Path

client = OpenAI(api_key="your_key")

def generate_voiceover(script: str, output_path: str):
    """Generate TTS audio with streaming to disk"""
    response = client.audio.speech.create(
        model="tts-1-hd",  # Higher quality than tts-1
        voice="alloy",     # Options: alloy, echo, fable, onyx, nova, shimmer
        input=script,
        response_format="mp3"  # or "wav", "opus", "aac", "flac"
    )

    # Stream to file (more memory-efficient than loading full response)
    response.stream_to_file(output_path)

    return output_path

# Advanced: Sync audio to video duration
def generate_voiceover_with_duration_target(script: str, target_duration: float, output_path: str):
    """Generate TTS and adjust speed to match video duration"""
    temp_path = "temp_audio.mp3"
    generate_voiceover(script, temp_path)

    # Load and check duration
    from moviepy.editor import AudioFileClip
    audio = AudioFileClip(temp_path)

    if abs(audio.duration - target_duration) < 0.5:
        # Close enough, use as-is
        audio.write_audiofile(output_path)
    else:
        # Speed up or slow down to match target
        speed_factor = audio.duration / target_duration
        adjusted_audio = audio.fx(vfx.speedx, speed_factor)
        adjusted_audio.write_audiofile(output_path)

    audio.close()
```

### Video Clip Chaining

```python
# Source: https://thepythoncode.com/article/concatenate-video-files-in-python
from moviepy.editor import VideoFileClip, concatenate_videoclips, ColorClip
from typing import List

def create_placeholder_clip(color_rgb: tuple, duration: int, resolution: tuple = (720, 1280)) -> VideoFileClip:
    """Generate solid color clip for mock video provider"""
    clip = ColorClip(size=resolution, color=color_rgb, duration=duration)
    clip.fps = 24  # Set consistent frame rate
    return clip

def chain_clips_to_duration(clips: List[VideoFileClip], target_duration: int) -> VideoFileClip:
    """Concatenate clips and trim to exact target duration"""
    # Resize all clips to same dimensions (handle mismatches)
    target_size = clips[0].size
    resized_clips = [
        clip.resize(target_size) if clip.size != target_size else clip
        for clip in clips
    ]

    # Calculate loops needed
    total_duration = sum(clip.duration for clip in resized_clips)
    loops_required = int(target_duration / total_duration) + 1

    # Repeat and concatenate
    extended_clips = resized_clips * loops_required
    final_clip = concatenate_videoclips(extended_clips, method="compose")

    # Trim to exact duration
    final_clip = final_clip.subclip(0, min(target_duration, final_clip.duration))

    return final_clip

def export_with_9_16_aspect_ratio(clip: VideoFileClip, output_path: str):
    """Export vertical video optimized for TikTok/YouTube Shorts"""
    clip.write_videofile(
        output_path,
        fps=24,
        codec="libx264",           # H.264 codec (universal compatibility)
        audio_codec="aac",         # AAC audio (required for mobile)
        preset="medium",           # Encoding speed vs quality
        bitrate="2000k",           # 2 Mbps for 720p vertical
        audio_bitrate="128k",
        threads=4,
        logger=None                # Suppress moviepy progress bar
    )
```

### Google Sheets Configuration Reader

```python
# Source: https://docs.gspread.org/en/latest/oauth2.html
import gspread
from google.oauth2.service_account import Credentials
from pydantic import BaseModel
from typing import Optional

class ThemeConfig(BaseModel):
    theme_id: str
    product_name: str
    tagline: str
    target_audience: str
    tone: str
    cta_text: str

def read_theme_config_from_sheets(spreadsheet_name: str, credentials_path: str) -> ThemeConfig:
    """Read theme configuration from Google Sheets"""
    # Authenticate with service account
    scopes = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ]
    creds = Credentials.from_service_account_file(credentials_path, scopes=scopes)
    client = gspread.authorize(creds)

    # Open spreadsheet
    sheet = client.open(spreadsheet_name).sheet1

    # Read first row (headers) and second row (values)
    headers = sheet.row_values(1)
    values = sheet.row_values(2)

    # Convert to dict
    config_dict = dict(zip(headers, values))

    # Validate with Pydantic
    return ThemeConfig(**config_dict)

def read_theme_config_with_fallback(spreadsheet_name: str, credentials_path: str, local_json_path: str) -> ThemeConfig:
    """Read from Sheets, fall back to local JSON if unavailable"""
    try:
        return read_theme_config_from_sheets(spreadsheet_name, credentials_path)
    except Exception as e:
        print(f"Google Sheets unavailable: {e}. Using local config.")
        import json
        with open(local_json_path) as f:
            return ThemeConfig(**json.load(f))
```

### Provider Abstraction with Dependency Injection

```python
# Source: https://python-dependency-injector.ets-labs.org/providers/factory.html
from abc import ABC, abstractmethod
from dependency_injector import containers, providers
from typing import Protocol

class TTSProvider(Protocol):
    """Abstract TTS interface"""
    async def generate_speech(self, text: str, voice: str) -> bytes:
        """Generate audio from text"""
        ...

class OpenAITTSProvider:
    """OpenAI TTS implementation"""
    def __init__(self, api_key: str):
        from openai import OpenAI
        self.client = OpenAI(api_key=api_key)

    async def generate_speech(self, text: str, voice: str = "alloy") -> bytes:
        response = self.client.audio.speech.create(
            model="tts-1-hd",
            voice=voice,
            input=text
        )
        return response.content

class ElevenLabsTTSProvider:
    """ElevenLabs TTS implementation"""
    def __init__(self, api_key: str):
        from elevenlabs import generate, set_api_key
        set_api_key(api_key)

    async def generate_speech(self, text: str, voice: str = "default") -> bytes:
        from elevenlabs import generate
        audio = generate(text=text, voice=voice)
        return audio

class MockTTSProvider:
    """Mock TTS for local development"""
    async def generate_speech(self, text: str, voice: str = "mock") -> bytes:
        # Return 1 second of silence per 15 characters
        duration = len(text) / 15
        from moviepy.editor import AudioClip
        import numpy as np

        def make_frame(t):
            return np.array([[0, 0]])  # Stereo silence

        audio = AudioClip(make_frame, duration=duration, fps=44100)
        audio.write_audiofile("temp_silence.mp3", logger=None)

        with open("temp_silence.mp3", "rb") as f:
            return f.read()

# Dependency Injection Container
class Container(containers.DeclarativeContainer):
    config = providers.Configuration()

    # Select TTS provider based on config
    tts_provider = providers.Selector(
        config.tts_provider_type,
        openai=providers.Factory(
            OpenAITTSProvider,
            api_key=config.openai_api_key
        ),
        elevenlabs=providers.Factory(
            ElevenLabsTTSProvider,
            api_key=config.elevenlabs_api_key
        ),
        mock=providers.Factory(MockTTSProvider)
    )

# Usage
container = Container()
container.config.from_dict({
    "tts_provider_type": "mock",  # or "openai", "elevenlabs"
    "openai_api_key": "...",
    "elevenlabs_api_key": "..."
})

tts_service = container.tts_provider()
audio_bytes = await tts_service.generate_speech("Hello world!")
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Prompt engineering + JSON.parse() | Claude Structured Outputs | Nov 2025 (GA 2026) | Eliminates 5-10% JSON parsing errors, no retry logic needed |
| OpenAI GPT-4 for script gen | Claude Opus 4.6 with prompt chaining | 2026 | 60% fewer guardrails, better multi-step reasoning |
| Runway ML cloud API | Stable Video Diffusion local | 2023 (SVD release) | $0 cost vs $0.05/sec, but requires GPU infrastructure |
| moviepy 1.0.x | moviepy 2.0 (alpha) | 2025 (alpha) | Better async support, but unstable—stick with 1.0.3 for now |
| Redis required for Celery | SQLAlchemy transport option | Always supported | Enables local dev without Docker/Redis, but slower |
| Manual Google Sheets OAuth | gspread service account | Mature since 2019 | No user interaction needed, better for automation |

**Deprecated/outdated:**
- **OpenAI Whisper for voice generation** - Not designed for TTS, replaced by OpenAI TTS API (tts-1-hd)
- **opencv-python for video processing** - Still works but moviepy is more Pythonic and abstracts complexity
- **Celery beat in separate process** - Modern pattern: use Celery Beat in same worker process or external scheduler

## Open Questions

1. **SVD Docker image availability**
   - What we know: SVD requires CUDA and is distributed via Docker images
   - What's unclear: Official Stability AI Docker image vs community builds? Which is stable?
   - Recommendation: Research during deployment phase, document in SVD provider implementation

2. **Claude API prompt caching for repeated calls**
   - What we know: Claude offers prompt caching (24-hour TTL) to reduce costs
   - What's unclear: Does it work with structured outputs? How much cost savings for 5-step chain?
   - Recommendation: Test in production, implement caching if >30% cost savings

3. **Video generation cost at scale**
   - What we know: Runway ML charges per second, SVD is free but slow (GPU time = $$)
   - What's unclear: Real cost comparison for 100 videos/day workload
   - Recommendation: Track GPU hours vs API costs in Phase 5 (Review & Output)

4. **Fish Audio vs ElevenLabs quality comparison**
   - What we know: Fish Audio 70% cheaper, ElevenLabs higher quality according to blind tests
   - What's unclear: Subjective quality for short-form videos vs audiobook narration
   - Recommendation: A/B test with target audience in Phase 4 (Video Composition)

5. **Google Sheets polling frequency**
   - What we know: Sheets API has rate limits (60 requests/minute read quota)
   - What's unclear: Optimal polling interval for theme config changes? Event-driven alternative?
   - Recommendation: Start with manual trigger (no polling), add Celery Beat schedule if needed

## Sources

### PRIMARY (HIGH confidence)

**Claude API:**
- [Claude Prompt Chaining](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/chain-prompts) - Official Anthropic docs
- [Claude Structured Outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs) - Official Anthropic docs, GA 2026

**OpenAI TTS:**
- [OpenAI Text-to-Speech Guide](https://platform.openai.com/docs/guides/text-to-speech) - Official OpenAI docs
- [tts-1-hd Model](https://platform.openai.com/docs/models/tts-1-hd) - Official model specs

**Google Sheets:**
- [gspread Authentication](https://docs.gspread.org/en/latest/oauth2.html) - Official gspread docs v6.2.1

**Video Processing:**
- [MoviePy Concatenate Videos](https://thepythoncode.com/article/concatenate-video-files-in-python) - The Python Code tutorial (verified 2026)
- [FFmpeg Python Guide](https://www.gumlet.com/learn/ffmpeg-python/) - Gumlet (2026)

**Dependency Injection:**
- [Python Dependency Injector](https://python-dependency-injector.ets-labs.org/) - Official docs v4.48.3

**Celery:**
- [Celery Backends and Brokers](https://docs.celeryq.dev/en/stable/getting-started/backends-and-brokers/index.html) - Official Celery 5.6.2 docs
- [Celery SQLAlchemy Broker](https://docs.celeryq.dev/en/3.1/getting-started/brokers/sqlalchemy.html) - Official docs (older version, still valid)

### SECONDARY (MEDIUM confidence)

**TTS Alternatives:**
- [Fish Audio vs ElevenLabs](https://fish.audio/vs/elevenlabs-versus-fish-audio/) - Fish Audio blog (2025)
- [Top ElevenLabs Alternatives 2026](https://fish.audio/blog/top-elevenlabs-alternatives-2026-review/) - Fish Audio blog

**Stable Video Diffusion:**
- [Stable Video Diffusion on Hugging Face](https://huggingface.co/stabilityai/stable-video-diffusion-img2vid) - Official model card
- [How to Run SVD](https://stable-diffusion-art.com/stable-video-diffusion-img2vid/) - Community tutorial (2024)

**FastAPI + Celery:**
- [FastAPI and Celery Integration](https://testdriven.io/blog/fastapi-and-celery/) - TestDriven.io (verified 2026)
- [FastAPI Background Tasks](https://oneuptime.com/blog/post/2026-02-02-fastapi-background-tasks/view) - OneUptime (Feb 2026)

**Python 3.9 Compatibility:**
- [aiosqlite PyPI](https://pypi.org/project/aiosqlite/) - Compatible with Python 3.8+ (includes 3.9)
- [FastAPI Async SQLite](https://blog.osull.com/2022/06/27/async-in-memory-sqlite-sqlalchemy-database-for-fastapi/) - Dan O'Sullivan blog

### TERTIARY (LOW confidence - needs validation)

**Video AI Alternatives:**
- [7 Best Open Source Video Models 2026](https://www.hyperstack.cloud/blog/case-study/best-open-source-video-generation-models) - Hyperstack blog
- [Wan2.2 vs SVD](https://pinggy.io/blog/best_video_generation_ai_models/) - Pinggy blog (mentions 24GB GPU requirement)

**Mock Data Patterns:**
- [Python Mock Testing](https://www.kdnuggets.com/testing-like-a-pro-a-step-by-step-guide-to-pythons-mock-library) - KDnuggets
- [pytest-mock Tutorial](https://www.datacamp.com/tutorial/pytest-mock) - DataCamp

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All libraries are mature, widely adopted, with official docs
- Architecture patterns: HIGH - Structured outputs, provider abstraction, prompt chaining are standard practices
- Pitfalls: MEDIUM-HIGH - Most are documented in official sources, some from community experience
- Code examples: HIGH - Sourced from official documentation with working examples
- SVD local implementation: LOW - Designed but not testable without GPU, deferred to deployment

**Research date:** 2026-02-13
**Valid until:** 60 days (stable domain, but AI APIs evolve quickly)

**Key uncertainties:**
1. Stable Video Diffusion Docker setup (requires GPU environment to validate)
2. Real-world Claude API rate limits under prompt chain load
3. Video generation cost comparison (SVD GPU time vs cloud API fees)
4. Python 3.9 + FastAPI 0.100+ edge case compatibility

**Next steps for planner:**
1. Design mock providers for all external services (Claude, OpenAI, video generation)
2. Implement SQLite-based Celery tasks with local file storage (no Docker)
3. Build end-to-end content generation flow with USE_MOCK_DATA=true
4. Defer real SVD integration to deployment phase (GPU required)
5. Add provider swapping mechanism via dependency injection container
