"""Google Imagen provider for AI-powered image generation."""

import os
from uuid import uuid4
from typing import List, Optional

try:
    import google.generativeai as genai
    from google.generativeai import ImageGenerationModel, configure
    IMAGEN_AVAILABLE = True
except ImportError:
    IMAGEN_AVAILABLE = False

from PIL import Image as PILImage
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import get_settings
from app.services.image_provider.base import ImageProvider
from app.services.image_provider.mock import MockImageProvider


class GoogleImagenProvider(ImageProvider):
    """Google Imagen 4 image generation via google-generativeai SDK.

    Imagen 4 is Google's premium text-to-image model with photorealistic quality.
    Pricing: ~$0.04 per image generation.
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

        # Configure API if available
        if IMAGEN_AVAILABLE and api_key:
            configure(api_key=api_key)

        # Fallback to mock provider when not configured
        self._mock_provider = None

    @property
    def mock_provider(self) -> MockImageProvider:
        """Lazy initialization of mock provider for fallback.

        Returns:
            MockImageProvider instance
        """
        if self._mock_provider is None:
            self._mock_provider = MockImageProvider(output_dir=self.output_dir)
        return self._mock_provider

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=4, max=30))
    def _generate_with_retry(
        self,
        model: ImageGenerationModel,
        prompt: str,
        num_images: int,
        aspect_ratio: str,
        reference_images: Optional[List[PILImage.Image]] = None
    ):
        """Generate images with retry logic.

        Args:
            model: ImageGenerationModel instance
            prompt: Text description of the image
            num_images: Number of images to generate
            aspect_ratio: Aspect ratio string (e.g., "9:16", "16:9", "1:1")
            reference_images: Optional list of PIL Image objects for style guidance

        Returns:
            Response object from generate_images call
        """
        kwargs = {
            "prompt": prompt,
            "number_of_images": num_images,
            "aspect_ratio": aspect_ratio
        }

        if reference_images:
            kwargs["reference_images"] = reference_images

        return model.generate_images(**kwargs)

    def generate_image(
        self,
        prompt: str,
        width: int = 1024,
        height: int = 1024,
        num_images: int = 1,
        reference_images: Optional[List[str]] = None
    ) -> List[str]:
        """Generate images using Imagen 4 via Google AI API.

        Falls back to mock provider if USE_MOCK_DATA is True, api_key is empty,
        or SDK is not installed.

        Args:
            prompt: Text description of the image to generate
            width: Image width in pixels
            height: Image height in pixels
            num_images: Number of images to generate
            reference_images: Optional list of reference image paths for style guidance

        Returns:
            List of paths to generated PNG files
        """
        settings = get_settings()

        # Fallback to mock if configured, no API key, or SDK not available
        if settings.use_mock_data or not self.api_key or not IMAGEN_AVAILABLE:
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
            # Initialize model
            model = ImageGenerationModel("imagen-4.0-generate-001")

            # Load reference images if provided
            reference_pil_images = None
            if reference_images:
                reference_pil_images = []
                for img_path in reference_images:
                    try:
                        img = PILImage.open(img_path)
                        reference_pil_images.append(img)
                    except Exception as e:
                        print(f"Warning: Failed to load reference image {img_path}: {e}")

            # Generate images with retry
            response = self._generate_with_retry(
                model=model,
                prompt=prompt,
                num_images=num_images,
                aspect_ratio=aspect_ratio,
                reference_images=reference_pil_images
            )

            # Save generated images
            output_paths = []
            for img in response.images:
                filename = f"imagen_{uuid4().hex[:8]}.png"
                output_path = os.path.join(self.images_dir, filename)
                img.save(output_path)
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
        """Check if Imagen provider supports the given resolution.

        Imagen supports common sizes in the 512-2048 pixel range.

        Args:
            width: Image width in pixels
            height: Image height in pixels

        Returns:
            True if both dimensions are in supported range
        """
        # Imagen supports sizes from 512 to 2048 in both dimensions
        return (512 <= width <= 2048) and (512 <= height <= 2048)
