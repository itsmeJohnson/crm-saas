"""Sales Analytics — add lead.lost_reason for lost-reason analysis.

Revision ID: sales_analytics_0001
Revises: report_builder_0001
Create Date: 2026-07-07
"""
import sqlalchemy as sa
from alembic import op

revision = 'sales_analytics_0001'
down_revision = 'report_builder_0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('leads', sa.Column('lost_reason', sa.String(length=150), nullable=True))


def downgrade() -> None:
    op.drop_column('leads', 'lost_reason')
