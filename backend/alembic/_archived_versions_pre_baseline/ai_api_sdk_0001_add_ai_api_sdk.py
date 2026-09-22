"""AI API & SDK — developer API keys, public-API request ledger and signed
outbound AI webhooks (with retry/dead-letter deliveries).

Revision ID: ai_api_sdk_0001
Revises: ai_gov_0001
Create Date: 2026-07-23
"""
import sqlalchemy as sa
from alembic import op

revision = 'ai_api_sdk_0001'
down_revision = 'ai_gov_0001'
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
        'ai_api_keys',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('organization_id', sa.UUID(), sa.ForeignKey('organizations.id'), nullable=False, index=True),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('environment', sa.String(length=8), nullable=False, server_default='live'),
        sa.Column('key_prefix', sa.String(length=24), nullable=False, index=True),
        sa.Column('key_hash', sa.String(length=64), nullable=False),
        sa.Column('scopes', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('rate_limit_per_min', sa.Integer(), nullable=False, server_default='60'),
        sa.Column('daily_quota', sa.Integer(), nullable=False, server_default='1000'),
        sa.Column('allowed_providers', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('allowed_models', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('allowed_ips', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('use_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true(), index=True),
        sa.Column('created_by', sa.UUID(), sa.ForeignKey('users.id'), nullable=False),
        *_base_cols(),
        sa.UniqueConstraint('key_hash', name='uq_ai_api_key_hash'),
    )
    op.create_table(
        'ai_api_requests',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('organization_id', sa.UUID(), sa.ForeignKey('organizations.id'), nullable=False, index=True),
        sa.Column('api_key_id', sa.UUID(), sa.ForeignKey('ai_api_keys.id', ondelete='CASCADE'), nullable=True, index=True),
        sa.Column('endpoint', sa.String(length=80), nullable=False, index=True),
        sa.Column('method', sa.String(length=8), nullable=False, server_default='POST'),
        sa.Column('api_version', sa.String(length=8), nullable=False, server_default='v1'),
        sa.Column('status_code', sa.Integer(), nullable=False, server_default='200', index=True),
        sa.Column('latency_ms', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('cost_usd', sa.Numeric(10, 6), nullable=False, server_default='0'),
        sa.Column('provider', sa.String(length=20), nullable=True),
        sa.Column('model', sa.String(length=80), nullable=True),
        sa.Column('error', sa.String(length=300), nullable=True),
        *_base_cols(),
    )
    op.create_index('ix_ai_api_requests_key_created', 'ai_api_requests', ['api_key_id', 'created_at'])
    op.create_table(
        'ai_webhooks',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('organization_id', sa.UUID(), sa.ForeignKey('organizations.id'), nullable=False, index=True),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('url', sa.String(length=500), nullable=False),
        sa.Column('events', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('secret', sa.String(length=64), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true(), index=True),
        sa.Column('max_attempts', sa.Integer(), nullable=False, server_default='5'),
        sa.Column('delivered_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('failed_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_status', sa.String(length=16), nullable=True),
        sa.Column('last_delivery_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', sa.UUID(), sa.ForeignKey('users.id'), nullable=False),
        *_base_cols(),
    )
    op.create_table(
        'ai_webhook_deliveries',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('organization_id', sa.UUID(), sa.ForeignKey('organizations.id'), nullable=False, index=True),
        sa.Column('webhook_id', sa.UUID(), sa.ForeignKey('ai_webhooks.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('event_type', sa.String(length=60), nullable=False, index=True),
        sa.Column('payload', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('status', sa.String(length=16), nullable=False, server_default='pending', index=True),
        sa.Column('attempts', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('response_code', sa.Integer(), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.Column('next_retry_at', sa.DateTime(timezone=True), nullable=True, index=True),
        sa.Column('delivered_at', sa.DateTime(timezone=True), nullable=True),
        *_base_cols(),
    )


def downgrade() -> None:
    op.drop_table('ai_webhook_deliveries')
    op.drop_table('ai_webhooks')
    op.drop_index('ix_ai_api_requests_key_created', table_name='ai_api_requests')
    op.drop_table('ai_api_requests')
    op.drop_table('ai_api_keys')
