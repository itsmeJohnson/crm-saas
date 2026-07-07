"""add campaign module: campaigns + campaign_recipients + campaign_segments

Revision ID: a0b1c2d3e4f5
Revises: f9a0b1c2d3e4
Create Date: 2026-07-03 20:00:00.000000
"""
import sqlalchemy as sa
from alembic import op

revision = 'a0b1c2d3e4f5'
down_revision = 'f9a0b1c2d3e4'
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
        'campaign_segments',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(length=150), nullable=False),
        sa.Column('description', sa.String(length=255), nullable=True),
        sa.Column('entity_type', sa.String(length=20), nullable=False, server_default='lead'),  # lead|contact
        sa.Column('definition', sa.JSON(), nullable=False),
        sa.Column('cached_count', sa.Integer(), nullable=True),
        sa.Column('created_by', sa.Uuid(), nullable=False),
        *_audit(),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_campaign_segments_organization_id', 'campaign_segments', ['organization_id'])

    op.create_table(
        'campaigns',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('description', sa.String(length=500), nullable=True),
        sa.Column('channel', sa.String(length=20), nullable=False),  # SMS|Email|WhatsApp|Call
        sa.Column('template_id', sa.Uuid(), nullable=True),
        sa.Column('subject', sa.String(length=255), nullable=True),
        sa.Column('body', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='draft'),
        # draft|scheduled|running|paused|completed|cancelled
        sa.Column('audience_type', sa.String(length=20), nullable=False, server_default='filter'),  # filter|list|segment
        sa.Column('audience_definition', sa.JSON(), nullable=True),
        sa.Column('segment_id', sa.Uuid(), nullable=True),
        sa.Column('entity_type', sa.String(length=20), nullable=False, server_default='lead'),  # lead|contact
        sa.Column('scheduled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('total_recipients', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('sent_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('delivered_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('failed_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('opened_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('clicked_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('converted_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('cost_per_message', sa.Numeric(12, 4), nullable=False, server_default='0'),
        sa.Column('revenue', sa.Numeric(14, 2), nullable=False, server_default='0'),
        sa.Column('max_retries', sa.Integer(), nullable=False, server_default='2'),
        sa.Column('created_by', sa.Uuid(), nullable=False),
        *_audit(),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['template_id'], ['communication_templates.id']),
        sa.ForeignKeyConstraint(['segment_id'], ['campaign_segments.id']),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_campaigns_organization_id', 'campaigns', ['organization_id'])
    op.create_index('ix_campaigns_status', 'campaigns', ['status'])
    op.create_index('ix_campaigns_scheduled_at', 'campaigns', ['scheduled_at'])

    op.create_table(
        'campaign_recipients',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('campaign_id', sa.Uuid(), nullable=False),
        sa.Column('lead_id', sa.Uuid(), nullable=True),
        sa.Column('contact_id', sa.Uuid(), nullable=True),
        sa.Column('to_address', sa.String(length=320), nullable=True),  # phone or email
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
        # pending|sent|delivered|failed|opened|clicked|converted|skipped
        sa.Column('activity_id', sa.Uuid(), nullable=True),
        sa.Column('error', sa.String(length=500), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        *_audit(),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['campaign_id'], ['campaigns.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['lead_id'], ['leads.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['contact_id'], ['contacts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_campaign_recipients_campaign_id', 'campaign_recipients', ['campaign_id'])
    op.create_index('ix_campaign_recipients_organization_id', 'campaign_recipients', ['organization_id'])
    op.create_index('ix_campaign_recipients_status', 'campaign_recipients', ['status'])
    op.create_unique_constraint('uq_campaign_recipient_lead', 'campaign_recipients', ['campaign_id', 'lead_id'])
    op.create_unique_constraint('uq_campaign_recipient_contact', 'campaign_recipients', ['campaign_id', 'contact_id'])


def downgrade() -> None:
    op.drop_table('campaign_recipients')
    op.drop_table('campaigns')
    op.drop_table('campaign_segments')
