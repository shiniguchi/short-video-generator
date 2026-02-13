from sqlalchemy import Column, Integer, String, Text, DateTime, Float, Boolean, JSON, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from datetime import datetime

Base = declarative_base()


class Job(Base):
    """Pipeline execution job tracking"""
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True)
    status = Column(String(50), nullable=False, default="pending")  # pending, running, completed, failed
    stage = Column(String(50))  # current pipeline stage
    theme = Column(String(255))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    error_message = Column(Text)
    extra_data = Column("metadata", JSON)  # Flexible storage for stage-specific data


class Trend(Base):
    """Collected trending videos from TikTok/YouTube"""
    __tablename__ = "trends"

    id = Column(Integer, primary_key=True)
    platform = Column(String(50), nullable=False)  # tiktok, youtube
    external_id = Column(String(255), nullable=False, unique=True)  # Platform's video ID
    title = Column(String(500))
    creator = Column(String(255))
    hashtags = Column(JSON)  # Array of hashtag strings
    views = Column(Integer)
    likes = Column(Integer)
    comments = Column(Integer)
    shares = Column(Integer)
    video_url = Column(String(1000))
    thumbnail_url = Column(String(1000))
    collected_at = Column(DateTime(timezone=True), server_default=func.now())
    extra_data = Column("metadata", JSON)


class Script(Base):
    """Generated video production plans (scripts)"""
    __tablename__ = "scripts"

    id = Column(Integer, primary_key=True)
    job_id = Column(Integer, ForeignKey("jobs.id"))
    video_prompt = Column(Text, nullable=False)
    scenes = Column(JSON, nullable=False)  # Array of scene objects
    text_overlays = Column(JSON)  # Array of text overlay objects
    voiceover_script = Column(Text)
    title = Column(String(500))
    description = Column(Text)
    hashtags = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Video(Base):
    """Generated video metadata and file paths"""
    __tablename__ = "videos"

    id = Column(Integer, primary_key=True)
    job_id = Column(Integer, ForeignKey("jobs.id"))
    script_id = Column(Integer, ForeignKey("scripts.id"))
    status = Column(String(50), default="generated")  # generated, approved, rejected, published
    file_path = Column(String(1000))
    thumbnail_path = Column(String(1000))
    duration_seconds = Column(Float)
    cost_usd = Column(Float)  # Total generation cost
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    approved_at = Column(DateTime(timezone=True))
    published_at = Column(DateTime(timezone=True))
    published_url = Column(String(1000))
    extra_data = Column("metadata", JSON)
