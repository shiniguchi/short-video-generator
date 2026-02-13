from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class TrendCreate(BaseModel):
    """Schema for creating/updating a trend from scraper output."""
    platform: str  # "tiktok" or "youtube"
    external_id: str
    title: Optional[str] = None
    description: Optional[str] = None
    hashtags: Optional[List[str]] = None
    views: Optional[int] = 0
    likes: Optional[int] = 0
    comments: Optional[int] = 0
    shares: Optional[int] = 0
    duration: Optional[int] = None  # seconds
    creator: Optional[str] = None
    creator_id: Optional[str] = None
    sound_name: Optional[str] = None
    video_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    posted_at: Optional[datetime] = None
    engagement_velocity: Optional[float] = None


class TrendResponse(BaseModel):
    """Schema for trend API responses."""
    id: int
    platform: str
    external_id: str
    title: Optional[str]
    description: Optional[str]
    hashtags: Optional[List[str]]
    views: Optional[int]
    likes: Optional[int]
    comments: Optional[int]
    shares: Optional[int]
    duration: Optional[int]
    creator: Optional[str]
    engagement_velocity: Optional[float]
    collected_at: Optional[datetime]

    class Config:
        from_attributes = True


class VideoStyleSchema(BaseModel):
    """Style classification for a group of videos."""
    category: str  # cinematic, talking-head, montage, text-heavy, animation
    confidence: float
    count: int


class TrendPatternSchema(BaseModel):
    """Extracted pattern from trending videos."""
    format_description: str
    avg_duration_seconds: float
    hook_type: str  # question, shock, story, tutorial
    uses_text_overlay: bool
    audio_type: str  # original, trending-sound, voiceover, music


class TrendReportCreate(BaseModel):
    """Schema for Claude analysis output."""
    analyzed_count: int
    video_styles: List[VideoStyleSchema]
    common_patterns: List[TrendPatternSchema]
    avg_engagement_velocity: float
    top_hashtags: List[str]
    recommendations: List[str]


class TrendReportResponse(BaseModel):
    """Schema for trend report API responses."""
    id: int
    analyzed_count: int
    date_range_start: datetime
    date_range_end: datetime
    video_styles: List[VideoStyleSchema]
    common_patterns: List[TrendPatternSchema]
    avg_engagement_velocity: Optional[float]
    top_hashtags: Optional[List[str]]
    recommendations: Optional[List[str]]
    created_at: Optional[datetime]

    class Config:
        from_attributes = True


# Video Production Plan Schemas (Phase 3: Content Generation)

class SceneSchema(BaseModel):
    """Individual scene in video production plan."""
    scene_number: int
    duration_seconds: int  # 2-4 second range
    visual_prompt: str  # Text prompt for video generation
    transition: str  # fade, cut, dissolve


class TextOverlaySchema(BaseModel):
    """Text overlay timing and positioning."""
    text: str
    timestamp_start: float  # seconds
    timestamp_end: float  # seconds
    position: str  # top, center, bottom
    style: str  # bold, normal, highlight


class VideoProductionPlanCreate(BaseModel):
    """Complete video production plan from Claude (used as tool-use schema)."""
    video_prompt: str  # Master visual prompt
    duration_target: int  # 15-30 seconds
    aspect_ratio: str  # Always "9:16"
    scenes: List[SceneSchema]
    voiceover_script: str
    hook_text: str  # First 3 seconds hook
    cta_text: str  # Call-to-action
    text_overlays: List[TextOverlaySchema]
    hashtags: List[str]
    title: str
    description: str


class VideoProductionPlanResponse(BaseModel):
    """Video production plan API response."""
    id: int
    video_prompt: str
    duration_target: int
    aspect_ratio: str
    scenes: List[SceneSchema]
    voiceover_script: str
    hook_text: str
    cta_text: str
    text_overlays: List[TextOverlaySchema]
    hashtags: List[str]
    title: str
    description: str
    created_at: Optional[datetime]

    class Config:
        from_attributes = True
