"""add attendance management: shifts + shift_assignments + attendance_records
+ attendance_breaks + attendance_corrections

Revision ID: f5a6b7c8d9e0
Revises: e4f5a6b7c8d9
Create Date: 2026-07-04 14:00:00.000000
"""
import sqlalchemy as sa
from alembic import op

revision = 'f5a6b7c8d9e0'
down_revision = 'e4f5a6b7c8d9'
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
        'shifts',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('code', sa.String(length=30), nullable=True),
        sa.Column('start_time', sa.Time(), nullable=False),
        sa.Column('end_time', sa.Time(), nullable=False),
        sa.Column('break_minutes', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('grace_minutes', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('working_days', sa.JSON(), nullable=True),
        sa.Column('is_night_shift', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='active'),
        sa.Column('color', sa.String(length=20), nullable=True),
        sa.Column('created_by', sa.Uuid(), nullable=False),
        *_audit(),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organization_id', 'code', name='uq_shift_org_code'),
    )
    op.create_index('ix_shifts_organization_id', 'shifts', ['organization_id'])
    op.create_index('ix_shifts_status', 'shifts', ['status'])

    op.create_table(
        'shift_assignments',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('shift_id', sa.Uuid(), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=True),
        sa.Column('created_by', sa.Uuid(), nullable=False),
        *_audit(),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['shift_id'], ['shifts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_shift_assignments_organization_id', 'shift_assignments', ['organization_id'])
    op.create_index('ix_shift_assignments_user_id', 'shift_assignments', ['user_id'])
    op.create_index('ix_shift_assignments_shift_id', 'shift_assignments', ['shift_id'])
    op.create_index('ix_shift_assignments_start_date', 'shift_assignments', ['start_date'])

    op.create_table(
        'attendance_records',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('work_date', sa.Date(), nullable=False),
        sa.Column('shift_id', sa.Uuid(), nullable=True),
        sa.Column('clock_in_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('clock_out_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='present'),
        sa.Column('is_late', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('late_minutes', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_early_logout', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('early_minutes', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('worked_minutes', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('break_minutes', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('in_latitude', sa.Numeric(10, 6), nullable=True),
        sa.Column('in_longitude', sa.Numeric(10, 6), nullable=True),
        sa.Column('out_latitude', sa.Numeric(10, 6), nullable=True),
        sa.Column('out_longitude', sa.Numeric(10, 6), nullable=True),
        sa.Column('source', sa.String(length=20), nullable=False, server_default='web'),
        sa.Column('device_id', sa.String(length=100), nullable=True),
        sa.Column('notes', sa.String(length=500), nullable=True),
        sa.Column('created_by', sa.Uuid(), nullable=True),
        *_audit(),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['shift_id'], ['shifts.id']),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organization_id', 'user_id', 'work_date', name='uq_attendance_user_date'),
    )
    op.create_index('ix_attendance_records_organization_id', 'attendance_records', ['organization_id'])
    op.create_index('ix_attendance_records_user_id', 'attendance_records', ['user_id'])
    op.create_index('ix_attendance_records_work_date', 'attendance_records', ['work_date'])
    op.create_index('ix_attendance_records_shift_id', 'attendance_records', ['shift_id'])
    op.create_index('ix_attendance_records_status', 'attendance_records', ['status'])

    op.create_table(
        'attendance_breaks',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('attendance_id', sa.Uuid(), nullable=False),
        sa.Column('break_start', sa.DateTime(timezone=True), nullable=False),
        sa.Column('break_end', sa.DateTime(timezone=True), nullable=True),
        sa.Column('minutes', sa.Integer(), nullable=True),
        sa.Column('reason', sa.String(length=200), nullable=True),
        *_audit(),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['attendance_id'], ['attendance_records.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_attendance_breaks_organization_id', 'attendance_breaks', ['organization_id'])
    op.create_index('ix_attendance_breaks_attendance_id', 'attendance_breaks', ['attendance_id'])

    op.create_table(
        'attendance_corrections',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('attendance_id', sa.Uuid(), nullable=True),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('work_date', sa.Date(), nullable=False),
        sa.Column('reason', sa.String(length=500), nullable=False),
        sa.Column('proposed', sa.JSON(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
        sa.Column('requested_by', sa.Uuid(), nullable=False),
        sa.Column('reviewed_by', sa.Uuid(), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('review_note', sa.String(length=500), nullable=True),
        *_audit(),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['attendance_id'], ['attendance_records.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['requested_by'], ['users.id']),
        sa.ForeignKeyConstraint(['reviewed_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_attendance_corrections_organization_id', 'attendance_corrections', ['organization_id'])
    op.create_index('ix_attendance_corrections_attendance_id', 'attendance_corrections', ['attendance_id'])
    op.create_index('ix_attendance_corrections_user_id', 'attendance_corrections', ['user_id'])
    op.create_index('ix_attendance_corrections_status', 'attendance_corrections', ['status'])


def downgrade() -> None:
    op.drop_table('attendance_corrections')
    op.drop_table('attendance_breaks')
    op.drop_table('attendance_records')
    op.drop_table('shift_assignments')
    op.drop_table('shifts')
