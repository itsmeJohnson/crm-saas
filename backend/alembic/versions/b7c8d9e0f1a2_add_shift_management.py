"""add shift management: extend shifts (shift_type/is_flexible/works_on_holidays)
+ shift_rotations + shift_rotation_members

Revision ID: b7c8d9e0f1a2
Revises: a6b7c8d9e0f1
Create Date: 2026-07-04 18:00:00.000000
"""
import sqlalchemy as sa
from alembic import op

revision = 'b7c8d9e0f1a2'
down_revision = 'a6b7c8d9e0f1'
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
    # Backward-compatible: existing shifts become fixed "general" shifts.
    op.add_column('shifts', sa.Column('shift_type', sa.String(length=20), nullable=False, server_default='general'))
    op.add_column('shifts', sa.Column('is_flexible', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('shifts', sa.Column('works_on_holidays', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_index('ix_shifts_shift_type', 'shifts', ['shift_type'])

    op.create_table(
        'shift_rotations',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('code', sa.String(length=30), nullable=True),
        sa.Column('description', sa.String(length=300), nullable=True),
        sa.Column('shift_sequence', sa.JSON(), nullable=False),
        sa.Column('rotation_days', sa.Integer(), nullable=False, server_default='7'),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='active'),
        sa.Column('created_by', sa.Uuid(), nullable=False),
        *_audit(),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organization_id', 'code', name='uq_shift_rotation_org_code'),
    )
    op.create_index('ix_shift_rotations_organization_id', 'shift_rotations', ['organization_id'])
    op.create_index('ix_shift_rotations_status', 'shift_rotations', ['status'])

    op.create_table(
        'shift_rotation_members',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('rotation_id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('anchor_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=True),
        sa.Column('created_by', sa.Uuid(), nullable=False),
        *_audit(),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['rotation_id'], ['shift_rotations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('rotation_id', 'user_id', name='uq_shift_rotation_member'),
    )
    op.create_index('ix_shift_rotation_members_organization_id', 'shift_rotation_members', ['organization_id'])
    op.create_index('ix_shift_rotation_members_rotation_id', 'shift_rotation_members', ['rotation_id'])
    op.create_index('ix_shift_rotation_members_user_id', 'shift_rotation_members', ['user_id'])


def downgrade() -> None:
    op.drop_table('shift_rotation_members')
    op.drop_table('shift_rotations')
    op.drop_index('ix_shifts_shift_type', table_name='shifts')
    op.drop_column('shifts', 'works_on_holidays')
    op.drop_column('shifts', 'is_flexible')
    op.drop_column('shifts', 'shift_type')
