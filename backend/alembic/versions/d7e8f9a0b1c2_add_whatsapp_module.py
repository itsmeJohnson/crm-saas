"""add whatsapp module: settings + conversations + quick replies + WA columns on activities

Revision ID: d7e8f9a0b1c2
Revises: c6d7e8f9a0b1
Create Date: 2026-07-03 14:00:00.000000
"""
import sqlalchemy as sa
from alembic import op

revision = 'd7e8f9a0b1c2'
down_revision = 'c6d7e8f9a0b1'
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
    # WhatsApp lifecycle on the Activity row (activity_type='WhatsApp'). Reuses
    # to_number/from_number (added for SMS), attachments (media), call_direction.
    op.add_column('activities', sa.Column('wa_status', sa.String(length=20), nullable=True))         # sent|delivered|read|failed|received
    op.add_column('activities', sa.Column('wa_message_id', sa.String(length=128), nullable=True))    # provider WAMID
    op.add_column('activities', sa.Column('wa_error', sa.String(length=500), nullable=True))
    op.add_column('activities', sa.Column('wa_media_type', sa.String(length=20), nullable=True))      # text|image|video|document|audio
    op.add_column('activities', sa.Column('wa_template_name', sa.String(length=128), nullable=True))
    op.add_column('activities', sa.Column('wa_conversation_id', sa.Uuid(), nullable=True))
    op.create_index('ix_activities_wa_status', 'activities', ['wa_status'])
    op.create_index('ix_activities_wa_message_id', 'activities', ['wa_message_id'])
    op.create_index('ix_activities_wa_conversation_id', 'activities', ['wa_conversation_id'])

    # Per-org WhatsApp Business config (one row per org).
    op.create_table(
        'whatsapp_settings',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('provider', sa.String(length=30), nullable=False, server_default='mock'),  # mock|meta
        sa.Column('phone_number_id', sa.String(length=64), nullable=True),
        sa.Column('business_account_id', sa.String(length=64), nullable=True),
        sa.Column('access_token', sa.Text(), nullable=True),
        sa.Column('sender_number', sa.String(length=32), nullable=True),
        sa.Column('webhook_token', sa.String(length=64), nullable=True),        # secures status/inbound POST
        sa.Column('webhook_verify_token', sa.String(length=64), nullable=True),  # Meta GET hub.verify_token
        sa.Column('daily_limit', sa.Integer(), nullable=False, server_default='2000'),
        sa.Column('auto_reply_enabled', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('auto_reply_message', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        *_audit(),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organization_id', name='uq_whatsapp_settings_organization'),
    )
    op.create_index('ix_whatsapp_settings_organization_id', 'whatsapp_settings', ['organization_id'])
    op.create_index('ix_whatsapp_settings_webhook_token', 'whatsapp_settings', ['webhook_token'])

    # One conversation per counterparty phone: holds the 24h window + assignment.
    op.create_table(
        'whatsapp_conversations',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('phone', sa.String(length=32), nullable=False),
        sa.Column('contact_id', sa.Uuid(), nullable=True),
        sa.Column('lead_id', sa.Uuid(), nullable=True),
        sa.Column('assigned_user_id', sa.Uuid(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='open'),  # open|closed
        sa.Column('display_name', sa.String(length=255), nullable=True),
        sa.Column('last_inbound_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_outbound_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_message_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('window_expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('unread_count', sa.Integer(), nullable=False, server_default='0'),
        *_audit(),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['assigned_user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['contact_id'], ['contacts.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['lead_id'], ['leads.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organization_id', 'phone', name='uq_whatsapp_conversation_org_phone'),
    )
    op.create_index('ix_whatsapp_conversations_organization_id', 'whatsapp_conversations', ['organization_id'])
    op.create_index('ix_whatsapp_conversations_assigned_user_id', 'whatsapp_conversations', ['assigned_user_id'])
    op.create_index('ix_whatsapp_conversations_phone', 'whatsapp_conversations', ['phone'])

    # Canned agent replies.
    op.create_table(
        'whatsapp_quick_replies',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('shortcut', sa.String(length=50), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('created_by', sa.Uuid(), nullable=False),
        *_audit(),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_whatsapp_quick_replies_organization_id', 'whatsapp_quick_replies', ['organization_id'])


def downgrade() -> None:
    op.drop_table('whatsapp_quick_replies')
    op.drop_table('whatsapp_conversations')
    op.drop_table('whatsapp_settings')
    op.drop_index('ix_activities_wa_conversation_id', table_name='activities')
    op.drop_index('ix_activities_wa_message_id', table_name='activities')
    op.drop_index('ix_activities_wa_status', table_name='activities')
    op.drop_column('activities', 'wa_conversation_id')
    op.drop_column('activities', 'wa_template_name')
    op.drop_column('activities', 'wa_media_type')
    op.drop_column('activities', 'wa_error')
    op.drop_column('activities', 'wa_message_id')
    op.drop_column('activities', 'wa_status')
