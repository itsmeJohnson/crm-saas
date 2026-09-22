"""Business Rule Designer — rule actions, reusable components, user variables,
and version history on top of the Rule Engine.

Revision ID: rule_designer_0001
Revises: approval_auto_0001
Create Date: 2026-07-07
"""
import sqlalchemy as sa
from alembic import op

revision = 'rule_designer_0001'
down_revision = 'approval_auto_0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('rules', sa.Column('actions', sa.JSON(), nullable=True))

    op.create_table(
        'rule_components',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('organization_id', sa.UUID(), sa.ForeignKey('organizations.id'), nullable=False, index=True),
        sa.Column('name', sa.String(length=150), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('entity_type', sa.String(length=40), nullable=False, server_default='lead'),
        sa.Column('definition', sa.JSON(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_by', sa.UUID(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=True, server_default=sa.false()),
    )

    op.create_table(
        'rule_variables',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('organization_id', sa.UUID(), sa.ForeignKey('organizations.id'), nullable=False, index=True),
        sa.Column('name', sa.String(length=80), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('value_type', sa.String(length=16), nullable=False, server_default='string'),
        sa.Column('value', sa.String(length=500), nullable=True),
        sa.Column('created_by', sa.UUID(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=True, server_default=sa.false()),
    )
    op.create_index('ix_rule_variables_org_name', 'rule_variables', ['organization_id', 'name'])

    op.create_table(
        'rule_versions',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('organization_id', sa.UUID(), sa.ForeignKey('organizations.id'), nullable=False, index=True),
        sa.Column('rule_id', sa.UUID(), sa.ForeignKey('rules.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('version_no', sa.Integer(), nullable=False),
        sa.Column('snapshot', sa.JSON(), nullable=False),
        sa.Column('note', sa.String(length=200), nullable=True),
        sa.Column('created_by', sa.UUID(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=True, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_table('rule_versions')
    op.drop_index('ix_rule_variables_org_name', table_name='rule_variables')
    op.drop_table('rule_variables')
    op.drop_table('rule_components')
    op.drop_column('rules', 'actions')
