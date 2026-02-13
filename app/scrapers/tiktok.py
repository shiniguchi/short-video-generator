import logging
import time
from typing import List, Dict, Any
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.config import get_settings
from app.scrapers.base import load_mock_data

logger = logging.getLogger(__name__)


def scrape_tiktok_trends(limit: int = 50) -> List[Dict[str, Any]]:
    """
    Scrape trending TikTok videos.

    Mock mode: Returns mock data from tiktok_trending.json
    Real mode: Uses Apify API to scrape trending videos

    Args:
        limit: Number of trends to return

    Returns:
        List of trend dicts matching TrendCreate schema
    """
    settings = get_settings()

    if settings.use_mock_data:
        logger.info(f"Using mock data for TikTok trends (limit={limit})")
        return _get_mock_tiktok_trends(limit)
    else:
        logger.info(f"Scraping real TikTok trends via Apify (limit={limit})")
        return _scrape_tiktok_apify(limit)


def _get_mock_tiktok_trends(limit: int) -> List[Dict[str, Any]]:
    """Load and cycle through mock data to reach desired limit."""
    mock_data = load_mock_data("tiktok_trending.json")

    if len(mock_data) >= limit:
        return mock_data[:limit]

    # Cycle through mock data to reach limit
    result = []
    cycle_count = 0
    while len(result) < limit:
        for item in mock_data:
            if len(result) >= limit:
                break
            # Make a copy and modify external_id to ensure uniqueness
            trend = item.copy()
            if cycle_count > 0:
                trend["external_id"] = f"{item['external_id']}_dup_{cycle_count}"
            result.append(trend)
        cycle_count += 1

    logger.info(f"Generated {len(result)} TikTok trends from {len(mock_data)} mock entries")
    return result


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=4, max=60),
    retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.ConnectError)),
)
def _scrape_tiktok_apify(limit: int) -> List[Dict[str, Any]]:
    """
    Scrape TikTok using Apify REST API.

    Uses the lexis-solutions~tiktok-trending-videos-scraper actor.
    """
    settings = get_settings()

    if not settings.apify_api_token:
        logger.error("Apify API token not configured")
        return []

    try:
        with httpx.Client(timeout=300.0) as client:
            # Step 1: Start the actor run
            logger.info("Starting Apify actor run...")
            start_response = client.post(
                "https://api.apify.com/v2/acts/lexis-solutions~tiktok-trending-videos-scraper/runs",
                headers={"Authorization": f"Bearer {settings.apify_api_token}"},
                json={"maxResults": limit}
            )
            start_response.raise_for_status()
            run_data = start_response.json()
            run_id = run_data["data"]["id"]
            logger.info(f"Actor run started: {run_id}")

            # Step 2: Poll run status until completed
            max_wait_time = 300  # 5 minutes
            start_time = time.time()
            while time.time() - start_time < max_wait_time:
                time.sleep(10)  # Poll every 10 seconds

                status_response = client.get(
                    f"https://api.apify.com/v2/actor-runs/{run_id}",
                    headers={"Authorization": f"Bearer {settings.apify_api_token}"}
                )
                status_response.raise_for_status()
                status_data = status_response.json()
                status = status_data["data"]["status"]

                logger.info(f"Actor run status: {status}")

                if status == "SUCCEEDED":
                    dataset_id = status_data["data"]["defaultDatasetId"]
                    logger.info(f"Actor run completed. Dataset ID: {dataset_id}")

                    # Step 3: Fetch results
                    results_response = client.get(
                        f"https://api.apify.com/v2/datasets/{dataset_id}/items",
                        headers={"Authorization": f"Bearer {settings.apify_api_token}"}
                    )
                    results_response.raise_for_status()
                    items = results_response.json()

                    # Step 4: Normalize to internal format
                    normalized = _normalize_apify_results(items)
                    logger.info(f"Scraped {len(normalized)} TikTok trends from Apify")
                    return normalized

                elif status in ("FAILED", "ABORTED", "TIMED-OUT"):
                    logger.error(f"Actor run failed with status: {status}")
                    return []

            logger.error("Actor run timed out after 5 minutes")
            return []

    except Exception as e:
        logger.error(f"Error scraping TikTok via Apify: {e}", exc_info=True)
        return []


def _normalize_apify_results(items: List[Dict]) -> List[Dict[str, Any]]:
    """
    Normalize Apify API response to internal TrendCreate format.

    Apify response fields -> Internal fields mapping:
    - id -> external_id
    - text -> title
    - createTime -> posted_at
    - authorMeta.name -> creator
    - authorMeta.id -> creator_id
    - musicMeta.musicName -> sound_name
    - videoMeta.duration -> duration
    - diggCount -> likes
    - shareCount -> shares
    - playCount -> views
    - commentCount -> comments
    """
    normalized = []

    for item in items:
        try:
            trend = {
                "external_id": str(item.get("id", "")),
                "title": item.get("text", ""),
                "description": item.get("text", ""),  # TikTok doesn't separate description
                "hashtags": [tag.get("name", "") for tag in item.get("hashtags", [])],
                "views": item.get("playCount", 0),
                "likes": item.get("diggCount", 0),
                "comments": item.get("commentCount", 0),
                "shares": item.get("shareCount", 0),
                "duration": item.get("videoMeta", {}).get("duration", 0),
                "creator": item.get("authorMeta", {}).get("name", ""),
                "creator_id": str(item.get("authorMeta", {}).get("id", "")),
                "sound_name": item.get("musicMeta", {}).get("musicName", ""),
                "video_url": item.get("videoUrl", ""),
                "thumbnail_url": item.get("covers", {}).get("default", ""),
                "posted_at": item.get("createTime", ""),
            }
            normalized.append(trend)
        except Exception as e:
            logger.warning(f"Failed to normalize TikTok item: {e}")
            continue

    return normalized
