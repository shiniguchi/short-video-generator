"""Gemini LLM provider using google-genai SDK."""

import logging
from typing import Type, Optional
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential
from google import genai
from google.genai import types

from app.services.llm_provider.base import LLMProvider

logger = logging.getLogger(__name__)


class GeminiLLMProvider(LLMProvider):
    """LLM provider using Google Gemini API via google-genai SDK."""

    def __init__(self, api_key: str):
        """Initialize Gemini provider.

        Args:
            api_key: Google API key with Gemini access
        """
        self.client = genai.Client(api_key=api_key)
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
        """
        logger.info(f"GeminiLLMProvider: generating structured output for {schema.__name__}")

        response_text = self._generate_structured_with_retry(
            prompt=prompt,
            schema=schema,
            system_prompt=system_prompt,
            temperature=temperature
        )

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
        prompt: str,
        schema: Type[BaseModel],
        system_prompt: Optional[str],
        temperature: float
    ) -> str:
        """Generate structured content with retry logic."""
        try:
            # Build contents with system instruction
            full_prompt = prompt
            if system_prompt:
                full_prompt = f"{system_prompt}\n\n{prompt}"

            config = types.GenerateContentConfig(
                temperature=temperature,
                response_mime_type="application/json",
                response_schema=schema,
            )

            response = self.client.models.generate_content(
                model=self.model_name,
                contents=full_prompt,
                config=config,
            )

            return response.text

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
        """
        logger.info("GeminiLLMProvider: generating text")

        return self._generate_text_with_retry(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens
        )

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=4, max=30))
    def _generate_text_with_retry(
        self,
        prompt: str,
        system_prompt: Optional[str],
        temperature: float,
        max_tokens: int
    ) -> str:
        """Generate text content with retry logic."""
        try:
            full_prompt = prompt
            if system_prompt:
                full_prompt = f"{system_prompt}\n\n{prompt}"

            config = types.GenerateContentConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
            )

            response = self.client.models.generate_content(
                model=self.model_name,
                contents=full_prompt,
                config=config,
            )

            logger.info("GeminiLLMProvider: text generation successful")
            return response.text

        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            raise
