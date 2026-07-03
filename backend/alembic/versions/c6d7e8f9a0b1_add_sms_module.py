"""add sms module: sms_settings + SMS lifecycle columns on activities

Revision ID: c6d7e8f9a0b1
Revises: b5c6d7e8f9a0
Create Date: 2026-07-03 12:00:00.000000
"""
import sqlalchemy as sa
from alembic import op

revision = 'c6d7e8f9a0b1'
down_revision = 'b5c6d7e8f9a0'
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
    # SMS delivery lifecycle lives on the Activity row (SMS is already an
    # activity_type='SMS' activity, so timeline/conversation/feed keep working).
    op.add_column('activities', sa.Column('sms_status', sa.String(length=20), nullable=True))
    op.add_column('activities', sa.Column('sms_provider_id', sa.String(length=128), nullable=True))
    op.add_column('activities', sa.Column('sms_error', sa.String(length=500), nullable=True))
    op.add_column('activities', sa.Column('sms_retry_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('activities', sa.Column('sms_segments', sa.Integer(), nullable=True))
    op.add_column('activities', sa.Column('to_number', sa.String(length=32), nullable=True))
    op.add_column('activities', sa.Column('from_number', sa.String(length=32), nullable=True))
    op.create_index('ix_activities_sms_status', 'activities', ['sms_status'])
    op.create_index('ix_activities_sms_provider_id', 'activities', ['sms_provider_id'])

    # Per-org SMS provider configuration (one row per org).
    op.create_table(
        'sms_settings',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('provider', sa.String(length=30), nullable=False, server_default='mock'),
        sa.Column('account_sid', sa.String(length=255), nullable=True),
        sa.Column('auth_token', sa.String(length=255), nullable=True),
        sa.Column('sender_id', sa.String(length=32), nullable=True),
        sa.Column('webhook_token', sa.String(length=64), nullable=True),
        sa.Column('daily_limit', sa.Integer(), nullable=False, server_default='1000'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        *_audit(),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organization_id', name='uq_sms_settings_organization'),
    )
    op.create_index('ix_sms_settings_organization_id', 'sms_settings', ['organization_id'])
    op.create_index('ix_sms_settings_webhook_token', 'sms_settings', ['webhook_token'])


def downgrade() -> None:
    op.drop_table('sms_settings')
    op.drop_index('ix_activities_sms_provider_id', table_name='activities')
    op.drop_index('ix_activities_sms_status', table_name='activities')
    op.drop_column('activities', 'from_number')
    op.drop_column('activities', 'to_number')
    op.drop_column('activities', 'sms_segments')
    op.drop_column('activities', 'sms_retry_count')
    op.drop_column('activities', 'sms_error')
    op.drop_column('activities', 'sms_provider_id')
    op.drop_column('activities', 'sms_status')
