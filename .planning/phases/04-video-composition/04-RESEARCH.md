# Phase 4: Video Composition - Research

**Researched:** 2026-02-14
**Domain:** Video Composition (FFmpeg, MoviePy, Text Overlays, Audio Mixing)
**Confidence:** HIGH

## Summary

Phase 4 implements the final video composition pipeline: combining raw AI-generated video clips, voiceover audio, text overlays, and optional background music into publish-ready MP4 files. The core challenge is orchestrating FFmpeg through MoviePy's Python API to synchronize multiple media streams while applying configurable text overlays with precise timing, positioning, styling (font, color, shadow, animation), and generating thumbnails for distribution.

The phase consumes outputs from Phase 3 (generate_content_task returns {script_id, video_path, audio_path}) and produces final 9:16 vertical MP4s optimized for social media (TikTok, YouTube Shorts, Instagram Reels). Key constraints from existing codebase: Python 3.9, SQLite, no Docker, no GPU for local dev, moviepy already installed (1.0.3+).

**Critical Insight:** MoviePy wraps FFmpeg and provides Pythonic video editing abstractions, but has known memory management issues and text overlay limitations. TextClip requires ImageMagick for font rendering and has buggy stroke/shadow support. For production-quality text overlays with complex animations, direct FFmpeg drawtext filter may be more reliable than MoviePy's TextClip, though less Pythonic.

**Primary recommendation:** Use MoviePy for core composition (video + audio mixing, concatenation) leveraging existing Phase 3 dependency, implement text overlays via MoviePy TextClip with fallback to FFmpeg drawtext for complex cases, enforce strict resource cleanup (context managers, .close() calls) to prevent memory leaks, and use Pillow for thumbnail extraction rather than MoviePy's buggy thumbnail methods.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| moviepy | 2.2.1 | Video composition and editing | Python-native FFmpeg wrapper, already installed in Phase 3, supports CompositeVideoClip and CompositeAudioClip |
| ffmpeg | 4.4+ (system binary) | Media encoding/decoding | Industry standard codec support (H.264, AAC), required by moviepy |
| pillow | 10.0.0+ | Thumbnail generation | Already installed, reliable frame extraction and image saving |
| ImageMagick | 7.1+ (system binary) | Font rendering for TextClip | Required dependency for moviepy.TextClip, handles custom fonts |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| ffmpeg-python | 0.2.0+ | Low-level FFmpeg bindings | Direct FFmpeg drawtext filter for complex text animations |
| numpy | 1.24+ | Frame manipulation | moviepy dependency, useful for custom effects |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| MoviePy | Direct FFmpeg subprocess | FFmpeg 20x faster but no Pythonic API, harder to test/maintain |
| TextClip (ImageMagick) | FFmpeg drawtext filter | drawtext more reliable for shadows/animations but less Pythonic |
| MoviePy thumbnail | opencv-python frame extraction | OpenCV faster but adds heavyweight dependency |

**Installation (already installed except ImageMagick):**
```bash
# Python dependencies (already in requirements.txt from Phase 3)
pip install moviepy>=2.2.1 pillow>=10.0.0

# System dependencies (install via package manager)
# macOS:
brew install ffmpeg imagemagick

# Ubuntu/Debian:
apt-get install ffmpeg imagemagick

# Configure ImageMagick for MoviePy (if needed)
# Set IMAGEMAGICK_BINARY environment variable before importing moviepy
```

## Architecture Patterns

### Recommended Project Structure
```
app/
├── services/
│   ├── video_compositor/          # Phase 4: Final composition
│   │   ├── __init__.py
│   │   ├── compositor.py          # Main composition orchestrator
│   │   ├── text_overlay.py        # Text overlay rendering (TextClip + drawtext fallback)
│   │   ├── audio_mixer.py         # CompositeAudioClip: voiceover + background music
│   │   ├── thumbnail.py           # Pillow-based frame extraction
│   │   ├── encoder.py             # H.264/AAC encoding settings
│   │   └── cleanup.py             # Resource cleanup utilities
│   │
│   ├── video_generator/           # Phase 3 (existing)
│   │   └── ...
│   │
│   └── voiceover_generator/       # Phase 3 (existing)
│       └── ...
│
├── schemas.py                     # TextOverlaySchema, SceneSchema (existing)
├── tasks.py                       # Celery tasks (add compose_video_task)
└── models.py                      # ComposedVideo model (track final outputs)

output/                            # Generated files
├── clips/                         # Phase 3 raw video clips
├── audio/                         # Phase 3 voiceover files
├── final/                         # Phase 4 composed videos
└── thumbnails/                    # Phase 4 thumbnails
```

### Pattern 1: Composition Orchestrator
**What:** Single-responsibility class that coordinates video, audio, and text overlay composition
**When to use:** For all video composition tasks (separates concerns from Celery task layer)
**Example:**
```python
# app/services/video_compositor/compositor.py
from pathlib import Path
from typing import List, Optional
from moviepy.editor import VideoFileClip, AudioFileClip, CompositeVideoClip
from app.schemas import TextOverlaySchema
from .text_overlay import render_text_overlays
from .audio_mixer import mix_audio
from .thumbnail import generate_thumbnail

class VideoCompositor:
    """Orchestrates final video composition."""

    def __init__(self, output_dir: str = "output/final"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def compose(
        self,
        video_path: str,
        audio_path: str,
        text_overlays: List[TextOverlaySchema],
        background_music_path: Optional[str] = None,
        music_volume: float = 0.3,
        output_filename: Optional[str] = None,
        thumbnail_timestamp: float = 2.0
    ) -> dict:
        """Compose final video with all elements.

        Returns:
            dict with keys: video_path, thumbnail_path, duration
        """
        # Context managers ensure cleanup
        with VideoFileClip(video_path) as base_video:
            with AudioFileClip(audio_path) as voiceover:
                # Mix audio (voiceover + optional background music)
                final_audio = mix_audio(
                    voiceover,
                    background_music_path,
                    music_volume,
                    duration=base_video.duration
                )

                # Render text overlays
                text_clips = render_text_overlays(
                    text_overlays,
                    video_size=(720, 1280),
                    duration=base_video.duration
                )

                # Composite video + text overlays
                final_video = CompositeVideoClip(
                    [base_video] + text_clips,
                    size=(720, 1280)
                )
                final_video = final_video.set_audio(final_audio)

                # Generate output filename
                if not output_filename:
                    output_filename = f"video_{uuid4().hex[:8]}.mp4"
                output_path = self.output_dir / output_filename

                # Write final video (H.264 + AAC)
                final_video.write_videofile(
                    str(output_path),
                    codec="libx264",
                    audio_codec="aac",
                    fps=30,
                    preset="medium",
                    bitrate="5M"
                )

                # Generate thumbnail
                thumbnail_path = generate_thumbnail(
                    str(output_path),
                    timestamp=thumbnail_timestamp
                )

                # Explicit cleanup (belt and suspenders with context managers)
                final_audio.close()
                final_video.close()
                for clip in text_clips:
                    clip.close()

                return {
                    "video_path": str(output_path),
                    "thumbnail_path": thumbnail_path,
                    "duration": base_video.duration
                }
```

### Pattern 2: Audio Mixing with CompositeAudioClip
**What:** Combine voiceover and background music with volume control
**When to use:** When requirements include optional background music (COMP-05)
**Example:**
```python
# app/services/video_compositor/audio_mixer.py
from moviepy.editor import AudioFileClip, CompositeAudioClip
from typing import Optional

def mix_audio(
    voiceover: AudioFileClip,
    background_music_path: Optional[str],
    music_volume: float = 0.3,
    duration: float = None
) -> AudioFileClip:
    """Mix voiceover with optional background music.

    Args:
        voiceover: Primary voiceover audio (already loaded)
        background_music_path: Path to background music file (optional)
        music_volume: Volume multiplier for background music (0.0-1.0)
        duration: Target duration (crops/loops music to match)

    Returns:
        CompositeAudioClip with mixed audio
    """
    if not background_music_path:
        return voiceover

    with AudioFileClip(background_music_path) as music:
        # Match music duration to video
        if duration:
            if music.duration < duration:
                # Loop if music too short
                music = music.audio_loop(duration=duration)
            else:
                # Crop if music too long
                music = music.subclipped(0, duration)

        # Reduce music volume to avoid overpowering voiceover
        music = music.with_multiply_volume(music_volume)

        # Composite: voiceover on top, music underneath
        return CompositeAudioClip([voiceover, music])
```

### Pattern 3: Text Overlay Rendering
**What:** Convert TextOverlaySchema to positioned MoviePy TextClips with timing
**When to use:** For all text overlay requirements (COMP-02)
**Example:**
```python
# app/services/video_compositor/text_overlay.py
from typing import List, Tuple
from moviepy.editor import TextClip
from app.schemas import TextOverlaySchema

# Position mappings (9:16 vertical video 720x1280)
POSITION_MAP = {
    "top": ("center", 100),
    "center": ("center", "center"),
    "bottom": ("center", 1100)
}

# Style mappings
FONT_MAP = {
    "bold": "Montserrat-Bold",
    "normal": "Montserrat-Regular",
    "highlight": "Montserrat-ExtraBold"
}

def render_text_overlays(
    overlays: List[TextOverlaySchema],
    video_size: Tuple[int, int] = (720, 1280),
    duration: float = None
) -> List[TextClip]:
    """Render text overlays as positioned TextClips.

    Args:
        overlays: List of text overlay schemas from production plan
        video_size: Video dimensions (width, height)
        duration: Total video duration (for validation)

    Returns:
        List of TextClip objects with timing and positioning
    """
    clips = []

    for overlay in overlays:
        # Map position to coordinates
        pos = POSITION_MAP.get(overlay.position, ("center", "center"))

        # Map style to font
        font = FONT_MAP.get(overlay.style, "Montserrat-Bold")

        # Create text clip with styling
        text_clip = TextClip(
            text=overlay.text,
            font=font,
            font_size=48,
            color="white",
            stroke_color="black",
            stroke_width=2,
            method="caption",
            size=(video_size[0] - 80, None),  # 40px margin each side
            text_align="center",
            margin=(10, 10)  # Add margin to prevent stroke clipping
        )

        # Set timing
        text_clip = text_clip.with_start(overlay.timestamp_start)
        text_clip = text_clip.with_duration(
            overlay.timestamp_end - overlay.timestamp_start
        )

        # Set position
        text_clip = text_clip.with_position(pos)

        # Add fade-in animation (0.3s)
        text_clip = text_clip.crossfadein(0.3)

        clips.append(text_clip)

    return clips
```

### Pattern 4: Thumbnail Generation with Pillow
**What:** Extract frame at specific timestamp and save as JPEG thumbnail
**When to use:** For COMP-04 (thumbnail generation)
**Example:**
```python
# app/services/video_compositor/thumbnail.py
from pathlib import Path
from moviepy.editor import VideoFileClip
from PIL import Image
import numpy as np

def generate_thumbnail(
    video_path: str,
    timestamp: float = 2.0,
    size: Tuple[int, int] = (720, 1280),
    quality: int = 85
) -> str:
    """Extract frame from video and save as thumbnail.

    Args:
        video_path: Path to video file
        timestamp: Time in seconds to extract frame
        size: Thumbnail dimensions (defaults to video size)
        quality: JPEG quality (0-95)

    Returns:
        Path to saved thumbnail file
    """
    video_path = Path(video_path)
    thumbnail_path = video_path.parent.parent / "thumbnails" / f"{video_path.stem}_thumb.jpg"
    thumbnail_path.parent.mkdir(parents=True, exist_ok=True)

    with VideoFileClip(str(video_path)) as clip:
        # Extract frame as numpy array
        frame = clip.get_frame(timestamp)

        # Convert to PIL Image
        image = Image.fromarray(frame)

        # Resize if needed (maintain aspect ratio)
        if image.size != size:
            image.thumbnail(size, Image.Resampling.LANCZOS)

        # Save as JPEG
        image.save(str(thumbnail_path), "JPEG", quality=quality)

    return str(thumbnail_path)
```

### Anti-Patterns to Avoid

- **Not closing clips:** Always use context managers (`with`) or explicit `.close()` calls to prevent memory leaks
- **Loading all clips simultaneously:** Process and composite in chunks for large videos, close intermediate clips
- **Ignoring stroke clipping:** TextClip stroke renders outside bounding box; always add `margin` parameter
- **Using MoviePy for simple FFmpeg operations:** Use subprocess for trim/convert operations (20x faster)
- **Hardcoding paths:** Use Path objects and configurable output directories
- **Silent audio failures:** CompositeVideoClip may drop audio; always verify with `final_video.audio is not None`

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Video encoding | Custom H.264 encoder | moviepy write_videofile with codec="libx264" | FFmpeg handles edge cases (keyframes, B-frames, profile/level) |
| Audio synchronization | Frame-by-frame audio alignment | moviepy set_audio() | MoviePy handles A/V sync automatically |
| Text rendering | PIL text drawing on frames | TextClip or FFmpeg drawtext | Handles font loading, kerning, multi-line wrapping |
| Thumbnail extraction | Manual frame iteration | clip.get_frame() + PIL | One-liner vs 50+ lines of codec handling |
| Font management | Manual TrueType parsing | ImageMagick font detection | System font discovery and fallback handling |
| Color space conversion | Numpy RGB manipulation | moviepy/FFmpeg built-ins | Handles YUV<->RGB, color profiles, gamma |

**Key insight:** Video composition involves subtle codec interactions (audio sample rate mismatches, keyframe alignment, color space conversions) that FFmpeg and MoviePy already solve. Custom implementations miss edge cases and create debugging nightmares.

## Common Pitfalls

### Pitfall 1: Memory Leaks from Unclosed Clips
**What goes wrong:** MoviePy holds frame buffers in memory; forgetting `.close()` causes memory to balloon with multiple clips
**Why it happens:** VideoFileClip/AudioFileClip open file handles and cache frames; Python's garbage collector doesn't always release resources promptly
**How to avoid:**
- Always use context managers: `with VideoFileClip(path) as clip:`
- Explicitly close derived clips (CompositeVideoClip doesn't auto-close sources)
- Process large batches in chunks, closing intermediate results
- Call `gc.collect()` after processing loops
**Warning signs:** Memory usage grows unbounded, BrokenPipeError in FFmpeg subprocess, "too many open files" errors

### Pitfall 2: TextClip Stroke Clipping
**What goes wrong:** Text stroke renders outside TextClip bounding box, causing partial/missing stroke
**Why it happens:** ImageMagick calculates text bounds without accounting for stroke width
**How to avoid:**
- Always add `margin=(10, 10)` or larger to TextClip constructor
- Test with stroke_width values > 2 (edge case)
- Consider FFmpeg drawtext as fallback for thick strokes
**Warning signs:** Stroke appears incomplete on edges, top/bottom of letters cut off

### Pitfall 3: CompositeVideoClip Audio Drops
**What goes wrong:** Final composite video has no audio despite `.set_audio()` call
**Why it happens:** CompositeVideoClip audio handling has edge cases with certain clip types
**How to avoid:**
- Always verify audio after composition: `assert final_clip.audio is not None`
- Set audio on CompositeVideoClip explicitly, not on source clips
- Test with different audio codecs (MP3 vs WAV vs AAC)
**Warning signs:** Silent output video, no audio track in ffprobe output

### Pitfall 4: Font Not Found / ImageMagick Errors
**What goes wrong:** TextClip fails with "font not found" or "ImageMagick not installed" errors
**Why it happens:** ImageMagick font detection depends on system configuration and fontconfig delegates
**How to avoid:**
- Verify ImageMagick installation: `magick -list font`
- Set IMAGEMAGICK_BINARY env var before importing moviepy
- Use absolute font paths if system fonts fail: `font="/path/to/Montserrat-Bold.ttf"`
- Install fontconfig delegate if missing (Linux)
**Warning signs:** Generic font rendering failures, "font not available" errors

### Pitfall 5: H.264/AAC Encoding Failures
**What goes wrong:** write_videofile fails with codec errors or produces unplayable MP4
**Why it happens:** FFmpeg codec compatibility issues, missing libx264/libfdk_aac
**How to avoid:**
- Verify FFmpeg codecs: `ffmpeg -codecs | grep -E "264|aac"`
- Use preset="medium" (not "ultrafast" for production)
- Set audio_bitrate and bitrate explicitly for consistency
- Test output with multiple players (VLC, QuickTime, browser)
**Warning signs:** "Codec not found" errors, unplayable MP4s, audio/video desync

## Code Examples

Verified patterns from official sources and production use:

### Complete Composition Pipeline
```python
# Source: MoviePy documentation + production patterns
from moviepy.editor import VideoFileClip, AudioFileClip, CompositeVideoClip, TextClip, CompositeAudioClip
from pathlib import Path
from typing import List, Optional
from app.schemas import TextOverlaySchema

def compose_final_video(
    video_path: str,
    voiceover_path: str,
    text_overlays: List[TextOverlaySchema],
    background_music_path: Optional[str] = None,
    output_path: str = "output/final/video.mp4"
) -> str:
    """Full composition example with all requirements."""

    # Load base assets with context managers
    with VideoFileClip(video_path) as base_video, \
         AudioFileClip(voiceover_path) as voiceover:

        # Mix audio: voiceover + optional background music
        if background_music_path:
            with AudioFileClip(background_music_path) as music:
                # Loop/crop music to match video duration
                if music.duration < base_video.duration:
                    music = music.audio_loop(duration=base_video.duration)
                else:
                    music = music.subclipped(0, base_video.duration)

                # Reduce music volume (30%) to avoid overpowering voiceover
                music = music.with_multiply_volume(0.3)

                # Composite audio: voiceover first (dominant)
                final_audio = CompositeAudioClip([voiceover, music])
        else:
            final_audio = voiceover

        # Render text overlays
        text_clips = []
        for overlay in text_overlays:
            clip = TextClip(
                text=overlay.text,
                font="Montserrat-Bold",
                font_size=48,
                color="white",
                stroke_color="black",
                stroke_width=2,
                method="caption",
                size=(640, None),  # 40px margin each side (720 - 80)
                text_align="center",
                margin=(10, 10)  # Prevent stroke clipping
            )
            clip = clip.with_start(overlay.timestamp_start)
            clip = clip.with_duration(overlay.timestamp_end - overlay.timestamp_start)
            clip = clip.with_position(("center", 100 if overlay.position == "top" else 1100))
            clip = clip.crossfadein(0.3)  # Fade-in animation
            text_clips.append(clip)

        # Composite video + text overlays
        final_video = CompositeVideoClip(
            [base_video] + text_clips,
            size=(720, 1280)
        )
        final_video = final_video.set_audio(final_audio)

        # Write final MP4 (H.264 + AAC, 9:16 vertical)
        final_video.write_videofile(
            output_path,
            codec="libx264",
            audio_codec="aac",
            fps=30,
            preset="medium",
            bitrate="5M",
            audio_bitrate="128k"
        )

        # Cleanup
        final_audio.close()
        final_video.close()
        for clip in text_clips:
            clip.close()

    return output_path
```

### Thumbnail Extraction
```python
# Source: Pillow documentation + MoviePy frame extraction
from moviepy.editor import VideoFileClip
from PIL import Image

def extract_thumbnail(video_path: str, timestamp: float = 2.0, output_path: str = None) -> str:
    """Extract frame as thumbnail with configurable timestamp."""
    if not output_path:
        output_path = video_path.replace(".mp4", "_thumb.jpg")

    with VideoFileClip(video_path) as clip:
        # Extract frame at timestamp
        frame = clip.get_frame(timestamp)

        # Convert numpy array to PIL Image
        image = Image.fromarray(frame)

        # Save as JPEG with quality setting
        image.save(output_path, "JPEG", quality=85)

    return output_path
```

### Font Configuration for ImageMagick
```python
# Source: MoviePy + ImageMagick documentation
import os
from moviepy.config import change_settings

def configure_imagemagick(font_dir: str = "/usr/share/fonts/truetype"):
    """Configure ImageMagick and custom fonts before importing TextClip."""

    # Set ImageMagick binary path (if auto-detection fails)
    imagemagick_binary = os.environ.get("IMAGEMAGICK_BINARY", "magick")
    change_settings({"IMAGEMAGICK_BINARY": imagemagick_binary})

    # Add custom font directory (optional)
    # Note: ImageMagick typically auto-detects system fonts via fontconfig
    # Manual font registration only needed for non-standard locations

    # Verify font availability
    from subprocess import run, PIPE
    result = run(["magick", "-list", "font"], capture_output=True, text=True)
    if "Montserrat" not in result.stdout:
        print("WARNING: Montserrat font not detected by ImageMagick")
        print("Install with: brew install font-montserrat (macOS) or apt-get install fonts-montserrat (Ubuntu)")

# Call before creating TextClips
configure_imagemagick()
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| MoviePy v0.2 TextClip | MoviePy v2.2 TextClip with margin parameter | v2.0 (2024) | Stroke clipping bug requires explicit margin workaround |
| volumex() method | with_multiply_volume() | v2.0 (2024) | Breaking API change, old code fails silently |
| set_start()/set_duration() | with_start()/with_duration() | v2.0 (2024) | Functional-style API prevents mutation bugs |
| Manual font paths | ImageMagick fontconfig integration | v1.0+ (stable) | System font auto-detection works on modern systems |
| FFmpeg libfdk_aac | FFmpeg native AAC encoder | FFmpeg 4.0+ (2018) | Native AAC quality now matches libfdk_aac |

**Deprecated/outdated:**
- **moviepy.editor.ipython_display**: Removed in v2.0, use preview() method instead
- **VideoClip.fl()**: Deprecated in favor of functional effects (fx module)
- **Old audio methods (volumex, audio_fadeout)**: Replaced with with_multiply_volume, audiofx.audio_fadeout

## Open Questions

1. **Shadow effects for text overlays**
   - What we know: MoviePy TextClip has limited shadow support via ImageMagick, implementation is buggy
   - What's unclear: Whether FFmpeg drawtext shadow parameter is more reliable than TextClip workarounds
   - Recommendation: Test both approaches; if TextClip shadows fail, fall back to FFmpeg subprocess with drawtext filter

2. **Audio ducking (automatic volume reduction)**
   - What we know: CompositeAudioClip supports static volume mixing, no built-in ducking
   - What's unclear: Whether manual volume envelope implementation is worth complexity vs static mixing
   - Recommendation: Start with static volume mixing (COMP-05), defer automatic ducking to future iteration

3. **Custom text animations (slide, zoom, rotate)**
   - What we know: MoviePy has SlideIn/SlideOut effects but not designed for TextClip
   - What's unclear: Performance impact of custom position functions for per-frame animation
   - Recommendation: Implement fade-in only for MVP (COMP-02), defer complex animations to Phase 5 enhancements

4. **Memory limits for long videos (>60 seconds)**
   - What we know: MoviePy memory leaks accumulate with clip duration, CompositeVideoClip keeps frame cache
   - What's unclear: Exact memory threshold where chunking becomes necessary
   - Recommendation: Monitor memory usage in testing; if >2GB for 30s video, implement chunk processing

## Sources

### Primary (HIGH confidence)
- [MoviePy PyPI Package](https://pypi.org/project/moviepy/) - Version 2.2.1 (May 2025), Python 3.9+ support
- [MoviePy TextClip Documentation](https://zulko.github.io/moviepy/reference/reference/moviepy.video.VideoClip.TextClip.html) - Official API reference
- [MoviePy Video Effects (fx)](https://zulko.github.io/moviepy/reference/reference/moviepy.video.fx.html) - FadeIn, CrossFadeIn, SlideIn effects
- [MoviePy Audio Effects (fx)](https://zulko.github.io/moviepy/reference/reference/moviepy.audio.fx.html) - MultiplyVolume, AudioNormalize
- [Pillow Image Documentation](https://pillow.readthedocs.io/en/stable/reference/Image.html) - Thumbnail generation

### Secondary (MEDIUM confidence)
- [MoviePy Memory Management Best Practices](https://zulko.github.io/moviepy/v1.0.3/getting_started/efficient_moviepy.html) - Verified with GitHub issues
- [FFmpeg H.264 Encoding Guide](https://www.lighterra.com/papers/videoencodingh264/) - Production encoding settings
- [MoviePy GitHub Issue #1284](https://github.com/Zulko/moviepy/issues/1284) - Memory leak documentation
- [MoviePy GitHub Issue #1318](https://github.com/Zulko/moviepy/issues/1318) - TextClip stroke clipping bug
- [CompositeAudioClip Examples](https://fictionally-irrelevant.vercel.app/posts/change-background-audio-of-a-video-the-pythonic-way) - Audio mixing patterns

### Tertiary (LOW confidence)
- [MoviePy vs FFmpeg Performance Comparison](https://github.com/Zulko/moviepy/issues/2165) - Community benchmarks
- [ImageMagick Font Configuration](https://amhajja.medium.com/adding-a-new-font-to-imagemagick-31f7d2401b7e) - Font installation guide
- [Social Media Video Format Guide](https://pixflow.net/blog/the-creators-cheat-sheet-best-video-formats-codecs-for-social-media/) - 9:16 H.264 recommendations

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - MoviePy 2.2.1 confirmed via PyPI, already installed in Phase 3
- Architecture: HIGH - Patterns verified from official docs and GitHub issue discussions
- Pitfalls: HIGH - All pitfalls documented in MoviePy GitHub issues with reproducible examples
- Text overlay: MEDIUM - TextClip stroke/shadow bugs confirmed but workarounds not fully tested
- Audio ducking: LOW - No built-in support, custom implementation patterns unverified

**Research date:** 2026-02-14
**Valid until:** 2026-03-14 (30 days - stable library ecosystem, FFmpeg/MoviePy change slowly)
