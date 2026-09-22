"""add approval workflow: approval_chains + approval_requests + approval_actions
+ approval_delegations

Revision ID: d9e0f1a2b3c4
Revises: c8d9e0f1a2b3
Create Date: 2026-07-04 22:00:00.000000
"""
import sqlalchemy as sa
from alembic import op

revision = 'd9e0f1a2b3c4'
down_revision = 'c8d9e0f1a2b3'
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
        'approval_chains',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(length=150), nullable=False),
        sa.Column('request_type', sa.String(length=20), nullable=False),
        sa.Column('min_amount', sa.Numeric(14, 2), nullable=False, server_default='0'),
        sa.Column('steps', sa.JSON(), nullable=False),
        sa.Column('escalation_hours', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_by', sa.Uuid(), nullable=False),
        *_audit(),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_approval_chains_organization_id', 'approval_chains', ['organization_id'])
    op.create_index('ix_approval_chains_request_type', 'approval_chains', ['request_type'])
    op.create_index('ix_approval_chains_is_active', 'approval_chains', ['is_active'])

    op.create_table(
        'approval_requests',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('request_type', sa.String(length=20), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('amount', sa.Numeric(14, 2), nullable=True),
        sa.Column('reference_type', sa.String(length=50), nullable=True),
        sa.Column('reference_id', sa.String(length=64), nullable=True),
        sa.Column('payload', sa.JSON(), nullable=True),
        sa.Column('chain_id', sa.Uuid(), nullable=True),
        sa.Column('current_level', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('total_levels', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('status', sa.String(length=12), nullable=False, server_default='pending'),
        sa.Column('requested_by', sa.Uuid(), nullable=False),
        sa.Column('escalated', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('decided_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', sa.Uuid(), nullable=False),
        *_audit(),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['chain_id'], ['approval_chains.id']),
        sa.ForeignKeyConstraint(['requested_by'], ['users.id']),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_approval_requests_organization_id', 'approval_requests', ['organization_id'])
    op.create_index('ix_approval_requests_request_type', 'approval_requests', ['request_type'])
    op.create_index('ix_approval_requests_chain_id', 'approval_requests', ['chain_id'])
    op.create_index('ix_approval_requests_status', 'approval_requests', ['status'])
    op.create_index('ix_approval_requests_requested_by', 'approval_requests', ['requested_by'])

    op.create_table(
        'approval_actions',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('request_id', sa.Uuid(), nullable=False),
        sa.Column('level', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('actor_id', sa.Uuid(), nullable=True),
        sa.Column('on_behalf_of', sa.Uuid(), nullable=True),
        sa.Column('action', sa.String(length=16), nullable=False),
        sa.Column('note', sa.String(length=500), nullable=True),
        *_audit(),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['request_id'], ['approval_requests.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['actor_id'], ['users.id']),
        sa.ForeignKeyConstraint(['on_behalf_of'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_approval_actions_organization_id', 'approval_actions', ['organization_id'])
    op.create_index('ix_approval_actions_request_id', 'approval_actions', ['request_id'])

    op.create_table(
        'approval_delegations',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('delegator_id', sa.Uuid(), nullable=False),
        sa.Column('delegate_id', sa.Uuid(), nullable=False),
        sa.Column('request_type', sa.String(length=20), nullable=True),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_by', sa.Uuid(), nullable=False),
        *_audit(),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['delegator_id'], ['users.id']),
        sa.ForeignKeyConstraint(['delegate_id'], ['users.id']),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_approval_delegations_organization_id', 'approval_delegations', ['organization_id'])
    op.create_index('ix_approval_delegations_delegator_id', 'approval_delegations', ['delegator_id'])
    op.create_index('ix_approval_delegations_delegate_id', 'approval_delegations', ['delegate_id'])
    op.create_index('ix_approval_delegations_is_active', 'approval_delegations', ['is_active'])


def downgrade() -> None:
    op.drop_table('approval_delegations')
    op.drop_table('approval_actions')
    op.drop_table('approval_requests')
    op.drop_table('approval_chains')
