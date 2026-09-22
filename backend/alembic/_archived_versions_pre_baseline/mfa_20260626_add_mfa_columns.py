"""add_mfa_columns_to_users

Revision ID: mfa_20260626
Revises: sa_ctrl_v2_20260625
Create Date: 2026-06-26 00:00:00.000000

Adds:
  - users.mfa_enabled (boolean, default false)
  - users.mfa_secret (varchar 64, nullable)
  - users.mfa_backup_codes (varchar 1024, nullable - JSON list of hashed codes)
"""
from alembic import op
import sqlalchemy as sa

revision = 'mfa_20260626'
down_revision = 'sa_ctrl_v2_20260625'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('users', sa.Column('mfa_enabled', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('users', sa.Column('mfa_secret', sa.String(length=64), nullable=True))
    op.add_column('users', sa.Column('mfa_backup_codes', sa.String(length=1024), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'mfa_backup_codes')
    op.drop_column('users', 'mfa_secret')
    op.drop_column('users', 'mfa_enabled')
