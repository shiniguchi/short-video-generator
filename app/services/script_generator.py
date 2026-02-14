"""Claude-powered script generator with 5-step prompt chain."""
import logging
from typing import List, Dict, Any, Optional

from app.config import get_settings
from app.schemas import VideoProductionPlanCreate

logger = logging.getLogger(__name__)

# Prompt templates for the 5-step chain
# Steps 1-4 combined into a single analysis prompt (Call 1)
# Step 5 uses tool-use for structured output (Call 2)

ANALYSIS_PROMPT = """You are a viral short-form video content strategist. Perform the following 4 analysis steps for a video production plan.

THEME/PRODUCT INFORMATION:
{theme_info}

CONTENT REFERENCES:
{content_refs_text}

{trend_section}

Perform these 4 steps in sequence:

**STEP 1 - Theme Interpretation:**
Analyze the core message, target audience, emotional tone, and key selling points of this product/theme.

**STEP 2 - Trend Alignment:**
Based on the trend data (if available), select the best trend patterns for this theme. Choose a style classification (cinematic, talking-head, montage, text-heavy, animation). Identify engagement hooks that match current viral patterns.

**STEP 3 - Scene Construction:**
Build a scene breakdown with 3-7 scenes, each 2-4 seconds long. Total duration should be {duration_target} seconds. For each scene, write a detailed visual prompt suitable for AI video generation. Include transitions (fade, cut, dissolve).

**STEP 4 - Narration Script:**
Write a voiceover script that matches the scene timing. Create a hook_text for the first 3 seconds to capture attention. Create a cta_text (call-to-action) for the final seconds.

Provide your complete analysis covering all 4 steps."""

STRUCTURED_OUTPUT_PROMPT = """Based on the following analysis and original inputs, create a complete Video Production Plan.

ORIGINAL THEME INFORMATION:
{theme_info}

CONTENT REFERENCES:
{content_refs_text}

ANALYSIS FROM PREVIOUS STEPS:
{analysis_text}

Now create the final Video Production Plan using the create_production_plan tool. Include:
- video_prompt: Master visual prompt describing the overall video concept
- duration_target: {duration_target} seconds
- aspect_ratio: "9:16"
- scenes: Array of scenes with scene_number, duration_seconds (2-4s each), visual_prompt, transition
- voiceover_script: Full narration text
- hook_text: Attention-grabbing text for first 3 seconds
- cta_text: Call-to-action text
- text_overlays: Array with text, timestamp_start, timestamp_end, position (top/center/bottom), style (bold/normal/highlight)
- hashtags: 5-8 relevant hashtags
- title: Short catchy title
- description: Platform-optimized description

Ensure scenes durations sum to approximately {duration_target} seconds."""


def _format_theme_info(theme_config: dict) -> str:
    """Format theme config into prompt text."""
    lines = []
    for key in ['theme', 'product_name', 'tagline', 'target_audience', 'tone',
                'style', 'target_platform', 'video_duration_seconds']:
        if key in theme_config and theme_config[key]:
            lines.append(f"- {key.replace('_', ' ').title()}: {theme_config[key]}")
    return '\n'.join(lines) if lines else "- Theme: General content"


def _format_content_refs(content_refs: List[dict]) -> str:
    """Format content references into prompt text."""
    if not content_refs:
        return "No specific content references provided."

    lines = []
    for ref in content_refs:
        lines.append(f"- {ref.get('title', 'Untitled')}: {ref.get('description', '')}")
        points = ref.get('talking_points', [])
        if points:
            for p in points:
                lines.append(f"  * {p}")
    return '\n'.join(lines)


def _format_trend_section(trend_report: Optional[dict]) -> str:
    """Format trend report data for the prompt."""
    if not trend_report:
        return "TREND DATA: No trend data available. Use general viral content best practices."

    lines = ["CURRENT TREND DATA:"]

    styles = trend_report.get('video_styles', [])
    if styles:
        lines.append("Top video styles:")
        for s in styles[:4]:
            lines.append(f"  - {s.get('category', 'unknown')} (confidence: {s.get('confidence', 0):.0%}, count: {s.get('count', 0)})")

    patterns = trend_report.get('common_patterns', [])
    if patterns:
        lines.append("Common patterns:")
        for p in patterns[:3]:
            lines.append(f"  - {p.get('format_description', '')}")
            lines.append(f"    Hook: {p.get('hook_type', 'N/A')}, Audio: {p.get('audio_type', 'N/A')}, Text overlay: {p.get('uses_text_overlay', False)}")

    hashtags = trend_report.get('top_hashtags', [])
    if hashtags:
        lines.append(f"Trending hashtags: {', '.join(hashtags[:10])}")

    velocity = trend_report.get('avg_engagement_velocity')
    if velocity:
        lines.append(f"Average engagement velocity: {velocity:.0f}/hr")

    recs = trend_report.get('recommendations', [])
    if recs:
        lines.append("Recommendations:")
        for r in recs:
            lines.append(f"  - {r}")

    return '\n'.join(lines)


def generate_production_plan(
    theme_config: dict,
    content_refs: List[dict],
    trend_report: Optional[dict] = None
) -> dict:
    """Generate a Video Production Plan using Claude 5-step prompt chain.

    All 5 conceptual steps (theme interpretation, trend alignment, scene
    construction, narration, text overlay design) are preserved but optimized
    into 2 API calls for efficiency.

    Falls back to mock plan if USE_MOCK_DATA=True, no API key, or on errors.

    Args:
        theme_config: Theme/product configuration dict
        content_refs: List of content reference dicts
        trend_report: Optional trend report dict from Phase 2

    Returns:
        Dict matching VideoProductionPlanCreate schema
    """
    settings = get_settings()

    if settings.use_mock_data or not settings.anthropic_api_key:
        logger.info("Using mock production plan (mock mode or no API key)")
        return _generate_mock_plan(theme_config, content_refs)

    try:
        return _generate_claude_plan(theme_config, content_refs, trend_report)
    except Exception as exc:
        logger.error(f"Claude plan generation failed: {exc}")
        logger.info("Falling back to mock production plan")
        return _generate_mock_plan(theme_config, content_refs)


def _generate_claude_plan(
    theme_config: dict,
    content_refs: List[dict],
    trend_report: Optional[dict] = None
) -> dict:
    """Generate plan using Claude API with 2-call optimization."""
    from anthropic import Anthropic
    from app.services.trend_analyzer import _add_additional_properties_false

    settings = get_settings()
    client = Anthropic(api_key=settings.anthropic_api_key)

    duration_target = theme_config.get('video_duration_seconds', 20)
    theme_info = _format_theme_info(theme_config)
    content_refs_text = _format_content_refs(content_refs)
    trend_section = _format_trend_section(trend_report)

    # Call 1: Steps 1-4 (analysis)
    analysis_prompt = ANALYSIS_PROMPT.format(
        theme_info=theme_info,
        content_refs_text=content_refs_text,
        trend_section=trend_section,
        duration_target=duration_target
    )

    logger.info("Claude Call 1/2: Running steps 1-4 analysis")
    response1 = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        messages=[{"role": "user", "content": analysis_prompt}]
    )

    analysis_text = response1.content[0].text
    logger.info(f"Call 1 complete: {len(analysis_text)} chars of analysis")

    # Call 2: Step 5 (structured output via tool-use)
    structured_prompt = STRUCTURED_OUTPUT_PROMPT.format(
        theme_info=theme_info,
        content_refs_text=content_refs_text,
        analysis_text=analysis_text,
        duration_target=duration_target
    )

    base_schema = VideoProductionPlanCreate.model_json_schema()
    schema = _add_additional_properties_false(base_schema)

    logger.info("Claude Call 2/2: Generating structured production plan")
    response2 = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        tools=[
            {
                "name": "create_production_plan",
                "description": "Create a complete Video Production Plan with all required fields",
                "input_schema": schema
            }
        ],
        messages=[{"role": "user", "content": structured_prompt}]
    )

    # Extract tool use from response
    tool_use_block = None
    for block in response2.content:
        if block.type == "tool_use" and block.name == "create_production_plan":
            tool_use_block = block
            break

    if not tool_use_block:
        raise ValueError("Claude did not return a create_production_plan tool_use block")

    # Validate with Pydantic
    plan_data = tool_use_block.input
    validated = VideoProductionPlanCreate(**plan_data)
    result = validated.model_dump()

    logger.info(f"Production plan generated: '{result['title']}' with {len(result['scenes'])} scenes")
    return result


def _generate_mock_plan(theme_config: dict, content_refs: List[dict]) -> dict:
    """Generate a realistic mock production plan for testing.

    Args:
        theme_config: Theme/product configuration dict
        content_refs: List of content reference dicts

    Returns:
        Dict matching VideoProductionPlanCreate schema
    """
    theme = theme_config.get('theme', 'Product Demo')
    product = theme_config.get('product_name', 'Amazing Product')
    tagline = theme_config.get('tagline', 'The best solution')
    style = theme_config.get('style', 'cinematic')
    duration = theme_config.get('video_duration_seconds', 20)

    # Get talking points from content refs
    talking_points = []
    for ref in content_refs:
        talking_points.extend(ref.get('talking_points', []))
    if not talking_points:
        talking_points = ["Premium quality", "Easy to use", "Transform your life"]

    # Build scenes (divide duration evenly, 3-4 seconds each)
    num_scenes = max(3, min(7, duration // 4))
    scene_duration = duration // num_scenes
    remainder = duration - (scene_duration * num_scenes)

    scenes = []
    scene_prompts = [
        f"Dynamic opening shot, {style} style, product reveal with dramatic lighting",
        f"Close-up of {product}, showcasing premium design and details, smooth camera movement",
        f"Person using {product} in modern setting, natural lighting, lifestyle shot",
        f"Split screen comparison showing before and after, clean graphics",
        f"Customer reaction shot, genuine excitement, warm tones",
        f"Product features montage, quick cuts, text overlay highlights",
        f"Final hero shot of {product} with brand colors, call to action overlay",
    ]

    for i in range(num_scenes):
        d = scene_duration + (1 if i < remainder else 0)
        scenes.append({
            "scene_number": i + 1,
            "duration_seconds": d,
            "visual_prompt": scene_prompts[i % len(scene_prompts)],
            "transition": "cut" if i == 0 else ("fade" if i == num_scenes - 1 else "dissolve")
        })

    # Build text overlays
    text_overlays = [
        {
            "text": tagline,
            "timestamp_start": 0.0,
            "timestamp_end": 3.0,
            "position": "center",
            "style": "bold"
        },
        {
            "text": talking_points[0] if talking_points else "Premium Quality",
            "timestamp_start": 4.0,
            "timestamp_end": 8.0,
            "position": "bottom",
            "style": "normal"
        },
        {
            "text": talking_points[1] if len(talking_points) > 1 else "Easy to Use",
            "timestamp_start": 9.0,
            "timestamp_end": 13.0,
            "position": "center",
            "style": "highlight"
        },
        {
            "text": "Follow for more!",
            "timestamp_start": float(duration - 3),
            "timestamp_end": float(duration),
            "position": "bottom",
            "style": "bold"
        },
    ]

    voiceover = (
        f"Discover {product} - {tagline}. "
        f"{talking_points[0]}. "
        f"{''.join(talking_points[1]) if len(talking_points) > 1 else 'Transform your experience today'}. "
        f"Try it now and see the difference!"
    )

    plan = {
        "video_prompt": f"{style} style short-form video showcasing {product}, vertical 9:16, "
                        f"engaging visuals with modern editing, targeting {theme_config.get('target_audience', 'general audience')}",
        "duration_target": duration,
        "aspect_ratio": "9:16",
        "scenes": scenes,
        "voiceover_script": voiceover,
        "hook_text": f"You NEED to see this {product}!",
        "cta_text": "Follow for more amazing content!",
        "text_overlays": text_overlays,
        "hashtags": [
            "#viral", "#trending", f"#{product.replace(' ', '').lower()}",
            "#fyp", "#musthave", "#tiktokmademebuyit",
            f"#{theme.replace(' ', '').lower()}", "#shorts"
        ],
        "title": f"{product} - {tagline}",
        "description": f"Check out {product}! {tagline}. {talking_points[0]}. #viral #fyp"
    }

    # Validate against schema
    validated = VideoProductionPlanCreate(**plan)
    result = validated.model_dump()

    logger.info(f"Mock production plan generated: '{result['title']}' with {len(result['scenes'])} scenes")
    return result


async def save_production_plan(
    plan_data: dict,
    theme_config: dict,
    trend_report_id: Optional[int] = None,
    job_id: Optional[int] = None
) -> int:
    """Save production plan to database.

    Args:
        plan_data: Dict matching VideoProductionPlanCreate schema
        theme_config: Theme config snapshot to store
        trend_report_id: Optional ID of trend report used
        job_id: Optional ID of orchestrating Job

    Returns:
        Script ID in database
    """
    from app.models import Script
    from app.database import async_session_factory

    async with async_session_factory() as session:
        script = Script(
            job_id=job_id,
            video_prompt=plan_data['video_prompt'],
            scenes=plan_data['scenes'],
            text_overlays=plan_data.get('text_overlays'),
            voiceover_script=plan_data.get('voiceover_script'),
            title=plan_data.get('title'),
            description=plan_data.get('description'),
            hashtags=plan_data.get('hashtags'),
            duration_target=plan_data.get('duration_target'),
            aspect_ratio=plan_data.get('aspect_ratio', '9:16'),
            hook_text=plan_data.get('hook_text'),
            cta_text=plan_data.get('cta_text'),
            theme_config=theme_config,
            trend_report_id=trend_report_id,
        )

        session.add(script)
        await session.commit()
        await session.refresh(script)

        logger.info(f"Saved production plan as Script ID {script.id} for Job {job_id}: '{script.title}'")
        return script.id
