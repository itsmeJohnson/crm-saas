"""add performance management: performance_kpis + performance_goals
+ performance_achievements

Revision ID: c8d9e0f1a2b3
Revises: b7c8d9e0f1a2
Create Date: 2026-07-04 20:00:00.000000
"""
import sqlalchemy as sa
from alembic import op

revision = 'c8d9e0f1a2b3'
down_revision = 'b7c8d9e0f1a2'
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
        'performance_kpis',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('code', sa.String(length=30), nullable=True),
        sa.Column('metric', sa.String(length=30), nullable=False),
        sa.Column('description', sa.String(length=300), nullable=True),
        sa.Column('unit', sa.String(length=12), nullable=False, server_default='count'),
        sa.Column('weight', sa.Numeric(5, 2), nullable=False, server_default='1'),
        sa.Column('higher_is_better', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='active'),
        sa.Column('color', sa.String(length=20), nullable=True),
        sa.Column('created_by', sa.Uuid(), nullable=False),
        *_audit(),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organization_id', 'code', name='uq_perf_kpi_org_code'),
    )
    op.create_index('ix_performance_kpis_organization_id', 'performance_kpis', ['organization_id'])
    op.create_index('ix_performance_kpis_status', 'performance_kpis', ['status'])

    op.create_table(
        'performance_goals',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('kpi_id', sa.Uuid(), nullable=False),
        sa.Column('period', sa.String(length=12), nullable=False, server_default='monthly'),
        sa.Column('target_value', sa.Numeric(14, 2), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=False),
        sa.Column('status', sa.String(length=12), nullable=False, server_default='active'),
        sa.Column('created_by', sa.Uuid(), nullable=False),
        *_audit(),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['kpi_id'], ['performance_kpis.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_performance_goals_organization_id', 'performance_goals', ['organization_id'])
    op.create_index('ix_performance_goals_user_id', 'performance_goals', ['user_id'])
    op.create_index('ix_performance_goals_kpi_id', 'performance_goals', ['kpi_id'])
    op.create_index('ix_performance_goals_start_date', 'performance_goals', ['start_date'])
    op.create_index('ix_performance_goals_end_date', 'performance_goals', ['end_date'])
    op.create_index('ix_performance_goals_status', 'performance_goals', ['status'])

    op.create_table(
        'performance_achievements',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('goal_id', sa.Uuid(), nullable=True),
        sa.Column('kpi_id', sa.Uuid(), nullable=True),
        sa.Column('title', sa.String(length=150), nullable=False),
        sa.Column('badge', sa.String(length=20), nullable=True),
        sa.Column('period_label', sa.String(length=40), nullable=True),
        sa.Column('achieved_value', sa.Numeric(14, 2), nullable=False, server_default='0'),
        sa.Column('target_value', sa.Numeric(14, 2), nullable=False, server_default='0'),
        sa.Column('attainment', sa.Numeric(6, 1), nullable=False, server_default='0'),
        sa.Column('awarded_at', sa.DateTime(timezone=True), nullable=False),
        *_audit(),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['goal_id'], ['performance_goals.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['kpi_id'], ['performance_kpis.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('goal_id', 'user_id', name='uq_perf_achievement_goal_user'),
    )
    op.create_index('ix_performance_achievements_organization_id', 'performance_achievements', ['organization_id'])
    op.create_index('ix_performance_achievements_user_id', 'performance_achievements', ['user_id'])
    op.create_index('ix_performance_achievements_goal_id', 'performance_achievements', ['goal_id'])


def downgrade() -> None:
    op.drop_table('performance_achievements')
    op.drop_table('performance_goals')
    op.drop_table('performance_kpis')
