"""add communication center: activity.attachments, communication_templates, communication_flags

Revision ID: a3b4c5d6e7f8
Revises: f2a3b4c5d6e7
Create Date: 2026-07-02 17:00:00.000000
"""
import sqlalchemy as sa
from alembic import op

revision = 'a3b4c5d6e7f8'
down_revision = 'f2a3b4c5d6e7'
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
    op.add_column('activities', sa.Column('attachments', sa.JSON(), nullable=True))

    op.create_table(
        'communication_templates',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(length=150), nullable=False),
        sa.Column('channel', sa.String(length=20), nullable=False, server_default='Email'),
        sa.Column('subject', sa.String(length=255), nullable=True),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('created_by', sa.Uuid(), nullable=False),
        *_audit(),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_communication_templates_organization_id', 'communication_templates', ['organization_id'])
    op.create_index('ix_communication_templates_channel', 'communication_templates', ['channel'])
    op.create_index('ix_communication_templates_created_by', 'communication_templates', ['created_by'])

    op.create_table(
        'communication_flags',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('activity_id', sa.Uuid(), nullable=False),
        sa.Column('is_read', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('is_pinned', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
        *_audit(),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['activity_id'], ['activities.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'activity_id', name='uq_comm_flag_user_activity'),
    )
    op.create_index('ix_communication_flags_organization_id', 'communication_flags', ['organization_id'])
    op.create_index('ix_communication_flags_user_id', 'communication_flags', ['user_id'])
    op.create_index('ix_communication_flags_activity_id', 'communication_flags', ['activity_id'])
    op.create_index('ix_communication_flags_is_read', 'communication_flags', ['is_read'])
    op.create_index('ix_communication_flags_is_pinned', 'communication_flags', ['is_pinned'])


def downgrade() -> None:
    op.drop_table('communication_flags')
    op.drop_table('communication_templates')
    op.drop_column('activities', 'attachments')
