"""Export & BI Integration — bi_tokens + bi_settings + export_jobs + bi_sync_configs.

Revision ID: bi_export_0001
Revises: sched_reports_0001
Create Date: 2026-07-17
"""
import sqlalchemy as sa
from alembic import op

revision = 'bi_export_0001'
down_revision = 'sched_reports_0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'bi_tokens',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('organization_id', sa.UUID(), sa.ForeignKey('organizations.id'), nullable=False, index=True),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('token', sa.String(length=64), nullable=False, unique=True, index=True),
        sa.Column('datasets', sa.JSON(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true(), index=True),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('use_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_by', sa.UUID(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=True, server_default=sa.false()),
    )

    op.create_table(
        'bi_settings',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('organization_id', sa.UUID(), sa.ForeignKey('organizations.id'), nullable=False, index=True),
        sa.Column('storage_provider', sa.String(length=12), nullable=False, server_default='local'),
        sa.Column('s3_bucket', sa.String(length=200), nullable=True),
        sa.Column('s3_region', sa.String(length=50), nullable=True),
        sa.Column('s3_access_key', sa.String(length=200), nullable=True),
        sa.Column('s3_secret_key', sa.String(length=200), nullable=True),
        sa.Column('s3_prefix', sa.String(length=200), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=True, server_default=sa.false()),
        sa.UniqueConstraint('organization_id', name='uq_bi_settings_org'),
    )

    op.create_table(
        'export_jobs',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('organization_id', sa.UUID(), sa.ForeignKey('organizations.id'), nullable=False, index=True),
        sa.Column('kind', sa.String(length=12), nullable=False, index=True),
        sa.Column('source_type', sa.String(length=12), nullable=False, server_default='dataset'),
        sa.Column('source_key', sa.String(length=64), nullable=False),
        sa.Column('format', sa.String(length=8), nullable=False, server_default='csv'),
        sa.Column('target', sa.String(length=500), nullable=True),
        sa.Column('status', sa.String(length=12), nullable=False, server_default='success', index=True),
        sa.Column('rows', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('size_bytes', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('error', sa.String(length=500), nullable=True),
        sa.Column('detail', sa.JSON(), nullable=True),
        sa.Column('created_by', sa.UUID(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=True, server_default=sa.false()),
    )

    op.create_table(
        'bi_sync_configs',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('organization_id', sa.UUID(), sa.ForeignKey('organizations.id'), nullable=False, index=True),
        sa.Column('name', sa.String(length=150), nullable=False),
        sa.Column('source_type', sa.String(length=12), nullable=False, server_default='dataset'),
        sa.Column('source_key', sa.String(length=64), nullable=False),
        sa.Column('format', sa.String(length=8), nullable=False, server_default='json'),
        sa.Column('destination', sa.String(length=12), nullable=False, server_default='webhook'),
        sa.Column('target_url', sa.String(length=500), nullable=True),
        sa.Column('path_prefix', sa.String(length=200), nullable=True),
        sa.Column('mode', sa.String(length=12), nullable=False, server_default='full'),
        sa.Column('last_cursor', sa.String(length=40), nullable=True),
        sa.Column('frequency', sa.String(length=12), nullable=False, server_default='daily'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true(), index=True),
        sa.Column('next_run_at', sa.DateTime(timezone=True), nullable=True, index=True),
        sa.Column('last_run_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_status', sa.String(length=12), nullable=True),
        sa.Column('run_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_by', sa.UUID(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=True, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_table('bi_sync_configs')
    op.drop_table('export_jobs')
    op.drop_table('bi_settings')
    op.drop_table('bi_tokens')
