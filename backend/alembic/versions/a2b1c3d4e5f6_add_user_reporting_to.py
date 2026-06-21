"""add_user_reporting_to

Revision ID: a2b1c3d4e5f6
Revises: fe7554e40f40
Create Date: 2026-06-21 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a2b1c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'fe7554e40f40'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add column reporting_to_id to users table
    op.add_column('users', sa.Column('reporting_to_id', sa.Uuid(), nullable=True))
    op.create_foreign_key('fk_users_reporting_to', 'users', 'users', ['reporting_to_id'], ['id'])
    op.create_index(op.f('ix_users_reporting_to_id'), 'users', ['reporting_to_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_users_reporting_to_id'), table_name='users')
    op.drop_constraint('fk_users_reporting_to', 'users', type_='foreignkey')
    op.drop_column('users', 'reporting_to_id')
