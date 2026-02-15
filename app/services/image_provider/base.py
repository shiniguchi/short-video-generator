"""Abstract base class for image providers."""

from abc import ABC, abstractmethod
from typing import List, Optional


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
        """Generate images from text prompt and return file paths.

        Args:
            prompt: Text description of the image to generate
            width: Image width in pixels
            height: Image height in pixels
            num_images: Number of images to generate
            reference_images: Optional list of reference image paths for style guidance

        Returns:
            List of paths to generated image files
        """
        pass

    @abstractmethod
    def supports_resolution(self, width: int, height: int) -> bool:
        """Check if provider supports the given resolution.

        Args:
            width: Image width in pixels
            height: Image height in pixels

        Returns:
            True if resolution is supported
        """
        pass
