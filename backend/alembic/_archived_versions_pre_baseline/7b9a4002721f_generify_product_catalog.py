"""generify_product_catalog

Revision ID: 7b9a4002721f
Revises: b9e387d2eb8e
Create Date: 2026-08-19 21:10:12.606531

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7b9a4002721f'
down_revision: Union[str, Sequence[str], None] = 'b9e387d2eb8e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()
    if 'treatment_catalog_items' in tables:
        op.rename_table('treatment_catalog_items', 'product_catalog_items')
    elif 'product_catalog_items' not in tables:
        op.create_table(
            'product_catalog_items',
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
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default=sa.false()),
        )


def downgrade() -> None:
    """Downgrade schema."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()
    if 'product_catalog_items' in tables:
        op.rename_table('product_catalog_items', 'treatment_catalog_items')

