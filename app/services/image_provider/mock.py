"""Mock image provider for local development."""

import os
import hashlib
from uuid import uuid4
from typing import List, Optional, Tuple

from PIL import Image as PILImage

from app.services.image_provider.base import ImageProvider


class MockImageProvider(ImageProvider):
    """Generates solid-color placeholder images for testing."""

    # Color palette for variety (RGB tuples)
    COLORS = [
        (52, 152, 219),   # Blue
        (46, 204, 113),   # Green
        (155, 89, 182),   # Purple
        (241, 196, 15),   # Yellow
        (230, 126, 34),   # Orange
        (231, 76, 60),    # Red
        (26, 188, 156),   # Turquoise
        (149, 165, 166),  # Gray
    ]

    def __init__(self, output_dir: str):
        """Initialize mock provider.

        Args:
            output_dir: Base directory for output files
        """
        self.output_dir = output_dir
        self.images_dir = os.path.join(output_dir, "images")
        os.makedirs(self.images_dir, exist_ok=True)

    def generate_image(
        self,
        prompt: str,
        width: int = 1024,
        height: int = 1024,
        num_images: int = 1,
        reference_images: Optional[List[str]] = None
    ) -> List[str]:
        """Generate solid-color mock images.

        Args:
            prompt: Text description (used to pick color via hash)
            width: Image width in pixels
            height: Image height in pixels
            num_images: Number of images to generate
            reference_images: Ignored by mock provider

        Returns:
            List of paths to generated PNG files
        """
        # Pick color based on prompt hash for consistency
        color = self._pick_color(prompt)

        # Generate images
        output_paths = []
        for _ in range(num_images):
            # Generate unique filename
            filename = f"mock_{uuid4().hex[:8]}.png"
            output_path = os.path.join(self.images_dir, filename)

            # Create solid color image
            img = PILImage.new("RGB", (width, height), color)
            img.save(output_path)

            output_paths.append(output_path)

        return output_paths

    def supports_resolution(self, width: int, height: int) -> bool:
        """Mock provider supports any resolution.

        Args:
            width: Image width in pixels
            height: Image height in pixels

        Returns:
            Always True for mock provider
        """
        return True

    def _pick_color(self, prompt: str) -> Tuple[int, int, int]:
        """Pick a color from palette based on prompt hash.

        Args:
            prompt: Text to hash

        Returns:
            RGB color tuple
        """
        hash_value = int(hashlib.md5(prompt.encode()).hexdigest(), 16)
        color_index = hash_value % len(self.COLORS)
        return self.COLORS[color_index]
