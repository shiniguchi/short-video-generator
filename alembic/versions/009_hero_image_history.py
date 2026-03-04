"""hero image history

Revision ID: 009
Revises: 008
Create Date: 2026-02-22

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '009'
down_revision: Union[str, None] = '008'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('ugc_jobs', sa.Column('hero_image_history', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('ugc_jobs', 'hero_image_history')
