"""add roles & permissions (custom_roles/role_permissions/field_permissions +
users.custom_role_id) and team management (teams/team_members/team_targets)

Revision ID: d3e4f5a6b7c8
Revises: c2d3e4f5a6b7
Create Date: 2026-07-04 10:00:00.000000
"""
import sqlalchemy as sa
from alembic import op

revision = 'd3e4f5a6b7c8'
down_revision = 'c2d3e4f5a6b7'
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
    # ---------- Roles & Permissions ----------
    op.create_table(
        'custom_roles',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.String(length=500), nullable=True),
        sa.Column('base_role', sa.String(length=20), nullable=False, server_default='Employee'),  # Employee|Manager|OrgAdmin
        sa.Column('is_system', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='active'),  # active|archived
        sa.Column('created_by', sa.Uuid(), nullable=False),
        *_audit(),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organization_id', 'name', name='uq_custom_role_org_name'),
    )
    op.create_index('ix_custom_roles_organization_id', 'custom_roles', ['organization_id'])

    op.create_table(
        'role_permissions',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('role_id', sa.Uuid(), nullable=False),
        sa.Column('resource', sa.String(length=50), nullable=False),
        sa.Column('action', sa.String(length=30), nullable=False),  # view|create|edit|delete|export|import|assign|bulk
        sa.Column('allowed', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('scope', sa.String(length=20), nullable=True),  # own|team|department|all
        *_audit(),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['role_id'], ['custom_roles.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('role_id', 'resource', 'action', name='uq_role_perm_cell'),
    )
    op.create_index('ix_role_permissions_organization_id', 'role_permissions', ['organization_id'])
    op.create_index('ix_role_permissions_role_id', 'role_permissions', ['role_id'])

    op.create_table(
        'field_permissions',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('role_id', sa.Uuid(), nullable=False),
        sa.Column('resource', sa.String(length=50), nullable=False),
        sa.Column('field_name', sa.String(length=100), nullable=False),
        sa.Column('access', sa.String(length=10), nullable=False, server_default='write'),  # read|write|hidden
        *_audit(),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['role_id'], ['custom_roles.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('role_id', 'resource', 'field_name', name='uq_field_perm'),
    )
    op.create_index('ix_field_permissions_organization_id', 'field_permissions', ['organization_id'])
    op.create_index('ix_field_permissions_role_id', 'field_permissions', ['role_id'])

    # Backward-compatible: existing users get NULL custom_role_id.
    op.add_column('users', sa.Column('custom_role_id', sa.Uuid(), nullable=True))
    op.create_foreign_key('fk_users_custom_role', 'users', 'custom_roles', ['custom_role_id'], ['id'])
    op.create_index('ix_users_custom_role_id', 'users', ['custom_role_id'])

    # ---------- Team Management ----------
    op.create_table(
        'teams',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(length=150), nullable=False),
        sa.Column('code', sa.String(length=30), nullable=True),
        sa.Column('description', sa.String(length=500), nullable=True),
        sa.Column('team_leader_id', sa.Uuid(), nullable=True),
        sa.Column('department_id', sa.Uuid(), nullable=True),
        sa.Column('capacity', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='active'),  # active|archived
        sa.Column('color', sa.String(length=20), nullable=True),
        sa.Column('created_by', sa.Uuid(), nullable=False),
        *_audit(),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['team_leader_id'], ['users.id']),
        sa.ForeignKeyConstraint(['department_id'], ['departments.id']),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organization_id', 'name', name='uq_team_org_name'),
    )
    op.create_index('ix_teams_organization_id', 'teams', ['organization_id'])
    op.create_index('ix_teams_team_leader_id', 'teams', ['team_leader_id'])
    op.create_index('ix_teams_department_id', 'teams', ['department_id'])
    op.create_index('ix_teams_status', 'teams', ['status'])

    op.create_table(
        'team_members',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('team_id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('role_in_team', sa.String(length=20), nullable=False, server_default='member'),  # member|leader
        sa.Column('joined_at', sa.DateTime(timezone=True), nullable=False),
        *_audit(),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['team_id'], ['teams.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('team_id', 'user_id', name='uq_team_member'),
    )
    op.create_index('ix_team_members_organization_id', 'team_members', ['organization_id'])
    op.create_index('ix_team_members_team_id', 'team_members', ['team_id'])
    op.create_index('ix_team_members_user_id', 'team_members', ['user_id'])

    op.create_table(
        'team_targets',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('team_id', sa.Uuid(), nullable=False),
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
        sa.ForeignKeyConstraint(['team_id'], ['teams.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_team_targets_organization_id', 'team_targets', ['organization_id'])
    op.create_index('ix_team_targets_team_id', 'team_targets', ['team_id'])


def downgrade() -> None:
    op.drop_table('team_targets')
    op.drop_table('team_members')
    op.drop_table('teams')
    op.drop_index('ix_users_custom_role_id', table_name='users')
    op.drop_constraint('fk_users_custom_role', 'users', type_='foreignkey')
    op.drop_column('users', 'custom_role_id')
    op.drop_table('field_permissions')
    op.drop_table('role_permissions')
    op.drop_table('custom_roles')
