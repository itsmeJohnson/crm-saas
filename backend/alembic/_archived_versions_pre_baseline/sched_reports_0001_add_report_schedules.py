"""Scheduled Reports — report_schedules + report_delivery_logs.

Revision ID: sched_reports_0001
Revises: data_viz_0001
Create Date: 2026-07-17
"""
import sqlalchemy as sa
from alembic import op

revision = 'sched_reports_0001'
down_revision = 'data_viz_0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'report_schedules',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('organization_id', sa.UUID(), sa.ForeignKey('organizations.id'), nullable=False, index=True),
        sa.Column('report_id', sa.UUID(), sa.ForeignKey('report_definitions.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('name', sa.String(length=150), nullable=False),
        sa.Column('frequency', sa.String(length=12), nullable=False, server_default='weekly'),
        sa.Column('formats', sa.JSON(), nullable=False),
        sa.Column('channels', sa.JSON(), nullable=False),
        sa.Column('recipients', sa.JSON(), nullable=False),
        sa.Column('extra_emails', sa.JSON(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true(), index=True),
        sa.Column('max_retries', sa.Integer(), nullable=False, server_default='2'),
        sa.Column('fail_streak', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('next_run_at', sa.DateTime(timezone=True), nullable=True, index=True),
        sa.Column('last_run_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_status', sa.String(length=12), nullable=True),
        sa.Column('run_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_by', sa.UUID(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=True, server_default=sa.false()),
    )

    op.create_table(
        'report_delivery_logs',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('organization_id', sa.UUID(), sa.ForeignKey('organizations.id'), nullable=False, index=True),
        sa.Column('schedule_id', sa.UUID(), sa.ForeignKey('report_schedules.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('report_id', sa.UUID(), sa.ForeignKey('report_definitions.id', ondelete='SET NULL'), nullable=True),
        sa.Column('status', sa.String(length=12), nullable=False, server_default='pending', index=True),
        sa.Column('attempt', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('triggered_by', sa.String(length=12), nullable=False, server_default='schedule'),
        sa.Column('frequency', sa.String(length=12), nullable=True),
        sa.Column('formats', sa.JSON(), nullable=True),
        sa.Column('channels', sa.JSON(), nullable=True),
        sa.Column('recipient_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('rows_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('detail', sa.JSON(), nullable=True),
        sa.Column('error', sa.String(length=500), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=True, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_table('report_delivery_logs')
    op.drop_table('report_schedules')
