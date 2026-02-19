"""waitlist collection schema

Revision ID: 004
Revises: 003
Create Date: 2026-02-19

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '004'
down_revision: Union[str, None] = '003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'waitlist_entries',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('lp_source', sa.String(50), nullable=True),
        sa.Column('signed_up_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email', name='uq_waitlist_email'),
    )


def downgrade() -> None:
    op.drop_table('waitlist_entries')
