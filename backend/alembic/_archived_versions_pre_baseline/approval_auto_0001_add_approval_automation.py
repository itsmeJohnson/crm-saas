"""Approval Automation — dynamic rules, conditional/parallel levels, auto
approve/reject and per-level timeouts on approval chains.

Revision ID: approval_auto_0001
Revises: escalation_0001
Create Date: 2026-07-07
"""
import sqlalchemy as sa
from alembic import op

revision = 'approval_auto_0001'
down_revision = 'escalation_0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('approval_chains', sa.Column('conditions', sa.JSON(), nullable=True))
    op.add_column('approval_chains', sa.Column('auto_approve_conditions', sa.JSON(), nullable=True))
    op.add_column('approval_chains', sa.Column('auto_reject_conditions', sa.JSON(), nullable=True))
    op.add_column('approval_chains', sa.Column('timeout_hours', sa.Integer(), nullable=True))
    op.add_column('approval_chains', sa.Column('timeout_action', sa.String(length=16), nullable=True))


def downgrade() -> None:
    op.drop_column('approval_chains', 'timeout_action')
    op.drop_column('approval_chains', 'timeout_hours')
    op.drop_column('approval_chains', 'auto_reject_conditions')
    op.drop_column('approval_chains', 'auto_approve_conditions')
    op.drop_column('approval_chains', 'conditions')
