"""add SLA Management: extend sla_policies + sla_trackers + sla_pauses

Revision ID: sla_mgmt_0001
Revises: notif_auto_0001
Create Date: 2026-07-06 14:00:00.000000
"""
import sqlalchemy as sa
from alembic import op

revision = 'sla_mgmt_0001'
down_revision = 'notif_auto_0001'
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
    # ---- extend sla_policies (nullable/defaulted → automation path unaffected) ----
    op.add_column('sla_policies', sa.Column('priority_field', sa.String(length=40), nullable=False, server_default='priority'))
    op.add_column('sla_policies', sa.Column('priorities', sa.JSON(), nullable=True))
    op.add_column('sla_policies', sa.Column('response_hours', sa.Float(), nullable=True))
    op.add_column('sla_policies', sa.Column('resolution_hours', sa.Float(), nullable=True))
    op.add_column('sla_policies', sa.Column('business_hours_only', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('sla_policies', sa.Column('skip_holidays', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('sla_policies', sa.Column('escalate_after_hours', sa.Float(), nullable=True))
    op.add_column('sla_policies', sa.Column('escalate_to_role', sa.String(length=40), nullable=True))

    op.create_table(
        'sla_trackers',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('policy_id', sa.Uuid(), nullable=False),
        sa.Column('entity_type', sa.String(length=40), nullable=False),
        sa.Column('entity_id', sa.Uuid(), nullable=False),
        sa.Column('priority_level', sa.String(length=40), nullable=True),
        sa.Column('status', sa.String(length=16), nullable=False, server_default='running'),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('response_due_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolution_due_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('first_response_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('paused_seconds', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('paused_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('response_hours', sa.Float(), nullable=True),
        sa.Column('resolution_hours', sa.Float(), nullable=True),
        sa.Column('breach_type', sa.String(length=16), nullable=True),
        sa.Column('breached_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('response_breached', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('resolution_breached', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('escalated', sa.Boolean(), nullable=False, server_default=sa.false()),
        *_audit(),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['policy_id'], ['sla_policies.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_sla_trackers_organization_id', 'sla_trackers', ['organization_id'])
    op.create_index('ix_sla_trackers_policy_id', 'sla_trackers', ['policy_id'])
    op.create_index('ix_sla_trackers_entity_id', 'sla_trackers', ['entity_id'])
    op.create_index('ix_sla_trackers_status', 'sla_trackers', ['status'])
    op.create_index('ix_sla_trackers_response_due_at', 'sla_trackers', ['response_due_at'])
    op.create_index('ix_sla_trackers_resolution_due_at', 'sla_trackers', ['resolution_due_at'])
    op.create_index('ix_sla_trackers_scan', 'sla_trackers', ['organization_id', 'status'])
    op.create_index('ix_sla_trackers_entity', 'sla_trackers', ['entity_type', 'entity_id'])

    op.create_table(
        'sla_pauses',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('tracker_id', sa.Uuid(), nullable=False),
        sa.Column('reason', sa.String(length=200), nullable=True),
        sa.Column('paused_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('resumed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('paused_by', sa.Uuid(), nullable=True),
        *_audit(),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['tracker_id'], ['sla_trackers.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['paused_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_sla_pauses_organization_id', 'sla_pauses', ['organization_id'])
    op.create_index('ix_sla_pauses_tracker_id', 'sla_pauses', ['tracker_id'])


def downgrade() -> None:
    op.drop_table('sla_pauses')
    op.drop_table('sla_trackers')
    for col in ('escalate_to_role', 'escalate_after_hours', 'skip_holidays', 'business_hours_only',
                'resolution_hours', 'response_hours', 'priorities', 'priority_field'):
        op.drop_column('sla_policies', col)
