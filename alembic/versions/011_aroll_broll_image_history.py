"""Add aroll/broll image history columns

Revision ID: 011
Revises: 010
"""
from alembic import op
import sqlalchemy as sa

revision = "011"
down_revision = "010"


def upgrade():
    op.add_column("ugc_jobs", sa.Column("aroll_image_history", sa.JSON(), nullable=True))
    op.add_column("ugc_jobs", sa.Column("broll_image_history", sa.JSON(), nullable=True))


def downgrade():
    op.drop_column("ugc_jobs", "broll_image_history")
    op.drop_column("ugc_jobs", "aroll_image_history")
