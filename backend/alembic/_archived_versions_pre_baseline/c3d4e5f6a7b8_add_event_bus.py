"""add event bus: events + event_subscriptions + event_deliveries

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-07-05 18:00:00.000000
"""
import sqlalchemy as sa
from alembic import op

revision = 'c3d4e5f6a7b8'
down_revision = 'b2c3d4e5f6a7'
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
        'events',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('event_type', sa.String(length=80), nullable=False),
        sa.Column('entity_type', sa.String(length=40), nullable=True),
        sa.Column('entity_id', sa.String(length=64), nullable=True),
        sa.Column('payload', sa.JSON(), nullable=True),
        sa.Column('actor_user_id', sa.Uuid(), nullable=True),
        sa.Column('source', sa.String(length=20), nullable=False, server_default='trigger'),
        sa.Column('status', sa.String(length=16), nullable=False, server_default='published'),
        sa.Column('subscriber_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('delivered_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('failed_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=False),
        *_audit(),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['actor_user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_events_organization_id', 'events', ['organization_id'])
    op.create_index('ix_events_event_type', 'events', ['event_type'])
    op.create_index('ix_events_entity_id', 'events', ['entity_id'])
    op.create_index('ix_events_org_type', 'events', ['organization_id', 'event_type'])

    op.create_table(
        'event_subscriptions',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('event_pattern', sa.String(length=80), nullable=False),
        sa.Column('subscriber_type', sa.String(length=20), nullable=False, server_default='webhook'),
        sa.Column('config', sa.JSON(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('max_attempts', sa.Integer(), nullable=False, server_default='3'),
        sa.Column('delivered_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('failed_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_by', sa.Uuid(), nullable=False),
        *_audit(),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_event_subscriptions_organization_id', 'event_subscriptions', ['organization_id'])
    op.create_index('ix_event_subscriptions_event_pattern', 'event_subscriptions', ['event_pattern'])
    op.create_index('ix_event_subscriptions_is_active', 'event_subscriptions', ['is_active'])

    op.create_table(
        'event_deliveries',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('event_id', sa.Uuid(), nullable=False),
        sa.Column('subscription_id', sa.Uuid(), nullable=True),
        sa.Column('subscriber', sa.String(length=120), nullable=False),
        sa.Column('event_type', sa.String(length=80), nullable=False),
        sa.Column('status', sa.String(length=16), nullable=False, server_default='success'),
        sa.Column('attempts', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.Column('is_dead_letter', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('delivered_at', sa.DateTime(timezone=True), nullable=False),
        *_audit(),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['event_id'], ['events.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['subscription_id'], ['event_subscriptions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_event_deliveries_organization_id', 'event_deliveries', ['organization_id'])
    op.create_index('ix_event_deliveries_event_id', 'event_deliveries', ['event_id'])
    op.create_index('ix_event_deliveries_subscription_id', 'event_deliveries', ['subscription_id'])
    op.create_index('ix_event_deliveries_status', 'event_deliveries', ['status'])
    op.create_index('ix_event_deliveries_is_dead_letter', 'event_deliveries', ['is_dead_letter'])


def downgrade() -> None:
    op.drop_table('event_deliveries')
    op.drop_table('event_subscriptions')
    op.drop_table('events')
