"""Custom Report Builder — report definitions + versions.

Revision ID: report_builder_0001
Revises: exec_dashboard_0001
Create Date: 2026-07-07
"""
import sqlalchemy as sa
from alembic import op

revision = 'report_builder_0001'
down_revision = 'exec_dashboard_0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'report_definitions',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('organization_id', sa.UUID(), sa.ForeignKey('organizations.id'), nullable=False, index=True),
        sa.Column('name', sa.String(length=150), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('dataset', sa.String(length=40), nullable=False),
        sa.Column('columns', sa.JSON(), nullable=False),
        sa.Column('filters', sa.JSON(), nullable=True),
        sa.Column('group_by', sa.JSON(), nullable=True),
        sa.Column('sort', sa.JSON(), nullable=True),
        sa.Column('calculated_fields', sa.JSON(), nullable=True),
        sa.Column('pivot', sa.JSON(), nullable=True),
        sa.Column('chart', sa.JSON(), nullable=True),
        sa.Column('is_template', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('visibility', sa.String(length=16), nullable=False, server_default='private'),
        sa.Column('pinned_to_dashboard', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('schedule_frequency', sa.String(length=12), nullable=True),
        sa.Column('schedule_recipients', sa.JSON(), nullable=True),
        sa.Column('next_run', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_run', sa.DateTime(timezone=True), nullable=True),
        sa.Column('run_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('created_by', sa.UUID(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=True, server_default=sa.false()),
    )
    op.create_index('ix_report_definitions_org_dataset', 'report_definitions', ['organization_id', 'dataset'])

    op.create_table(
        'report_versions',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('organization_id', sa.UUID(), sa.ForeignKey('organizations.id'), nullable=False, index=True),
        sa.Column('report_id', sa.UUID(), sa.ForeignKey('report_definitions.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('version_no', sa.Integer(), nullable=False),
        sa.Column('snapshot', sa.JSON(), nullable=False),
        sa.Column('note', sa.String(length=200), nullable=True),
        sa.Column('created_by', sa.UUID(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=True, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_table('report_versions')
    op.drop_index('ix_report_definitions_org_dataset', table_name='report_definitions')
    op.drop_table('report_definitions')
