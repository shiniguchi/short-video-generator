"""Mock LLM provider for local development."""

import logging
from typing import Type, Optional, List
from pydantic import BaseModel

from app.services.llm_provider.base import LLMProvider

logger = logging.getLogger(__name__)


class MockLLMProvider(LLMProvider):
    """Generates mock structured data for testing without API calls."""

    def __init__(self):
        """Initialize mock LLM provider."""
        pass

    def generate_structured(
        self,
        prompt: str,
        schema: Type[BaseModel],
        system_prompt: Optional[str] = None,
        temperature: float = 1.0
    ) -> BaseModel:
        """Generate mock structured output matching schema.

        Creates instance with default values based on field types:
        - str: empty string
        - int/float: 0
        - bool: False
        - List: empty list
        - dict: empty dict
        - Nested BaseModel: recursively create instance
        - Optional: None

        Args:
            prompt: User prompt (logged but not used)
            schema: Pydantic model class
            system_prompt: System instructions (ignored)
            temperature: Randomness (ignored)

        Returns:
            Instance of schema with mock default values
        """
        logger.info(f"MockLLMProvider: returning mock structured output for {schema.__name__}")

        # Get schema info to build defaults
        schema_dict = schema.model_json_schema()
        properties = schema_dict.get("properties", {})
        required = schema_dict.get("required", [])
        definitions = schema_dict.get("$defs", {})

        # Build defaults based on field types
        defaults = {}
        for field_name, field_info in properties.items():
            field_type = field_info.get("type")

            if field_type == "string":
                defaults[field_name] = ""
            elif field_type == "integer":
                defaults[field_name] = 0
            elif field_type == "number":
                defaults[field_name] = 0.0
            elif field_type == "boolean":
                defaults[field_name] = False
            elif field_type == "array":
                defaults[field_name] = []
            elif field_type == "object":
                # Check if this is a nested Pydantic model (has $ref)
                if "$ref" in field_info:
                    # Extract the nested model name from $ref: "#/$defs/ModelName"
                    ref_path = field_info["$ref"].split("/")[-1]
                    if ref_path in definitions:
                        # Recursively create nested model
                        # Get the actual Pydantic model from schema's model_fields
                        nested_model = schema.model_fields[field_name].annotation
                        defaults[field_name] = self.generate_structured(
                            prompt=f"Mock nested {ref_path}",
                            schema=nested_model
                        )
                    else:
                        defaults[field_name] = {}
                else:
                    defaults[field_name] = {}
            elif field_type == "null":
                defaults[field_name] = None
            else:
                # For complex types or anyOf, check for $ref (nested model)
                if "$ref" in field_info:
                    ref_path = field_info["$ref"].split("/")[-1]
                    if ref_path in definitions:
                        nested_model = schema.model_fields[field_name].annotation
                        defaults[field_name] = self.generate_structured(
                            prompt=f"Mock nested {ref_path}",
                            schema=nested_model
                        )
                    else:
                        defaults[field_name] = "" if field_name in required else None
                else:
                    # For complex types or anyOf, provide None for optional or empty string
                    if field_name in required:
                        defaults[field_name] = ""
                    else:
                        defaults[field_name] = None

        # Create and validate instance
        return schema(**defaults)

    def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 1.0,
        max_tokens: int = 4096
    ) -> str:
        """Generate mock text response.

        Args:
            prompt: User prompt
            system_prompt: System instructions (ignored)
            temperature: Randomness (ignored)
            max_tokens: Max length (ignored)

        Returns:
            Mock text response with truncated prompt
        """
        logger.info(f"MockLLMProvider: generating mock text for prompt: {prompt[:50]}...")
        return f"Mock LLM response for: {prompt[:100]}..."
