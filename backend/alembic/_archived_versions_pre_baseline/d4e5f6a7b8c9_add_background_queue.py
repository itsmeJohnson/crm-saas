"""add background queue: queue_jobs + queue_workers

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-07-05 20:00:00.000000
"""
import sqlalchemy as sa
from alembic import op

revision = 'bg_queue_0001'
down_revision = 'c3d4e5f6a7b8'
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
        'queue_jobs',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('queue', sa.String(length=20), nullable=False, server_default='default'),
        sa.Column('job_type', sa.String(length=50), nullable=False),
        sa.Column('priority', sa.Integer(), nullable=False, server_default='5'),
        sa.Column('payload', sa.JSON(), nullable=True),
        sa.Column('status', sa.String(length=16), nullable=False, server_default='queued'),
        sa.Column('attempts', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('max_attempts', sa.Integer(), nullable=False, server_default='3'),
        sa.Column('run_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('result', sa.JSON(), nullable=True),
        sa.Column('worker_id', sa.Uuid(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.Column('created_by', sa.Uuid(), nullable=True),
        *_audit(),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_queue_jobs_organization_id', 'queue_jobs', ['organization_id'])
    op.create_index('ix_queue_jobs_queue', 'queue_jobs', ['queue'])
    op.create_index('ix_queue_jobs_job_type', 'queue_jobs', ['job_type'])
    op.create_index('ix_queue_jobs_priority', 'queue_jobs', ['priority'])
    op.create_index('ix_queue_jobs_status', 'queue_jobs', ['status'])
    op.create_index('ix_queue_jobs_run_at', 'queue_jobs', ['run_at'])
    op.create_index('ix_queue_jobs_claim', 'queue_jobs', ['status', 'run_at', 'priority'])

    op.create_table(
        'queue_workers',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=True),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('status', sa.String(length=12), nullable=False, server_default='idle'),
        sa.Column('last_heartbeat', sa.DateTime(timezone=True), nullable=True),
        sa.Column('jobs_processed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('current_job_id', sa.Uuid(), nullable=True),
        sa.Column('queues', sa.String(length=200), nullable=True),
        *_audit(),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_queue_workers_organization_id', 'queue_workers', ['organization_id'])


def downgrade() -> None:
    op.drop_table('queue_workers')
    op.drop_table('queue_jobs')
