"""Add lp_section_images column to landing_pages

Revision ID: 013
Revises: 012
"""
from alembic import op
import sqlalchemy as sa

revision = "013"
down_revision = "012"


def upgrade():
    op.add_column("landing_pages", sa.Column("lp_section_images", sa.JSON(), nullable=True))


def downgrade():
    op.drop_column("landing_pages", "lp_section_images")
