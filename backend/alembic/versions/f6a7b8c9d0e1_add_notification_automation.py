"""add notification automation: notification_rules + notification_deliveries
+ notification_digest_items

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-07-06 12:00:00.000000
"""
import sqlalchemy as sa
from alembic import op

revision = 'notif_auto_0001'
down_revision = 'scheduler_0001'
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
    op.create_table(
        'notification_rules',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(length=150), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('trigger_event', sa.String(length=80), nullable=False),
        sa.Column('entity_type', sa.String(length=40), nullable=True),
        sa.Column('conditions', sa.JSON(), nullable=True),
        sa.Column('recipients', sa.JSON(), nullable=False),
        sa.Column('channels', sa.JSON(), nullable=False),
        sa.Column('template_key', sa.String(length=100), nullable=True),
        sa.Column('title', sa.String(length=255), nullable=True),
        sa.Column('body', sa.Text(), nullable=True),
        sa.Column('category', sa.String(length=50), nullable=False, server_default='system'),
        sa.Column('priority', sa.String(length=12), nullable=False, server_default='normal'),
        sa.Column('digest', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('run_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('notif_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_by', sa.Uuid(), nullable=False),
        *_audit(),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_notification_rules_organization_id', 'notification_rules', ['organization_id'])
    op.create_index('ix_notification_rules_trigger_event', 'notification_rules', ['trigger_event'])
    op.create_index('ix_notification_rules_is_active', 'notification_rules', ['is_active'])
    op.create_index('ix_notif_rules_org_trigger', 'notification_rules', ['organization_id', 'trigger_event', 'is_active'])

    op.create_table(
        'notification_deliveries',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('notification_id', sa.Uuid(), nullable=True),
        sa.Column('rule_id', sa.Uuid(), nullable=True),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('channel', sa.String(length=12), nullable=False),
        sa.Column('status', sa.String(length=12), nullable=False, server_default='sent'),
        sa.Column('attempts', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('queue_job_id', sa.Uuid(), nullable=True),
        sa.Column('title', sa.String(length=255), nullable=True),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        *_audit(),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['notification_id'], ['notifications.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['rule_id'], ['notification_rules.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_notification_deliveries_organization_id', 'notification_deliveries', ['organization_id'])
    op.create_index('ix_notification_deliveries_rule_id', 'notification_deliveries', ['rule_id'])
    op.create_index('ix_notification_deliveries_user_id', 'notification_deliveries', ['user_id'])
    op.create_index('ix_notification_deliveries_channel', 'notification_deliveries', ['channel'])
    op.create_index('ix_notification_deliveries_status', 'notification_deliveries', ['status'])

    op.create_table(
        'notification_digest_items',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('rule_id', sa.Uuid(), nullable=True),
        sa.Column('category', sa.String(length=50), nullable=False, server_default='system'),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('body', sa.Text(), nullable=True),
        sa.Column('link_url', sa.String(length=500), nullable=True),
        sa.Column('is_sent', sa.Boolean(), nullable=False, server_default=sa.false()),
        *_audit(),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['rule_id'], ['notification_rules.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_notification_digest_items_organization_id', 'notification_digest_items', ['organization_id'])
    op.create_index('ix_notification_digest_items_user_id', 'notification_digest_items', ['user_id'])
    op.create_index('ix_notification_digest_items_is_sent', 'notification_digest_items', ['is_sent'])


def downgrade() -> None:
    op.drop_table('notification_digest_items')
    op.drop_table('notification_deliveries')
    op.drop_table('notification_rules')
