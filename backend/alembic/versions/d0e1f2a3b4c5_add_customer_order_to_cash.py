"""add customer order-to-cash tables: orders, invoices, payments, contracts

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
Create Date: 2026-07-02 14:00:00.000000
"""
import sqlalchemy as sa
from alembic import op

revision = 'd0e1f2a3b4c5'
down_revision = 'c9d0e1f2a3b4'
branch_labels = None
depends_on = None


def _audit_cols():
    return [
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=True),
    ]


def upgrade() -> None:
    op.create_table(
        'customer_orders',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('company_id', sa.Uuid(), nullable=False),
        sa.Column('contact_id', sa.Uuid(), nullable=True),
        sa.Column('order_number', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=30), nullable=False, server_default='Draft'),
        sa.Column('currency', sa.String(length=10), nullable=False, server_default='USD'),
        sa.Column('order_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('items', sa.JSON(), nullable=False),
        sa.Column('subtotal', sa.Numeric(14, 2), nullable=False, server_default='0'),
        sa.Column('tax_amount', sa.Numeric(14, 2), nullable=False, server_default='0'),
        sa.Column('discount_amount', sa.Numeric(14, 2), nullable=False, server_default='0'),
        sa.Column('total_amount', sa.Numeric(14, 2), nullable=False, server_default='0'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_by', sa.Uuid(), nullable=False),
        *_audit_cols(),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['contact_id'], ['contacts.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    for col in ('organization_id', 'company_id', 'contact_id', 'order_number', 'status', 'created_by'):
        op.create_index(f'ix_customer_orders_{col}', 'customer_orders', [col])

    op.create_table(
        'customer_invoices',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('company_id', sa.Uuid(), nullable=False),
        sa.Column('contact_id', sa.Uuid(), nullable=True),
        sa.Column('order_id', sa.Uuid(), nullable=True),
        sa.Column('invoice_number', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=30), nullable=False, server_default='Draft'),
        sa.Column('currency', sa.String(length=10), nullable=False, server_default='USD'),
        sa.Column('issue_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('due_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('items', sa.JSON(), nullable=False),
        sa.Column('subtotal', sa.Numeric(14, 2), nullable=False, server_default='0'),
        sa.Column('tax_amount', sa.Numeric(14, 2), nullable=False, server_default='0'),
        sa.Column('discount_amount', sa.Numeric(14, 2), nullable=False, server_default='0'),
        sa.Column('total_amount', sa.Numeric(14, 2), nullable=False, server_default='0'),
        sa.Column('amount_paid', sa.Numeric(14, 2), nullable=False, server_default='0'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_by', sa.Uuid(), nullable=False),
        *_audit_cols(),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['contact_id'], ['contacts.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['order_id'], ['customer_orders.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    for col in ('organization_id', 'company_id', 'contact_id', 'order_id', 'invoice_number', 'status', 'due_date', 'created_by'):
        op.create_index(f'ix_customer_invoices_{col}', 'customer_invoices', [col])

    op.create_table(
        'customer_payments',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('company_id', sa.Uuid(), nullable=False),
        sa.Column('invoice_id', sa.Uuid(), nullable=False),
        sa.Column('amount', sa.Numeric(14, 2), nullable=False),
        sa.Column('currency', sa.String(length=10), nullable=False, server_default='USD'),
        sa.Column('method', sa.String(length=30), nullable=False, server_default='BankTransfer'),
        sa.Column('reference', sa.String(length=120), nullable=True),
        sa.Column('paid_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_by', sa.Uuid(), nullable=False),
        *_audit_cols(),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['invoice_id'], ['customer_invoices.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    for col in ('organization_id', 'company_id', 'invoice_id', 'created_by'):
        op.create_index(f'ix_customer_payments_{col}', 'customer_payments', [col])

    op.create_table(
        'contracts',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('company_id', sa.Uuid(), nullable=False),
        sa.Column('contact_id', sa.Uuid(), nullable=True),
        sa.Column('contract_number', sa.String(length=50), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('status', sa.String(length=30), nullable=False, server_default='Draft'),
        sa.Column('start_date', sa.Date(), nullable=True),
        sa.Column('end_date', sa.Date(), nullable=True),
        sa.Column('value', sa.Numeric(14, 2), nullable=True),
        sa.Column('currency', sa.String(length=10), nullable=False, server_default='USD'),
        sa.Column('renewal_terms', sa.String(length=255), nullable=True),
        sa.Column('document_url', sa.String(length=512), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_by', sa.Uuid(), nullable=False),
        *_audit_cols(),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['contact_id'], ['contacts.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    for col in ('organization_id', 'company_id', 'contact_id', 'contract_number', 'status', 'end_date', 'created_by'):
        op.create_index(f'ix_contracts_{col}', 'contracts', [col])


def downgrade() -> None:
    op.drop_table('contracts')
    op.drop_table('customer_payments')
    op.drop_table('customer_invoices')
    op.drop_table('customer_orders')
