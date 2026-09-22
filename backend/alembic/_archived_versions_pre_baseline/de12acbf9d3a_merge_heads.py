"""merge heads

Revision ID: de12acbf9d3a
Revises: c0fc3643ec52, d4e5f6a7b8c9
Create Date: 2026-06-21 08:21:47.570676

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'de12acbf9d3a'
down_revision: Union[str, Sequence[str], None] = ('c0fc3643ec52', 'd4e5f6a7b8c9')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
