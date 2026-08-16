"""add_metadata_engine

Revision ID: metadata_engine_0001
Revises: b2c9befa8805
Create Date: 2026-08-03 18:42:00.000000

"""
import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'metadata_engine_0001'
down_revision: Union[str, Sequence[str], None] = 'b2c9befa8805'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create table pipelines
    op.create_table(
        'pipelines',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.String(length=255), nullable=True),
        sa.Column('is_default', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organization_id', 'name', name='uq_pipelines_organization_name')
    )
    op.create_index('idx_pipelines_organization', 'pipelines', ['organization_id'], unique=False)

    # 2. Backfill Default Pipelines for existing organizations
    connection = op.get_bind()
    orgs = connection.execute(sa.text("SELECT id FROM organizations;")).fetchall()
    
    # Track mapping of organization_id to pipeline_id
    org_pipeline_map = {}
    for org in orgs:
        org_id = org[0]
        pipeline_id = str(uuid.uuid4())
        org_pipeline_map[org_id] = pipeline_id
        connection.execute(
            sa.text(
                "INSERT INTO pipelines (id, organization_id, name, description, is_default, is_active, is_deleted, created_at, updated_at) "
                "VALUES (:id, :org_id, 'Default Pipeline', 'Primary Sales Pipeline', true, true, false, now(), now());"
            ),
            {"id": pipeline_id, "org_id": str(org_id)}
        )

    # 3. Alter pipeline_stages to add new columns
    op.add_column('pipeline_stages', sa.Column('pipeline_id', sa.UUID(), nullable=True))
    op.add_column('pipeline_stages', sa.Column('is_won', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('pipeline_stages', sa.Column('is_lost', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('pipeline_stages', sa.Column('probability', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('pipeline_stages', sa.Column('color', sa.String(length=20), nullable=False, server_default='#4F46E5'))
    op.add_column('pipeline_stages', sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'))

    # 4. Map active stages to default pipelines and set won/lost flags
    stages = connection.execute(sa.text("SELECT id, organization_id, name FROM pipeline_stages;")).fetchall()
    for stage in stages:
        stage_id = stage[0]
        org_id = stage[1]
        stage_name = stage[2]
        
        pipeline_id = org_pipeline_map.get(org_id)
        if pipeline_id:
            # Determine won/lost flags
            is_won = stage_name.lower().strip() in ('converted', 'won')
            is_lost = stage_name.lower().strip() in ('lost', 'dropped')
            
            connection.execute(
                sa.text(
                    "UPDATE pipeline_stages "
                    "SET pipeline_id = :pipeline_id, is_won = :is_won, is_lost = :is_lost "
                    "WHERE id = :stage_id;"
                ),
                {
                    "pipeline_id": pipeline_id,
                    "is_won": is_won,
                    "is_lost": is_lost,
                    "stage_id": str(stage_id)
                }
            )

    # 5. Enforce non-nullability on pipeline_id and alter unique constraints
    op.alter_column('pipeline_stages', 'pipeline_id', nullable=False)
    op.create_foreign_key(
        'fk_pipeline_stages_pipeline_id',
        'pipeline_stages', 'pipelines',
        ['pipeline_id'], ['id'],
        ondelete='CASCADE'
    )
    op.drop_constraint('uq_pipeline_stages_organization_name', 'pipeline_stages', type_='unique')
    op.drop_constraint('uq_pipeline_stages_organization_order', 'pipeline_stages', type_='unique')
    
    op.create_unique_constraint('uq_pipeline_stages_pipeline_name', 'pipeline_stages', ['pipeline_id', 'name'])
    op.create_unique_constraint('uq_pipeline_stages_pipeline_order', 'pipeline_stages', ['pipeline_id', 'order_position'])
    op.create_index('idx_pipeline_stages_pipeline', 'pipeline_stages', ['pipeline_id'], unique=False)

    # 6. Alter leads to add pipeline_id and custom_fields
    op.add_column('leads', sa.Column('pipeline_id', sa.UUID(), nullable=True))
    op.add_column('leads', sa.Column('custom_fields', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.create_foreign_key(
        'fk_leads_pipeline_id',
        'leads', 'pipelines',
        ['pipeline_id'], ['id'],
        ondelete='SET NULL'
    )
    
    # Backfill active leads' pipeline_id
    leads = connection.execute(sa.text("SELECT id, organization_id FROM leads;")).fetchall()
    for lead in leads:
        lead_id = lead[0]
        org_id = lead[1]
        pipeline_id = org_pipeline_map.get(org_id)
        if pipeline_id:
            connection.execute(
                sa.text("UPDATE leads SET pipeline_id = :pipeline_id WHERE id = :lead_id;"),
                {"pipeline_id": pipeline_id, "lead_id": str(lead_id)}
            )
            
    op.create_index('idx_leads_pipeline', 'leads', ['pipeline_id'], unique=False)
    op.create_index('idx_leads_custom_fields', 'leads', ['custom_fields'], unique=False, postgresql_using='gin')

    # 7. Alter custom_field_definitions to add validation, layout, and control attributes
    op.add_column('custom_field_definitions', sa.Column('placeholder', sa.String(length=255), nullable=True))
    op.add_column('custom_field_definitions', sa.Column('description', sa.String(length=500), nullable=True))
    op.add_column('custom_field_definitions', sa.Column('default_value', sa.JSON(), nullable=True))
    op.add_column('custom_field_definitions', sa.Column('validation_rules', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('custom_field_definitions', sa.Column('section', sa.String(length=100), nullable=True))
    op.add_column('custom_field_definitions', sa.Column('read_only', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('custom_field_definitions', sa.Column('visible', sa.Boolean(), nullable=False, server_default='true'))
    op.add_column('custom_field_definitions', sa.Column('searchable', sa.Boolean(), nullable=False, server_default='true'))
    op.add_column('custom_field_definitions', sa.Column('filterable', sa.Boolean(), nullable=False, server_default='true'))
    op.add_column('custom_field_definitions', sa.Column('exportable', sa.Boolean(), nullable=False, server_default='true'))
    op.add_column('custom_field_definitions', sa.Column('importable', sa.Boolean(), nullable=False, server_default='true'))
    op.add_column('custom_field_definitions', sa.Column('updated_by', sa.UUID(), nullable=True))
    op.create_foreign_key(
        'fk_custom_field_definitions_updated_by',
        'custom_field_definitions', 'users',
        ['updated_by'], ['id'],
        ondelete='SET NULL'
    )


def downgrade() -> None:
    # 1. Revert custom_field_definitions alterations
    op.drop_constraint('fk_custom_field_definitions_updated_by', 'custom_field_definitions', type_='foreignkey')
    op.drop_column('custom_field_definitions', 'updated_by')
    op.drop_column('custom_field_definitions', 'importable')
    op.drop_column('custom_field_definitions', 'exportable')
    op.drop_column('custom_field_definitions', 'filterable')
    op.drop_column('custom_field_definitions', 'searchable')
    op.drop_column('custom_field_definitions', 'visible')
    op.drop_column('custom_field_definitions', 'read_only')
    op.drop_column('custom_field_definitions', 'section')
    op.drop_column('custom_field_definitions', 'validation_rules')
    op.drop_column('custom_field_definitions', 'default_value')
    op.drop_column('custom_field_definitions', 'description')
    op.drop_column('custom_field_definitions', 'placeholder')

    # 2. Revert leads alterations
    op.drop_index('idx_leads_custom_fields', table_name='leads')
    op.drop_index('idx_leads_pipeline', table_name='leads')
    op.drop_constraint('fk_leads_pipeline_id', 'leads', type_='foreignkey')
    op.drop_column('leads', 'custom_fields')
    op.drop_column('leads', 'pipeline_id')

    # 3. Revert pipeline_stages alterations
    op.drop_index('idx_pipeline_stages_pipeline', table_name='pipeline_stages')
    op.drop_constraint('uq_pipeline_stages_pipeline_order', 'pipeline_stages', type_='unique')
    op.drop_constraint('uq_pipeline_stages_pipeline_name', 'pipeline_stages', type_='unique')
    op.drop_constraint('fk_pipeline_stages_pipeline_id', 'pipeline_stages', type_='foreignkey')
    
    op.create_unique_constraint('uq_pipeline_stages_organization_order', 'pipeline_stages', ['organization_id', 'order_position'])
    op.create_unique_constraint('uq_pipeline_stages_organization_name', 'pipeline_stages', ['organization_id', 'name'])
    
    op.drop_column('pipeline_stages', 'is_active')
    op.drop_column('pipeline_stages', 'color')
    op.drop_column('pipeline_stages', 'probability')
    op.drop_column('pipeline_stages', 'is_lost')
    op.drop_column('pipeline_stages', 'is_won')
    op.drop_column('pipeline_stages', 'pipeline_id')

    # 4. Revert pipelines table
    op.drop_index('idx_pipelines_organization', table_name='pipelines')
    op.drop_table('pipelines')
