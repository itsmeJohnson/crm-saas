"""add_friendly_name_to_whatsapp_settings

Revision ID: f9b3c7d1e8c9
Revises: e03485c55747
Create Date: 2026-08-06 15:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f9b3c7d1e8c9'
down_revision: Union[str, Sequence[str], None] = 'e03485c55747'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('whatsapp_settings', sa.Column('friendly_name', sa.String(length=100), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('whatsapp_settings', 'friendly_name')
