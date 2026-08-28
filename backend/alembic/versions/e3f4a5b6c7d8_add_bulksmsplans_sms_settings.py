"""add BulkSMSPlans columns to sms_settings (sms_type, default_template_id)

Additive, reversible, inspector-guarded. Safe on SQLite (tests) and PostgreSQL
(prod). Only adds two nullable/defaulted columns used by the BulkSMSPlans SMS
provider; other providers ignore them.

Revision ID: e3f4a5b6c7d8
Revises: d2e3f4a5b6c7
Create Date: 2026-08-28
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e3f4a5b6c7d8"
down_revision: Union[str, Sequence[str], None] = "d2e3f4a5b6c7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    cols = {c["name"] for c in inspector.get_columns("sms_settings")}
    if "sms_type" not in cols:
        op.add_column(
            "sms_settings",
            sa.Column("sms_type", sa.String(length=20), nullable=False,
                      server_default="Transactional"),
        )
    if "default_template_id" not in cols:
        op.add_column(
            "sms_settings",
            sa.Column("default_template_id", sa.String(length=64), nullable=True),
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    cols = {c["name"] for c in inspector.get_columns("sms_settings")}
    if "default_template_id" in cols:
        op.drop_column("sms_settings", "default_template_id")
    if "sms_type" in cols:
        op.drop_column("sms_settings", "sms_type")
