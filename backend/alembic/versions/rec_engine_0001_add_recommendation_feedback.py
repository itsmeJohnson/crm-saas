"""AI Recommendation Engine — recommendation feedback log backing the feedback
loop (dismiss/accept/snooze) and recommendation analytics.

Revision ID: rec_engine_0001
Revises: doc_intel_0001
Create Date: 2026-07-22
"""
import sqlalchemy as sa
from alembic import op

revision = 'rec_engine_0001'
down_revision = 'doc_intel_0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'recommendation_feedback',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('organization_id', sa.UUID(), sa.ForeignKey('organizations.id'), nullable=False, index=True),
        sa.Column('user_id', sa.UUID(), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('rec_type', sa.String(length=30), nullable=False, index=True),
        sa.Column('rec_key', sa.String(length=200), nullable=False, index=True),
        sa.Column('target_type', sa.String(length=30), nullable=True),
        sa.Column('target_id', sa.String(length=64), nullable=True, index=True),
        sa.Column('title', sa.String(length=300), nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('score', sa.Float(), nullable=False, server_default='0'),
        sa.Column('rank', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('payload', sa.JSON(), nullable=False, server_default='{}'),
        sa.Column('action', sa.String(length=16), nullable=False, server_default='pending', index=True),
        sa.Column('acted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('snooze_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=True, server_default=sa.false()),
    )
    op.create_index('ix_rec_feedback_user_key', 'recommendation_feedback', ['user_id', 'rec_key'])


def downgrade() -> None:
    op.drop_index('ix_rec_feedback_user_key', table_name='recommendation_feedback')
    op.drop_table('recommendation_feedback')
