"""lp integration schema

Revision ID: 007
Revises: 006
Create Date: 2026-02-21

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '007'
down_revision: Union[str, None] = '006'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('landing_pages', sa.Column('ugc_job_id', sa.Integer(), sa.ForeignKey('ugc_jobs.id'), nullable=True))
    op.add_column('landing_pages', sa.Column('lp_module_approvals', sa.JSON(), nullable=True))
    op.add_column('landing_pages', sa.Column('lp_hero_image_path', sa.String(1000), nullable=True))
    op.add_column('landing_pages', sa.Column('lp_hero_candidate_path', sa.String(1000), nullable=True))
    op.add_column('landing_pages', sa.Column('lp_review_locked', sa.Boolean(), nullable=True, server_default='true'))
    op.add_column('landing_pages', sa.Column('lp_copy', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('landing_pages', 'lp_copy')
    op.drop_column('landing_pages', 'lp_review_locked')
    op.drop_column('landing_pages', 'lp_hero_candidate_path')
    op.drop_column('landing_pages', 'lp_hero_image_path')
    op.drop_column('landing_pages', 'lp_module_approvals')
    op.drop_column('landing_pages', 'ugc_job_id')
