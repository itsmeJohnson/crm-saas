"""Executive Dashboard — saved views / widget configuration.

Revision ID: exec_dashboard_0001
Revises: rule_designer_0001
Create Date: 2026-07-07
"""
import sqlalchemy as sa
from alembic import op

revision = 'exec_dashboard_0001'
down_revision = 'rule_designer_0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'dashboard_views',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('organization_id', sa.UUID(), sa.ForeignKey('organizations.id'), nullable=False, index=True),
        sa.Column('user_id', sa.UUID(), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('persona', sa.String(length=20), nullable=False, server_default='ceo'),
        sa.Column('scope', sa.String(length=20), nullable=False, server_default='organization'),
        sa.Column('widgets', sa.JSON(), nullable=False),
        sa.Column('is_default', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('created_by', sa.UUID(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=True, server_default=sa.false()),
    )
    op.create_index('ix_dashboard_views_org_user', 'dashboard_views', ['organization_id', 'user_id'])


def downgrade() -> None:
    op.drop_index('ix_dashboard_views_org_user', table_name='dashboard_views')
    op.drop_table('dashboard_views')
