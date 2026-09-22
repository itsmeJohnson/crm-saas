"""create_pipeline_stages

Revision ID: b3c4d5e6f7a8
Revises: a2b1c3d4e5f6
Create Date: 2026-06-21 12:10:00.000000

"""
import uuid
import datetime
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b3c4d5e6f7a8'
down_revision: Union[str, Sequence[str], None] = 'a2b1c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create pipeline_stages table
    op.create_table(
        'pipeline_stages',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('order_position', sa.Integer(), nullable=False),
        sa.Column('is_system_default', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='false'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organization_id', 'name', name='uq_pipeline_stages_organization_name'),
        sa.UniqueConstraint('organization_id', 'order_position', name='uq_pipeline_stages_organization_order')
    )
    op.create_index(op.f('ix_pipeline_stages_organization_id'), 'pipeline_stages', ['organization_id'], unique=False)

    # 2. Inject default system stages for existing organizations
    connection = op.get_bind()
    org_rows = connection.execute(sa.text("SELECT id FROM organizations")).fetchall()
    
    org_to_default_stage = {}
    now = datetime.datetime.now(datetime.timezone.utc)
    
    for r in org_rows:
        org_id = r[0]
        fresh_leads_id = uuid.uuid4()
        org_to_default_stage[org_id] = fresh_leads_id
        
        stages = [
            (fresh_leads_id, org_id, "Fresh Leads", 1, True),
            (uuid.uuid4(), org_id, "Contacted", 2, False),
            (uuid.uuid4(), org_id, "Followup", 3, False),
            (uuid.uuid4(), org_id, "Dropped", 4, False),
            (uuid.uuid4(), org_id, "Converted", 5, False)
        ]
        
        for stage_id, o_id, name, pos, is_default in stages:
            connection.execute(
                sa.text(
                    "INSERT INTO pipeline_stages (id, organization_id, name, order_position, is_system_default, created_at, updated_at, is_deleted) "
                    "VALUES (:id, :org_id, :name, :pos, :is_default, :now, :now, false)"
                ),
                {
                    "id": stage_id,
                    "org_id": o_id,
                    "name": name,
                    "pos": pos,
                    "is_default": is_default,
                    "now": now
                }
            )

    # 3. Add nullable stage_id to leads
    with op.batch_alter_table('leads') as batch_op:
        batch_op.add_column(sa.Column('stage_id', sa.Uuid(), nullable=True))

    # 4. Migrate data: update existing leads to point to the Fresh Leads stage of their organization
    lead_rows = connection.execute(sa.text("SELECT id, organization_id FROM leads")).fetchall()
    for l_id, o_id in lead_rows:
        default_stage_id = org_to_default_stage.get(o_id)
        if default_stage_id:
            connection.execute(
                sa.text("UPDATE leads SET stage_id = :stage_id WHERE id = :lead_id"),
                {"stage_id": default_stage_id, "lead_id": l_id}
            )

    # 5. Make stage_id non-nullable, create FK and index
    with op.batch_alter_table('leads') as batch_op:
        batch_op.alter_column('stage_id', nullable=False)
        batch_op.create_foreign_key('fk_leads_stage_id', 'pipeline_stages', ['stage_id'], ['id'])
        batch_op.create_index('ix_leads_stage_id', ['stage_id'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('leads') as batch_op:
        batch_op.drop_index('ix_leads_stage_id')
        batch_op.drop_constraint('fk_leads_stage_id', type_='foreignkey')
        batch_op.drop_column('stage_id')

    op.drop_index(op.f('ix_pipeline_stages_organization_id'), table_name='pipeline_stages')
    op.drop_table('pipeline_stages')
