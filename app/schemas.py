from pydantic import BaseModel, Field, HttpUrl
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


# Pipeline Orchestration Schemas (Phase 6)

class PipelineTriggerRequest(BaseModel):
    """Request body for POST /api/generate."""
    theme: Optional[str] = None  # Theme override (uses sample-data.yml default if None)
    config_path: Optional[str] = None  # Custom config file path


class PipelineTriggerResponse(BaseModel):
    """Response for POST /api/generate."""
    job_id: int
    task_id: str
    status: str  # "queued"
    poll_url: str  # "/api/jobs/{job_id}"
    message: str


class JobStatusResponse(BaseModel):
    """Response for GET /api/jobs/{id}."""
    id: int
    status: str  # pending, running, completed, failed
    stage: Optional[str]  # Current or last pipeline stage
    theme: Optional[str]
    created_at: Optional[str]  # ISO format
    updated_at: Optional[str]  # ISO format
    error_message: Optional[str]
    completed_stages: Optional[List[str]]  # Stages that finished successfully
    total_stages: int  # Total pipeline stages count
    progress_pct: Optional[float]  # Percentage complete (completed/total * 100)


class JobListResponse(BaseModel):
    """Response for GET /api/jobs."""
    count: int
    jobs: List[JobStatusResponse]


class JobRetryResponse(BaseModel):
    """Response for POST /api/jobs/{id}/retry."""
    job_id: int
    task_id: str
    status: str  # "queued"
    resume_from: Optional[str]  # Stage resuming from
    skipping_stages: List[str]  # Already completed stages
    message: str


# UGC Product Ad Pipeline Schemas (Phase 13)

class ProductInput(BaseModel):
    """Input schema for UGC product ad creation."""
    product_name: str
    description: str
    product_url: Optional[str] = None  # Use str not HttpUrl for Form parsing simplicity
    target_duration: int = 30  # seconds, 25-30s range
    style_preference: Optional[str] = None  # selfie-review, unboxing, tutorial, lifestyle


class ProductAnalysis(BaseModel):
    """LLM-generated product analysis for UGC ad creation."""
    category: str = Field(description="Product category: cosmetics, tech, food, fashion, SaaS, etc.")
    key_features: List[str] = Field(description="3-5 standout features")
    target_audience: str = Field(description="Primary demographic and psychographic profile")
    ugc_style: str = Field(description="Best UGC style: selfie-review, unboxing, tutorial, lifestyle")
    emotional_tone: str = Field(description="Tone: excited, authentic, educational, aspirational")
    visual_keywords: List[str] = Field(description="5-8 visual keywords for image/video generation")


class MasterScript(BaseModel):
    """Hook-Problem-Proof-CTA script structure."""
    hook: str = Field(description="Opening line, first 3 seconds")
    problem: str = Field(description="Pain point, 3-8 seconds")
    proof: str = Field(description="Product solution with social proof, 8-20 seconds")
    cta: str = Field(description="Call-to-action, final 5-10 seconds")
    full_script: str = Field(description="Complete voiceover script combining all sections")
    total_duration: int = Field(description="Total script duration in seconds")


class ArollScene(BaseModel):
    """A-Roll scene (UGC creator talking) for Veo generation."""
    frame_number: int
    duration_seconds: int = Field(ge=4, le=8, description="Veo max 8s per clip")
    visual_prompt: str = Field(description="UGC creator visual + action for Veo")
    voice_direction: str = Field(description="Voice tone and delivery for Veo audio")
    script_text: str = Field(description="Actual words spoken in this scene")
    camera_angle: str = Field(default="medium close-up", description="Camera angle for Veo: close-up, medium close-up, medium shot, POV, over-shoulder")


class BrollShot(BaseModel):
    """B-Roll shot (product close-up/lifestyle) for Imagen + Veo."""
    shot_number: int
    image_prompt: str = Field(description="Imagen prompt for product close-up/lifestyle")
    animation_prompt: str = Field(description="Veo image-to-video motion description")
    duration_seconds: int = Field(default=5, description="Standard 5s B-roll")
    overlay_start: float = Field(description="When to start overlay in final timeline (seconds)")
    reference_image_index: int = Field(default=0, description="Index into product_images list for Imagen reference")


class AdBreakdown(BaseModel):
    """Complete UGC ad breakdown with A-Roll scenes and B-Roll shots."""
    master_script: MasterScript
    aroll_scenes: List[ArollScene]
    broll_shots: List[BrollShot]
    total_duration: int


class UGCAdResponse(BaseModel):
    """API response for UGC ad generation request."""
    job_id: int
    task_id: str
    status: str = "queued"
    poll_url: str
    message: str
