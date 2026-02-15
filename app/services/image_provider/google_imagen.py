"""Google Imagen provider for AI-powered image generation via google-genai SDK."""

import os
from uuid import uuid4
from typing import List, Optional

from google import genai
from google.genai import types
from PIL import Image as PILImage
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import get_settings
from app.services.image_provider.base import ImageProvider
from app.services.image_provider.mock import MockImageProvider


class GoogleImagenProvider(ImageProvider):
    """Google Imagen 4 image generation via google-genai SDK.

    Imagen 4 is Google's premium text-to-image model with photorealistic quality.
    """

    def __init__(self, api_key: str, output_dir: str):
        """Initialize Imagen provider.

        Args:
            api_key: Google API key for authentication
            output_dir: Base directory for output files
        """
        self.api_key = api_key
        self.output_dir = output_dir
        self.images_dir = os.path.join(output_dir, "images")
        os.makedirs(self.images_dir, exist_ok=True)

        self.client = genai.Client(api_key=api_key)
        self.model_name = "imagen-4.0-fast-generate-001"

        # Fallback to mock provider when not configured
        self._mock_provider = None

    @property
    def mock_provider(self) -> MockImageProvider:
        """Lazy initialization of mock provider for fallback."""
        if self._mock_provider is None:
            self._mock_provider = MockImageProvider(output_dir=self.output_dir)
        return self._mock_provider

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=4, max=30))
    def _generate_with_retry(self, prompt: str, num_images: int, aspect_ratio: str):
        """Generate images with retry logic."""
        config = types.GenerateImagesConfig(
            number_of_images=num_images,
            aspect_ratio=aspect_ratio,
            output_mime_type="image/png",
        )

        return self.client.models.generate_images(
            model=self.model_name,
            prompt=prompt,
            config=config,
        )

    def generate_image(
        self,
        prompt: str,
        width: int = 1024,
        height: int = 1024,
        num_images: int = 1,
        reference_images: Optional[List[str]] = None
    ) -> List[str]:
        """Generate images using Imagen 4 via Google AI API.

        Falls back to mock provider if USE_MOCK_DATA is True or api_key is empty.

        Args:
            prompt: Text description of the image to generate
            width: Image width in pixels
            height: Image height in pixels
            num_images: Number of images to generate
            reference_images: Optional list of reference image paths (not used by Imagen 4 basic)

        Returns:
            List of paths to generated PNG files
        """
        settings = get_settings()

        # Fallback to mock if configured or no API key
        if settings.use_mock_data or not self.api_key:
            return self.mock_provider.generate_image(
                prompt=prompt,
                width=width,
                height=height,
                num_images=num_images,
                reference_images=reference_images
            )

        # Derive aspect ratio from width/height
        if height > width:
            aspect_ratio = "9:16"
        elif width > height:
            aspect_ratio = "16:9"
        else:
            aspect_ratio = "1:1"

        try:
            response = self._generate_with_retry(
                prompt=prompt,
                num_images=num_images,
                aspect_ratio=aspect_ratio,
            )

            # Save generated images
            output_paths = []
            for img in response.generated_images:
                filename = f"imagen_{uuid4().hex[:8]}.png"
                output_path = os.path.join(self.images_dir, filename)
                img.image.save(output_path)
                output_paths.append(output_path)

            print(f"Imagen generated {len(output_paths)} image(s) "
                  f"(aspect_ratio={aspect_ratio}, ~${0.04 * num_images:.3f})")

            return output_paths

        except Exception as e:
            print(f"Imagen generation failed: {e}, falling back to mock")
            return self.mock_provider.generate_image(
                prompt=prompt,
                width=width,
                height=height,
                num_images=num_images,
                reference_images=reference_images
            )

    def supports_resolution(self, width: int, height: int) -> bool:
        """Check if Imagen provider supports the given resolution."""
        return (512 <= width <= 2048) and (512 <= height <= 2048)
