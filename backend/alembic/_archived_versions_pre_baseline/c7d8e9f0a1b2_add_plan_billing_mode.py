"""add billing_mode, lead_cap, website_limit to plans (flat agency pricing)

Additive, reversible, inspector-guarded.

Revision ID: c7d8e9f0a1b2
Revises: b6c7d8e9f0a1
Create Date: 2026-08-29
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c7d8e9f0a1b2"
down_revision: Union[str, Sequence[str], None] = "b6c7d8e9f0a1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    cols = {c["name"] for c in sa.inspect(conn).get_columns("plans")}
    if "billing_mode" not in cols:
        op.add_column("plans", sa.Column("billing_mode", sa.String(length=20), nullable=False, server_default="per_seat"))
    if "lead_cap" not in cols:
        op.add_column("plans", sa.Column("lead_cap", sa.Integer(), nullable=True))
    if "website_limit" not in cols:
        op.add_column("plans", sa.Column("website_limit", sa.Integer(), nullable=False, server_default="1"))


def downgrade() -> None:
    conn = op.get_bind()
    cols = {c["name"] for c in sa.inspect(conn).get_columns("plans")}
    for c in ("website_limit", "lead_cap", "billing_mode"):
        if c in cols:
            op.drop_column("plans", c)
