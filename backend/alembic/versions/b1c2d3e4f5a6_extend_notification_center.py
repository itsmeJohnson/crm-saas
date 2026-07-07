"""extend notification center: notifications columns + preferences + push subscriptions

Revision ID: b1c2d3e4f5a6
Revises: a0b1c2d3e4f5
Create Date: 2026-07-03 22:00:00.000000
"""
import sqlalchemy as sa
from alembic import op

revision = 'b1c2d3e4f5a6'
down_revision = 'a0b1c2d3e4f5'
branch_labels = None
depends_on = None


def _audit():
    return [
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=True),
    ]


def upgrade() -> None:
    op.add_column('notifications', sa.Column('priority', sa.String(length=20), nullable=False, server_default='normal'))
    op.add_column('notifications', sa.Column('is_dismissed', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('notifications', sa.Column('dismissed_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('notifications', sa.Column('actions', sa.JSON(), nullable=True))       # [{label,url,style}]
    op.add_column('notifications', sa.Column('channels_sent', sa.JSON(), nullable=True))  # ["in_app","email",...]
    op.create_index('ix_notifications_priority', 'notifications', ['priority'])
    op.create_index('ix_notifications_category', 'notifications', ['category'])
    op.create_index('ix_notifications_is_dismissed', 'notifications', ['is_dismissed'])

    op.create_table(
        'notification_preferences',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('category', sa.String(length=50), nullable=False),
        sa.Column('in_app', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('email', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('sms', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('whatsapp', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('push', sa.Boolean(), nullable=False, server_default=sa.false()),
        *_audit(),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'category', name='uq_notif_pref_user_category'),
    )
    op.create_index('ix_notification_preferences_user_id', 'notification_preferences', ['user_id'])
    op.create_index('ix_notification_preferences_organization_id', 'notification_preferences', ['organization_id'])

    op.create_table(
        'push_subscriptions',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('endpoint', sa.Text(), nullable=False),
        sa.Column('p256dh', sa.String(length=255), nullable=True),
        sa.Column('auth', sa.String(length=255), nullable=True),
        sa.Column('user_agent', sa.String(length=255), nullable=True),
        *_audit(),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'endpoint', name='uq_push_sub_user_endpoint'),
    )
    op.create_index('ix_push_subscriptions_user_id', 'push_subscriptions', ['user_id'])
    op.create_index('ix_push_subscriptions_organization_id', 'push_subscriptions', ['organization_id'])


def downgrade() -> None:
    op.drop_table('push_subscriptions')
    op.drop_table('notification_preferences')
    op.drop_index('ix_notifications_is_dismissed', table_name='notifications')
    op.drop_index('ix_notifications_category', table_name='notifications')
    op.drop_index('ix_notifications_priority', table_name='notifications')
    for col in ('channels_sent', 'actions', 'dismissed_at', 'is_dismissed', 'priority'):
        op.drop_column('notifications', col)
