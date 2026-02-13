import logging
from typing import List, Dict, Any
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def calculate_engagement_velocity(trend_dict: Dict[str, Any]) -> float:
    """
    Calculate engagement velocity for a trend.

    Formula: (likes + comments + shares) / hours_since_posted

    Args:
        trend_dict: Dictionary with likes, comments, shares, posted_at fields

    Returns:
        Engagement velocity as float (rounded to 2 decimals)
    """
    try:
        # Get engagement metrics (default to 0 if missing)
        likes = trend_dict.get('likes', 0) or 0
        comments = trend_dict.get('comments', 0) or 0
        shares = trend_dict.get('shares', 0) or 0
        total_engagement = likes + comments + shares

        # Parse posted_at timestamp
        posted_at_str = trend_dict.get('posted_at')
        if not posted_at_str:
            logger.warning("Missing posted_at, returning velocity 0.0")
            return 0.0

        # Parse ISO timestamp (handle both with and without 'Z')
        posted_at = datetime.fromisoformat(posted_at_str.replace('Z', '+00:00'))

        # Calculate hours since posted
        hours_since_posted = (datetime.now(timezone.utc) - posted_at).total_seconds() / 3600

        # Minimum threshold to prevent division by zero (6 minutes = 0.1 hours)
        hours_since_posted = max(hours_since_posted, 0.1)

        # Calculate velocity
        velocity = total_engagement / hours_since_posted

        return round(velocity, 2)

    except Exception as e:
        logger.error(f"Error calculating engagement velocity: {e}", exc_info=True)
        return 0.0


def enrich_trends_with_velocity(trends: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Calculate engagement velocity for each trend and sort by velocity.

    Args:
        trends: List of trend dictionaries

    Returns:
        List of trends with 'engagement_velocity' field added, sorted descending by velocity
    """
    # Calculate velocity for each trend
    for trend in trends:
        velocity = calculate_engagement_velocity(trend)
        trend['engagement_velocity'] = velocity

    # Sort by velocity descending
    trends_sorted = sorted(trends, key=lambda t: t.get('engagement_velocity', 0), reverse=True)

    logger.info(f"Enriched {len(trends_sorted)} trends with engagement velocity")
    return trends_sorted
