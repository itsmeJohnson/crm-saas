"""Add sms_priority to sms_settings — BhashSMS-style gateways route by a
per-sender priority (ndnd=transactional, dnd=promotional). A promotional
sender (e.g. BHASH) must send with 'dnd', so priority has to be configurable
per org rather than hardcoded. Defaults to 'ndnd' (transactional), which is a
no-op for Mock/Twilio.

Revision ID: sms_priority_0001
Revises: integration_hub_0001
Create Date: 2026-07-25
"""
import sqlalchemy as sa
from alembic import op

revision = 'sms_priority_0001'
down_revision = 'integration_hub_0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('sms_settings', sa.Column('sms_priority', sa.String(length=8),
                                            nullable=False, server_default='ndnd'))


def downgrade() -> None:
    op.drop_column('sms_settings', 'sms_priority')
