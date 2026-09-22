"""add leave management: leave_types + leave_balances + leave_requests
(Holiday Calendar reuses the existing `holidays` table)

Revision ID: a6b7c8d9e0f1
Revises: f5a6b7c8d9e0
Create Date: 2026-07-04 16:00:00.000000
"""
import sqlalchemy as sa
from alembic import op

revision = 'a6b7c8d9e0f1'
down_revision = 'f5a6b7c8d9e0'
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
        'leave_types',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('code', sa.String(length=30), nullable=True),
        sa.Column('description', sa.String(length=300), nullable=True),
        sa.Column('is_paid', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('annual_quota', sa.Numeric(5, 1), nullable=False, server_default='0'),
        sa.Column('max_consecutive_days', sa.Integer(), nullable=True),
        sa.Column('allow_half_day', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('requires_approval', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('deducts_balance', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('color', sa.String(length=20), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='active'),
        sa.Column('created_by', sa.Uuid(), nullable=False),
        *_audit(),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organization_id', 'code', name='uq_leave_type_org_code'),
    )
    op.create_index('ix_leave_types_organization_id', 'leave_types', ['organization_id'])
    op.create_index('ix_leave_types_status', 'leave_types', ['status'])

    op.create_table(
        'leave_balances',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('leave_type_id', sa.Uuid(), nullable=False),
        sa.Column('year', sa.Integer(), nullable=False),
        sa.Column('allocated', sa.Numeric(6, 1), nullable=False, server_default='0'),
        sa.Column('carried_forward', sa.Numeric(6, 1), nullable=False, server_default='0'),
        sa.Column('created_by', sa.Uuid(), nullable=False),
        *_audit(),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['leave_type_id'], ['leave_types.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organization_id', 'user_id', 'leave_type_id', 'year',
                            name='uq_leave_balance_user_type_year'),
    )
    op.create_index('ix_leave_balances_organization_id', 'leave_balances', ['organization_id'])
    op.create_index('ix_leave_balances_user_id', 'leave_balances', ['user_id'])
    op.create_index('ix_leave_balances_leave_type_id', 'leave_balances', ['leave_type_id'])
    op.create_index('ix_leave_balances_year', 'leave_balances', ['year'])

    op.create_table(
        'leave_requests',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('request_type', sa.String(length=10), nullable=False, server_default='leave'),
        sa.Column('leave_type_id', sa.Uuid(), nullable=True),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=False),
        sa.Column('is_half_day', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('half_day_period', sa.String(length=12), nullable=True),
        sa.Column('day_count', sa.Numeric(5, 1), nullable=False, server_default='0'),
        sa.Column('reason', sa.String(length=500), nullable=True),
        sa.Column('status', sa.String(length=12), nullable=False, server_default='pending'),
        sa.Column('reviewed_by', sa.Uuid(), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('review_note', sa.String(length=500), nullable=True),
        sa.Column('created_by', sa.Uuid(), nullable=False),
        *_audit(),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['leave_type_id'], ['leave_types.id']),
        sa.ForeignKeyConstraint(['reviewed_by'], ['users.id']),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_leave_requests_organization_id', 'leave_requests', ['organization_id'])
    op.create_index('ix_leave_requests_user_id', 'leave_requests', ['user_id'])
    op.create_index('ix_leave_requests_request_type', 'leave_requests', ['request_type'])
    op.create_index('ix_leave_requests_leave_type_id', 'leave_requests', ['leave_type_id'])
    op.create_index('ix_leave_requests_start_date', 'leave_requests', ['start_date'])
    op.create_index('ix_leave_requests_end_date', 'leave_requests', ['end_date'])
    op.create_index('ix_leave_requests_status', 'leave_requests', ['status'])


def downgrade() -> None:
    op.drop_table('leave_requests')
    op.drop_table('leave_balances')
    op.drop_table('leave_types')
