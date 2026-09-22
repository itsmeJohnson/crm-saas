"""add email module: email_settings + email lifecycle columns on activities

Revision ID: e8f9a0b1c2d3
Revises: d7e8f9a0b1c2
Create Date: 2026-07-03 16:00:00.000000
"""
import sqlalchemy as sa
from alembic import op

revision = 'e8f9a0b1c2d3'
down_revision = 'd7e8f9a0b1c2'
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
    # Email lifecycle on the Activity row (activity_type='Email'). Reuses subject,
    # description (HTML body), attachments, call_direction, contact/lead/company.
    op.add_column('activities', sa.Column('email_message_id', sa.String(length=255), nullable=True))
    op.add_column('activities', sa.Column('email_thread_id', sa.Uuid(), nullable=True))
    op.add_column('activities', sa.Column('email_in_reply_to', sa.String(length=255), nullable=True))
    op.add_column('activities', sa.Column('email_from', sa.String(length=320), nullable=True))
    op.add_column('activities', sa.Column('email_to', sa.String(length=1024), nullable=True))
    op.add_column('activities', sa.Column('email_cc', sa.String(length=1024), nullable=True))
    op.add_column('activities', sa.Column('email_status', sa.String(length=20), nullable=True))  # draft|sent|failed|received
    op.add_column('activities', sa.Column('email_open_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('activities', sa.Column('email_click_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('activities', sa.Column('email_opened_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('activities', sa.Column('email_clicked_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('activities', sa.Column('is_draft', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('activities', sa.Column('email_tracking_id', sa.String(length=64), nullable=True))
    op.create_index('ix_activities_email_thread_id', 'activities', ['email_thread_id'])
    op.create_index('ix_activities_email_message_id', 'activities', ['email_message_id'])
    op.create_index('ix_activities_email_tracking_id', 'activities', ['email_tracking_id'])
    op.create_index('ix_activities_email_status', 'activities', ['email_status'])

    # Per-org mailbox config (one row per org): SMTP send + IMAP fetch + OAuth.
    op.create_table(
        'email_settings',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('auth_method', sa.String(length=30), nullable=False, server_default='smtp'),  # smtp|oauth_google|oauth_microsoft
        sa.Column('from_email', sa.String(length=320), nullable=True),
        sa.Column('from_name', sa.String(length=150), nullable=True),
        # SMTP
        sa.Column('smtp_host', sa.String(length=255), nullable=True),
        sa.Column('smtp_port', sa.Integer(), nullable=True),
        sa.Column('smtp_username', sa.String(length=255), nullable=True),
        sa.Column('smtp_password', sa.String(length=512), nullable=True),
        sa.Column('smtp_use_tls', sa.Boolean(), nullable=False, server_default=sa.true()),
        # IMAP
        sa.Column('imap_host', sa.String(length=255), nullable=True),
        sa.Column('imap_port', sa.Integer(), nullable=True),
        sa.Column('imap_username', sa.String(length=255), nullable=True),
        sa.Column('imap_password', sa.String(length=512), nullable=True),
        sa.Column('imap_use_ssl', sa.Boolean(), nullable=False, server_default=sa.true()),
        # OAuth
        sa.Column('oauth_email', sa.String(length=320), nullable=True),
        sa.Column('oauth_access_token', sa.Text(), nullable=True),
        sa.Column('oauth_refresh_token', sa.Text(), nullable=True),
        sa.Column('oauth_expires_at', sa.DateTime(timezone=True), nullable=True),
        # Tracking + state
        sa.Column('tracking_enabled', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('tracking_base_url', sa.String(length=255), nullable=True),
        sa.Column('provider', sa.String(length=30), nullable=False, server_default='mock'),  # mock|smtp
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('last_synced_at', sa.DateTime(timezone=True), nullable=True),
        *_audit(),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organization_id', name='uq_email_settings_organization'),
    )
    op.create_index('ix_email_settings_organization_id', 'email_settings', ['organization_id'])


def downgrade() -> None:
    op.drop_table('email_settings')
    for ix in ('ix_activities_email_status', 'ix_activities_email_tracking_id',
               'ix_activities_email_message_id', 'ix_activities_email_thread_id'):
        op.drop_index(ix, table_name='activities')
    for col in ('email_tracking_id', 'is_draft', 'email_clicked_at', 'email_opened_at',
                'email_click_count', 'email_open_count', 'email_status', 'email_cc', 'email_to',
                'email_from', 'email_in_reply_to', 'email_thread_id', 'email_message_id'):
        op.drop_column('activities', col)
