"""Treatment & price master (treatment_catalog_items).

Revision ID: treatment_catalog_0001
Revises: org_invoice_settings_0001
Create Date: 2026-08-11
"""
import sqlalchemy as sa
from alembic import op

revision = 'treatment_catalog_0001'
down_revision = 'org_invoice_settings_0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'treatment_catalog_items',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('organization_id', sa.UUID(), sa.ForeignKey('organizations.id'), nullable=False, index=True),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('category', sa.String(length=100), nullable=True, index=True),
        sa.Column('code', sa.String(length=40), nullable=True),
        sa.Column('price', sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column('tax_percent', sa.Numeric(5, 2), nullable=False, server_default='0'),
        sa.Column('duration_minutes', sa.Integer(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true(), index=True),
        sa.Column('created_by', sa.UUID(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_table('treatment_catalog_items')
