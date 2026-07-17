"""Historical Analytics — metric_snapshots + history_settings.

Revision ID: hist_analytics_0001
Revises: bi_export_0001
Create Date: 2026-07-17
"""
import sqlalchemy as sa
from alembic import op

revision = 'hist_analytics_0001'
down_revision = 'bi_export_0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'metric_snapshots',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('organization_id', sa.UUID(), sa.ForeignKey('organizations.id'), nullable=False, index=True),
        sa.Column('snapshot_date', sa.Date(), nullable=False, index=True),
        sa.Column('metric', sa.String(length=50), nullable=False, index=True),
        sa.Column('value', sa.Numeric(18, 2), nullable=False, server_default='0'),
        sa.Column('granularity', sa.String(length=8), nullable=False, server_default='daily', index=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=True, server_default=sa.false()),
        sa.UniqueConstraint('organization_id', 'snapshot_date', 'metric', 'granularity', name='uq_metric_snapshot'),
    )
    op.create_index('ix_metric_snapshots_org_metric_date', 'metric_snapshots',
                    ['organization_id', 'metric', 'snapshot_date'])

    op.create_table(
        'history_settings',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('organization_id', sa.UUID(), sa.ForeignKey('organizations.id'), nullable=False, index=True),
        sa.Column('retention_days', sa.Integer(), nullable=False, server_default='730'),
        sa.Column('archive_enabled', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('capture_enabled', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=True, server_default=sa.false()),
        sa.UniqueConstraint('organization_id', name='uq_history_settings_org'),
    )


def downgrade() -> None:
    op.drop_table('history_settings')
    op.drop_index('ix_metric_snapshots_org_metric_date', table_name='metric_snapshots')
    op.drop_table('metric_snapshots')
