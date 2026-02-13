"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-02-13 21:09:45.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create jobs table
    op.create_table('jobs',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(length=50), nullable=False, server_default='pending'),
    sa.Column('stage', sa.String(length=50), nullable=True),
    sa.Column('theme', sa.String(length=255), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('error_message', sa.Text(), nullable=True),
    sa.Column('metadata', sa.JSON(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )

    # Create trends table
    op.create_table('trends',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('platform', sa.String(length=50), nullable=False),
    sa.Column('external_id', sa.String(length=255), nullable=False),
    sa.Column('title', sa.String(length=500), nullable=True),
    sa.Column('creator', sa.String(length=255), nullable=True),
    sa.Column('hashtags', sa.JSON(), nullable=True),
    sa.Column('views', sa.Integer(), nullable=True),
    sa.Column('likes', sa.Integer(), nullable=True),
    sa.Column('comments', sa.Integer(), nullable=True),
    sa.Column('shares', sa.Integer(), nullable=True),
    sa.Column('video_url', sa.String(length=1000), nullable=True),
    sa.Column('thumbnail_url', sa.String(length=1000), nullable=True),
    sa.Column('collected_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
    sa.Column('metadata', sa.JSON(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('external_id')
    )

    # Create scripts table
    op.create_table('scripts',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('job_id', sa.Integer(), nullable=True),
    sa.Column('video_prompt', sa.Text(), nullable=False),
    sa.Column('scenes', sa.JSON(), nullable=False),
    sa.Column('text_overlays', sa.JSON(), nullable=True),
    sa.Column('voiceover_script', sa.Text(), nullable=True),
    sa.Column('title', sa.String(length=500), nullable=True),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('hashtags', sa.JSON(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
    sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], ),
    sa.PrimaryKeyConstraint('id')
    )

    # Create videos table
    op.create_table('videos',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('job_id', sa.Integer(), nullable=True),
    sa.Column('script_id', sa.Integer(), nullable=True),
    sa.Column('status', sa.String(length=50), server_default='generated', nullable=True),
    sa.Column('file_path', sa.String(length=1000), nullable=True),
    sa.Column('thumbnail_path', sa.String(length=1000), nullable=True),
    sa.Column('duration_seconds', sa.Float(), nullable=True),
    sa.Column('cost_usd', sa.Float(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
    sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('published_url', sa.String(length=1000), nullable=True),
    sa.Column('metadata', sa.JSON(), nullable=True),
    sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], ),
    sa.ForeignKeyConstraint(['script_id'], ['scripts.id'], ),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('videos')
    op.drop_table('scripts')
    op.drop_table('trends')
    op.drop_table('jobs')
