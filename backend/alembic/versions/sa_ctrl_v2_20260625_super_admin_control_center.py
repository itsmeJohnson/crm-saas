"""super_admin_control_center_v2

Revision ID: sa_ctrl_v2_20260625
Revises: b3c4d5e6f7a8
Create Date: 2026-06-25 00:00:00.000000

Adds:
  - currencies table (new)
  - tax_configs table (new)
  - payment_gateways table (new)
  - notification_templates table (new)
  - coupons table (new)
  - plans: quarterly_discount, annual_discount, allow_seat_reduction,
           replace_employee_enabled, included_minutes, ai_minutes,
           extra_storage_price, sla_hours, dedicated_manager,
           base_currency, price_per_seat
  - organizations: country, country_code, plan_id, onboarding_completed,
                   suspended_at, suspension_reason, trial_extended_days
  - invoices: base_currency, invoice_currency, exchange_rate, base_amount,
              converted_amount, tax_type, tax_label, tax_rate, tax_inclusive,
              is_credit_note, parent_invoice_id, credit_reason, billing_cycle,
              billing_period_start, billing_period_end, seats_billed,
              invoice_notes, emailed_at, coupon_code, coupon_discount
  - payments: amount, currency, payment_method, notes
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'sa_ctrl_v2_20260625'
down_revision: Union[str, Sequence[str], None] = 'b3c4d5e6f7a8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── currencies ──────────────────────────────────────────────────────────
    op.create_table(
        'currencies',
        sa.Column('code', sa.String(10), primary_key=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('symbol', sa.String(10), nullable=False),
        sa.Column('exchange_rate', sa.Numeric(15, 6), nullable=False, server_default='1.0'),
        sa.Column('is_base', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('source', sa.String(50), nullable=False, server_default='manual'),
        sa.Column('last_updated', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    )

    # ── tax_configs ──────────────────────────────────────────────────────────
    op.create_table(
        'tax_configs',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('country_code', sa.String(10), nullable=False, index=True),
        sa.Column('country_name', sa.String(100), nullable=False),
        sa.Column('tax_type', sa.String(20), nullable=False, server_default='GST'),
        sa.Column('tax_rate', sa.Numeric(5, 2), nullable=False, server_default='0.0'),
        sa.Column('tax_label', sa.String(50), nullable=False, server_default='Tax'),
        sa.Column('tax_inclusive', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('is_default', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('state_code', sa.String(10), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='false'),
    )

    # ── payment_gateways ─────────────────────────────────────────────────────
    op.create_table(
        'payment_gateways',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('name', sa.String(50), unique=True, index=True, nullable=False),
        sa.Column('display_name', sa.String(100), nullable=False),
        sa.Column('is_enabled', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_sandbox', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('api_key', sa.Text(), nullable=True),
        sa.Column('api_secret', sa.Text(), nullable=True),
        sa.Column('webhook_secret', sa.Text(), nullable=True),
        sa.Column('extra_config', sa.JSON(), nullable=True),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('description', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='false'),
    )

    # ── notification_templates ───────────────────────────────────────────────
    op.create_table(
        'notification_templates',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('template_key', sa.String(100), unique=True, index=True, nullable=False),
        sa.Column('template_name', sa.String(150), nullable=False),
        sa.Column('channel', sa.String(20), nullable=False, server_default='email'),
        sa.Column('subject', sa.String(255), nullable=True),
        sa.Column('body', sa.Text(), nullable=False, server_default=''),
        sa.Column('variables', sa.JSON(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('category', sa.String(50), nullable=False, server_default='billing'),
        sa.Column('description', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='false'),
    )

    # ── coupons ──────────────────────────────────────────────────────────────
    op.create_table(
        'coupons',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('code', sa.String(50), unique=True, index=True, nullable=False),
        sa.Column('description', sa.String(255), nullable=True),
        sa.Column('discount_type', sa.String(20), nullable=False, server_default='percentage'),
        sa.Column('discount_value', sa.Numeric(10, 2), nullable=False, server_default='0.0'),
        sa.Column('max_uses', sa.Integer(), nullable=True),
        sa.Column('uses_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('valid_from', sa.DateTime(timezone=True), nullable=False),
        sa.Column('valid_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('min_order_value', sa.Numeric(10, 2), nullable=False, server_default='0.0'),
        sa.Column('applicable_plans', sa.JSON(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_by', sa.Uuid(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='false'),
    )

    # ── plans: new columns ───────────────────────────────────────────────────
    op.add_column('plans', sa.Column('quarterly_discount', sa.Numeric(5, 2), nullable=False, server_default='5.0'))
    op.add_column('plans', sa.Column('annual_discount', sa.Numeric(5, 2), nullable=False, server_default='15.0'))
    op.add_column('plans', sa.Column('allow_seat_reduction', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('plans', sa.Column('replace_employee_enabled', sa.Boolean(), nullable=False, server_default='true'))
    op.add_column('plans', sa.Column('included_minutes', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('plans', sa.Column('ai_minutes', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('plans', sa.Column('extra_storage_price', sa.Numeric(10, 2), nullable=False, server_default='0.0'))
    op.add_column('plans', sa.Column('sla_hours', sa.Integer(), nullable=False, server_default='48'))
    op.add_column('plans', sa.Column('dedicated_manager', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('plans', sa.Column('base_currency', sa.String(10), nullable=False, server_default='INR'))
    op.add_column('plans', sa.Column('price_per_seat', sa.Numeric(10, 2), nullable=False, server_default='0.0'))

    # ── organizations: new columns ───────────────────────────────────────────
    op.add_column('organizations', sa.Column('country', sa.String(100), nullable=False, server_default='India'))
    op.add_column('organizations', sa.Column('country_code', sa.String(10), nullable=False, server_default='IN'))
    op.add_column('organizations', sa.Column('plan_id', sa.Uuid(), sa.ForeignKey('plans.id'), nullable=True))
    op.add_column('organizations', sa.Column('onboarding_completed', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('organizations', sa.Column('suspended_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('organizations', sa.Column('suspension_reason', sa.String(500), nullable=True))
    op.add_column('organizations', sa.Column('trial_extended_days', sa.Integer(), nullable=False, server_default='0'))
    op.create_index('ix_organizations_plan_id', 'organizations', ['plan_id'])

    # ── invoices: new columns ────────────────────────────────────────────────
    op.add_column('invoices', sa.Column('base_currency', sa.String(10), nullable=False, server_default='INR'))
    op.add_column('invoices', sa.Column('invoice_currency', sa.String(10), nullable=False, server_default='INR'))
    op.add_column('invoices', sa.Column('exchange_rate', sa.Numeric(15, 6), nullable=False, server_default='1.0'))
    op.add_column('invoices', sa.Column('base_amount', sa.Numeric(12, 2), nullable=False, server_default='0.0'))
    op.add_column('invoices', sa.Column('converted_amount', sa.Numeric(12, 2), nullable=False, server_default='0.0'))
    op.add_column('invoices', sa.Column('tax_type', sa.String(20), nullable=False, server_default='GST'))
    op.add_column('invoices', sa.Column('tax_label', sa.String(50), nullable=False, server_default='GST @18%'))
    op.add_column('invoices', sa.Column('tax_rate', sa.Numeric(5, 2), nullable=False, server_default='18.0'))
    op.add_column('invoices', sa.Column('tax_inclusive', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('invoices', sa.Column('is_credit_note', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('invoices', sa.Column('parent_invoice_id', sa.Uuid(), sa.ForeignKey('invoices.id'), nullable=True))
    op.add_column('invoices', sa.Column('credit_reason', sa.String(500), nullable=True))
    op.add_column('invoices', sa.Column('billing_cycle', sa.String(20), nullable=False, server_default='monthly'))
    op.add_column('invoices', sa.Column('billing_period_start', sa.DateTime(timezone=True), nullable=True))
    op.add_column('invoices', sa.Column('billing_period_end', sa.DateTime(timezone=True), nullable=True))
    op.add_column('invoices', sa.Column('seats_billed', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('invoices', sa.Column('invoice_notes', sa.Text(), nullable=True))
    op.add_column('invoices', sa.Column('emailed_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('invoices', sa.Column('coupon_code', sa.String(50), nullable=True))
    op.add_column('invoices', sa.Column('coupon_discount', sa.Numeric(10, 2), nullable=False, server_default='0.0'))

    # ── payments: new columns ────────────────────────────────────────────────
    op.add_column('payments', sa.Column('amount', sa.Numeric(12, 2), nullable=False, server_default='0.0'))
    op.add_column('payments', sa.Column('currency', sa.String(10), nullable=False, server_default='INR'))
    op.add_column('payments', sa.Column('payment_method', sa.String(50), nullable=True))
    op.add_column('payments', sa.Column('notes', sa.Text(), nullable=True))


def downgrade() -> None:
    # payments
    op.drop_column('payments', 'notes')
    op.drop_column('payments', 'payment_method')
    op.drop_column('payments', 'currency')
    op.drop_column('payments', 'amount')

    # invoices
    for col in ['coupon_discount', 'coupon_code', 'emailed_at', 'invoice_notes',
                'seats_billed', 'billing_period_end', 'billing_period_start', 'billing_cycle',
                'credit_reason', 'parent_invoice_id', 'is_credit_note',
                'tax_inclusive', 'tax_rate', 'tax_label', 'tax_type',
                'converted_amount', 'base_amount', 'exchange_rate', 'invoice_currency', 'base_currency']:
        op.drop_column('invoices', col)

    # organizations
    op.drop_index('ix_organizations_plan_id', table_name='organizations')
    for col in ['trial_extended_days', 'suspension_reason', 'suspended_at',
                'onboarding_completed', 'plan_id', 'country_code', 'country']:
        op.drop_column('organizations', col)

    # plans
    for col in ['price_per_seat', 'base_currency', 'dedicated_manager', 'sla_hours',
                'extra_storage_price', 'ai_minutes', 'included_minutes',
                'replace_employee_enabled', 'allow_seat_reduction', 'annual_discount', 'quarterly_discount']:
        op.drop_column('plans', col)

    # new tables
    op.drop_table('coupons')
    op.drop_table('notification_templates')
    op.drop_table('payment_gateways')
    op.drop_table('tax_configs')
    op.drop_table('currencies')
