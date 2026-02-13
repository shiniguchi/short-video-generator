"""Trend report database operations."""
import logging
from typing import List, Dict, Optional
from datetime import datetime
from sqlalchemy import select
from app.models import TrendReport, Trend
from app.database import async_session_factory

logger = logging.getLogger(__name__)


async def save_report(
    report_data: Dict,
    date_range_start: datetime,
    date_range_end: datetime
) -> int:
    """
    Save a trend analysis report to database.

    Args:
        report_data: Dict matching TrendReportCreate schema
        date_range_start: Start of analysis date range
        date_range_end: End of analysis date range

    Returns:
        ID of saved report
    """
    async with async_session_factory() as session:
        report = TrendReport(
            analyzed_count=report_data['analyzed_count'],
            date_range_start=date_range_start,
            date_range_end=date_range_end,
            video_styles=report_data['video_styles'],
            common_patterns=report_data['common_patterns'],
            avg_engagement_velocity=report_data.get('avg_engagement_velocity'),
            top_hashtags=report_data.get('top_hashtags'),
            recommendations=report_data.get('recommendations'),
            raw_report=report_data  # Store full report for debugging
        )

        session.add(report)
        await session.commit()
        await session.refresh(report)

        logger.info(f"Saved trend report ID {report.id} with {report.analyzed_count} trends")
        return report.id


async def get_latest_report() -> Optional[Dict]:
    """
    Get the most recent trend analysis report.

    Returns:
        Report dict or None if no reports exist
    """
    async with async_session_factory() as session:
        query = select(TrendReport).order_by(TrendReport.created_at.desc()).limit(1)
        result = await session.execute(query)
        report = result.scalars().first()

        if not report:
            return None

        return {
            'id': report.id,
            'analyzed_count': report.analyzed_count,
            'date_range_start': report.date_range_start,
            'date_range_end': report.date_range_end,
            'video_styles': report.video_styles,
            'common_patterns': report.common_patterns,
            'avg_engagement_velocity': report.avg_engagement_velocity,
            'top_hashtags': report.top_hashtags,
            'recommendations': report.recommendations,
            'created_at': report.created_at
        }


async def get_reports(limit: int = 10) -> List[Dict]:
    """
    Get recent trend analysis reports.

    Args:
        limit: Maximum number of reports to return

    Returns:
        List of report dicts
    """
    async with async_session_factory() as session:
        query = select(TrendReport).order_by(TrendReport.created_at.desc()).limit(limit)
        result = await session.execute(query)
        reports = result.scalars().all()

        return [
            {
                'id': r.id,
                'analyzed_count': r.analyzed_count,
                'date_range_start': r.date_range_start,
                'date_range_end': r.date_range_end,
                'video_styles': r.video_styles,
                'common_patterns': r.common_patterns,
                'avg_engagement_velocity': r.avg_engagement_velocity,
                'top_hashtags': r.top_hashtags,
                'recommendations': r.recommendations,
                'created_at': r.created_at
            }
            for r in reports
        ]


async def get_trends_for_analysis(hours: int = 24) -> List[Dict]:
    """
    Get recent trends for analysis.

    Args:
        hours: Number of hours to look back

    Returns:
        List of trend dicts with all fields
    """
    from datetime import timezone, timedelta

    async with async_session_factory() as session:
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)

        query = (
            select(Trend)
            .where(Trend.collected_at >= cutoff_time)
            .order_by(Trend.engagement_velocity.desc())
            .limit(100)
        )

        result = await session.execute(query)
        trends = result.scalars().all()

        # Convert SQLAlchemy models to dicts
        trend_dicts = []
        for trend in trends:
            trend_dict = {c.name: getattr(trend, c.name) for c in Trend.__table__.columns}
            trend_dicts.append(trend_dict)

        logger.info(f"Retrieved {len(trend_dicts)} trends from last {hours} hours for analysis")
        return trend_dicts
