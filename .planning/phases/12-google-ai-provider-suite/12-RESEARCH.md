# Phase 12: Google AI Provider Suite - Research

**Researched:** 2026-02-15
**Domain:** Google AI APIs (Gemini, Imagen, Veo) integration for LLM, image, and video generation
**Confidence:** MEDIUM-HIGH

## Summary

Phase 12 unifies Google's AI capabilities under a single API key architecture. The Google AI Studio ecosystem provides Gemini (LLM), Imagen (image generation), and Veo 3.1 (video generation with native audio) through a unified authentication model. This consolidation replaces three separate providers (Claude for LLM, fal.ai for video, and dedicated TTS services) with Google-native alternatives.

**Critical finding:** Python 3.9 compatibility requires using the **deprecated** `google-generativeai` package (supports Python >=3.9, EOL November 30, 2025) rather than the new `google-genai` SDK (requires Python >=3.10). The deprecated package is in maintenance-only mode with critical bug fixes only, creating technical debt. User should consider Python upgrade path or accept using deprecated SDK.

**Veo limitation:** Video generation maxes at 8 seconds per clip with automatic voice selection—no custom voice control. Built-in lip-sync works for short dialogue but degrades on complex/multi-speaker content. This partially replaces TTS but doesn't eliminate it for all use cases.

**Primary recommendation:** Implement three new provider types (LLMProvider, ImageProvider, VideoProvider extension) following existing provider abstraction pattern. Use `google-generativeai` for Python 3.9 compatibility despite deprecation. Leverage Pydantic structured outputs for Gemini (simpler than Claude's tool-use pattern). Design Veo provider with 8-second clip awareness and optional TTS fallback.

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| google-generativeai | 0.8.x | Google AI API client (Gemini, Imagen, Veo) | Python 3.9 compatible, official Google SDK (deprecated but maintained until Nov 2025) |
| httpx | latest | Async HTTP client | Already in requirements.txt, recommended for modern async API calls |
| tenacity | latest | Retry logic with exponential backoff | Already in requirements.txt, Google-recommended retry pattern |
| pydantic | >=2.0 | Schema validation and JSON serialization | Already in use, natively supported by Gemini structured output |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Pillow | >=10.0.0 | Image processing | Already in requirements.txt, needed for Imagen reference images |
| typing | stdlib | Type hints for Python 3.9 | Use `from typing import List, Optional` not `list[str]` syntax |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| google-generativeai | google-genai (new SDK) | New SDK requires Python 3.10+, incompatible with project |
| google-generativeai | google-cloud-aiplatform (Vertex AI) | Vertex AI requires GCP project setup, billing, and service account auth—overkill for API key usage |
| Gemini structured output | Gemini tool-use (function calling) | Tool-use is designed for external API invocation, not pure data extraction; structured output is simpler and purpose-built |
| Veo native audio | Keep separate TTS provider | Veo auto-generates voice without control; TTS gives voice customization but requires separate API |

**Installation:**
```bash
pip install google-generativeai httpx tenacity pydantic pillow
# httpx, tenacity, pydantic, pillow already in requirements.txt
```

## Architecture Patterns

### Recommended Project Structure
```
app/services/
├── llm_provider/              # NEW: LLM abstraction layer
│   ├── base.py                # LLMProvider ABC
│   ├── mock.py                # Mock LLM for testing
│   ├── gemini.py              # Gemini LLM implementation
│   ├── claude.py              # OPTIONAL: Keep Claude as alternative
│   └── __init__.py            # Factory function
├── image_provider/            # NEW: Image generation abstraction
│   ├── base.py                # ImageProvider ABC
│   ├── mock.py                # Mock image generator
│   ├── google_imagen.py       # Imagen implementation
│   └── __init__.py            # Factory function
├── video_generator/           # EXISTING: Extend with Veo
│   ├── base.py                # VideoProvider ABC (already exists)
│   ├── mock.py                # MockVideoProvider (already exists)
│   ├── google_veo.py          # NEW: Veo provider
│   ├── fal_kling.py           # Existing fal.ai Kling
│   ├── fal_minimax.py         # Existing fal.ai Minimax
│   └── __init__.py            # Update factory
├── script_generator.py        # REFACTOR: Use LLMProvider instead of direct Anthropic
└── trend_analyzer.py          # REFACTOR: Use LLMProvider
```

### Pattern 1: LLM Provider Abstraction (New)

**What:** Abstract base class for LLM text generation with structured outputs
**When to use:** Script generation, trend analysis, prompt engineering—any LLM task
**Example:**
```python
# app/services/llm_provider/base.py
from abc import ABC, abstractmethod
from typing import Dict, Any, Type, Optional
from pydantic import BaseModel

class LLMProvider(ABC):
    """Abstract interface for LLM providers."""

    @abstractmethod
    def generate_structured(
        self,
        prompt: str,
        schema: Type[BaseModel],
        system_prompt: Optional[str] = None,
        temperature: float = 1.0
    ) -> BaseModel:
        """Generate structured output matching Pydantic schema.

        Args:
            prompt: User prompt for generation
            schema: Pydantic model class defining output structure
            system_prompt: Optional system instructions
            temperature: Sampling temperature (0.0-2.0)

        Returns:
            Instance of schema with validated data
        """
        pass

    @abstractmethod
    def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 1.0,
        max_tokens: int = 4096
    ) -> str:
        """Generate freeform text output.

        Args:
            prompt: User prompt for generation
            system_prompt: Optional system instructions
            temperature: Sampling temperature
            max_tokens: Maximum output length

        Returns:
            Generated text string
        """
        pass
```

### Pattern 2: Gemini Structured Output (Simpler than Claude)

**What:** Use `response_mime_type` + `response_json_schema` for type-safe JSON
**When to use:** Any structured data extraction (scripts, analysis, reports)
**Example:**
```python
# app/services/llm_provider/gemini.py
from google.generativeai import GenerativeModel, configure
from pydantic import BaseModel
from typing import Type, Optional

class GeminiLLMProvider(LLMProvider):
    def __init__(self, api_key: str):
        configure(api_key=api_key)
        self.model = GenerativeModel("gemini-2.5-flash")

    def generate_structured(
        self,
        prompt: str,
        schema: Type[BaseModel],
        system_prompt: Optional[str] = None,
        temperature: float = 1.0
    ) -> BaseModel:
        """Generate structured output using Gemini's native JSON mode."""
        generation_config = {
            "temperature": temperature,
            "response_mime_type": "application/json",
            "response_json_schema": schema.model_json_schema()
        }

        full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
        response = self.model.generate_content(
            full_prompt,
            generation_config=generation_config
        )

        # Pydantic validates JSON response
        return schema.model_validate_json(response.text)
```

**Source:** [Gemini Structured Output Docs](https://ai.google.dev/gemini-api/docs/structured-output)

### Pattern 3: Image Provider Abstraction (New)

**What:** Abstract interface for text-to-image and image-to-image generation
**When to use:** Thumbnail generation, reference images for video, background assets
**Example:**
```python
# app/services/image_provider/base.py
from abc import ABC, abstractmethod
from typing import Optional, List

class ImageProvider(ABC):
    """Abstract interface for image generation providers."""

    @abstractmethod
    def generate_image(
        self,
        prompt: str,
        width: int = 1024,
        height: int = 1024,
        num_images: int = 1,
        reference_images: Optional[List[str]] = None
    ) -> List[str]:
        """Generate images from text prompt with optional reference images.

        Args:
            prompt: Text description of desired image
            width: Image width in pixels
            height: Image height in pixels
            num_images: Number of variations to generate (1-4)
            reference_images: Optional list of reference image paths for style/subject

        Returns:
            List of paths to generated image files
        """
        pass

    @abstractmethod
    def supports_resolution(self, width: int, height: int) -> bool:
        """Check if provider supports given resolution."""
        pass
```

### Pattern 4: Veo Video Provider with Native Audio

**What:** Extend VideoProvider ABC with Veo's text-to-video + image-to-video capabilities
**When to use:** Short-form video generation with built-in dialogue/sound
**Example:**
```python
# app/services/video_generator/google_veo.py
import time
from google.generativeai import GenerativeModel, configure
from app.services.video_generator.base import VideoProvider

class GoogleVeoProvider(VideoProvider):
    """Veo 3.1 video generation with native audio."""

    def __init__(self, api_key: str, output_dir: str):
        configure(api_key=api_key)
        self.model = GenerativeModel("veo-3.1-generate-preview")
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def generate_clip(
        self,
        prompt: str,
        duration_seconds: int,
        width: int = 720,
        height: int = 1280,
        reference_image: Optional[str] = None
    ) -> str:
        """Generate video clip with Veo 3.1.

        Veo auto-generates synchronized audio including dialogue,
        ambient sound, and effects based on prompt description.

        CRITICAL: duration_seconds is clamped to max 8 seconds.
        """
        # Veo limitation: max 8 seconds per generation
        duration_seconds = min(duration_seconds, 8)

        aspect_ratio = "9:16" if height > width else "16:9"
        config = {
            "aspect_ratio": aspect_ratio,
            "resolution": "1080p" if width >= 1080 else "720p",
            "duration_seconds": str(duration_seconds)
        }

        # Image-to-video if reference provided
        if reference_image:
            operation = self.model.generate_videos(
                prompt=prompt,
                image=reference_image,
                config=config
            )
        else:
            # Text-to-video
            operation = self.model.generate_videos(
                prompt=prompt,
                config=config
            )

        # Poll until complete (async operation)
        while not operation.done:
            time.sleep(10)
            operation = operation.refresh()

        video = operation.response.generated_videos[0]
        output_path = os.path.join(self.output_dir, f"veo_{uuid4().hex[:8]}.mp4")
        video.video.save(output_path)

        return output_path

    def supports_resolution(self, width: int, height: int) -> bool:
        """Veo supports 720p and 1080p in 9:16 or 16:9."""
        valid_widths = [720, 1080, 1920]
        valid_heights = [720, 1080, 1280]
        return width in valid_widths and height in valid_heights
```

**Source:** [Veo API Docs](https://ai.google.dev/gemini-api/docs/video)

### Pattern 5: Provider Factory with Config-Driven Selection

**What:** Factory functions select provider implementation based on Settings
**When to use:** Service initialization, dependency injection
**Example:**
```python
# app/services/llm_provider/__init__.py
from app.config import get_settings
from app.services.llm_provider.base import LLMProvider
from app.services.llm_provider.mock import MockLLMProvider
from app.services.llm_provider.gemini import GeminiLLMProvider

def get_llm_provider() -> LLMProvider:
    """Factory: select LLM provider based on LLM_PROVIDER_TYPE setting."""
    settings = get_settings()
    provider_type = getattr(settings, "llm_provider_type", "mock")

    if provider_type == "gemini":
        api_key = getattr(settings, "google_api_key", "")
        if not api_key and not settings.use_mock_data:
            logger.warning("No GOOGLE_API_KEY, falling back to mock")
            return MockLLMProvider()
        return GeminiLLMProvider(api_key=api_key)
    else:
        # Default to mock
        return MockLLMProvider()
```

### Anti-Patterns to Avoid

- **Direct API client usage in business logic:** Don't call `GenerativeModel` directly in `script_generator.py`—use LLMProvider abstraction for testability and swappability
- **Ignoring Veo 8-second limit:** Don't request 20-second clips—chain multiple 8-second generations or use scene splitting
- **Assuming Veo voice customization:** Veo auto-selects voices; if user needs specific voice/accent, keep TTS provider as fallback
- **Hardcoded provider selection:** Don't `import GeminiLLMProvider` directly—always use factory function for config-driven selection
- **Mixing structured output patterns:** Don't use tool-use for data extraction when structured output (JSON schema) is simpler and purpose-built

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Retry logic for rate limits | Custom sleep/retry loops | `tenacity` library with exponential backoff | Google recommends exponential backoff with jitter; tenacity handles edge cases (max retries, circuit breaking) |
| JSON schema generation | Manual dict construction | `pydantic.BaseModel.model_json_schema()` | Pydantic auto-generates JSON Schema from type hints; Gemini API accepts it natively |
| Async API polling | `while True: time.sleep()` | Built-in operation polling (Veo) or `asyncio` patterns | Veo SDK has `.refresh()` method; manual polling blocks event loop |
| Image format conversion | Custom PIL wrappers | Pillow's standard methods | Imagen accepts standard formats (PNG, JPEG); Pillow handles conversions reliably |
| API key validation | Manual key format checks | Let API client fail fast on first request | Google SDK validates keys server-side; client-side validation adds complexity |

**Key insight:** Google's SDKs are well-designed for common patterns (structured output, async operations, retries). Don't reimplement what the SDK provides—focus on abstraction layer that makes providers swappable.

## Common Pitfalls

### Pitfall 1: Python 3.9 Compatibility Trap

**What goes wrong:** Installing `google-genai` (new SDK) on Python 3.9 environment causes dependency errors. The new SDK requires Python 3.10+.

**Why it happens:** User project is pinned to Python 3.9 (system Python on macOS). Google released new unified SDK in 2025 with Python 3.10 requirement. Old SDK `google-generativeai` is deprecated (EOL Nov 30, 2025) but still works.

**How to avoid:**
- Use deprecated `google-generativeai>=0.8.0` package for Python 3.9 compatibility
- Pin version in requirements.txt: `google-generativeai>=0.8.0,<1.0`
- Document technical debt: package is maintenance-only, consider Python 3.10+ upgrade in future
- Test thoroughly—deprecated package still receives critical bug fixes until EOL

**Warning signs:**
- `pip install google-genai` fails with "Requires Python >=3.10"
- Import errors: `ModuleNotFoundError: No module named 'google.genai'`
- Version conflicts with other dependencies

**Source:** [google-generativeai PyPI](https://pypi.org/project/google-generativeai/)

### Pitfall 2: Veo 8-Second Duration Limit

**What goes wrong:** Requesting 20-second video clip from Veo fails or gets silently truncated to 8 seconds. User expects full-length clip.

**Why it happens:** Veo 3.1 has hard 8-second limit per generation. Documentation mentions this but easy to miss. Longer videos require chaining multiple clips.

**How to avoid:**
- Clamp `duration_seconds` to `min(requested, 8)` in provider implementation
- Log warning when user requests >8 seconds: "Veo clamped to 8s, consider scene splitting"
- Design scene breakdown logic to split long scenes into 4-8 second segments
- Use existing `chain_clips_to_duration()` utility (already in codebase) to stitch clips

**Warning signs:**
- Video output is shorter than `duration_target` in script
- Multiple scenes but all exactly 8 seconds (unnatural uniformity)
- API errors mentioning duration limits

**Source:** [Veo API Docs](https://ai.google.dev/gemini-api/docs/video)

### Pitfall 3: Gemini vs Claude Structured Output Confusion

**What goes wrong:** Developer tries to use Claude's tool-use pattern with Gemini, creating unnecessary complexity. Or assumes Gemini has same limitations as Claude.

**Why it happens:** Existing codebase uses Claude with tool-use for structured outputs (see `trend_analyzer.py`). Gemini has native JSON mode that's simpler.

**How to avoid:**
- Use `response_mime_type: "application/json"` + `response_json_schema` for Gemini
- Don't define "tools" or use function calling for pure data extraction
- Leverage Pydantic `model_validate_json()` for one-line deserialization
- Reserve function calling for actual external API integration needs

**Warning signs:**
- Gemini code has `tools` parameter when not calling external APIs
- Manual JSON parsing instead of Pydantic validation
- Multiple round-trip calls when single generation suffices

**Source:** [Gemini Structured Output](https://ai.google.dev/gemini-api/docs/structured-output)

### Pitfall 4: Single API Key Assumption

**What goes wrong:** Developer assumes `GOOGLE_API_KEY` works for all three services out-of-box. In reality, API key permissions may need explicit enablement in Google AI Studio.

**Why it happens:** Documentation emphasizes "single API key" but doesn't detail that new APIs need manual activation in console.

**How to avoid:**
- Test all three APIs (Gemini, Imagen, Veo) with key before deployment
- Implement graceful fallback: if Veo call fails with 403, log clear error + fall back to mock
- Add health check endpoint that validates all three provider types
- Document setup: "Enable Gemini API, Imagen API, and Veo API in Google AI Studio console"

**Warning signs:**
- 403 Forbidden errors on Imagen/Veo but Gemini works
- "API not enabled for this project" error messages
- Inconsistent behavior between API types

**Source:** [Using Gemini API Keys](https://ai.google.dev/gemini-api/docs/api-key)

### Pitfall 5: Veo Voice Control Expectations

**What goes wrong:** User expects to specify voice gender, accent, or style for Veo-generated dialogue. Veo auto-selects voices based on scene context without user control.

**Why it happens:** Coming from dedicated TTS providers (ElevenLabs, Fish Audio) with rich voice libraries. Veo's built-in audio is convenience feature, not full TTS replacement.

**How to avoid:**
- Keep TTS provider abstraction available for use cases requiring voice customization
- Use Veo audio for quick demos, generic content, or where voice doesn't matter
- Design VideoProvider with optional `tts_provider` fallback for precise voice needs
- Document limitation clearly: "Veo auto-generates voice; use TTS provider for custom voices"

**Warning signs:**
- User stories mention "brand voice consistency" or "specific accent requirements"
- Video content is character-driven with defined voice personalities
- Compliance needs (e.g., certain demographics require certain voice characteristics)

**Source:** [Veo Limitations Discussion](https://skywork.ai/blog/how-to-prompt-lip-synced-dialogue-google-veo-3/)

### Pitfall 6: Rate Limit Surprise (Free Tier)

**What goes wrong:** Free tier Gemini API hits 5 RPM limit during batch processing, causing 429 errors. Developer didn't anticipate such low limits.

**Why it happens:** Google reduced free tier quotas in December 2025. Gemini 2.5 Pro is now 5 RPM (requests per minute) and 100 RPD (requests per day). Fine for interactive use, not batch jobs.

**How to avoid:**
- Implement retry with exponential backoff using `tenacity`
- Add request pacing: sleep between API calls in batch operations
- Monitor quota usage, log warnings at 80% of daily limit
- Consider paid Tier 1 ($0 spend, 150 RPM) for production
- Design tasks to minimize API calls: batch prompts, cache results

**Warning signs:**
- HTTP 429 errors in logs
- Slow batch processing (hitting rate limits repeatedly)
- API calls during peak hours failing more than off-peak

**Source:** [Gemini API Rate Limits](https://ai.google.dev/gemini-api/docs/rate-limits)

## Code Examples

Verified patterns from official sources:

### Example 1: Gemini Structured Output with Pydantic

```python
# Source: https://ai.google.dev/gemini-api/docs/structured-output
from google.generativeai import GenerativeModel, configure
from pydantic import BaseModel, Field
from typing import List, Optional

class Scene(BaseModel):
    scene_number: int
    duration_seconds: int = Field(ge=2, le=8)  # Veo limit
    visual_prompt: str
    transition: str

class VideoScript(BaseModel):
    title: str
    scenes: List[Scene]
    total_duration: int

configure(api_key=os.getenv("GOOGLE_API_KEY"))
model = GenerativeModel("gemini-2.5-flash")

prompt = """Create a 20-second product demo video script.
Break into scenes of 4-6 seconds each with smooth transitions."""

response = model.generate_content(
    prompt,
    generation_config={
        "temperature": 0.8,
        "response_mime_type": "application/json",
        "response_json_schema": VideoScript.model_json_schema()
    }
)

# One-line validation and parsing
script = VideoScript.model_validate_json(response.text)
print(f"Generated {len(script.scenes)} scenes for '{script.title}'")
```

### Example 2: Imagen Image Generation with Reference

```python
# Source: https://ai.google.dev/gemini-api/docs/imagen
from google.generativeai import ImageGenerationModel, configure
from PIL import Image

configure(api_key=os.getenv("GOOGLE_API_KEY"))
model = ImageGenerationModel("imagen-4.0-generate-001")

# Generate thumbnail with reference style
reference_img = Image.open("brand_style.png")

response = model.generate_images(
    prompt="Modern product thumbnail, minimalist design, vibrant colors",
    number_of_images=4,
    aspect_ratio="9:16",
    reference_images=[reference_img]  # Style/composition guide
)

for i, img in enumerate(response.images):
    img.save(f"thumbnail_{i}.png")
```

### Example 3: Veo Text-to-Video with Dialogue

```python
# Source: https://ai.google.dev/gemini-api/docs/video
import time
from google.generativeai import GenerativeModel, configure

configure(api_key=os.getenv("GOOGLE_API_KEY"))
model = GenerativeModel("veo-3.1-generate-preview")

# Prompt with quoted dialogue for lip-sync
prompt = """Close-up of professional woman in modern office.
She says "Discover our latest innovation" with confident smile.
Natural lighting, shallow depth of field."""

operation = model.generate_videos(
    prompt=prompt,
    config={
        "aspect_ratio": "9:16",
        "resolution": "1080p",
        "duration_seconds": "6",  # Under 8s limit
        "negative_prompt": "cartoon, anime, low quality"
    }
)

# Poll until ready
while not operation.done:
    print("Generating video...")
    time.sleep(10)
    operation = operation.refresh()

video = operation.response.generated_videos[0]
video.video.save("demo_with_voice.mp4")
# Video includes auto-generated voice saying the dialogue
```

### Example 4: Retry Strategy with Tenacity

```python
# Source: https://docs.cloud.google.com/iam/docs/retry-strategy
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)
from google.api_core.exceptions import ResourceExhausted

@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=60),
    retry=retry_if_exception_type(ResourceExhausted),
    reraise=True
)
def generate_with_retry(model, prompt, config):
    """Retry Gemini API calls with exponential backoff on 429 errors."""
    return model.generate_content(prompt, generation_config=config)

# Usage
try:
    response = generate_with_retry(model, prompt, config)
except ResourceExhausted:
    logger.error("Rate limit exceeded after retries")
    # Fall back to mock or queue for later
```

### Example 5: LLM Provider Abstraction (Refactor Pattern)

```python
# Before: Direct Anthropic usage in script_generator.py
from anthropic import Anthropic
client = Anthropic(api_key=settings.anthropic_api_key)
response = client.messages.create(...)

# After: Provider abstraction allows Gemini or Claude
from app.services.llm_provider import get_llm_provider
from app.schemas import VideoProductionPlanCreate

llm = get_llm_provider()  # Returns Gemini or Claude based on config
plan = llm.generate_structured(
    prompt=analysis_prompt,
    schema=VideoProductionPlanCreate,
    system_prompt="You are a viral video content strategist.",
    temperature=0.8
)
# Works with both Gemini and Claude—no business logic changes
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| google-generativeai | google-genai SDK | May 2025 GA | New SDK requires Python 3.10+; project stuck on deprecated package |
| Claude tool-use for structured output | Gemini native JSON mode | Nov 2024 | Simpler API, no multi-step tool loop, same type safety |
| Separate TTS + video providers | Veo native audio | Oct 2025 (Veo 3.1) | Eliminates TTS API call for simple talking-head content |
| Multi-step LLM chains | Single structured output call | Ongoing | Gemini JSON schema + Pydantic = 1 API call vs Claude's 2-call pattern |
| Manual quota tracking | Built-in rate limit headers | 2024 | APIs return quota headers; easier to monitor usage |

**Deprecated/outdated:**
- **google-generativeai package**: EOL November 30, 2025, replaced by google-genai (Python 3.10+ only)
- **Veo 2.x**: Replaced by Veo 3.1 with better lip-sync and native audio (October 2025)
- **Imagen 2**: Replaced by Imagen 3 and 4 with improved quality and reference image support
- **Gemini 1.5 models**: Replaced by Gemini 2.5 and 3.x series with better reasoning

## Open Questions

### 1. Should we maintain Claude as LLM fallback?

**What we know:** Claude (Anthropic) is already integrated in `script_generator.py` and `trend_analyzer.py`. User wants Google-only setup but hasn't explicitly said "remove Claude."

**What's unclear:** Whether to keep Claude as alternative LLM provider or fully replace with Gemini. Claude has longer context window (200K vs Gemini 2M, both large), different reasoning style.

**Recommendation:**
- Implement LLMProvider abstraction with both Claude and Gemini providers
- Default to Gemini when `GOOGLE_API_KEY` present
- Keep Claude provider code but make it optional (if `ANTHROPIC_API_KEY` present)
- Config: `LLM_PROVIDER_TYPE=gemini|claude|mock` (default: gemini)
- LOW RISK: User can disable Claude later if Gemini proves sufficient

### 2. How to handle Veo's 8-second limit for long scenes?

**What we know:** Veo max 8 seconds per generation. User's video scripts have 20-60 second target durations with 3-7 scenes. Codebase has `chain_clips_to_duration()` utility.

**What's unclear:** Whether to auto-split scenes >8 seconds into sub-clips, or redesign scene generation to never exceed 8 seconds per scene.

**Recommendation:**
- Modify Gemini script generation prompt: "Each scene MUST be 4-8 seconds (Veo technical limit)"
- Clamp Veo provider to `min(duration, 8)` with warning log
- Use chaining for scene transitions, not for single-scene extension
- MEDIUM RISK: Scene splitting might create unnatural cuts

### 3. Imagen vs existing thumbnail/background workflow?

**What we know:** Phase 4 (video composition) generates thumbnails by extracting frames from composed video. No current image generation provider exists.

**What's unclear:** User's intent for Imagen—is it for pre-generating reference images for Veo, or for standalone thumbnail/background generation?

**Recommendation:**
- Implement ImageProvider abstraction but don't force integration in Phase 12
- Document use cases: "Imagen can generate reference images for Veo image-to-video, or standalone assets"
- Let user decide in later phase whether to replace frame extraction with AI-generated thumbnails
- LOW RISK: Adding abstraction without forced integration keeps options open

### 4. What about Google AI Studio free tier quotas for production?

**What we know:** Free tier is 5 RPM (Gemini Pro), 100 RPD. Paid Tier 1 is 150 RPM with $0 initial spend. User has Google Business account.

**What's unclear:** Whether "Business account" means Workspace (not relevant to API quotas) or GCP billing setup. Production workload not defined.

**Recommendation:**
- Implement retry/backoff for rate limits (free tier viable for MVP)
- Log quota warnings at 80% daily limit
- Document upgrade path: "Tier 1 requires payment method on file but costs $0 until usage"
- Add Settings field: `google_api_tier: str = "free"` for future quota tuning
- MEDIUM RISK: User discovers limits only at production scale

### 5. Veo voice quality vs dedicated TTS providers?

**What we know:** Veo auto-generates voice, no customization. Existing TTS providers (ElevenLabs, Fish Audio, OpenAI) offer voice libraries and fine control.

**What's unclear:** Whether Veo audio quality meets user's production standards, or if TTS fallback is essential.

**Recommendation:**
- Keep TTS provider abstraction (don't remove existing TTS code)
- VideoProvider can have optional `tts_override: bool` parameter
- Test Veo audio in review phase (Phase 5), gather feedback
- If Veo voice insufficient, pipeline can use: Veo video (no audio) + separate TTS + composition
- HIGH RISK if removed: Voice quality is subjective, hard to predict

## Sources

### Primary (HIGH confidence)

- [Google Gen AI SDK Documentation](https://googleapis.github.io/python-genai/) - Official SDK reference
- [Gemini API Libraries](https://ai.google.dev/gemini-api/docs/libraries) - SDK selection guide
- [Gemini Structured Output](https://ai.google.dev/gemini-api/docs/structured-output) - Native JSON mode with Pydantic
- [Imagen 3 Generation API](https://ai.google.dev/gemini-api/docs/imagen) - Text-to-image with reference images
- [Veo 3.1 Video Generation](https://ai.google.dev/gemini-api/docs/video) - Text-to-video, image-to-video, native audio
- [google-generativeai PyPI](https://pypi.org/project/google-generativeai/) - Python 3.9 compatibility confirmation
- [Gemini API Rate Limits](https://ai.google.dev/gemini-api/docs/rate-limits) - Free tier quotas (5 RPM, 100 RPD)
- [Google IAM Retry Strategy](https://docs.cloud.google.com/iam/docs/retry-strategy) - Exponential backoff best practices

### Secondary (MEDIUM confidence)

- [Gemini API Free Tier Guide 2026](https://blog.laozhang.ai/en/posts/gemini-api-free-tier) - Rate limit details, tier comparison
- [Veo 3.1 Announcement](https://developers.googleblog.com/introducing-veo-3-1-and-new-creative-capabilities-in-the-gemini-api/) - Native audio capabilities
- [Imagen 3 Developer Guide](https://cloud.google.com/blog/products/ai-machine-learning/a-developers-guide-to-imagen-3-on-vertex-ai) - Advanced features
- [Structured Output Comparison](https://medium.com/@rosgluk/structured-output-comparison-across-popular-llm-providers-openai-gemini-anthropic-mistral-and-1a5d42fa612a) - Gemini vs Claude vs OpenAI patterns
- [Google Veo Pricing Guide](https://costgoat.com/pricing/google-veo) - Veo 3.1 cost analysis
- [HTTPX Best Practices](https://medium.com/@sparknp1/8-httpx-asyncio-patterns-for-safer-faster-clients-f27bc82e93e6) - Async client patterns

### Tertiary (LOW confidence - needs validation)

- [Veo Lip Sync Prompting Guide](https://skywork.ai/blog/how-to-prompt-lip-synced-dialogue-google-veo-3/) - Community best practices (not official Google)
- [Google AI Studio Review 2026](https://aitoolanalysis.com/google-ai-studio-review/) - Third-party tool analysis
- Community discussions on Veo voice limitations (multiple sources, anecdotal)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Official Google SDKs documented, Python 3.9 compatibility verified via PyPI
- Architecture patterns: HIGH - Provider abstraction follows existing codebase patterns, structured output verified in official docs
- Gemini/Imagen APIs: HIGH - Official documentation with code examples, well-established
- Veo API: MEDIUM-HIGH - Official docs exist but Veo 3.1 is recent (Oct 2025), fewer production reports
- Python 3.9 workaround: MEDIUM - Using deprecated package is workable but creates technical debt
- Veo audio quality: LOW - Subjective, needs user testing; official docs don't detail voice characteristics
- Single API key behavior: MEDIUM - Docs confirm unified key but don't detail permission edge cases

**Research date:** 2026-02-15
**Valid until:** ~45 days (March 2026) - Google AI APIs evolving rapidly, Veo 3.1 still new. Python SDK deprecation clock ticking (EOL Nov 2025 for old package).

**Critical action items for planner:**
1. Add `google-generativeai>=0.8.0,<1.0` to requirements.txt with comment about Python 3.9 compatibility
2. Create three new provider abstractions (LLMProvider, ImageProvider, extend VideoProvider)
3. Test all three Google APIs with single API key to confirm unified auth works
4. Design Veo provider with 8-second awareness and clear logging
5. Refactor `script_generator.py` and `trend_analyzer.py` to use LLMProvider abstraction
6. Keep mock providers for all three types (USE_MOCK_DATA fallback)
7. Add new Settings fields: `GOOGLE_API_KEY`, `LLM_PROVIDER_TYPE`, `IMAGE_PROVIDER_TYPE`
8. Document migration path from Claude to Gemini in plan
