"""Native mobile push tokens (FCM/APNS) — Gap A for the mobile platform.
Parallel to push_subscriptions (Web Push); the notification dispatcher fans out
to both. Reuses NotificationService — no new dispatch logic.

Revision ID: device_tokens_0001
Revises: sms_priority_0001
Create Date: 2026-07-26
"""
import sqlalchemy as sa
from alembic import op

revision = 'device_tokens_0001'
down_revision = 'sms_priority_0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'device_tokens',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('organization_id', sa.UUID(), sa.ForeignKey('organizations.id'), nullable=False, index=True),
        sa.Column('user_id', sa.UUID(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('token', sa.Text(), nullable=False),
        sa.Column('platform', sa.String(length=10), nullable=False),
        sa.Column('device_name', sa.String(length=120), nullable=True),
        sa.Column('is_active_token', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=True, server_default=sa.false()),
        sa.UniqueConstraint('user_id', 'token', name='uq_device_token_user_token'),
    )


def downgrade() -> None:
    op.drop_table('device_tokens')
