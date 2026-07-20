"""add saved_filters table

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-07-02 10:30:00.000000
"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = 'f6a7b8c9d0e1'
down_revision = 'e5f6a7b8c9d0'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'saved_filters',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(length=150), nullable=False),
        sa.Column('entity_type', sa.String(length=50), nullable=False, server_default='lead'),
        sa.Column('definition', sa.JSON(), nullable=False),
        sa.Column('is_shared', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_saved_filters_organization_id', 'saved_filters', ['organization_id'])
    op.create_index('ix_saved_filters_user_id', 'saved_filters', ['user_id'])
    op.create_index('ix_saved_filters_entity_type', 'saved_filters', ['entity_type'])


def downgrade() -> None:
    op.drop_index('ix_saved_filters_entity_type', table_name='saved_filters')
    op.drop_index('ix_saved_filters_user_id', table_name='saved_filters')
    op.drop_index('ix_saved_filters_organization_id', table_name='saved_filters')
    op.drop_table('saved_filters')
