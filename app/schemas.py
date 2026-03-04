from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional


# UGC Product Ad Pipeline Schemas

class ProductInput(BaseModel):
    """Input schema for UGC product ad creation."""
    product_name: str
    description: str
    product_url: Optional[str] = None
    target_duration: int = 30  # seconds, 25-30s range
    style_preference: Optional[str] = None  # selfie-review, unboxing, tutorial, lifestyle


class ProductAnalysis(BaseModel):
    """LLM-generated product analysis for UGC ad creation."""
    category: str = Field(description="Product category: cosmetics, tech, food, fashion, SaaS, etc.")
    key_features: List[str] = Field(description="3-5 standout features")
    target_audience: str = Field(description="Primary demographic and psychographic profile")
    ugc_style: str = Field(description="Best video style: selfie-review, unboxing, tutorial, lifestyle")
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
    creator_persona: str = Field(default="", description="Physical appearance of the UGC creator — reused in every scene automatically")
    voice_direction: str = Field(default="", description="Voice tone and delivery style for the whole video")


class ArollScene(BaseModel):
    """A-Roll scene (UGC creator talking) for Veo generation."""
    frame_number: int
    duration_seconds: int = Field(ge=4, le=8, description="Veo max 8s per clip")
    visual_prompt: str = Field(description="Scene action, gestures, product interaction — NOT the person's appearance")
    script_text: str = Field(description="Actual words spoken in this scene")
    camera_angle: str = Field(default="medium close-up", description="Camera angle for Veo: close-up, medium close-up, medium shot, POV, over-shoulder")
    voice_direction: str = Field(default="", description="Legacy — use master_script.voice_direction")


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


# Landing Page Generation Schemas

class LandingPageRequest(BaseModel):
    """Input schema for landing page generation."""
    product_idea: str
    target_audience: str
    industry: Optional[str] = None
    region: Optional[str] = None
    color_preference: Optional[str] = None  # "extract", "research", "preset"
    color_preset: Optional[str] = None
    video_path: Optional[str] = None
    hero_image_path: Optional[str] = None
    product_images: Optional[List[str]] = None


class LPResearchPattern(BaseModel):
    """Single landing page research pattern extracted from competitor LP."""
    url: str
    hero_headline: str
    cta_texts: List[str]
    section_order: List[str]
    has_video: bool
    video_placement: Optional[str] = None
    color_scheme: Optional[dict] = None


class LPResearchResult(BaseModel):
    """Aggregated research results from multiple competitor LPs."""
    patterns: List[LPResearchPattern]
    common_sections: List[str]
    dominant_cta_style: str
    video_placement_trend: str
    color_trends: List[dict]


class LPBenefit(BaseModel):
    """Single benefit item for LP copy."""
    title: str
    description: str
    icon_emoji: str


class LPFeature(BaseModel):
    """Single feature item for LP copy."""
    title: str
    description: str
    stat: str


class LPHowItWorksStep(BaseModel):
    """Single how-it-works step for LP copy."""
    step_number: int
    title: str
    description: str


class LPFAQItem(BaseModel):
    """Single FAQ item for LP copy."""
    question: str
    answer: str


class LandingPageCopy(BaseModel):
    """AI-generated landing page copy content."""
    headline: str  # 5-8 words, benefit-driven, specific
    subheadline: str  # 15-25 words, expands headline with specificity
    benefits: List[LPBenefit]  # Product-specific benefits
    features: Optional[List[LPFeature]] = None  # Quantified product specs
    how_it_works: Optional[List[LPHowItWorksStep]] = None  # 3 numbered steps
    faq: Optional[List[LPFAQItem]] = None  # Common objections answered
    cta_text: str  # 2-4 words, action verb + benefit
    urgency_text: Optional[str] = None  # Scarcity/urgency near CTA
    social_proof_text: str  # Specific number + context
    trust_text: Optional[str] = None  # Privacy/guarantee micro-copy
    footer_text: str
    meta_title: str  # Under 60 chars
    meta_description: str  # ~160 chars


class ColorScheme(BaseModel):
    """Color scheme for landing page."""
    primary: str
    secondary: str
    accent: str
    background: str
    text: str
    source: str  # "extracted", "research", "preset"


class LandingPageResult(BaseModel):
    """Result of landing page generation."""
    html_path: str
    product_idea: str
    color_scheme: ColorScheme
    sections: List[str]
    lp_copy: Optional[dict] = None  # LandingPageCopy.model_dump() for LP review cards


# Waitlist Schemas

class WaitlistSubmit(BaseModel):
    """Waitlist form submission from LP visitor."""
    email: EmailStr
    lp_source: Optional[str] = None


class WaitlistResponse(BaseModel):
    """Response for waitlist submission."""
    message: str
