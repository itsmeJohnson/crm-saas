"""add contact module fields: tags/custom_fields/attachments, custom field defs, relationships

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-07-02 12:00:00.000000
"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = 'b8c9d0e1f2a3'
down_revision = 'a7b8c9d0e1f2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('contacts', sa.Column('tags', sa.JSON(), nullable=True))
    op.add_column('contacts', sa.Column('custom_fields', sa.JSON(), nullable=True))
    op.add_column('contacts', sa.Column('attachments', sa.JSON(), nullable=True))

    op.create_table(
        'custom_field_definitions',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('entity_type', sa.String(length=50), nullable=False, server_default='contact'),
        sa.Column('key', sa.String(length=80), nullable=False),
        sa.Column('label', sa.String(length=150), nullable=False),
        sa.Column('field_type', sa.String(length=30), nullable=False, server_default='text'),
        sa.Column('options', sa.JSON(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_by', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organization_id', 'entity_type', 'key', name='uq_custom_field_org_entity_key'),
    )
    op.create_index('ix_custom_field_definitions_organization_id', 'custom_field_definitions', ['organization_id'])
    op.create_index('ix_custom_field_definitions_entity_type', 'custom_field_definitions', ['entity_type'])
    op.create_index('ix_custom_field_definitions_created_by', 'custom_field_definitions', ['created_by'])

    op.create_table(
        'contact_relationships',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('contact_id', sa.Uuid(), nullable=False),
        sa.Column('related_contact_id', sa.Uuid(), nullable=False),
        sa.Column('relationship_type', sa.String(length=50), nullable=False),
        sa.Column('created_by', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['contact_id'], ['contacts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['related_contact_id'], ['contacts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('contact_id', 'related_contact_id', 'relationship_type', name='uq_contact_rel'),
    )
    op.create_index('ix_contact_relationships_organization_id', 'contact_relationships', ['organization_id'])
    op.create_index('ix_contact_relationships_contact_id', 'contact_relationships', ['contact_id'])
    op.create_index('ix_contact_relationships_related_contact_id', 'contact_relationships', ['related_contact_id'])
    op.create_index('ix_contact_relationships_created_by', 'contact_relationships', ['created_by'])


def downgrade() -> None:
    op.drop_table('contact_relationships')
    op.drop_table('custom_field_definitions')
    op.drop_column('contacts', 'attachments')
    op.drop_column('contacts', 'custom_fields')
    op.drop_column('contacts', 'tags')
