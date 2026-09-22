"""add calendar: calendar_events, holidays, working_hours_configs + user.calendar_feed_token

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-07-02 16:00:00.000000
"""
import sqlalchemy as sa
from alembic import op

revision = 'f2a3b4c5d6e7'
down_revision = 'e1f2a3b4c5d6'
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
    op.add_column('users', sa.Column('calendar_feed_token', sa.String(length=64), nullable=True))
    op.create_index('ix_users_calendar_feed_token', 'users', ['calendar_feed_token'])

    op.create_table(
        'calendar_events',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('event_type', sa.String(length=30), nullable=False, server_default='Meeting'),
        sa.Column('location', sa.String(length=255), nullable=True),
        sa.Column('start_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('end_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('all_day', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='Scheduled'),
        sa.Column('assigned_user_id', sa.Uuid(), nullable=True),
        sa.Column('created_by', sa.Uuid(), nullable=False),
        sa.Column('attendees', sa.JSON(), nullable=True),
        sa.Column('lead_id', sa.Uuid(), nullable=True),
        sa.Column('contact_id', sa.Uuid(), nullable=True),
        sa.Column('company_id', sa.Uuid(), nullable=True),
        sa.Column('recurrence', sa.String(length=20), nullable=False, server_default='none'),
        sa.Column('recurrence_until', sa.Date(), nullable=True),
        sa.Column('remind_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('reminded', sa.Boolean(), nullable=False, server_default=sa.false()),
        *_audit(),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['assigned_user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.ForeignKeyConstraint(['lead_id'], ['leads.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['contact_id'], ['contacts.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    for col in ('organization_id', 'event_type', 'start_at', 'status', 'assigned_user_id',
                'created_by', 'lead_id', 'contact_id', 'company_id', 'remind_at', 'reminded'):
        op.create_index(f'ix_calendar_events_{col}', 'calendar_events', [col])

    op.create_table(
        'holidays',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(length=150), nullable=False),
        sa.Column('holiday_date', sa.Date(), nullable=False),
        sa.Column('recurring_annual', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('created_by', sa.Uuid(), nullable=False),
        *_audit(),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_holidays_organization_id', 'holidays', ['organization_id'])
    op.create_index('ix_holidays_holiday_date', 'holidays', ['holiday_date'])
    op.create_index('ix_holidays_created_by', 'holidays', ['created_by'])

    op.create_table(
        'working_hours_configs',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('timezone', sa.String(length=64), nullable=False, server_default='UTC'),
        sa.Column('days', sa.JSON(), nullable=False),
        *_audit(),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organization_id'),
    )
    op.create_index('ix_working_hours_configs_organization_id', 'working_hours_configs', ['organization_id'])


def downgrade() -> None:
    op.drop_table('working_hours_configs')
    op.drop_table('holidays')
    op.drop_table('calendar_events')
    op.drop_index('ix_users_calendar_feed_token', table_name='users')
    op.drop_column('users', 'calendar_feed_token')
