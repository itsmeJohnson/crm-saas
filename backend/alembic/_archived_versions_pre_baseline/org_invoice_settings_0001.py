"""Per-tenant invoice settings (clinic branding, tax, currency, numbering).

Revision ID: org_invoice_settings_0001
Revises: lead_capture_0001
Create Date: 2026-08-10
"""
import sqlalchemy as sa
from alembic import op

revision = 'org_invoice_settings_0001'
down_revision = 'lead_capture_0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'org_invoice_settings',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('organization_id', sa.UUID(), sa.ForeignKey('organizations.id'), nullable=False),
        sa.Column('legal_name', sa.String(length=200), nullable=True),
        sa.Column('address', sa.Text(), nullable=True),
        sa.Column('phone', sa.String(length=50), nullable=True),
        sa.Column('email', sa.String(length=255), nullable=True),
        sa.Column('website', sa.String(length=255), nullable=True),
        sa.Column('logo_url', sa.Text(), nullable=True),
        sa.Column('gst_number', sa.String(length=30), nullable=True),
        sa.Column('pan', sa.String(length=20), nullable=True),
        sa.Column('tax_label', sa.String(length=20), nullable=False, server_default='GST'),
        sa.Column('default_tax_percent', sa.Numeric(5, 2), nullable=False, server_default='0'),
        sa.Column('currency', sa.String(length=10), nullable=False, server_default='INR'),
        sa.Column('currency_symbol', sa.String(length=6), nullable=False, server_default='₹'),
        sa.Column('invoice_prefix', sa.String(length=20), nullable=False, server_default='INV-'),
        sa.Column('next_invoice_number', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('number_padding', sa.Integer(), nullable=False, server_default='4'),
        sa.Column('bank_name', sa.String(length=120), nullable=True),
        sa.Column('account_holder', sa.String(length=120), nullable=True),
        sa.Column('account_number', sa.String(length=40), nullable=True),
        sa.Column('ifsc', sa.String(length=20), nullable=True),
        sa.Column('upi_id', sa.String(length=80), nullable=True),
        sa.Column('payment_terms', sa.Text(), nullable=True),
        sa.Column('footer_text', sa.Text(), nullable=True),
        sa.Column('default_notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.UniqueConstraint('organization_id', name='uq_org_invoice_settings_org'),
    )


def downgrade() -> None:
    op.drop_table('org_invoice_settings')
