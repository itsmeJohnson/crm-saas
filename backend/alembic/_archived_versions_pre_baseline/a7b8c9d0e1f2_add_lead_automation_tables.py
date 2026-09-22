"""add lead automation: convert link, reminders, escalation, workflow rules

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-07-02 11:00:00.000000
"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = 'a7b8c9d0e1f2'
down_revision = 'f6a7b8c9d0e1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Lead conversion link
    op.add_column('leads', sa.Column('converted_contact_id', sa.Uuid(), nullable=True))
    op.add_column('leads', sa.Column('converted_at', sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key('fk_leads_converted_contact', 'leads', 'contacts', ['converted_contact_id'], ['id'])
    op.create_index('ix_leads_converted_contact_id', 'leads', ['converted_contact_id'])

    # Lead reminders
    op.create_table(
        'lead_reminders',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('lead_id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('remind_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('is_sent', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('created_by', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['lead_id'], ['leads.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_lead_reminders_organization_id', 'lead_reminders', ['organization_id'])
    op.create_index('ix_lead_reminders_lead_id', 'lead_reminders', ['lead_id'])
    op.create_index('ix_lead_reminders_user_id', 'lead_reminders', ['user_id'])
    op.create_index('ix_lead_reminders_remind_at', 'lead_reminders', ['remind_at'])
    op.create_index('ix_lead_reminders_is_sent', 'lead_reminders', ['is_sent'])
    op.create_index('ix_lead_reminders_created_by', 'lead_reminders', ['created_by'])

    # Escalation config
    op.create_table(
        'escalation_configs',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('idle_days', sa.Integer(), nullable=False, server_default='3'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organization_id'),
    )
    op.create_index('ix_escalation_configs_organization_id', 'escalation_configs', ['organization_id'])

    # Workflow rules
    op.create_table(
        'workflow_rules',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(length=150), nullable=False),
        sa.Column('trigger_event', sa.String(length=50), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('conditions', sa.JSON(), nullable=False),
        sa.Column('actions', sa.JSON(), nullable=False),
        sa.Column('created_by', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_workflow_rules_organization_id', 'workflow_rules', ['organization_id'])
    op.create_index('ix_workflow_rules_trigger_event', 'workflow_rules', ['trigger_event'])
    op.create_index('ix_workflow_rules_is_active', 'workflow_rules', ['is_active'])
    op.create_index('ix_workflow_rules_created_by', 'workflow_rules', ['created_by'])


def downgrade() -> None:
    op.drop_table('workflow_rules')
    op.drop_table('escalation_configs')
    op.drop_table('lead_reminders')
    op.drop_index('ix_leads_converted_contact_id', table_name='leads')
    op.drop_constraint('fk_leads_converted_contact', 'leads', type_='foreignkey')
    op.drop_column('leads', 'converted_at')
    op.drop_column('leads', 'converted_contact_id')
