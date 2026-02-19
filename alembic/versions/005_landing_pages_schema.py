"""landing pages schema

Revision ID: 039d14368a2d
Revises: 004
Create Date: 2026-02-19

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '039d14368a2d'
down_revision: Union[str, None] = '004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'landing_pages',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('run_id', sa.String(50), nullable=False),
        sa.Column('product_idea', sa.String(500), nullable=False),
        sa.Column('target_audience', sa.String(500), nullable=True),
        sa.Column('html_path', sa.String(1000), nullable=True),
        sa.Column('status', sa.String(50), server_default='generated'),
        sa.Column('color_scheme_source', sa.String(50), nullable=True),
        sa.Column('sections', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('deployed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deployed_url', sa.String(1000), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('run_id', name='uq_lp_run_id'),
    )


def downgrade() -> None:
    op.drop_table('landing_pages')
