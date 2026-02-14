import logging
from typing import List, Dict, Any
from sqlalchemy.exc import SQLAlchemyError

from app.database import get_task_session_factory
from app.config import get_settings
from app.models import Trend
from app.schemas import TrendCreate
from app.scrapers.tiktok import scrape_tiktok_trends
from app.scrapers.youtube import scrape_youtube_shorts
from app.services.engagement import enrich_trends_with_velocity

logger = logging.getLogger(__name__)


async def save_trends(trends: List[Dict[str, Any]], platform: str) -> int:
    """
    Save trends to database with UPSERT on (platform, external_id).

    Args:
        trends: List of trend dictionaries
        platform: Platform name (tiktok, youtube)

    Returns:
        Number of trends saved/updated
    """
    if not trends:
        logger.warning(f"No trends to save for platform: {platform}")
        return 0

    saved_count = 0

    try:
        async with get_task_session_factory()() as session:
            for trend_dict in trends:
                try:
                    # Add platform to the dict before validation
                    trend_dict['platform'] = platform

                    # Validate with Pydantic schema
                    trend_data = TrendCreate(**trend_dict)

                    # Get values for database insert
                    trend_values = trend_data.model_dump()

                    # UPSERT using appropriate dialect
                    settings = get_settings()
                    if settings.database_url.startswith("sqlite"):
                        from sqlalchemy.dialects.sqlite import insert as dialect_insert
                    else:
                        from sqlalchemy.dialects.postgresql import insert as dialect_insert
                    stmt = dialect_insert(Trend).values(**trend_values)

                    # On conflict (duplicate platform+external_id), update engagement metrics
                    stmt = stmt.on_conflict_do_update(
                        index_elements=['platform', 'external_id'],
                        set_={
                            'title': stmt.excluded.title,
                            'description': stmt.excluded.description,
                            'views': stmt.excluded.views,
                            'likes': stmt.excluded.likes,
                            'comments': stmt.excluded.comments,
                            'shares': stmt.excluded.shares,
                            'engagement_velocity': stmt.excluded.engagement_velocity,
                        }
                    )

                    await session.execute(stmt)
                    saved_count += 1

                except Exception as e:
                    logger.error(f"Failed to save trend {trend_dict.get('external_id')}: {e}")
                    continue

            await session.commit()
            logger.info(f"Saved {saved_count} {platform} trends to database")

    except SQLAlchemyError as e:
        logger.error(f"Database error saving {platform} trends: {e}", exc_info=True)
        raise

    return saved_count


async def collect_all_trends() -> Dict[str, int]:
    """
    Collect trends from all platforms and save to database.

    Returns:
        Dictionary with platform counts: {"tiktok": 50, "youtube": 45}
    """
    results = {}

    # Collect TikTok trends
    try:
        logger.info("Collecting TikTok trends...")
        tiktok_trends = scrape_tiktok_trends(limit=50)
        tiktok_enriched = enrich_trends_with_velocity(tiktok_trends)
        tiktok_count = await save_trends(tiktok_enriched, platform='tiktok')
        results['tiktok'] = tiktok_count
    except Exception as e:
        logger.error(f"Failed to collect TikTok trends: {e}", exc_info=True)
        results['tiktok'] = 0

    # Collect YouTube trends
    try:
        logger.info("Collecting YouTube trends...")
        youtube_trends = scrape_youtube_shorts(limit=50)
        youtube_enriched = enrich_trends_with_velocity(youtube_trends)
        youtube_count = await save_trends(youtube_enriched, platform='youtube')
        results['youtube'] = youtube_count
    except Exception as e:
        logger.error(f"Failed to collect YouTube trends: {e}", exc_info=True)
        results['youtube'] = 0

    logger.info(f"Trend collection complete: {results}")
    return results
