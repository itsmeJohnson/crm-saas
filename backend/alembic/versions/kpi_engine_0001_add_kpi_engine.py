"""KPI Engine — kpi_definitions + kpi_alerts.

Revision ID: kpi_engine_0001
Revises: financial_analytics_0001
Create Date: 2026-07-16
"""
import sqlalchemy as sa
from alembic import op

revision = 'kpi_engine_0001'
down_revision = 'financial_analytics_0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'kpi_definitions',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('organization_id', sa.UUID(), sa.ForeignKey('organizations.id'), nullable=False, index=True),
        sa.Column('name', sa.String(length=150), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('category', sa.String(length=24), nullable=False, server_default='custom'),
        sa.Column('metric', sa.String(length=50), nullable=False),
        sa.Column('unit', sa.String(length=12), nullable=False, server_default='count'),
        sa.Column('comparison', sa.String(length=16), nullable=False, server_default='higher_better'),
        sa.Column('target_value', sa.Numeric(16, 2), nullable=False, server_default='0'),
        sa.Column('warning_value', sa.Numeric(16, 2), nullable=True),
        sa.Column('critical_value', sa.Numeric(16, 2), nullable=True),
        sa.Column('manual_value', sa.Numeric(16, 2), nullable=True),
        sa.Column('window_days', sa.Integer(), nullable=False, server_default='30'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('notify', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('notify_roles', sa.JSON(), nullable=True),
        sa.Column('created_by', sa.UUID(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=True, server_default=sa.false()),
    )
    op.create_index('ix_kpi_definitions_org_active', 'kpi_definitions', ['organization_id', 'is_active'])

    op.create_table(
        'kpi_alerts',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('organization_id', sa.UUID(), sa.ForeignKey('organizations.id'), nullable=False, index=True),
        sa.Column('kpi_id', sa.UUID(), sa.ForeignKey('kpi_definitions.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('status', sa.String(length=12), nullable=False, server_default='warning'),
        sa.Column('value', sa.Numeric(16, 2), nullable=False),
        sa.Column('target_value', sa.Numeric(16, 2), nullable=False, server_default='0'),
        sa.Column('message', sa.String(length=300), nullable=True),
        sa.Column('resolved', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('notified', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=True, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_table('kpi_alerts')
    op.drop_index('ix_kpi_definitions_org_active', table_name='kpi_definitions')
    op.drop_table('kpi_definitions')
