"""add scheduler: schedules + schedule_runs

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-07-06 10:00:00.000000
"""
import sqlalchemy as sa
from alembic import op

revision = 'e5f6a7b8c9d0'
down_revision = 'd4e5f6a7b8c9'
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
        'schedules',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(length=150), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('task_type', sa.String(length=40), nullable=False),
        sa.Column('task_config', sa.JSON(), nullable=True),
        sa.Column('schedule_kind', sa.String(length=20), nullable=False, server_default='daily'),
        sa.Column('cron_expr', sa.String(length=120), nullable=True),
        sa.Column('time_of_day', sa.String(length=5), nullable=True),
        sa.Column('day_of_week', sa.Integer(), nullable=True),
        sa.Column('day_of_month', sa.Integer(), nullable=True),
        sa.Column('interval_minutes', sa.Integer(), nullable=True),
        sa.Column('timezone', sa.String(length=64), nullable=False, server_default='UTC'),
        sa.Column('business_hours_only', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('skip_holidays', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('max_retries', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('last_run_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_status', sa.String(length=12), nullable=True),
        sa.Column('next_run_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('run_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('fail_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('skip_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_by', sa.Uuid(), nullable=False),
        *_audit(),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_schedules_organization_id', 'schedules', ['organization_id'])
    op.create_index('ix_schedules_is_active', 'schedules', ['is_active'])
    op.create_index('ix_schedules_next_run_at', 'schedules', ['next_run_at'])
    op.create_index('ix_schedules_due', 'schedules', ['is_active', 'next_run_at'])

    op.create_table(
        'schedule_runs',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('schedule_id', sa.Uuid(), nullable=False),
        sa.Column('status', sa.String(length=12), nullable=False, server_default='success'),
        sa.Column('reason', sa.String(length=40), nullable=True),
        sa.Column('triggered_by', sa.String(length=20), nullable=False, server_default='schedule'),
        sa.Column('attempts', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('result', sa.JSON(), nullable=True),
        sa.Column('scheduled_for', sa.DateTime(timezone=True), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        *_audit(),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['schedule_id'], ['schedules.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_schedule_runs_organization_id', 'schedule_runs', ['organization_id'])
    op.create_index('ix_schedule_runs_schedule_id', 'schedule_runs', ['schedule_id'])
    op.create_index('ix_schedule_runs_status', 'schedule_runs', ['status'])


def downgrade() -> None:
    op.drop_table('schedule_runs')
    op.drop_table('schedules')
