"""Integration Hub — per-org connections across every category, the call/health
log, and inbound webhook events.

Revision ID: integration_hub_0001
Revises: ai_api_sdk_0001
Create Date: 2026-07-24
"""
import sqlalchemy as sa
from alembic import op

revision = 'integration_hub_0001'
down_revision = 'ai_api_sdk_0001'
branch_labels = None
depends_on = None


def _base_cols():
    return [
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=True, server_default=sa.false()),
    ]


def upgrade() -> None:
    op.create_table(
        'integrations',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('organization_id', sa.UUID(), sa.ForeignKey('organizations.id'), nullable=False, index=True),
        sa.Column('category', sa.String(length=24), nullable=False, index=True),
        sa.Column('provider', sa.String(length=40), nullable=False, index=True),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('environment', sa.String(length=10), nullable=False, server_default='live'),
        sa.Column('auth_type', sa.String(length=12), nullable=False, server_default='api_key'),
        sa.Column('credentials', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('config', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('is_enabled', sa.Boolean(), nullable=False, server_default=sa.true(), index=True),
        sa.Column('is_managed_elsewhere', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('managed_by', sa.String(length=40), nullable=True),
        sa.Column('status', sa.String(length=12), nullable=False, server_default='unconfigured', index=True),
        sa.Column('last_check_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_success_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_error', sa.String(length=500), nullable=True),
        sa.Column('consecutive_failures', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('latency_ms', sa.Integer(), nullable=True),
        sa.Column('max_attempts', sa.Integer(), nullable=False, server_default='3'),
        sa.Column('retry_backoff_seconds', sa.Integer(), nullable=False, server_default='2'),
        sa.Column('timeout_seconds', sa.Integer(), nullable=False, server_default='15'),
        sa.Column('fallback_integration_id', sa.UUID(),
                  sa.ForeignKey('integrations.id', ondelete='SET NULL'), nullable=True),
        sa.Column('inbound_token', sa.String(length=64), nullable=True, index=True),
        sa.Column('inbound_secret', sa.String(length=64), nullable=True),
        sa.Column('total_calls', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('failed_calls', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_by', sa.UUID(), sa.ForeignKey('users.id'), nullable=False),
        *_base_cols(),
    )
    op.create_index('ix_integrations_org_category', 'integrations', ['organization_id', 'category'])

    op.create_table(
        'integration_logs',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('organization_id', sa.UUID(), sa.ForeignKey('organizations.id'), nullable=False, index=True),
        sa.Column('integration_id', sa.UUID(), sa.ForeignKey('integrations.id', ondelete='CASCADE'),
                  nullable=False, index=True),
        sa.Column('operation', sa.String(length=40), nullable=False, index=True),
        sa.Column('method', sa.String(length=8), nullable=True),
        sa.Column('endpoint', sa.String(length=300), nullable=True),
        sa.Column('status', sa.String(length=12), nullable=False, server_default='success', index=True),
        sa.Column('status_code', sa.Integer(), nullable=True),
        sa.Column('attempts', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('latency_ms', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('fallback_from_id', sa.UUID(), nullable=True),
        sa.Column('request_summary', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('actor_user_id', sa.UUID(), sa.ForeignKey('users.id'), nullable=True),
        *_base_cols(),
    )
    op.create_index('ix_integration_logs_int_created', 'integration_logs', ['integration_id', 'created_at'])

    op.create_table(
        'integration_events',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('organization_id', sa.UUID(), sa.ForeignKey('organizations.id'), nullable=False, index=True),
        sa.Column('integration_id', sa.UUID(), sa.ForeignKey('integrations.id', ondelete='CASCADE'),
                  nullable=False, index=True),
        sa.Column('event_type', sa.String(length=80), nullable=False, server_default='inbound', index=True),
        sa.Column('payload', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('signature_valid', sa.Boolean(), nullable=True),
        sa.Column('processed', sa.Boolean(), nullable=False, server_default=sa.false(), index=True),
        sa.Column('forwarded_event_id', sa.UUID(), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('received_at', sa.DateTime(timezone=True), nullable=False),
        *_base_cols(),
    )


def downgrade() -> None:
    op.drop_table('integration_events')
    op.drop_index('ix_integration_logs_int_created', table_name='integration_logs')
    op.drop_table('integration_logs')
    op.drop_index('ix_integrations_org_category', table_name='integrations')
    op.drop_table('integrations')
