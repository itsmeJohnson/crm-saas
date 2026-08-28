"""add industry column to trial_requests (vertical chosen at public signup)

Additive, reversible, inspector-guarded. Safe on SQLite (tests) and PostgreSQL.

Revision ID: b6c7d8e9f0a1
Revises: a5b6c7d8e9f0
Create Date: 2026-08-28
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b6c7d8e9f0a1"
down_revision: Union[str, Sequence[str], None] = "a5b6c7d8e9f0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    cols = {c["name"] for c in inspector.get_columns("trial_requests")}
    if "industry" not in cols:
        op.add_column("trial_requests", sa.Column("industry", sa.String(length=50), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    cols = {c["name"] for c in inspector.get_columns("trial_requests")}
    if "industry" in cols:
        op.drop_column("trial_requests", "industry")
