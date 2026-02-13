import json
import logging
from pathlib import Path
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

MOCK_DATA_DIR = Path(__file__).parent / "mock_data"


def load_mock_data(filename: str) -> List[Dict[str, Any]]:
    """Load mock data from JSON fixture file."""
    filepath = MOCK_DATA_DIR / filename
    with open(filepath, "r") as f:
        data = json.load(f)
    logger.info(f"Loaded {len(data)} items from mock data: {filename}")
    return data
