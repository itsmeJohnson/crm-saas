"""add company module fields + lead.company_id FK

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-07-02 13:00:00.000000
"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = 'c9d0e1f2a3b4'
down_revision = 'b8c9d0e1f2a3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('companies', sa.Column('company_type', sa.String(length=30), nullable=False, server_default='Prospect'))
    op.add_column('companies', sa.Column('source', sa.String(length=100), nullable=True))
    op.add_column('companies', sa.Column('employee_count', sa.Integer(), nullable=True))
    op.add_column('companies', sa.Column('annual_revenue', sa.Numeric(15, 2), nullable=True))
    op.add_column('companies', sa.Column('tags', sa.JSON(), nullable=True))
    op.add_column('companies', sa.Column('attachments', sa.JSON(), nullable=True))
    op.create_index('ix_companies_industry', 'companies', ['industry'])
    op.create_index('ix_companies_company_type', 'companies', ['company_type'])

    op.add_column('leads', sa.Column('company_id', sa.Uuid(), nullable=True))
    op.create_foreign_key('fk_leads_company', 'leads', 'companies', ['company_id'], ['id'])
    op.create_index('ix_leads_company_id', 'leads', ['company_id'])


def downgrade() -> None:
    op.drop_index('ix_leads_company_id', table_name='leads')
    op.drop_constraint('fk_leads_company', 'leads', type_='foreignkey')
    op.drop_column('leads', 'company_id')
    op.drop_index('ix_companies_company_type', table_name='companies')
    op.drop_index('ix_companies_industry', table_name='companies')
    op.drop_column('companies', 'attachments')
    op.drop_column('companies', 'tags')
    op.drop_column('companies', 'annual_revenue')
    op.drop_column('companies', 'employee_count')
    op.drop_column('companies', 'source')
    op.drop_column('companies', 'company_type')
