"""add branch & territory management: territories + branches + territory_pincodes
+ leads.pin_code/branch_id/territory_id

Revision ID: e4f5a6b7c8d9
Revises: d3e4f5a6b7c8
Create Date: 2026-07-04 12:00:00.000000
"""
import sqlalchemy as sa
from alembic import op

revision = 'e4f5a6b7c8d9'
down_revision = 'd3e4f5a6b7c8'
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
        'territories',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(length=150), nullable=False),
        sa.Column('code', sa.String(length=30), nullable=True),
        sa.Column('level', sa.String(length=20), nullable=False, server_default='region'),  # region|zone|city|area
        sa.Column('parent_id', sa.Uuid(), nullable=True),
        sa.Column('manager_user_id', sa.Uuid(), nullable=True),
        sa.Column('description', sa.String(length=500), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='active'),
        sa.Column('color', sa.String(length=20), nullable=True),
        sa.Column('created_by', sa.Uuid(), nullable=False),
        *_audit(),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['parent_id'], ['territories.id']),
        sa.ForeignKeyConstraint(['manager_user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organization_id', 'code', name='uq_territory_org_code'),
    )
    op.create_index('ix_territories_organization_id', 'territories', ['organization_id'])
    op.create_index('ix_territories_level', 'territories', ['level'])
    op.create_index('ix_territories_parent_id', 'territories', ['parent_id'])
    op.create_index('ix_territories_status', 'territories', ['status'])

    op.create_table(
        'branches',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(length=150), nullable=False),
        sa.Column('code', sa.String(length=30), nullable=True),
        sa.Column('branch_manager_id', sa.Uuid(), nullable=True),
        sa.Column('territory_id', sa.Uuid(), nullable=True),
        sa.Column('address_line', sa.String(length=255), nullable=True),
        sa.Column('city', sa.String(length=100), nullable=True),
        sa.Column('state', sa.String(length=100), nullable=True),
        sa.Column('country', sa.String(length=100), nullable=True),
        sa.Column('pin_code', sa.String(length=20), nullable=True),
        sa.Column('phone', sa.String(length=50), nullable=True),
        sa.Column('email', sa.String(length=255), nullable=True),
        sa.Column('is_head_office', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='active'),
        sa.Column('created_by', sa.Uuid(), nullable=False),
        *_audit(),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['branch_manager_id'], ['users.id']),
        sa.ForeignKeyConstraint(['territory_id'], ['territories.id']),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organization_id', 'code', name='uq_branch_org_code'),
    )
    op.create_index('ix_branches_organization_id', 'branches', ['organization_id'])
    op.create_index('ix_branches_branch_manager_id', 'branches', ['branch_manager_id'])
    op.create_index('ix_branches_territory_id', 'branches', ['territory_id'])
    op.create_index('ix_branches_city', 'branches', ['city'])
    op.create_index('ix_branches_pin_code', 'branches', ['pin_code'])
    op.create_index('ix_branches_status', 'branches', ['status'])

    op.create_table(
        'territory_pincodes',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('pin_code', sa.String(length=20), nullable=False),
        sa.Column('city', sa.String(length=100), nullable=True),
        sa.Column('territory_id', sa.Uuid(), nullable=False),
        sa.Column('branch_id', sa.Uuid(), nullable=True),
        sa.Column('created_by', sa.Uuid(), nullable=False),
        *_audit(),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['territory_id'], ['territories.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['branch_id'], ['branches.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organization_id', 'pin_code', name='uq_territory_pincode_org_pin'),
    )
    op.create_index('ix_territory_pincodes_organization_id', 'territory_pincodes', ['organization_id'])
    op.create_index('ix_territory_pincodes_pin_code', 'territory_pincodes', ['pin_code'])
    op.create_index('ix_territory_pincodes_city', 'territory_pincodes', ['city'])
    op.create_index('ix_territory_pincodes_territory_id', 'territory_pincodes', ['territory_id'])
    op.create_index('ix_territory_pincodes_branch_id', 'territory_pincodes', ['branch_id'])

    # Backward-compatible: existing leads get NULL pin_code/branch_id/territory_id.
    op.add_column('leads', sa.Column('pin_code', sa.String(length=20), nullable=True))
    op.add_column('leads', sa.Column('branch_id', sa.Uuid(), nullable=True))
    op.add_column('leads', sa.Column('territory_id', sa.Uuid(), nullable=True))
    op.create_foreign_key('fk_leads_branch', 'leads', 'branches', ['branch_id'], ['id'])
    op.create_foreign_key('fk_leads_territory', 'leads', 'territories', ['territory_id'], ['id'])
    op.create_index('ix_leads_pin_code', 'leads', ['pin_code'])
    op.create_index('ix_leads_branch_id', 'leads', ['branch_id'])
    op.create_index('ix_leads_territory_id', 'leads', ['territory_id'])


def downgrade() -> None:
    op.drop_index('ix_leads_territory_id', table_name='leads')
    op.drop_index('ix_leads_branch_id', table_name='leads')
    op.drop_index('ix_leads_pin_code', table_name='leads')
    op.drop_constraint('fk_leads_territory', 'leads', type_='foreignkey')
    op.drop_constraint('fk_leads_branch', 'leads', type_='foreignkey')
    op.drop_column('leads', 'territory_id')
    op.drop_column('leads', 'branch_id')
    op.drop_column('leads', 'pin_code')
    op.drop_table('territory_pincodes')
    op.drop_table('branches')
    op.drop_table('territories')
