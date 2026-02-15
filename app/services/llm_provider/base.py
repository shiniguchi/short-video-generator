"""Abstract base class for LLM providers."""

from abc import ABC, abstractmethod
from typing import Type, Optional
from pydantic import BaseModel


class LLMProvider(ABC):
    """Abstract interface for LLM generation providers."""

    @abstractmethod
    def generate_structured(
        self,
        prompt: str,
        schema: Type[BaseModel],
        system_prompt: Optional[str] = None,
        temperature: float = 1.0
    ) -> BaseModel:
        """Generate structured output matching Pydantic schema.

        Args:
            prompt: User prompt for generation
            schema: Pydantic model class defining output structure
            system_prompt: Optional system instructions
            temperature: Randomness (0.0-2.0), higher = more creative

        Returns:
            Instance of schema with generated data
        """
        pass

    @abstractmethod
    def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 1.0,
        max_tokens: int = 4096
    ) -> str:
        """Generate freeform text output.

        Args:
            prompt: User prompt for generation
            system_prompt: Optional system instructions
            temperature: Randomness (0.0-2.0)
            max_tokens: Maximum response length

        Returns:
            Generated text
        """
        pass
