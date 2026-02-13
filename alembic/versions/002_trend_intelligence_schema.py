"""trend intelligence schema

Revision ID: 002
Revises: 001
Create Date: 2026-02-13 21:48:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # For SQLite: batch_alter_table with copy_from will recreate the table
    # We need to define table structure to copy from, removing old unique constraint
    with op.batch_alter_table('trends', recreate='always', copy_from=None) as batch_op:
        # Add new columns
        batch_op.add_column(sa.Column('description', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('duration', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('creator_id', sa.String(255), nullable=True))
        batch_op.add_column(sa.Column('sound_name', sa.String(500), nullable=True))
        batch_op.add_column(sa.Column('posted_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('engagement_velocity', sa.Float(), nullable=True))

        # Add composite unique constraint on (platform, external_id)
        # Note: The old unique constraint on external_id alone will be automatically
        # removed during table recreation
        batch_op.create_unique_constraint('uq_platform_external_id', ['platform', 'external_id'])

    # Create trend_reports table
    op.create_table('trend_reports',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('analyzed_count', sa.Integer(), nullable=False),
        sa.Column('date_range_start', sa.DateTime(timezone=True), nullable=False),
        sa.Column('date_range_end', sa.DateTime(timezone=True), nullable=False),
        sa.Column('video_styles', sa.JSON(), nullable=False),
        sa.Column('common_patterns', sa.JSON(), nullable=False),
        sa.Column('avg_engagement_velocity', sa.Float(), nullable=True),
        sa.Column('top_hashtags', sa.JSON(), nullable=True),
        sa.Column('recommendations', sa.JSON(), nullable=True),
        sa.Column('raw_report', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    # Drop trend_reports table
    op.drop_table('trend_reports')

    # Reverse changes to trends table
    with op.batch_alter_table('trends') as batch_op:
        # Drop composite unique constraint
        batch_op.drop_constraint('uq_platform_external_id', type_='unique')

        # Re-add old unique constraint on external_id
        batch_op.create_unique_constraint('uq_trends_external_id', ['external_id'])

        # Drop new columns
        batch_op.drop_column('engagement_velocity')
        batch_op.drop_column('posted_at')
        batch_op.drop_column('sound_name')
        batch_op.drop_column('creator_id')
        batch_op.drop_column('duration')
        batch_op.drop_column('description')
