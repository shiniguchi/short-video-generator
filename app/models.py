from sqlalchemy import Column, Integer, String, Text, DateTime, Float, Boolean, JSON, ForeignKey, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()


class WaitlistEntry(Base):
    """Visitor waitlist signups from landing pages."""
    __tablename__ = "waitlist_entries"

    id = Column(Integer, primary_key=True)
    email = Column(String(255), nullable=False)
    lp_source = Column(String(50), nullable=True)  # run_id of source LP
    signed_up_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint('email', name='uq_waitlist_email'),
    )


class LandingPage(Base):
    """Generated landing pages — tracks status and deployment info."""
    __tablename__ = "landing_pages"

    id = Column(Integer, primary_key=True)
    run_id = Column(String(50), nullable=False, unique=True)  # pipeline run ID
    product_idea = Column(String(500), nullable=False)
    target_audience = Column(String(500), nullable=True)
    html_path = Column(String(1000), nullable=True)  # local file path
    status = Column(String(50), default="generated")  # generated, deployed, archived
    color_scheme_source = Column(String(50), nullable=True)  # extract/research/preset
    sections = Column(JSON, nullable=True)  # section config snapshot
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    deployed_at = Column(DateTime(timezone=True), nullable=True)
    deployed_url = Column(String(1000), nullable=True)
    template_key = Column(String(50), nullable=True)  # premium template selection
    lp_section_images = Column(JSON, nullable=True)  # {"benefits": ["path0", ...], "how_it_works": [...]}

    # LP integration columns (phase 25)
    ugc_job_id = Column(Integer, ForeignKey("ugc_jobs.id"), nullable=True)
    lp_module_approvals = Column(JSON, nullable=True)  # {"headline": "approved", "hero": "pending", ...}
    lp_hero_image_path = Column(String(1000), nullable=True)   # frame from approved video
    lp_hero_candidate_path = Column(String(1000), nullable=True)  # regenerated candidate
    lp_review_locked = Column(Boolean, default=True)   # unlocked when UGCJob.status == "approved"
    lp_copy = Column(JSON, nullable=True)  # LandingPageCopy.model_dump() stored at generation time

    __table_args__ = (
        UniqueConstraint('run_id', name='uq_lp_run_id'),
    )


class UGCJob(Base):
    """UGC video generation job — all pipeline state persists here.

    Status valid values: pending, running, stage_analysis_review,
    stage_script_review, stage_aroll_review, stage_broll_review,
    stage_composition_review, approved, failed
    """
    __tablename__ = "ugc_jobs"

    id = Column(Integer, primary_key=True)

    # --- Input columns ---
    product_name = Column(String(500), nullable=False)
    description = Column(Text, nullable=False)
    product_url = Column(String(1000), nullable=True)
    product_image_paths = Column(JSON, nullable=True)  # list of local paths
    target_duration = Column(Integer, default=30)
    style_preference = Column(String(100), nullable=True)
    use_mock = Column(Boolean, default=True)  # passed per job, not from settings
    broll_include_creator = Column(Boolean, default=False)  # include A-Roll creator in B-Roll images

    # --- State columns ---
    status = Column(String(50), nullable=False, default="pending")
    error_message = Column(Text, nullable=True)

    # --- Stage 1: Product Analysis ---
    analysis_category = Column(String(200), nullable=True)
    analysis_ugc_style = Column(String(200), nullable=True)
    analysis_emotional_tone = Column(String(200), nullable=True)
    analysis_key_features = Column(JSON, nullable=True)       # list[str]
    analysis_visual_keywords = Column(JSON, nullable=True)    # list[str]
    analysis_target_audience = Column(String(500), nullable=True)

    # --- Stage 2: Hero Image ---
    hero_image_path = Column(String(1000), nullable=True)
    hero_image_history = Column(JSON, nullable=True)  # list of previous hero image paths (newest first)
    hero_sketch_path = Column(String(1000), nullable=True)  # optional hand-drawn sketch for guided gen

    # --- Stage 3: Script ---
    master_script = Column(JSON, nullable=True)    # dict
    aroll_scenes = Column(JSON, nullable=True)     # list[dict]
    broll_shots = Column(JSON, nullable=True)      # list[dict]

    # --- Stage 3a/4a: Per-scene images (review before video gen) ---
    aroll_image_paths = Column(JSON, nullable=True)  # list[str] per-scene images
    broll_image_paths = Column(JSON, nullable=True)  # list[str] per-shot images
    aroll_image_history = Column(JSON, nullable=True)  # list[list[str]] per-scene history (newest first)
    broll_image_history = Column(JSON, nullable=True)  # list[list[str]] per-scene history (newest first)

    # --- Stage 4: A-Roll Videos ---
    aroll_paths = Column(JSON, nullable=True)      # list[str]
    aroll_video_history = Column(JSON, nullable=True)  # list[list[str]] per-scene video history

    # --- Stage 5: B-Roll Videos ---
    broll_paths = Column(JSON, nullable=True)      # list[str]
    broll_video_history = Column(JSON, nullable=True)  # list[list[str]] per-shot video history

    # --- Stage 6: Composition ---
    final_video_path = Column(String(1000), nullable=True)
    cost_usd = Column(Float, nullable=True)

    # --- Candidate (regeneration) ---
    candidate_video_path = Column(String(1000), nullable=True)
    trim_history = Column(JSON, nullable=True)  # stack of previous video paths for multi-undo

    # --- Timestamps ---
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    approved_at = Column(DateTime(timezone=True), nullable=True)
