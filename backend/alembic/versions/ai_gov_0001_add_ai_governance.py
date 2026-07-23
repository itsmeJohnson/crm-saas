"""AI Security & Governance — org policy (PII/injection/content/model
restrictions/usage) + governance event compliance log.

Revision ID: ai_gov_0001
Revises: prompt_studio_0001
Create Date: 2026-07-23
"""
import sqlalchemy as sa
from alembic import op

revision = 'ai_gov_0001'
down_revision = 'prompt_studio_0001'
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
        'ai_governance_policies',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('organization_id', sa.UUID(), sa.ForeignKey('organizations.id'), nullable=False, index=True),
        sa.Column('is_enabled', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('pii_detection', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('pii_action', sa.String(length=10), nullable=False, server_default='mask'),
        sa.Column('pii_types', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('injection_protection', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('injection_action', sa.String(length=10), nullable=False, server_default='block'),
        sa.Column('content_filter', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('blocked_terms', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('allowed_providers', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('allowed_models', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('role_restrictions', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('max_prompt_chars', sa.Integer(), nullable=False, server_default='100000'),
        sa.Column('require_grounding', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('log_prompt_snippets', sa.Boolean(), nullable=False, server_default=sa.true()),
        *_base_cols(),
        sa.UniqueConstraint('organization_id', name='uq_ai_gov_policy_org'),
    )
    op.create_table(
        'ai_governance_events',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('organization_id', sa.UUID(), sa.ForeignKey('organizations.id'), nullable=False, index=True),
        sa.Column('user_id', sa.UUID(), sa.ForeignKey('users.id'), nullable=True, index=True),
        sa.Column('event_type', sa.String(length=30), nullable=False, index=True),
        sa.Column('action_taken', sa.String(length=10), nullable=False, index=True),
        sa.Column('rule', sa.String(length=80), nullable=True),
        sa.Column('task_type', sa.String(length=30), nullable=True),
        sa.Column('provider', sa.String(length=20), nullable=True),
        sa.Column('model', sa.String(length=80), nullable=True),
        sa.Column('findings', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('prompt_snippet', sa.Text(), nullable=True),
        *_base_cols(),
    )


def downgrade() -> None:
    op.drop_table('ai_governance_events')
    op.drop_table('ai_governance_policies')
