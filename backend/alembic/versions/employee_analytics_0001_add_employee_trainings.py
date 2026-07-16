"""Employee Analytics — employee_trainings (training-score data source).

Revision ID: employee_analytics_0001
Revises: sales_analytics_0001
Create Date: 2026-07-16
"""
import sqlalchemy as sa
from alembic import op

revision = 'employee_analytics_0001'
down_revision = 'sales_analytics_0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'employee_trainings',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('organization_id', sa.UUID(), sa.ForeignKey('organizations.id'), nullable=False, index=True),
        sa.Column('user_id', sa.UUID(), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('name', sa.String(length=150), nullable=False),
        sa.Column('category', sa.String(length=60), nullable=True),
        sa.Column('status', sa.String(length=16), nullable=False, server_default='completed'),
        sa.Column('score', sa.Integer(), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', sa.UUID(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=True, server_default=sa.false()),
    )
    op.create_index('ix_employee_trainings_org_user', 'employee_trainings', ['organization_id', 'user_id'])


def downgrade() -> None:
    op.drop_index('ix_employee_trainings_org_user', table_name='employee_trainings')
    op.drop_table('employee_trainings')
