"""add automation engine: automation_jobs + automation_runs + sla_policies
+ sla_breaches + scheduled_reports

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-07-05 16:00:00.000000
"""
import sqlalchemy as sa
from alembic import op

revision = 'b2c3d4e5f6a7'
down_revision = 'a1b2c3d4e5f6'
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
        'automation_jobs',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('job_key', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('category', sa.String(length=40), nullable=False, server_default='general'),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_enabled', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('schedule', sa.String(length=30), nullable=False, server_default='daily'),
        sa.Column('max_retries', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('last_run_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_status', sa.String(length=12), nullable=True),
        sa.Column('next_run_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('run_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('fail_count', sa.Integer(), nullable=False, server_default='0'),
        *_audit(),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_automation_jobs_organization_id', 'automation_jobs', ['organization_id'])
    op.create_index('ix_automation_jobs_job_key', 'automation_jobs', ['job_key'])
    op.create_index('ix_automation_jobs_is_enabled', 'automation_jobs', ['is_enabled'])
    op.create_index('uq_automation_job_org_key', 'automation_jobs', ['organization_id', 'job_key'], unique=True)

    op.create_table(
        'automation_runs',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('job_id', sa.Uuid(), nullable=True),
        sa.Column('job_key', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=12), nullable=False, server_default='running'),
        sa.Column('triggered_by', sa.String(length=20), nullable=False, server_default='schedule'),
        sa.Column('items_processed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('actor_user_id', sa.Uuid(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        *_audit(),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['job_id'], ['automation_jobs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['actor_user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_automation_runs_organization_id', 'automation_runs', ['organization_id'])
    op.create_index('ix_automation_runs_job_id', 'automation_runs', ['job_id'])
    op.create_index('ix_automation_runs_job_key', 'automation_runs', ['job_key'])
    op.create_index('ix_automation_runs_status', 'automation_runs', ['status'])

    op.create_table(
        'sla_policies',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(length=150), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('entity_type', sa.String(length=40), nullable=False, server_default='lead'),
        sa.Column('metric', sa.String(length=30), nullable=False, server_default='first_response'),
        sa.Column('threshold_hours', sa.Float(), nullable=False, server_default='24.0'),
        sa.Column('conditions', sa.JSON(), nullable=True),
        sa.Column('on_breach', sa.String(length=30), nullable=False, server_default='notify_manager'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('breach_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_by', sa.Uuid(), nullable=False),
        *_audit(),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_sla_policies_organization_id', 'sla_policies', ['organization_id'])
    op.create_index('ix_sla_policies_is_active', 'sla_policies', ['is_active'])

    op.create_table(
        'sla_breaches',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('policy_id', sa.Uuid(), nullable=False),
        sa.Column('entity_type', sa.String(length=40), nullable=False),
        sa.Column('entity_id', sa.Uuid(), nullable=False),
        sa.Column('metric', sa.String(length=30), nullable=False),
        sa.Column('hours_elapsed', sa.Float(), nullable=False),
        sa.Column('resolved', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('notified', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('breached_at', sa.DateTime(timezone=True), nullable=False),
        *_audit(),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['policy_id'], ['sla_policies.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_sla_breaches_organization_id', 'sla_breaches', ['organization_id'])
    op.create_index('ix_sla_breaches_policy_id', 'sla_breaches', ['policy_id'])
    op.create_index('ix_sla_breaches_entity_id', 'sla_breaches', ['entity_id'])

    op.create_table(
        'scheduled_reports',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(length=150), nullable=False),
        sa.Column('report_type', sa.String(length=40), nullable=False, server_default='lead_summary'),
        sa.Column('frequency', sa.String(length=20), nullable=False, server_default='weekly'),
        sa.Column('channel', sa.String(length=20), nullable=False, server_default='in_app'),
        sa.Column('recipients', sa.JSON(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('last_sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('next_run_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('send_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_by', sa.Uuid(), nullable=False),
        *_audit(),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_scheduled_reports_organization_id', 'scheduled_reports', ['organization_id'])
    op.create_index('ix_scheduled_reports_is_active', 'scheduled_reports', ['is_active'])


def downgrade() -> None:
    op.drop_table('scheduled_reports')
    op.drop_table('sla_breaches')
    op.drop_table('sla_policies')
    op.drop_table('automation_runs')
    op.drop_table('automation_jobs')
