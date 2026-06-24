"""add_lead_disposition_fields

Revision ID: d4e5f6a7b8c9
Revises: b3c4d5e6f7a8
Create Date: 2026-06-21 13:30:00.000000

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = 'd4e5f6a7b8c9'
down_revision = 'b3c4d5e6f7a8'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column('leads', sa.Column('available_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('leads', sa.Column('call_attempts_count', sa.Integer(), nullable=False, server_default='0'))

def downgrade() -> None:
    op.drop_column('leads', 'call_attempts_count')
    op.drop_column('leads', 'available_at')
