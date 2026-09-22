"""add calling platform fields: activities.call_tags + activities.call_disposition

Revision ID: b5c6d7e8f9a0
Revises: a3b4c5d6e7f8
Create Date: 2026-07-03 10:00:00.000000
"""
import sqlalchemy as sa
from alembic import op

revision = 'b5c6d7e8f9a0'
down_revision = 'a3b4c5d6e7f8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('activities', sa.Column('call_tags', sa.JSON(), nullable=True))
    op.add_column('activities', sa.Column('call_disposition', sa.String(length=50), nullable=True))
    op.create_index('ix_activities_call_disposition', 'activities', ['call_disposition'])
    op.create_index('ix_activities_activity_type', 'activities', ['activity_type'])


def downgrade() -> None:
    op.drop_index('ix_activities_activity_type', table_name='activities')
    op.drop_index('ix_activities_call_disposition', table_name='activities')
    op.drop_column('activities', 'call_disposition')
    op.drop_column('activities', 'call_tags')
