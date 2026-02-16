"""
Theme configuration reader service.

Reads theme and content reference data from local YAML config file
with Pydantic validation.
"""
from pydantic import BaseModel
from typing import List, Optional
import yaml
from pathlib import Path

from app.config import get_settings

# Allowed base directory for config files (resolved at import time)
_CONFIG_BASE_DIR = Path("config").resolve()


def _validate_config_path(path: str) -> Path:
    """Ensure the config path resolves within the allowed config directory.

    Raises:
        ValueError: If path escapes the allowed config directory.
    """
    resolved = Path(path).resolve()
    if not resolved.is_relative_to(_CONFIG_BASE_DIR):
        raise ValueError(
            f"Config path must be inside '{_CONFIG_BASE_DIR}'. "
            f"Got: '{resolved}'"
        )
    return resolved


class ThemeConfig(BaseModel):
    """Theme configuration from sample-data.yml config section."""
    theme: str
    target_platform: str
    video_duration_seconds: int
    style: str
    auto_post: bool = False
    product_name: Optional[str] = None
    tagline: Optional[str] = None
    target_audience: Optional[str] = None
    tone: Optional[str] = None


class ContentReference(BaseModel):
    """Content reference (product/topic) from sample-data.yml."""
    ref_id: str
    type: str
    title: str
    description: str
    media_url: Optional[str] = None
    talking_points: List[str]


def read_theme_config(config_path: Optional[str] = None) -> ThemeConfig:
    """
    Read theme configuration from YAML file.

    Args:
        config_path: Path to config YAML. If None, uses settings.local_config_path

    Returns:
        Validated ThemeConfig instance

    Raises:
        FileNotFoundError: If config file doesn't exist
        ValueError: If config section missing or invalid
    """
    settings = get_settings()
    path = config_path or settings.local_config_path

    config_file = _validate_config_path(path)
    if not config_file.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with open(config_file, 'r') as f:
        data = yaml.safe_load(f)

    if 'config' not in data:
        raise ValueError(f"Missing 'config' key in {path}")

    return ThemeConfig(**data['config'])


def read_content_references(config_path: Optional[str] = None) -> List[ContentReference]:
    """
    Read content references from YAML file.

    Args:
        config_path: Path to config YAML. If None, uses settings.local_config_path

    Returns:
        List of validated ContentReference instances

    Raises:
        FileNotFoundError: If config file doesn't exist
        ValueError: If content_references section missing or invalid
    """
    settings = get_settings()
    path = config_path or settings.local_config_path

    config_file = _validate_config_path(path)
    if not config_file.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with open(config_file, 'r') as f:
        data = yaml.safe_load(f)

    if 'content_references' not in data:
        raise ValueError(f"Missing 'content_references' key in {path}")

    return [ContentReference(**ref) for ref in data['content_references']]
