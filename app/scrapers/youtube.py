import logging
from typing import List, Dict, Any
from datetime import datetime, timedelta, timezone
import isodate
from googleapiclient.discovery import build
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.config import get_settings
from app.scrapers.base import load_mock_data

logger = logging.getLogger(__name__)


def scrape_youtube_shorts(limit: int = 50) -> List[Dict[str, Any]]:
    """
    Scrape trending YouTube Shorts.

    Mock mode: Returns mock data from youtube_shorts.json
    Real mode: Uses YouTube Data API v3 to search and fetch shorts

    Args:
        limit: Number of shorts to return

    Returns:
        List of trend dicts matching TrendCreate schema
    """
    settings = get_settings()

    if settings.use_mock_data:
        logger.info(f"Using mock data for YouTube Shorts (limit={limit})")
        return _get_mock_youtube_shorts(limit)
    else:
        logger.info(f"Scraping real YouTube Shorts via Data API (limit={limit})")
        return _scrape_youtube_api(limit)


def _get_mock_youtube_shorts(limit: int) -> List[Dict[str, Any]]:
    """Load and cycle through mock data to reach desired limit."""
    mock_data = load_mock_data("youtube_shorts.json")

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

    logger.info(f"Generated {len(result)} YouTube Shorts from {len(mock_data)} mock entries")
    return result


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=4, max=60),
    retry=retry_if_exception_type(Exception),
)
def _scrape_youtube_api(limit: int) -> List[Dict[str, Any]]:
    """
    Scrape YouTube Shorts using YouTube Data API v3.

    Process:
    1. Search for short videos (videoDuration='short')
    2. Fetch detailed info for found videos
    3. Filter to actual shorts (< 60 seconds)
    4. Normalize to internal format
    """
    settings = get_settings()

    if not settings.youtube_api_key:
        logger.error("YouTube API key not configured")
        return []

    try:
        youtube = build('youtube', 'v3', developerKey=settings.youtube_api_key)

        # Step 1: Search for short videos from the last 7 days
        seven_days_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()

        search_request = youtube.search().list(
            part='id',
            type='video',
            videoDuration='short',
            order='viewCount',
            publishedAfter=seven_days_ago,
            maxResults=min(limit, 50)  # API max is 50
        )
        search_response = search_request.execute()

        video_ids = [item['id']['videoId'] for item in search_response.get('items', [])]

        if not video_ids:
            logger.warning("No videos found in YouTube search")
            return []

        logger.info(f"Found {len(video_ids)} video IDs from search")

        # Step 2: Fetch detailed info for videos
        videos_request = youtube.videos().list(
            part='snippet,statistics,contentDetails',
            id=','.join(video_ids),
            fields='items(id,snippet(title,description,tags,thumbnails,channelTitle,channelId,publishedAt),statistics(viewCount,likeCount,commentCount),contentDetails(duration))'
        )
        videos_response = videos_request.execute()

        # Step 3: Parse and filter to actual shorts (< 60 seconds)
        shorts = []
        for video in videos_response.get('items', []):
            try:
                duration_iso = video['contentDetails']['duration']
                duration_seconds = int(isodate.parse_duration(duration_iso).total_seconds())

                # Filter to actual Shorts (< 60 seconds)
                if duration_seconds >= 60:
                    continue

                # Normalize to internal format
                snippet = video['snippet']
                stats = video.get('statistics', {})

                trend = {
                    "external_id": video['id'],
                    "title": snippet.get('title', ''),
                    "description": snippet.get('description', ''),
                    "hashtags": snippet.get('tags', []),
                    "views": int(stats.get('viewCount', 0)),
                    "likes": int(stats.get('likeCount', 0)),
                    "comments": int(stats.get('commentCount', 0)),
                    "shares": 0,  # YouTube API doesn't expose share count
                    "duration": duration_seconds,
                    "creator": snippet.get('channelTitle', ''),
                    "creator_id": snippet.get('channelId', ''),
                    "sound_name": "",  # YouTube doesn't attribute sounds like TikTok
                    "video_url": f"https://www.youtube.com/shorts/{video['id']}",
                    "thumbnail_url": snippet.get('thumbnails', {}).get('high', {}).get('url', ''),
                    "posted_at": snippet.get('publishedAt', ''),
                }
                shorts.append(trend)

            except Exception as e:
                logger.warning(f"Failed to parse YouTube video: {e}")
                continue

        if len(shorts) < limit:
            logger.warning(f"Only found {len(shorts)} shorts after filtering (requested {limit})")

        logger.info(f"Scraped {len(shorts)} YouTube Shorts from API")
        return shorts

    except Exception as e:
        logger.error(f"Error scraping YouTube via API: {e}", exc_info=True)
        return []
