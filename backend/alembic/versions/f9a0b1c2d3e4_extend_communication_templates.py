"""extend communication_templates (category/approval/versioning) + versions table

Revision ID: f9a0b1c2d3e4
Revises: e8f9a0b1c2d3
Create Date: 2026-07-03 18:00:00.000000
"""
import sqlalchemy as sa
from alembic import op

revision = 'f9a0b1c2d3e4'
down_revision = 'e8f9a0b1c2d3'
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
    # status defaults to 'approved' so existing rows + the legacy quick-create path
    # stay immediately usable; the managed module creates drafts explicitly.
    op.add_column('communication_templates', sa.Column('category', sa.String(length=80), nullable=True))
    op.add_column('communication_templates', sa.Column('description', sa.String(length=255), nullable=True))
    op.add_column('communication_templates', sa.Column('status', sa.String(length=20), nullable=False, server_default='approved'))
    op.add_column('communication_templates', sa.Column('version', sa.Integer(), nullable=False, server_default='1'))
    op.add_column('communication_templates', sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('communication_templates', sa.Column('approved_by', sa.Uuid(), nullable=True))
    op.add_column('communication_templates', sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('communication_templates', sa.Column('rejected_reason', sa.String(length=500), nullable=True))
    op.add_column('communication_templates', sa.Column('usage_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('communication_templates', sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('communication_templates', sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()))
    op.create_index('ix_communication_templates_status', 'communication_templates', ['status'])
    op.create_index('ix_communication_templates_category', 'communication_templates', ['category'])
    op.create_foreign_key('fk_comm_templates_approved_by', 'communication_templates', 'users', ['approved_by'], ['id'])

    op.create_table(
        'communication_template_versions',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('template_id', sa.Uuid(), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=150), nullable=False),
        sa.Column('channel', sa.String(length=20), nullable=False),
        sa.Column('subject', sa.String(length=255), nullable=True),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('category', sa.String(length=80), nullable=True),
        sa.Column('change_note', sa.String(length=255), nullable=True),
        sa.Column('edited_by', sa.Uuid(), nullable=False),
        *_audit(),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['template_id'], ['communication_templates.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['edited_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_comm_template_versions_template_id', 'communication_template_versions', ['template_id'])
    op.create_index('ix_comm_template_versions_organization_id', 'communication_template_versions', ['organization_id'])


def downgrade() -> None:
    op.drop_table('communication_template_versions')
    op.drop_constraint('fk_comm_templates_approved_by', 'communication_templates', type_='foreignkey')
    op.drop_index('ix_communication_templates_category', table_name='communication_templates')
    op.drop_index('ix_communication_templates_status', table_name='communication_templates')
    for col in ('is_active', 'last_used_at', 'usage_count', 'rejected_reason', 'approved_at', 'approved_by',
                'submitted_at', 'version', 'status', 'description', 'category'):
        op.drop_column('communication_templates', col)
