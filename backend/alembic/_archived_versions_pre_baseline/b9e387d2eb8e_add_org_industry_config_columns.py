"""add_org_industry_config_columns

Revision ID: b9e387d2eb8e
Revises: treatment_catalog_0001
Create Date: 2026-08-19 20:25:04.863349

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b9e387d2eb8e'
down_revision: Union[str, Sequence[str], None] = 'treatment_catalog_0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('organizations', sa.Column('industry', sa.String(length=50), nullable=False, server_default='healthcare_dental'))
    op.add_column('organizations', sa.Column('business_template', sa.String(length=50), nullable=False, server_default='healthcare_dental'))
    op.add_column('organizations', sa.Column('enabled_modules', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('organizations', 'enabled_modules')
    op.drop_column('organizations', 'business_template')
    op.drop_column('organizations', 'industry')
