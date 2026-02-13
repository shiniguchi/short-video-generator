"""content generation schema

Revision ID: 003
Revises: 002
Create Date: 2026-02-13 23:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '003'
down_revision: Union[str, None] = '002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add Phase 3 content generation columns to scripts table
    with op.batch_alter_table('scripts') as batch_op:
        batch_op.add_column(sa.Column('duration_target', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('aspect_ratio', sa.String(10), nullable=True, server_default='9:16'))
        batch_op.add_column(sa.Column('hook_text', sa.String(500), nullable=True))
        batch_op.add_column(sa.Column('cta_text', sa.String(500), nullable=True))
        batch_op.add_column(sa.Column('theme_config', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('trend_report_id', sa.Integer(), nullable=True))

        # Add foreign key constraint to trend_reports
        batch_op.create_foreign_key(
            'fk_scripts_trend_report_id',
            'trend_reports',
            ['trend_report_id'],
            ['id']
        )


def downgrade() -> None:
    # Remove Phase 3 columns from scripts table
    with op.batch_alter_table('scripts') as batch_op:
        # Drop foreign key first
        batch_op.drop_constraint('fk_scripts_trend_report_id', type_='foreignkey')

        # Drop columns
        batch_op.drop_column('trend_report_id')
        batch_op.drop_column('theme_config')
        batch_op.drop_column('cta_text')
        batch_op.drop_column('hook_text')
        batch_op.drop_column('aspect_ratio')
        batch_op.drop_column('duration_target')
