"""Google Imagen provider for AI-powered image generation via google-genai SDK."""

import logging
import os
from uuid import uuid4
from typing import List, Optional

logger = logging.getLogger(__name__)

from google import genai
from google.genai import types
from PIL import Image as PILImage
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import get_settings
from app.services.image_provider.base import ImageProvider
from app.services.image_provider.mock import MockImageProvider
from app.services.quota_tracker import record_imagen_request


def _friendly_error(exc: Exception) -> str:
    """Extract a human-readable error from Imagen API exceptions."""
    msg = str(exc)
    # Dig into RetryError -> ClientError -> JSON message
    cause = exc
    for _ in range(5):
        if hasattr(cause, '__cause__') and cause.__cause__:
            cause = cause.__cause__
        elif hasattr(cause, 'last_attempt'):
            try:
                cause = cause.last_attempt.result()
            except Exception as inner:
                cause = inner
        else:
            break
    cause_msg = str(cause)

    if "sensitive words" in cause_msg or "Responsible AI" in cause_msg:
        return "Image rejected by safety filter — try removing explicit or sensitive words from Visual Keywords"
    if "more than 2 reference images" in cause_msg:
        return "Too many reference images for vertical/horizontal format (max 2). Remove some reference photos."
    if "unavailable" in cause_msg:
        return f"Imagen model unavailable — contact support. Details: {cause_msg}"
    if "PERMISSION_DENIED" in cause_msg or "403" in cause_msg:
        return "Permission denied — check Vertex AI service account has aiplatform.user role"
    if "safety" in cause_msg.lower() or "filtered" in cause_msg.lower():
        return "Image blocked by safety filter — try adjusting your prompt or visual keywords"
    # Fallback: show the innermost error message
    return cause_msg[:200]


class GoogleImagenProvider(ImageProvider):
    """Google Imagen image generation via google-genai SDK.

    Supports two client modes:
    - Google AI (API key): text-to-image only (generate_images)
    - Vertex AI (service account): text-to-image + edit_image (subject refs, sketches)
    """

    def __init__(self, api_key: str, output_dir: str):
        self.api_key = api_key
        self.output_dir = output_dir
        self.images_dir = os.path.join(output_dir, "images")
        os.makedirs(self.images_dir, exist_ok=True)

        settings = get_settings()
        self.model_name = settings.imagen_model

        # Prefer Vertex AI (enables edit_image) — fall back to API key
        vertex_project = settings.vertex_ai_project
        vertex_location = settings.vertex_ai_location
        creds_path = settings.google_application_credentials

        if vertex_project and creds_path and os.path.exists(creds_path):
            from google.oauth2.service_account import Credentials
            credentials = Credentials.from_service_account_file(
                creds_path,
                scopes=["https://www.googleapis.com/auth/cloud-platform"],
            )
            self.client = genai.Client(
                vertexai=True,
                project=vertex_project,
                location=vertex_location,
                credentials=credentials,
            )
            self.supports_edit = True
            logger.info("Imagen: Vertex AI client (project=%s, location=%s)", vertex_project, vertex_location)
        else:
            self.client = genai.Client(api_key=api_key)
            self.supports_edit = False
            logger.info("Imagen: Google AI client (API key) — edit_image disabled")

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

        record_imagen_request()
        response = self.client.models.generate_images(
            model=self.model_name,
            prompt=prompt,
            config=config,
        )

        # Imagen may return empty results (safety filter, quota, etc.)
        if not response.generated_images:
            logger.warning("Imagen returned no images (model=%s, prompt_len=%d). Response: %s",
                           self.model_name, len(prompt), response)
            raise ValueError("Image blocked by safety filter — try adjusting Visual Keywords to remove sensitive content")

        return response

    def generate_image(
        self,
        prompt: str,
        width: int = 1024,
        height: int = 1024,
        num_images: int = 1,
        reference_images: Optional[List[str]] = None,
        subject_type: str = "product",
        subject_description: str = "the product",
        extra_refs: Optional[List[dict]] = None,
    ) -> List[str]:
        """Generate images. Uses subject refs via edit_image when Vertex AI + refs available.

        subject_description: Human-readable description of the subject for Imagen.
        extra_refs: Additional references with different subject type.
            Each dict: {"path": str, "subject_type": str, "description": str}
        """
        if not self.api_key:
            return self.mock_provider.generate_image(
                prompt=prompt, width=width, height=height,
                num_images=num_images, reference_images=reference_images
            )

        aspect_ratio = "9:16" if height > width else ("16:9" if width > height else "1:1")

        # Use edit_image with subject refs when Vertex AI is available and refs provided
        valid_refs = [p for p in (reference_images or []) if os.path.exists(p)]
        # Validate extra_refs paths
        valid_extra = [er for er in (extra_refs or []) if os.path.exists(er.get("path", ""))]

        try:
            if valid_refs and self.supports_edit:
                try:
                    response = self._edit_with_subject_refs(
                        prompt=prompt, reference_paths=valid_refs,
                        aspect_ratio=aspect_ratio,
                        subject_type=subject_type,
                        subject_description=subject_description,
                        extra_refs=valid_extra or None,
                    )
                except Exception as e:
                    logger.error("Subject-ref edit_image failed after retries: %s", e)
                    raise
            else:
                response = self._generate_with_retry(
                    prompt=prompt, num_images=num_images, aspect_ratio=aspect_ratio,
                )

            # Save generated images
            output_paths = []
            for img in response.generated_images:
                filename = f"imagen_{uuid4().hex[:8]}.png"
                output_path = os.path.join(self.images_dir, filename)
                img.image.save(output_path)
                output_paths.append(output_path)

            logger.info("Imagen generated %d image(s) (aspect_ratio=%s, ~$%.3f)",
                        len(output_paths), aspect_ratio, 0.04 * num_images)

            return output_paths

        except Exception as e:
            logger.error("Imagen generation failed: %s: %s", type(e).__name__, e)
            raise RuntimeError(_friendly_error(e)) from e

    # Map string subject_type to SDK enum
    _SUBJECT_TYPE_MAP = {
        "product": types.SubjectReferenceType.SUBJECT_TYPE_PRODUCT,
        "person": types.SubjectReferenceType.SUBJECT_TYPE_PERSON,
        "animal": types.SubjectReferenceType.SUBJECT_TYPE_ANIMAL,
        "default": types.SubjectReferenceType.SUBJECT_TYPE_DEFAULT,
    }

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=4, max=30))
    def _edit_with_subject_refs(self, prompt: str, reference_paths: List[str],
                                 aspect_ratio: str, subject_description: str = "the product",
                                 subject_type: str = "product",
                                 extra_refs: Optional[List[dict]] = None):
        """Subject-referenced image generation via Imagen edit_image API.

        Uses SubjectReferenceImage to preserve the subject's appearance.
        subject_type: "product", "person", "animal", or "default".
        extra_refs: Additional refs with different subject type.
            Each dict: {"path": str, "subject_type": str, "description": str}
        """
        settings = get_settings()
        edit_model = settings.imagen_edit_model

        # Non-square aspect ratios: max 2 reference images total
        max_refs = 2 if aspect_ratio != "1:1" else 4

        st = self._SUBJECT_TYPE_MAP.get(
            subject_type, types.SubjectReferenceType.SUBJECT_TYPE_PRODUCT
        )
        refs = []
        # Primary references (reference_id=1)
        for path in reference_paths[:max_refs]:
            refs.append(types.SubjectReferenceImage(
                reference_id=1,
                reference_image=types.Image.from_file(location=path),
                config=types.SubjectReferenceConfig(
                    subject_type=st,
                    subject_description=subject_description,
                ),
            ))

        # Extra references with different subject type (reference_id=2)
        if extra_refs:
            remaining = max_refs - len(refs)
            for er in extra_refs[:remaining]:
                er_st = self._SUBJECT_TYPE_MAP.get(
                    er.get("subject_type", "product"),
                    types.SubjectReferenceType.SUBJECT_TYPE_PRODUCT,
                )
                refs.append(types.SubjectReferenceImage(
                    reference_id=2,
                    reference_image=types.Image.from_file(location=er["path"]),
                    config=types.SubjectReferenceConfig(
                        subject_type=er_st,
                        subject_description=er.get("description", "the product"),
                    ),
                ))

        if len(refs) > max_refs:
            logger.warning("Imagen subject-ref: truncating %d refs to %d", len(refs), max_refs)
            refs = refs[:max_refs]

        config = types.EditImageConfig(
            edit_mode=types.EditMode.EDIT_MODE_DEFAULT,
            number_of_images=1,
            aspect_ratio=aspect_ratio,
            output_mime_type="image/png",
        )

        record_imagen_request()
        response = self.client.models.edit_image(
            model=edit_model,
            prompt=prompt,
            reference_images=refs,
            config=config,
        )

        if not response.generated_images:
            logger.warning("Imagen subject-ref returned no images (model=%s). Response: %s", edit_model, response)
            raise ValueError("Image blocked by safety filter — try adjusting Visual Keywords to remove sensitive content")

        return response

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=4, max=30))
    def _edit_with_sketch(self, prompt: str, sketch_path: str, aspect_ratio: str):
        """Sketch-guided image generation via Imagen edit_image API."""
        settings = get_settings()
        edit_model = settings.imagen_edit_model

        sketch_ref = types.ControlReferenceImage(
            reference_id=1,
            reference_image=types.Image.from_file(location=sketch_path),
            config=types.ControlReferenceConfig(
                control_type=types.ControlReferenceType.CONTROL_TYPE_SCRIBBLE
            ),
        )

        config = types.EditImageConfig(
            edit_mode=types.EditMode.EDIT_MODE_CONTROLLED_EDITING,
            number_of_images=1,
            aspect_ratio=aspect_ratio,
            output_mime_type="image/png",
        )

        record_imagen_request()
        response = self.client.models.edit_image(
            model=edit_model,
            prompt=prompt,
            reference_images=[sketch_ref],
            config=config,
        )

        if not response.generated_images:
            logger.warning("Imagen sketch returned no images (model=%s). Response: %s", edit_model, response)
            raise ValueError("Image blocked by safety filter — try adjusting Visual Keywords to remove sensitive content")

        return response

    def generate_with_references(
        self,
        prompt: str,
        reference_images: List[str],
        subject_description: str = "the product",
        width: int = 720,
        height: int = 1280,
    ) -> List[str]:
        """Generate image using product photos as subject references.

        Uses Imagen's edit_image API with SubjectReferenceImage to preserve
        the product's appearance in the generated composition.
        """
        if not self.api_key:
            return self.mock_provider.generate_image(prompt=prompt, width=width, height=height)

        aspect_ratio = "9:16" if height > width else ("16:9" if width > height else "1:1")

        try:
            response = self._edit_with_subject_refs(
                prompt=prompt,
                reference_paths=reference_images,
                aspect_ratio=aspect_ratio,
                subject_description=subject_description,
            )

            output_paths = []
            for img in response.generated_images:
                filename = f"imagen_ref_{uuid4().hex[:8]}.png"
                output_path = os.path.join(self.images_dir, filename)
                img.image.save(output_path)
                output_paths.append(output_path)

            logger.info("Imagen subject-ref: generated %d image(s)", len(output_paths))
            return output_paths

        except Exception as e:
            logger.error("Subject-ref generation failed: %s: %s", type(e).__name__, e)
            raise RuntimeError(_friendly_error(e)) from e

    def generate_from_sketch(
        self,
        prompt: str,
        sketch_path: str,
        width: int = 720,
        height: int = 1280,
    ) -> List[str]:
        """Generate image guided by a hand-drawn sketch.

        Uses Imagen's controlled editing API with scribble reference.
        """
        if not self.api_key:
            return self.mock_provider.generate_image(prompt=prompt, width=width, height=height)

        aspect_ratio = "9:16" if height > width else ("16:9" if width > height else "1:1")

        try:
            response = self._edit_with_sketch(
                prompt=prompt,
                sketch_path=sketch_path,
                aspect_ratio=aspect_ratio,
            )

            output_paths = []
            for img in response.generated_images:
                filename = f"imagen_sketch_{uuid4().hex[:8]}.png"
                output_path = os.path.join(self.images_dir, filename)
                img.image.save(output_path)
                output_paths.append(output_path)

            logger.info("Imagen sketch-guided: generated %d image(s)", len(output_paths))
            return output_paths

        except Exception as e:
            logger.error("Sketch-guided generation failed: %s: %s", type(e).__name__, e)
            raise RuntimeError(_friendly_error(e)) from e

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=4, max=30))
    def _edit_with_refs_and_sketch(self, prompt: str, reference_paths: List[str],
                                    sketch_path: str, aspect_ratio: str,
                                    subject_description: str = "the product"):
        """Combined subject reference + sketch control via Imagen edit_image API."""
        settings = get_settings()
        edit_model = settings.imagen_edit_model

        # Non-square: max 2 total refs (1 subject + 1 sketch). Square: max 3 + 1 sketch.
        max_subject = 1 if aspect_ratio != "1:1" else 3
        if len(reference_paths) > max_subject:
            logger.warning("Imagen refs+sketch: truncating %d refs to %d (aspect_ratio=%s)",
                           len(reference_paths), max_subject, aspect_ratio)
        refs = []
        for path in reference_paths[:max_subject]:
            refs.append(types.SubjectReferenceImage(
                reference_id=1,
                reference_image=types.Image.from_file(location=path),
                config=types.SubjectReferenceConfig(
                    subject_type=types.SubjectReferenceType.SUBJECT_TYPE_PRODUCT,
                    subject_description=subject_description,
                ),
            ))

        # Sketch control — reference_id=2
        refs.append(types.ControlReferenceImage(
            reference_id=2,
            reference_image=types.Image.from_file(location=sketch_path),
            config=types.ControlReferenceConfig(
                control_type=types.ControlReferenceType.CONTROL_TYPE_SCRIBBLE
            ),
        ))

        config = types.EditImageConfig(
            edit_mode=types.EditMode.EDIT_MODE_DEFAULT,
            number_of_images=1,
            aspect_ratio=aspect_ratio,
            output_mime_type="image/png",
        )

        record_imagen_request()
        response = self.client.models.edit_image(
            model=edit_model,
            prompt=prompt,
            reference_images=refs,
            config=config,
        )

        if not response.generated_images:
            logger.warning("Imagen refs+sketch returned no images (model=%s). Response: %s", edit_model, response)
            raise ValueError("Image blocked by safety filter — try adjusting Visual Keywords to remove sensitive content")

        return response

    def generate_with_refs_and_sketch(
        self,
        prompt: str,
        reference_images: List[str],
        sketch_path: str,
        subject_description: str = "the product",
        width: int = 720,
        height: int = 1280,
    ) -> List[str]:
        """Generate image combining product subject refs + sketch composition control."""
        if not self.api_key:
            return self.mock_provider.generate_image(prompt=prompt, width=width, height=height)

        aspect_ratio = "9:16" if height > width else ("16:9" if width > height else "1:1")

        try:
            response = self._edit_with_refs_and_sketch(
                prompt=prompt,
                reference_paths=reference_images,
                sketch_path=sketch_path,
                aspect_ratio=aspect_ratio,
                subject_description=subject_description,
            )

            output_paths = []
            for img in response.generated_images:
                filename = f"imagen_combo_{uuid4().hex[:8]}.png"
                output_path = os.path.join(self.images_dir, filename)
                img.image.save(output_path)
                output_paths.append(output_path)

            logger.info("Imagen refs+sketch: generated %d image(s)", len(output_paths))
            return output_paths

        except Exception as e:
            logger.error("Refs+sketch generation failed: %s: %s", type(e).__name__, e)
            raise RuntimeError(_friendly_error(e)) from e

    def supports_resolution(self, width: int, height: int) -> bool:
        """Check if Imagen provider supports the given resolution."""
        return (512 <= width <= 2048) and (512 <= height <= 2048)
