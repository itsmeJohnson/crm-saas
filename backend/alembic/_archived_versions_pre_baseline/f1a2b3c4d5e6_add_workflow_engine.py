"""add workflow orchestration engine: workflows + workflow_versions
+ workflow_executions + workflow_execution_steps (legacy workflow_rules untouched)

Revision ID: f1a2b3c4d5e6
Revises: e0f1a2b3c4d5
Create Date: 2026-07-05 12:00:00.000000
"""
import sqlalchemy as sa
from alembic import op

revision = 'f1a2b3c4d5e6'
down_revision = 'e0f1a2b3c4d5'
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
        'workflows',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(length=150), nullable=False),
        sa.Column('description', sa.String(length=500), nullable=True),
        sa.Column('category', sa.String(length=60), nullable=True),
        sa.Column('status', sa.String(length=12), nullable=False, server_default='draft'),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('is_enabled', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('is_template', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('trigger_event', sa.String(length=40), nullable=False),
        sa.Column('entity_type', sa.String(length=20), nullable=False, server_default='lead'),
        sa.Column('graph', sa.JSON(), nullable=False),
        sa.Column('created_by', sa.Uuid(), nullable=False),
        *_audit(),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_workflows_organization_id', 'workflows', ['organization_id'])
    op.create_index('ix_workflows_category', 'workflows', ['category'])
    op.create_index('ix_workflows_status', 'workflows', ['status'])
    op.create_index('ix_workflows_is_enabled', 'workflows', ['is_enabled'])
    op.create_index('ix_workflows_is_template', 'workflows', ['is_template'])
    op.create_index('ix_workflows_trigger_event', 'workflows', ['trigger_event'])

    op.create_table(
        'workflow_versions',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('workflow_id', sa.Uuid(), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('trigger_event', sa.String(length=40), nullable=False),
        sa.Column('graph', sa.JSON(), nullable=False),
        sa.Column('notes', sa.String(length=300), nullable=True),
        sa.Column('published_by', sa.Uuid(), nullable=False),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=False),
        *_audit(),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['workflow_id'], ['workflows.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['published_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('workflow_id', 'version', name='uq_workflow_version'),
    )
    op.create_index('ix_workflow_versions_organization_id', 'workflow_versions', ['organization_id'])
    op.create_index('ix_workflow_versions_workflow_id', 'workflow_versions', ['workflow_id'])

    op.create_table(
        'workflow_executions',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('workflow_id', sa.Uuid(), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('trigger_event', sa.String(length=40), nullable=False),
        sa.Column('entity_type', sa.String(length=20), nullable=False),
        sa.Column('entity_id', sa.String(length=64), nullable=True),
        sa.Column('status', sa.String(length=12), nullable=False, server_default='completed'),
        sa.Column('is_test', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('rolled_back', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('steps_run', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('triggered_by', sa.Uuid(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        *_audit(),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['workflow_id'], ['workflows.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['triggered_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_workflow_executions_organization_id', 'workflow_executions', ['organization_id'])
    op.create_index('ix_workflow_executions_workflow_id', 'workflow_executions', ['workflow_id'])
    op.create_index('ix_workflow_executions_trigger_event', 'workflow_executions', ['trigger_event'])
    op.create_index('ix_workflow_executions_status', 'workflow_executions', ['status'])
    op.create_index('ix_workflow_executions_is_test', 'workflow_executions', ['is_test'])

    op.create_table(
        'workflow_execution_steps',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('execution_id', sa.Uuid(), nullable=False),
        sa.Column('seq', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('node_id', sa.String(length=40), nullable=True),
        sa.Column('node_type', sa.String(length=20), nullable=False),
        sa.Column('action_type', sa.String(length=30), nullable=True),
        sa.Column('status', sa.String(length=12), nullable=False, server_default='success'),
        sa.Column('detail', sa.String(length=500), nullable=True),
        sa.Column('reverse', sa.JSON(), nullable=True),
        *_audit(),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['execution_id'], ['workflow_executions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_workflow_execution_steps_organization_id', 'workflow_execution_steps', ['organization_id'])
    op.create_index('ix_workflow_execution_steps_execution_id', 'workflow_execution_steps', ['execution_id'])


def downgrade() -> None:
    op.drop_table('workflow_execution_steps')
    op.drop_table('workflow_executions')
    op.drop_table('workflow_versions')
    op.drop_table('workflows')
