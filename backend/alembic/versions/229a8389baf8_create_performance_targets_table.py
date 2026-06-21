"""create_performance_targets_table

Revision ID: 229a8389baf8
Revises: de12acbf9d3a
Create Date: 2026-06-21 11:35:32.380643

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '229a8389baf8'
down_revision: Union[str, Sequence[str], None] = 'de12acbf9d3a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'performance_targets',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('target_type', sa.Enum('DAILY', 'WEEKLY', 'MONTHLY', 'QUARTERLY', 'YEARLY', name='targettype', native_enum=False), nullable=False),
        sa.Column('metric_type', sa.Enum('CALLS_MADE', 'LEADS_CONVERTED', name='metrictype', native_enum=False), nullable=False),
        sa.Column('target_value', sa.Integer(), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='false'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_performance_targets_organization_id'), 'performance_targets', ['organization_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_performance_targets_organization_id'), table_name='performance_targets')
    op.drop_table('performance_targets')
