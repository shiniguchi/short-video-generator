"""Add video history columns for A-Roll and B-Roll clips.

Revision ID: 016
"""
from alembic import op
import sqlalchemy as sa

revision = "016"
down_revision = "015"


def upgrade():
    op.add_column("ugc_jobs", sa.Column("aroll_video_history", sa.JSON(), nullable=True))
    op.add_column("ugc_jobs", sa.Column("broll_video_history", sa.JSON(), nullable=True))


def downgrade():
    op.drop_column("ugc_jobs", "broll_video_history")
    op.drop_column("ugc_jobs", "aroll_video_history")
