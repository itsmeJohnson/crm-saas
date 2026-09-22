"""Inbound lead-capture sources + event ledger.

Tenant-scoped webhook endpoints that turn ad-platform / web-form payloads
(Meta Lead Ads, Google Ads lead forms, landing pages, Zapier) into Leads.
lead_capture_events is the idempotency ledger + inbound activity log.

Revision ID: lead_capture_0001
Revises: f9b3c7d1e8c9
Create Date: 2026-08-10
"""
import sqlalchemy as sa
from alembic import op

revision = 'lead_capture_0001'
down_revision = 'f9b3c7d1e8c9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'lead_capture_sources',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('organization_id', sa.UUID(), sa.ForeignKey('organizations.id'), nullable=False, index=True),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('provider', sa.String(length=30), nullable=False, server_default='generic'),
        sa.Column('token', sa.String(length=64), nullable=False),
        sa.Column('secret', sa.String(length=128), nullable=True),
        sa.Column('meta_verify_token', sa.String(length=64), nullable=True),
        sa.Column('source_label', sa.String(length=100), nullable=False, server_default='Web Lead'),
        sa.Column('default_pipeline_id', sa.UUID(), sa.ForeignKey('pipelines.id', ondelete='SET NULL'), nullable=True),
        sa.Column('owner_user_id', sa.UUID(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('field_mapping', sa.JSON(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('leads_captured', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_received_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', sa.UUID(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index('ix_lead_capture_sources_token', 'lead_capture_sources', ['token'], unique=True)

    op.create_table(
        'lead_capture_events',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('organization_id', sa.UUID(), sa.ForeignKey('organizations.id'), nullable=False, index=True),
        sa.Column('source_id', sa.UUID(), sa.ForeignKey('lead_capture_sources.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('external_id', sa.String(length=191), nullable=True),
        sa.Column('lead_id', sa.UUID(), sa.ForeignKey('leads.id', ondelete='SET NULL'), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='created'),
        sa.Column('error', sa.String(length=500), nullable=True),
        sa.Column('raw_payload', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.UniqueConstraint('source_id', 'external_id', name='uq_lead_capture_event_external'),
    )


def downgrade() -> None:
    op.drop_table('lead_capture_events')
    op.drop_index('ix_lead_capture_sources_token', table_name='lead_capture_sources')
    op.drop_table('lead_capture_sources')
