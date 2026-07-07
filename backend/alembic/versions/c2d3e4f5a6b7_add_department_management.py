"""add department management: departments + department_targets + users.department_id

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
Create Date: 2026-07-03 23:30:00.000000
"""
import sqlalchemy as sa
from alembic import op

revision = 'c2d3e4f5a6b7'
down_revision = 'b1c2d3e4f5a6'
branch_labels = None
depends_on = None


def _audit():
    return [
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=True),
    ]


def upgrade() -> None:
    op.create_table(
        'departments',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(length=150), nullable=False),
        sa.Column('code', sa.String(length=30), nullable=True),
        sa.Column('description', sa.String(length=500), nullable=True),
        sa.Column('parent_department_id', sa.Uuid(), nullable=True),
        sa.Column('head_user_id', sa.Uuid(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='active'),  # active|archived
        sa.Column('budget', sa.Numeric(14, 2), nullable=True),
        sa.Column('budget_period', sa.String(length=20), nullable=True),  # monthly|quarterly|yearly
        sa.Column('cost_center', sa.String(length=50), nullable=True),
        sa.Column('color', sa.String(length=20), nullable=True),
        sa.Column('created_by', sa.Uuid(), nullable=False),
        *_audit(),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['parent_department_id'], ['departments.id']),
        sa.ForeignKeyConstraint(['head_user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organization_id', 'code', name='uq_department_org_code'),
    )
    op.create_index('ix_departments_organization_id', 'departments', ['organization_id'])
    op.create_index('ix_departments_parent_department_id', 'departments', ['parent_department_id'])
    op.create_index('ix_departments_status', 'departments', ['status'])

    op.create_table(
        'department_targets',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('department_id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(length=150), nullable=False),
        sa.Column('metric', sa.String(length=40), nullable=False),
        # leads_converted|calls_made|tasks_completed|revenue|activities|custom
        sa.Column('target_value', sa.Numeric(14, 2), nullable=False),
        sa.Column('period', sa.String(length=20), nullable=False, server_default='monthly'),
        sa.Column('start_date', sa.Date(), nullable=True),
        sa.Column('end_date', sa.Date(), nullable=True),
        sa.Column('created_by', sa.Uuid(), nullable=False),
        *_audit(),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['department_id'], ['departments.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_department_targets_department_id', 'department_targets', ['department_id'])
    op.create_index('ix_department_targets_organization_id', 'department_targets', ['organization_id'])

    # Backward-compatible: existing users get NULL department_id.
    op.add_column('users', sa.Column('department_id', sa.Uuid(), nullable=True))
    op.create_foreign_key('fk_users_department', 'users', 'departments', ['department_id'], ['id'])
    op.create_index('ix_users_department_id', 'users', ['department_id'])


def downgrade() -> None:
    op.drop_index('ix_users_department_id', table_name='users')
    op.drop_constraint('fk_users_department', 'users', type_='foreignkey')
    op.drop_column('users', 'department_id')
    op.drop_table('department_targets')
    op.drop_table('departments')
