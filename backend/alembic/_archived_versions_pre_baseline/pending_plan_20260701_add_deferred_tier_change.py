"""add_pending_plan_change_to_tenant_subscriptions

Revision ID: pending_plan_20260701
Revises: mfa_20260626
Create Date: 2026-07-01 00:00:00.000000

Adds:
  - tenant_subscriptions.pending_plan_id (uuid, FK -> plans.id, nullable)
  - tenant_subscriptions.pending_billing_cycle (varchar 20, nullable)

Supports scheduling a tier switch for an already-active, mid-commitment
subscription: the change is applied at end_date (renewal) instead of
immediately, mirroring the existing users_purchased_next deferred-seat pattern.
"""
from alembic import op
import sqlalchemy as sa

revision = 'pending_plan_20260701'
down_revision = 'mfa_20260626'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('tenant_subscriptions', sa.Column('pending_plan_id', sa.UUID(), sa.ForeignKey('plans.id'), nullable=True))
    op.add_column('tenant_subscriptions', sa.Column('pending_billing_cycle', sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column('tenant_subscriptions', 'pending_billing_cycle')
    op.drop_column('tenant_subscriptions', 'pending_plan_id')
