"""add_org_metadata_version

Revision ID: metadata_version_0001
Revises: metadata_engine_0001
Create Date: 2026-08-03 19:07:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'metadata_version_0001'
down_revision: Union[str, Sequence[str], None] = 'metadata_engine_0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('organizations', sa.Column('metadata_version', sa.Integer(), nullable=False, server_default='1'))


def downgrade() -> None:
    op.drop_column('organizations', 'metadata_version')
