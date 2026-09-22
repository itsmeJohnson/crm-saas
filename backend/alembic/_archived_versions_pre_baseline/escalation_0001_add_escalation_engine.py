"""add escalation engine: escalation_rules + escalation_events

Revision ID: escalation_0001
Revises: sla_mgmt_0001
Create Date: 2026-07-06 16:00:00.000000
"""
import sqlalchemy as sa
from alembic import op

revision = 'escalation_0001'
down_revision = 'sla_mgmt_0001'
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
        'escalation_rules',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(length=150), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('entity_type', sa.String(length=40), nullable=False, server_default='lead'),
        sa.Column('trigger_condition', sa.String(length=30), nullable=False, server_default='no_activity'),
        sa.Column('conditions', sa.JSON(), nullable=True),
        sa.Column('levels', sa.JSON(), nullable=False),
        sa.Column('business_hours_only', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('run_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('escalation_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_by', sa.Uuid(), nullable=False),
        *_audit(),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_escalation_rules_organization_id', 'escalation_rules', ['organization_id'])
    op.create_index('ix_escalation_rules_entity_type', 'escalation_rules', ['entity_type'])
    op.create_index('ix_escalation_rules_is_active', 'escalation_rules', ['is_active'])
    op.create_index('ix_escalation_rules_org_active', 'escalation_rules', ['organization_id', 'entity_type', 'is_active'])

    op.create_table(
        'escalation_events',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('rule_id', sa.Uuid(), nullable=False),
        sa.Column('entity_type', sa.String(length=40), nullable=False),
        sa.Column('entity_id', sa.Uuid(), nullable=False),
        sa.Column('level', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('escalate_to', sa.String(length=30), nullable=True),
        sa.Column('escalated_to_user_id', sa.Uuid(), nullable=True),
        sa.Column('reason', sa.String(length=200), nullable=True),
        sa.Column('hours_elapsed', sa.Float(), nullable=True),
        sa.Column('reference_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('escalated_at', sa.DateTime(timezone=True), nullable=False),
        *_audit(),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['rule_id'], ['escalation_rules.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['escalated_to_user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_escalation_events_organization_id', 'escalation_events', ['organization_id'])
    op.create_index('ix_escalation_events_rule_id', 'escalation_events', ['rule_id'])
    op.create_index('ix_escalation_events_entity_id', 'escalation_events', ['entity_id'])
    op.create_index('ix_escalation_events_level', 'escalation_events', ['level'])


def downgrade() -> None:
    op.drop_table('escalation_events')
    op.drop_table('escalation_rules')
