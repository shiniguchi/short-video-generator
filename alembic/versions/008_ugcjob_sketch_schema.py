"""ugcjob sketch schema

Revision ID: 008
Revises: 007
Create Date: 2026-02-22

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '008'
down_revision: Union[str, None] = '007'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('ugc_jobs', sa.Column('hero_sketch_path', sa.String(1000), nullable=True))


def downgrade() -> None:
    op.drop_column('ugc_jobs', 'hero_sketch_path')
