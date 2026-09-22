"""Goal & OKR Management — objectives + key_results + okr_reviews.

Revision ID: okr_mgmt_0001
Revises: kpi_engine_0001
Create Date: 2026-07-16
"""
import sqlalchemy as sa
from alembic import op

revision = 'okr_mgmt_0001'
down_revision = 'kpi_engine_0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'objectives',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('organization_id', sa.UUID(), sa.ForeignKey('organizations.id'), nullable=False, index=True),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('description', sa.String(length=500), nullable=True),
        sa.Column('level', sa.String(length=16), nullable=False, index=True),
        sa.Column('department_id', sa.UUID(), sa.ForeignKey('departments.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('team_id', sa.UUID(), sa.ForeignKey('teams.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('user_id', sa.UUID(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('owner_id', sa.UUID(), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('parent_id', sa.UUID(), sa.ForeignKey('objectives.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('cycle_type', sa.String(length=12), nullable=False, server_default='quarterly'),
        sa.Column('cycle_year', sa.Integer(), nullable=False),
        sa.Column('cycle_quarter', sa.Integer(), nullable=True),
        sa.Column('start_date', sa.Date(), nullable=False, index=True),
        sa.Column('end_date', sa.Date(), nullable=False, index=True),
        sa.Column('status', sa.String(length=12), nullable=False, server_default='active', index=True),
        sa.Column('created_by', sa.UUID(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=True, server_default=sa.false()),
    )
    op.create_index('ix_objectives_org_cycle', 'objectives', ['organization_id', 'cycle_year', 'cycle_quarter'])

    op.create_table(
        'key_results',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('organization_id', sa.UUID(), sa.ForeignKey('organizations.id'), nullable=False, index=True),
        sa.Column('objective_id', sa.UUID(), sa.ForeignKey('objectives.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('kind', sa.String(length=8), nullable=False, server_default='manual'),
        sa.Column('metric', sa.String(length=40), nullable=True),
        sa.Column('unit', sa.String(length=12), nullable=False, server_default='count'),
        sa.Column('start_value', sa.Numeric(14, 2), nullable=False, server_default='0'),
        sa.Column('target_value', sa.Numeric(14, 2), nullable=False),
        sa.Column('current_value', sa.Numeric(14, 2), nullable=False, server_default='0'),
        sa.Column('weight', sa.Numeric(5, 2), nullable=False, server_default='1'),
        sa.Column('status', sa.String(length=12), nullable=False, server_default='active'),
        sa.Column('last_checkin_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', sa.UUID(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=True, server_default=sa.false()),
    )

    op.create_table(
        'okr_reviews',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('organization_id', sa.UUID(), sa.ForeignKey('organizations.id'), nullable=False, index=True),
        sa.Column('objective_id', sa.UUID(), sa.ForeignKey('objectives.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('key_result_id', sa.UUID(), sa.ForeignKey('key_results.id', ondelete='SET NULL'), nullable=True),
        sa.Column('reviewer_id', sa.UUID(), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('review_type', sa.String(length=12), nullable=False, server_default='checkin', index=True),
        sa.Column('rating', sa.Integer(), nullable=True),
        sa.Column('confidence', sa.Integer(), nullable=True),
        sa.Column('comment', sa.String(length=1000), nullable=True),
        sa.Column('progress_at', sa.Numeric(5, 1), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=True, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_table('okr_reviews')
    op.drop_table('key_results')
    op.drop_index('ix_objectives_org_cycle', table_name='objectives')
    op.drop_table('objectives')
