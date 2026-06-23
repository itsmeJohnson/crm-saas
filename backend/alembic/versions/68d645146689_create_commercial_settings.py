"""create_commercial_settings

Revision ID: 68d645146689
Revises: 0bb374d3c2a3
Create Date: 2026-06-23 16:39:50.579379

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '68d645146689'
down_revision: Union[str, Sequence[str], None] = '0bb374d3c2a3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table('commercial_settings'):
        op.create_table(
            'commercial_settings',
            sa.Column('id', sa.String(length=50), nullable=False),
            sa.Column('default_currency', sa.String(length=10), nullable=False, server_default='INR'),
            sa.Column('currency_symbol', sa.String(length=10), nullable=False, server_default='₹'),
            sa.Column('default_timezone', sa.String(length=100), nullable=False, server_default='Asia/Kolkata'),
            sa.Column('default_gst', sa.Numeric(precision=5, scale=2), nullable=False, server_default='18.0'),
            sa.Column('gst_inclusive', sa.Boolean(), nullable=False, server_default='false'),
            sa.Column('tax_label', sa.String(length=50), nullable=False, server_default='GST'),
            sa.Column('default_trial_days', sa.Integer(), nullable=False, server_default='14'),
            sa.Column('allow_trial', sa.Boolean(), nullable=False, server_default='true'),
            sa.Column('trial_reminder_days', sa.Integer(), nullable=False, server_default='3'),
            sa.Column('default_min_contract', sa.Integer(), nullable=False, server_default='3'),
            sa.Column('auto_renewal', sa.Boolean(), nullable=False, server_default='true'),
            sa.Column('notice_period_days', sa.Integer(), nullable=False, server_default='15'),
            sa.Column('default_setup_charge', sa.Numeric(precision=10, scale=2), nullable=False, server_default='0.0'),
            sa.Column('allow_setup_discount', sa.Boolean(), nullable=False, server_default='true'),
            sa.Column('free_setup_on_annual', sa.Boolean(), nullable=False, server_default='true'),
            sa.Column('default_extra_user_price', sa.Numeric(precision=10, scale=2), nullable=False, server_default='0.0'),
            sa.Column('minimum_users', sa.Integer(), nullable=False, server_default='10'),
            sa.Column('maximum_users', sa.Integer(), nullable=True),
            sa.Column('default_discount_percentage', sa.Numeric(precision=5, scale=2), nullable=False, server_default='0.0'),
            sa.Column('maximum_discount_percentage', sa.Numeric(precision=5, scale=2), nullable=False, server_default='25.0'),
            sa.Column('allow_custom_discount', sa.Boolean(), nullable=False, server_default='true'),
            sa.Column('allow_promo_code', sa.Boolean(), nullable=False, server_default='true'),
            sa.Column('late_payment_charge', sa.Numeric(precision=10, scale=2), nullable=False, server_default='0.0'),
            sa.Column('late_payment_type', sa.String(length=20), nullable=False, server_default='flat'),
            sa.Column('grace_period_days', sa.Integer(), nullable=False, server_default='7'),
            sa.Column('auto_suspend_days', sa.Integer(), nullable=False, server_default='30'),
            sa.Column('auto_reactivate', sa.Boolean(), nullable=False, server_default='true'),
            sa.Column('reminder_schedule', sa.String(length=500), nullable=False, server_default='{}'),
            sa.Column('invoice_reminder_days', sa.String(length=50), nullable=False, server_default='7,3,1'),
            sa.Column('subscription_reminder_days', sa.String(length=50), nullable=False, server_default='15,7,3,0'),
            sa.Column('payment_reminder_days', sa.String(length=50), nullable=False, server_default='0,3,7,15'),
            sa.Column('default_plan_id', sa.String(length=50), nullable=True),
            sa.Column('default_recording_retention_days', sa.Integer(), nullable=False, server_default='90'),
            sa.Column('default_storage_gb', sa.Integer(), nullable=False, server_default='50'),
            sa.Column('invoice_reminder_template', sa.String(length=2000), nullable=True),
            sa.Column('renewal_reminder_template', sa.String(length=2000), nullable=True),
            sa.Column('trial_expiry_template', sa.String(length=2000), nullable=True),
            sa.Column('payment_success_template', sa.String(length=2000), nullable=True),
            sa.Column('payment_failed_template', sa.String(length=2000), nullable=True),
            sa.Column('welcome_template', sa.String(length=2000), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
            sa.PrimaryKeyConstraint('id')
        )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('commercial_settings')
