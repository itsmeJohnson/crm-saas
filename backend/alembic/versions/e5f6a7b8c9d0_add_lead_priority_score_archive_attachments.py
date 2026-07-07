"""add lead priority, score, archive, attachments (merges dual heads)

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9, notifications_20260702
Create Date: 2026-07-02 10:00:00.000000

Adds the Lead Management fields introduced in the module completion work:
priority, score, is_archived/archived_at, attachments. Also acts as the
merge point for the previously-branched migration heads.
"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = 'e5f6a7b8c9d0'
down_revision = ('d4e5f6a7b8c9', 'notifications_20260702')
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('leads', sa.Column('priority', sa.String(length=20), nullable=False, server_default='Medium'))
    op.add_column('leads', sa.Column('score', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('leads', sa.Column('is_archived', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('leads', sa.Column('archived_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('leads', sa.Column('attachments', sa.JSON(), nullable=True))
    op.create_index('ix_leads_priority', 'leads', ['priority'])
    op.create_index('ix_leads_score', 'leads', ['score'])
    op.create_index('ix_leads_is_archived', 'leads', ['is_archived'])


def downgrade() -> None:
    op.drop_index('ix_leads_is_archived', table_name='leads')
    op.drop_index('ix_leads_score', table_name='leads')
    op.drop_index('ix_leads_priority', table_name='leads')
    op.drop_column('leads', 'attachments')
    op.drop_column('leads', 'archived_at')
    op.drop_column('leads', 'is_archived')
    op.drop_column('leads', 'score')
    op.drop_column('leads', 'priority')
