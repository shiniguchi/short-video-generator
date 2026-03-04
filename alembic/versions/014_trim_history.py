"""Add trim_history JSON column to ugc_jobs for multi-undo

Revision ID: 014
Revises: 013
"""
from alembic import op
import sqlalchemy as sa

revision = "014"
down_revision = "013"


def upgrade():
    op.add_column("ugc_jobs", sa.Column("trim_history", sa.JSON(), nullable=True))


def downgrade():
    op.drop_column("ugc_jobs", "trim_history")
