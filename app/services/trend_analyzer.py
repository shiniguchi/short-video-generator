"""Trend analysis using Claude API with structured outputs."""
import logging
from typing import List, Dict, Any, Optional
from collections import Counter
from app.config import get_settings
from app.schemas import TrendReportCreate

logger = logging.getLogger(__name__)
settings = get_settings()


def _extract_top_hashtags(trends: List[Dict], limit: int = 10) -> List[str]:
    """Extract most common hashtags from trends."""
    all_hashtags = []
    for trend in trends:
        hashtags = trend.get('hashtags', [])
        if hashtags:
            all_hashtags.extend(hashtags)

    if not all_hashtags:
        return []

    # Count occurrences and return top N
    counter = Counter(all_hashtags)
    return [tag for tag, count in counter.most_common(limit)]


def _add_additional_properties_false(schema: dict) -> dict:
    """
    Recursively add additionalProperties: false to all object types in JSON schema.
    Required by Claude API for structured outputs.
    """
    if isinstance(schema, dict):
        # Process current level
        if schema.get('type') == 'object' and 'properties' in schema:
            schema['additionalProperties'] = False

        # Recursively process all nested dicts
        for key, value in schema.items():
            if isinstance(value, dict):
                schema[key] = _add_additional_properties_false(value)
            elif isinstance(value, list):
                schema[key] = [_add_additional_properties_false(item) if isinstance(item, dict) else item for item in value]

    return schema


def analyze_trends(trends: List[Dict]) -> Dict:
    """
    Analyze trends using Claude API or return mock data.

    Args:
        trends: List of trend dicts from database

    Returns:
        Dict matching TrendReportCreate schema
    """
    # Check if we should use mock mode
    use_mock = settings.use_mock_data or not settings.anthropic_api_key

    if use_mock:
        logger.info("Using mock analysis (no API key configured)")

        # Return realistic mock report
        mock_report = {
            "analyzed_count": len(trends),
            "video_styles": [
                {"category": "talking-head", "confidence": 0.85, "count": max(1, len(trends) // 3)},
                {"category": "montage", "confidence": 0.78, "count": max(1, len(trends) // 4)},
                {"category": "text-heavy", "confidence": 0.72, "count": max(1, len(trends) // 5)},
                {"category": "cinematic", "confidence": 0.65, "count": max(1, len(trends) // 6)},
            ],
            "common_patterns": [
                {
                    "format_description": "Hook question in first 2 seconds followed by rapid montage",
                    "avg_duration_seconds": 28.5,
                    "hook_type": "question",
                    "uses_text_overlay": True,
                    "audio_type": "trending-sound"
                },
                {
                    "format_description": "Step-by-step tutorial with text overlays",
                    "avg_duration_seconds": 45.0,
                    "hook_type": "tutorial",
                    "uses_text_overlay": True,
                    "audio_type": "voiceover"
                },
                {
                    "format_description": "Reaction or commentary on trending topic",
                    "avg_duration_seconds": 35.0,
                    "hook_type": "shock",
                    "uses_text_overlay": False,
                    "audio_type": "original"
                },
            ],
            "avg_engagement_velocity": sum(t.get('engagement_velocity') or 0 for t in trends) / max(len(trends), 1),
            "top_hashtags": _extract_top_hashtags(trends, limit=10),
            "recommendations": [
                "Use hook questions in first 2 seconds to capture attention",
                "Keep videos between 25-45 seconds for optimal engagement",
                "Add text overlays for accessibility and silent viewing",
                "Use trending sounds when available for algorithm boost",
            ]
        }

        # Validate with Pydantic before returning
        validated = TrendReportCreate(**mock_report)
        return validated.model_dump()

    # Real mode: Use Claude API
    logger.info(f"Analyzing {len(trends)} trends with Claude API")

    try:
        from anthropic import Anthropic
        from tenacity import retry, stop_after_attempt, wait_exponential

        client = Anthropic(api_key=settings.anthropic_api_key)

        # Prepare trend summary (limit to top 50 by engagement velocity)
        sorted_trends = sorted(trends, key=lambda t: t.get('engagement_velocity', 0), reverse=True)
        top_trends = sorted_trends[:50]

        trend_summaries = []
        for i, trend in enumerate(top_trends, 1):
            hashtags = ', '.join(trend.get('hashtags', [])[:5]) if trend.get('hashtags') else 'none'
            summary = (
                f"{i}. Title: {trend.get('title', 'N/A')} | "
                f"Platform: {trend.get('platform', 'N/A')} | "
                f"Duration: {trend.get('duration', 0)}s | "
                f"Likes: {trend.get('likes', 0)}, Comments: {trend.get('comments', 0)}, Shares: {trend.get('shares', 0)} | "
                f"Velocity: {trend.get('engagement_velocity', 0):.1f}/hr | "
                f"Hashtags: {hashtags} | "
                f"Creator: {trend.get('creator', 'N/A')}"
            )
            trend_summaries.append(summary)

        trends_text = '\n'.join(trend_summaries)

        # Build the prompt
        prompt = f"""Analyze these {len(top_trends)} trending videos and identify patterns for viral content creation.

TRENDING VIDEOS:
{trends_text}

Please analyze these videos and provide:

1. VIDEO STYLES: Classify the videos into style categories (talking-head, montage, text-heavy, cinematic, animation) with confidence scores and counts.

2. COMMON PATTERNS: Identify recurring patterns including:
   - Format description (what makes the videos successful)
   - Average duration
   - Hook type (question, shock, story, tutorial)
   - Text overlay usage
   - Audio type (original, trending-sound, voiceover, music)

3. ENGAGEMENT METRICS: Calculate average engagement velocity across all videos.

4. TOP HASHTAGS: List the most frequently used hashtags.

5. RECOMMENDATIONS: Provide 3-5 actionable recommendations for creating viral content based on these patterns.

Use the generate_trend_report tool to structure your response."""

        # Get schema from Pydantic model and add additionalProperties: false
        base_schema = TrendReportCreate.model_json_schema()
        schema = _add_additional_properties_false(base_schema)

        # Use tool-use pattern for reliable structured output
        @retry(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=2, min=4, max=30)
        )
        def call_claude():
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                tools=[
                    {
                        "name": "generate_trend_report",
                        "description": "Generate a structured trend analysis report",
                        "input_schema": schema
                    }
                ],
                messages=[{"role": "user", "content": prompt}]
            )
            return response

        response = call_claude()

        # Extract tool use from response
        tool_use_block = None
        for block in response.content:
            if block.type == "tool_use" and block.name == "generate_trend_report":
                tool_use_block = block
                break

        if not tool_use_block:
            raise ValueError("Claude did not return a tool_use block")

        # Validate with Pydantic
        report_data = tool_use_block.input
        validated = TrendReportCreate(**report_data)

        logger.info(f"Claude analysis complete: {validated.analyzed_count} trends analyzed")
        return validated.model_dump()

    except Exception as exc:
        logger.error(f"Claude analysis failed: {exc}")
        # Fall back to mock data on error
        logger.info("Falling back to mock analysis due to API error")
        mock_report = {
            "analyzed_count": len(trends),
            "video_styles": [
                {"category": "talking-head", "confidence": 0.85, "count": max(1, len(trends) // 3)},
                {"category": "montage", "confidence": 0.78, "count": max(1, len(trends) // 4)},
                {"category": "text-heavy", "confidence": 0.72, "count": max(1, len(trends) // 5)},
                {"category": "cinematic", "confidence": 0.65, "count": max(1, len(trends) // 6)},
            ],
            "common_patterns": [
                {
                    "format_description": "Hook question in first 2 seconds followed by rapid montage",
                    "avg_duration_seconds": 28.5,
                    "hook_type": "question",
                    "uses_text_overlay": True,
                    "audio_type": "trending-sound"
                },
                {
                    "format_description": "Step-by-step tutorial with text overlays",
                    "avg_duration_seconds": 45.0,
                    "hook_type": "tutorial",
                    "uses_text_overlay": True,
                    "audio_type": "voiceover"
                },
                {
                    "format_description": "Reaction or commentary on trending topic",
                    "avg_duration_seconds": 35.0,
                    "hook_type": "shock",
                    "uses_text_overlay": False,
                    "audio_type": "original"
                },
            ],
            "avg_engagement_velocity": sum(t.get('engagement_velocity') or 0 for t in trends) / max(len(trends), 1),
            "top_hashtags": _extract_top_hashtags(trends, limit=10),
            "recommendations": [
                "Use hook questions in first 2 seconds to capture attention",
                "Keep videos between 25-45 seconds for optimal engagement",
                "Add text overlays for accessibility and silent viewing",
                "Use trending sounds when available for algorithm boost",
            ]
        }
        validated = TrendReportCreate(**mock_report)
        return validated.model_dump()
