"""Add template_key column to landing_pages

Revision ID: 012
Revises: 011
"""
from alembic import op
import sqlalchemy as sa

revision = "012"
down_revision = "011"


def upgrade():
    op.add_column("landing_pages", sa.Column("template_key", sa.String(50), nullable=True))


def downgrade():
    op.drop_column("landing_pages", "template_key")
