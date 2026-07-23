"""AI Prompt Studio — authoring overlay on ai_prompt_templates (version/status/
description/variables/tags/review fields) + immutable version-history table.

Revision ID: prompt_studio_0001
Revises: rec_engine_0001
Create Date: 2026-07-23
"""
import sqlalchemy as sa
from alembic import op

revision = 'prompt_studio_0001'
down_revision = 'rec_engine_0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('ai_prompt_templates', sa.Column('version', sa.Integer(), nullable=False, server_default='1'))
    op.add_column('ai_prompt_templates', sa.Column('status', sa.String(length=20), nullable=False, server_default='approved'))
    op.add_column('ai_prompt_templates', sa.Column('description', sa.Text(), nullable=True))
    op.add_column('ai_prompt_templates', sa.Column('variables', sa.JSON(), nullable=False, server_default='[]'))
    op.add_column('ai_prompt_templates', sa.Column('tags', sa.JSON(), nullable=False, server_default='[]'))
    op.add_column('ai_prompt_templates', sa.Column('updated_by', sa.UUID(), sa.ForeignKey('users.id'), nullable=True))
    op.add_column('ai_prompt_templates', sa.Column('reviewed_by', sa.UUID(), sa.ForeignKey('users.id'), nullable=True))
    op.add_column('ai_prompt_templates', sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('ai_prompt_templates', sa.Column('review_note', sa.Text(), nullable=True))
    op.add_column('ai_prompt_templates', sa.Column('last_tested_at', sa.DateTime(timezone=True), nullable=True))
    op.create_index('ix_ai_prompt_templates_status', 'ai_prompt_templates', ['status'])

    op.create_table(
        'ai_prompt_template_versions',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('organization_id', sa.UUID(), sa.ForeignKey('organizations.id'), nullable=False, index=True),
        sa.Column('template_id', sa.UUID(), sa.ForeignKey('ai_prompt_templates.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=150), nullable=False),
        sa.Column('task_type', sa.String(length=30), nullable=False),
        sa.Column('system_prompt', sa.Text(), nullable=True),
        sa.Column('template', sa.Text(), nullable=False),
        sa.Column('model_override', sa.String(length=80), nullable=True),
        sa.Column('provider_override', sa.String(length=20), nullable=True),
        sa.Column('temperature', sa.Numeric(3, 2), nullable=True),
        sa.Column('edited_by', sa.UUID(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('change_note', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=True, server_default=sa.false()),
        sa.UniqueConstraint('template_id', 'version', name='uq_ai_prompt_version'),
    )


def downgrade() -> None:
    op.drop_table('ai_prompt_template_versions')
    op.drop_index('ix_ai_prompt_templates_status', table_name='ai_prompt_templates')
    for col in ('last_tested_at', 'review_note', 'reviewed_at', 'reviewed_by', 'updated_by',
                'tags', 'variables', 'description', 'status', 'version'):
        op.drop_column('ai_prompt_templates', col)
