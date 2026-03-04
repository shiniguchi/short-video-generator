"""Add broll_include_creator boolean to ugc_jobs

Revision ID: 015
Revises: 014
"""
from alembic import op
import sqlalchemy as sa

revision = "015"
down_revision = "014"


def upgrade():
    op.add_column("ugc_jobs", sa.Column("broll_include_creator", sa.Boolean(), server_default="false", nullable=False))


def downgrade():
    op.drop_column("ugc_jobs", "broll_include_creator")
