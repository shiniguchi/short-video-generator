"""
Thumbnail Generation

Extracts a frame from a video at a specified timestamp and saves it as a JPEG.
"""

from typing import Optional
from pathlib import Path
from moviepy import VideoFileClip
from PIL import Image


def generate_thumbnail(
    video_path: str,
    timestamp: float = 2.0,
    output_dir: Optional[str] = None,
    quality: int = 85,
) -> str:
    """
    Extract a frame from a video and save it as a JPEG thumbnail.

    Args:
        video_path: Path to source video file
        timestamp: Time in seconds to extract frame (default 2.0)
        output_dir: Directory to save thumbnail (default: video_path parent / "thumbnails")
        quality: JPEG quality 1-100 (default 85)

    Returns:
        Path to saved thumbnail file
    """
    video_path_obj = Path(video_path)

    # Determine output directory
    if output_dir is None:
        output_dir = video_path_obj.parent / "thumbnails"
    else:
        output_dir = Path(output_dir)

    # Create output directory if needed
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate thumbnail filename
    thumbnail_filename = f"{video_path_obj.stem}_thumb.jpg"
    thumbnail_path = output_dir / thumbnail_filename

    # Extract frame using VideoFileClip context manager
    with VideoFileClip(str(video_path)) as clip:
        # Ensure timestamp is within video duration
        extract_time = min(timestamp, clip.duration - 0.1)

        # Extract frame as numpy array
        frame = clip.get_frame(extract_time)

    # Convert numpy array to PIL Image
    image = Image.fromarray(frame)

    # Save as JPEG
    image.save(str(thumbnail_path), "JPEG", quality=quality)

    return str(thumbnail_path)
