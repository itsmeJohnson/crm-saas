"""add rule engine: rules + rule_evaluations (reusable boolean condition trees)

Revision ID: a1b2c3d4e5f6
Revises: f1a2b3c4d5e6
Create Date: 2026-07-05 14:00:00.000000
"""
import sqlalchemy as sa
from alembic import op

revision = 'a1b2c3d4e5f6'
down_revision = 'f1a2b3c4d5e6'
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
        'rules',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(length=150), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('category', sa.String(length=80), nullable=True),
        sa.Column('entity_type', sa.String(length=40), nullable=False, server_default='lead'),
        sa.Column('definition', sa.JSON(), nullable=False),
        sa.Column('priority', sa.Integer(), nullable=False, server_default='100'),
        sa.Column('conflict_strategy', sa.String(length=30), nullable=False, server_default='highest_priority'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('is_template', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('match_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('eval_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_evaluated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', sa.Uuid(), nullable=False),
        *_audit(),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_rules_organization_id', 'rules', ['organization_id'])
    op.create_index('ix_rules_category', 'rules', ['category'])
    op.create_index('ix_rules_entity_type', 'rules', ['entity_type'])
    op.create_index('ix_rules_priority', 'rules', ['priority'])
    op.create_index('ix_rules_is_active', 'rules', ['is_active'])
    op.create_index('ix_rules_is_template', 'rules', ['is_template'])
    op.create_index('ix_rules_created_by', 'rules', ['created_by'])
    op.create_index('ix_rules_org_entity_active', 'rules', ['organization_id', 'entity_type', 'is_active'])

    op.create_table(
        'rule_evaluations',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('rule_id', sa.Uuid(), nullable=False),
        sa.Column('entity_type', sa.String(length=40), nullable=False),
        sa.Column('entity_id', sa.Uuid(), nullable=True),
        sa.Column('matched', sa.Boolean(), nullable=False),
        sa.Column('is_test', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('trace', sa.JSON(), nullable=True),
        sa.Column('evaluated_by', sa.Uuid(), nullable=True),
        *_audit(),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['rule_id'], ['rules.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['evaluated_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_rule_evaluations_organization_id', 'rule_evaluations', ['organization_id'])
    op.create_index('ix_rule_evaluations_rule_id', 'rule_evaluations', ['rule_id'])
    op.create_index('ix_rule_evaluations_matched', 'rule_evaluations', ['matched'])


def downgrade() -> None:
    op.drop_table('rule_evaluations')
    op.drop_table('rules')
