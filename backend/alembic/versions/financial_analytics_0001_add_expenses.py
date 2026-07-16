"""Financial Analytics — expenses table (expense/profitability/CAC source).

Revision ID: financial_analytics_0001
Revises: employee_analytics_0001
Create Date: 2026-07-16
"""
import sqlalchemy as sa
from alembic import op

revision = 'financial_analytics_0001'
down_revision = 'employee_analytics_0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'expenses',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('organization_id', sa.UUID(), sa.ForeignKey('organizations.id'), nullable=False, index=True),
        sa.Column('category', sa.String(length=60), nullable=False, server_default='General'),
        sa.Column('amount', sa.Numeric(14, 2), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('vendor', sa.String(length=150), nullable=True),
        sa.Column('incurred_at', sa.Date(), nullable=False),
        sa.Column('created_by', sa.UUID(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=True, server_default=sa.false()),
    )
    op.create_index('ix_expenses_org_incurred', 'expenses', ['organization_id', 'incurred_at'])


def downgrade() -> None:
    op.drop_index('ix_expenses_org_incurred', table_name='expenses')
    op.drop_table('expenses')
