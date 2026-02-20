"""ugcjob schema

Revision ID: 006
Revises: 039d14368a2d
Create Date: 2026-02-20

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '006'
down_revision: Union[str, None] = '039d14368a2d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'ugc_jobs',
        # Primary key
        sa.Column('id', sa.Integer(), nullable=False),

        # Input columns
        sa.Column('product_name', sa.String(500), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('product_url', sa.String(1000), nullable=True),
        sa.Column('product_image_paths', sa.JSON(), nullable=True),
        sa.Column('target_duration', sa.Integer(), nullable=True, server_default='30'),
        sa.Column('style_preference', sa.String(100), nullable=True),
        sa.Column('use_mock', sa.Boolean(), nullable=True, server_default='true'),

        # State columns
        sa.Column('status', sa.String(50), nullable=False, server_default='pending'),
        sa.Column('error_message', sa.Text(), nullable=True),

        # Stage 1: Product Analysis
        sa.Column('analysis_category', sa.String(200), nullable=True),
        sa.Column('analysis_ugc_style', sa.String(200), nullable=True),
        sa.Column('analysis_emotional_tone', sa.String(200), nullable=True),
        sa.Column('analysis_key_features', sa.JSON(), nullable=True),
        sa.Column('analysis_visual_keywords', sa.JSON(), nullable=True),
        sa.Column('analysis_target_audience', sa.String(500), nullable=True),

        # Stage 2: Hero Image
        sa.Column('hero_image_path', sa.String(1000), nullable=True),

        # Stage 3: Script
        sa.Column('master_script', sa.JSON(), nullable=True),
        sa.Column('aroll_scenes', sa.JSON(), nullable=True),
        sa.Column('broll_shots', sa.JSON(), nullable=True),

        # Stage 4: A-Roll
        sa.Column('aroll_paths', sa.JSON(), nullable=True),

        # Stage 5: B-Roll
        sa.Column('broll_paths', sa.JSON(), nullable=True),

        # Stage 6: Composition
        sa.Column('final_video_path', sa.String(1000), nullable=True),
        sa.Column('cost_usd', sa.Float(), nullable=True),

        # Candidate (regeneration)
        sa.Column('candidate_video_path', sa.String(1000), nullable=True),

        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),

        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('ugc_jobs')
