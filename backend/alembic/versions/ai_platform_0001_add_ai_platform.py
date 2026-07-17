"""AI Platform — settings, provider configs, prompt templates, conversations,
messages, usage logs, response cache.

Revision ID: ai_platform_0001
Revises: hist_analytics_0001
Create Date: 2026-07-17
"""
import sqlalchemy as sa
from alembic import op

revision = 'ai_platform_0001'
down_revision = 'hist_analytics_0001'
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
        'ai_settings',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('organization_id', sa.UUID(), sa.ForeignKey('organizations.id'), nullable=False, index=True),
        sa.Column('is_enabled', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('default_provider', sa.String(length=20), nullable=False, server_default='mock'),
        sa.Column('default_model', sa.String(length=80), nullable=False, server_default='mock-ai'),
        sa.Column('temperature', sa.Numeric(3, 2), nullable=False, server_default='0.7'),
        sa.Column('max_tokens', sa.Integer(), nullable=False, server_default='1024'),
        sa.Column('daily_request_limit', sa.Integer(), nullable=False, server_default='1000'),
        sa.Column('monthly_budget_usd', sa.Numeric(10, 2), nullable=False, server_default='100'),
        sa.Column('cache_enabled', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('cache_ttl_minutes', sa.Integer(), nullable=False, server_default='60'),
        sa.Column('streaming_enabled', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('memory_messages', sa.Integer(), nullable=False, server_default='10'),
        sa.Column('context_max_chars', sa.Integer(), nullable=False, server_default='4000'),
        *_base_cols(),
        sa.UniqueConstraint('organization_id', name='uq_ai_settings_org'),
    )

    op.create_table(
        'ai_provider_configs',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('organization_id', sa.UUID(), sa.ForeignKey('organizations.id'), nullable=False, index=True),
        sa.Column('provider', sa.String(length=20), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('api_key', sa.String(length=300), nullable=True),
        sa.Column('base_url', sa.String(length=300), nullable=True),
        sa.Column('deployment', sa.String(length=120), nullable=True),
        sa.Column('api_version', sa.String(length=40), nullable=True),
        sa.Column('default_model', sa.String(length=80), nullable=False),
        sa.Column('models', sa.JSON(), nullable=True),
        sa.Column('priority', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true(), index=True),
        sa.Column('created_by', sa.UUID(), sa.ForeignKey('users.id'), nullable=False),
        *_base_cols(),
    )

    op.create_table(
        'ai_prompt_templates',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('organization_id', sa.UUID(), sa.ForeignKey('organizations.id'), nullable=False, index=True),
        sa.Column('key', sa.String(length=60), nullable=False),
        sa.Column('name', sa.String(length=150), nullable=False),
        sa.Column('task_type', sa.String(length=30), nullable=False, server_default='general', index=True),
        sa.Column('system_prompt', sa.Text(), nullable=True),
        sa.Column('template', sa.Text(), nullable=False),
        sa.Column('model_override', sa.String(length=80), nullable=True),
        sa.Column('provider_override', sa.String(length=20), nullable=True),
        sa.Column('temperature', sa.Numeric(3, 2), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('is_builtin', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('usage_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_by', sa.UUID(), sa.ForeignKey('users.id'), nullable=True),
        *_base_cols(),
        sa.UniqueConstraint('organization_id', 'key', name='uq_ai_template_org_key'),
    )

    op.create_table(
        'ai_conversations',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('organization_id', sa.UUID(), sa.ForeignKey('organizations.id'), nullable=False, index=True),
        sa.Column('user_id', sa.UUID(), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('title', sa.String(length=200), nullable=False, server_default='New conversation'),
        sa.Column('context_type', sa.String(length=20), nullable=True),
        sa.Column('context_id', sa.String(length=64), nullable=True),
        sa.Column('message_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_message_at', sa.DateTime(timezone=True), nullable=True),
        *_base_cols(),
    )

    op.create_table(
        'ai_messages',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('organization_id', sa.UUID(), sa.ForeignKey('organizations.id'), nullable=False, index=True),
        sa.Column('conversation_id', sa.UUID(), sa.ForeignKey('ai_conversations.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('role', sa.String(length=12), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('model', sa.String(length=80), nullable=True),
        sa.Column('provider', sa.String(length=20), nullable=True),
        sa.Column('tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('cost_usd', sa.Numeric(10, 6), nullable=False, server_default='0'),
        *_base_cols(),
    )

    op.create_table(
        'ai_usage_logs',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('organization_id', sa.UUID(), sa.ForeignKey('organizations.id'), nullable=False, index=True),
        sa.Column('user_id', sa.UUID(), sa.ForeignKey('users.id'), nullable=True, index=True),
        sa.Column('provider', sa.String(length=20), nullable=False, index=True),
        sa.Column('model', sa.String(length=80), nullable=False),
        sa.Column('task_type', sa.String(length=30), nullable=False, server_default='general', index=True),
        sa.Column('template_key', sa.String(length=60), nullable=True),
        sa.Column('status', sa.String(length=12), nullable=False, server_default='success', index=True),
        sa.Column('prompt_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('completion_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('cost_usd', sa.Numeric(10, 6), nullable=False, server_default='0'),
        sa.Column('latency_ms', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('cache_hit', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('fallback_from', sa.String(length=20), nullable=True),
        sa.Column('error', sa.String(length=500), nullable=True),
        *_base_cols(),
    )

    op.create_table(
        'ai_cache',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('organization_id', sa.UUID(), sa.ForeignKey('organizations.id'), nullable=False, index=True),
        sa.Column('cache_key', sa.String(length=64), nullable=False, index=True),
        sa.Column('provider', sa.String(length=20), nullable=False),
        sa.Column('model', sa.String(length=80), nullable=False),
        sa.Column('response_text', sa.Text(), nullable=False),
        sa.Column('prompt_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('completion_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('hits', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True, index=True),
        *_base_cols(),
        sa.UniqueConstraint('organization_id', 'cache_key', name='uq_ai_cache_org_key'),
    )


def downgrade() -> None:
    for t in ('ai_cache', 'ai_usage_logs', 'ai_messages', 'ai_conversations',
              'ai_prompt_templates', 'ai_provider_configs', 'ai_settings'):
        op.drop_table(t)
