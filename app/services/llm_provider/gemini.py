"""Gemini LLM provider using google-generativeai SDK."""

import logging
from typing import Type, Optional
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential
import google.generativeai as genai
from google.api_core import exceptions as google_exceptions

from app.services.llm_provider.base import LLMProvider

logger = logging.getLogger(__name__)


class GeminiLLMProvider(LLMProvider):
    """LLM provider using Google Gemini API."""

    def __init__(self, api_key: str):
        """Initialize Gemini provider.

        Args:
            api_key: Google API key with Gemini access
        """
        genai.configure(api_key=api_key)
        self.model_name = "gemini-2.5-flash"
        logger.info(f"GeminiLLMProvider initialized with model: {self.model_name}")

    def generate_structured(
        self,
        prompt: str,
        schema: Type[BaseModel],
        system_prompt: Optional[str] = None,
        temperature: float = 1.0
    ) -> BaseModel:
        """Generate structured output using Gemini's native JSON mode.

        Args:
            prompt: User prompt for generation
            schema: Pydantic model class defining output structure
            system_prompt: Optional system instructions
            temperature: Randomness (0.0-2.0)

        Returns:
            Instance of schema with generated data

        Raises:
            google.api_core.exceptions.ResourceExhausted: Rate limit hit
            Exception: API errors
        """
        logger.info(f"GeminiLLMProvider: generating structured output for {schema.__name__}")

        # Build full prompt
        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"

        # Call API with retry
        response_text = self._generate_structured_with_retry(
            full_prompt=full_prompt,
            schema=schema,
            temperature=temperature
        )

        # Parse and validate response
        try:
            result = schema.model_validate_json(response_text)
            logger.info(f"GeminiLLMProvider: successfully generated {schema.__name__}")
            return result
        except Exception as e:
            logger.error(f"Failed to parse Gemini response as {schema.__name__}: {e}")
            logger.error(f"Response text: {response_text[:500]}")
            raise

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=4, max=30))
    def _generate_structured_with_retry(
        self,
        full_prompt: str,
        schema: Type[BaseModel],
        temperature: float
    ) -> str:
        """Generate structured content with retry logic.

        Args:
            full_prompt: Complete prompt with system instructions
            schema: Pydantic model class
            temperature: Randomness setting

        Returns:
            Raw JSON response text

        Raises:
            google.api_core.exceptions.ResourceExhausted: Rate limit (retried)
            Exception: Other API errors (retried)
        """
        try:
            # Create fresh model instance for each call
            model = genai.GenerativeModel(self.model_name)

            # Configure JSON mode with schema
            generation_config = {
                "temperature": temperature,
                "response_mime_type": "application/json",
                "response_schema": schema.model_json_schema()
            }

            # Generate content
            response = model.generate_content(
                full_prompt,
                generation_config=generation_config
            )

            return response.text

        except google_exceptions.ResourceExhausted as e:
            logger.warning(f"Gemini rate limit hit, retrying: {e}")
            raise
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            raise

    def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 1.0,
        max_tokens: int = 4096
    ) -> str:
        """Generate freeform text using Gemini.

        Args:
            prompt: User prompt for generation
            system_prompt: Optional system instructions
            temperature: Randomness (0.0-2.0)
            max_tokens: Maximum response length

        Returns:
            Generated text

        Raises:
            google.api_core.exceptions.ResourceExhausted: Rate limit hit
            Exception: API errors
        """
        logger.info("GeminiLLMProvider: generating text")

        # Build full prompt
        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"

        # Call API with retry
        return self._generate_text_with_retry(
            full_prompt=full_prompt,
            temperature=temperature,
            max_tokens=max_tokens
        )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=4, max=30))
    def _generate_text_with_retry(
        self,
        full_prompt: str,
        temperature: float,
        max_tokens: int
    ) -> str:
        """Generate text content with retry logic.

        Args:
            full_prompt: Complete prompt with system instructions
            temperature: Randomness setting
            max_tokens: Maximum output length

        Returns:
            Generated text

        Raises:
            google.api_core.exceptions.ResourceExhausted: Rate limit (retried)
            Exception: Other API errors (retried)
        """
        try:
            # Create fresh model instance
            model = genai.GenerativeModel(self.model_name)

            # Configure generation
            generation_config = {
                "temperature": temperature,
                "max_output_tokens": max_tokens
            }

            # Generate content
            response = model.generate_content(
                full_prompt,
                generation_config=generation_config
            )

            logger.info("GeminiLLMProvider: text generation successful")
            return response.text

        except google_exceptions.ResourceExhausted as e:
            logger.warning(f"Gemini rate limit hit, retrying: {e}")
            raise
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            raise
