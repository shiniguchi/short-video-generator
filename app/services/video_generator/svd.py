"""Stable Video Diffusion provider (stub for future GPU deployment)."""

from app.services.video_generator.base import VideoProvider


class StableVideoDiffusionProvider(VideoProvider):
    """Stable Video Diffusion provider - requires GPU and Docker.

    This is a stub for future implementation. Use MockVideoProvider
    for local development without GPU.
    """

    def generate_clip(
        self,
        prompt: str,
        duration_seconds: int,
        width: int = 720,
        height: int = 1280
    ) -> str:
        """Generate video clip using SVD.

        Note:
            Not yet implemented. Requires GPU hardware and Docker setup.

        Raises:
            NotImplementedError: Always raised - use MockVideoProvider instead
        """
        raise NotImplementedError(
            "SVD requires GPU and Docker - use MockVideoProvider for local development"
        )

    def supports_resolution(self, width: int, height: int) -> bool:
        """Check if resolution is supported by SVD.

        SVD has limitations on maximum resolution (typically 1024x1024).

        Args:
            width: Video width in pixels
            height: Video height in pixels

        Returns:
            True if resolution is within SVD limits
        """
        # SVD limitation: max 1024x1024
        return width <= 1024 and height <= 1024
