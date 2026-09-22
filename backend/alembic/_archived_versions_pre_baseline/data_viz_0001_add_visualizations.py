"""Data Visualization — visualizations table.

Revision ID: data_viz_0001
Revises: okr_mgmt_0001
Create Date: 2026-07-16
"""
import sqlalchemy as sa
from alembic import op

revision = 'data_viz_0001'
down_revision = 'okr_mgmt_0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'visualizations',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('organization_id', sa.UUID(), sa.ForeignKey('organizations.id'), nullable=False, index=True),
        sa.Column('name', sa.String(length=150), nullable=False),
        sa.Column('description', sa.String(length=300), nullable=True),
        sa.Column('viz_type', sa.String(length=16), nullable=False, index=True),
        sa.Column('dataset', sa.String(length=30), nullable=False),
        sa.Column('config', sa.JSON(), nullable=True),
        sa.Column('filters', sa.JSON(), nullable=True),
        sa.Column('visibility', sa.String(length=16), nullable=False, server_default='organization'),
        sa.Column('is_pinned', sa.Boolean(), nullable=False, server_default=sa.false(), index=True),
        sa.Column('created_by', sa.UUID(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=True, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_table('visualizations')
