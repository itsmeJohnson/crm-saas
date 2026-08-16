"""Organization-level telephony provider configuration (encrypted secrets).

One row per org. Secret columns (*_enc) hold AES-256-GCM ciphertext produced by
app.core.crypto; they are decrypted only server-side when calling a provider.
Managed by Super Admin / OrgAdmin(manage_integrations) — never per employee.

Revision ID: telephony_settings_0001
Revises: device_tokens_0001
Create Date: 2026-07-27
"""
import sqlalchemy as sa
from alembic import op

revision = 'telephony_settings_0001'
down_revision = 'device_tokens_0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'telephony_settings',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('organization_id', sa.UUID(), sa.ForeignKey('organizations.id'), nullable=False, index=True),
        sa.Column('provider', sa.String(length=30), nullable=False, server_default='myoperator'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('is_connected', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('company_id', sa.String(length=128), nullable=True),
        sa.Column('public_ivr_id', sa.String(length=128), nullable=True),
        sa.Column('call_type', sa.String(length=8), nullable=False, server_default='1'),
        sa.Column('user_uuid', sa.String(length=128), nullable=True),
        sa.Column('default_caller_id', sa.String(length=32), nullable=True),
        sa.Column('std_code', sa.String(length=8), nullable=True),
        sa.Column('webhook_url', sa.String(length=512), nullable=True),
        sa.Column('authentication_token_enc', sa.Text(), nullable=True),
        sa.Column('x_api_key_enc', sa.Text(), nullable=True),
        sa.Column('secret_token_enc', sa.Text(), nullable=True),
        sa.Column('webhook_secret_enc', sa.Text(), nullable=True),
        sa.Column('call_recording', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('power_dialer', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('predictive_dialer', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('auto_assignment', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('call_retry_count', sa.Integer(), nullable=False, server_default='4'),
        sa.Column('retry_interval_seconds', sa.Integer(), nullable=False, server_default='7200'),
        sa.Column('max_call_duration_seconds', sa.Integer(), nullable=False, server_default='3600'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=True, server_default=sa.false()),
        sa.UniqueConstraint('organization_id', name='uq_telephony_settings_organization'),
    )


def downgrade() -> None:
    op.drop_table('telephony_settings')
