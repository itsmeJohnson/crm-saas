"""add otp_verifications table (BulkSMSPlans verify / verify_status)

Additive, reversible, inspector-guarded. Safe on SQLite (tests) and PostgreSQL
(prod). Does not touch existing tables.

Revision ID: f4a5b6c7d8e9
Revises: e3f4a5b6c7d8
Create Date: 2026-08-28
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f4a5b6c7d8e9"
down_revision: Union[str, Sequence[str], None] = "e3f4a5b6c7d8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if "otp_verifications" in set(inspector.get_table_names()):
        return
    op.create_table(
        "otp_verifications",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("organization_id", sa.UUID(), sa.ForeignKey("organizations.id"), nullable=False, index=True),
        sa.Column("number", sa.String(length=32), nullable=False),
        sa.Column("purpose", sa.String(length=50), nullable=True),
        sa.Column("provider", sa.String(length=30), nullable=False, server_default="bulksmsplans"),
        sa.Column("provider_message_id", sa.String(length=128), nullable=True, index=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(length=300), nullable=True),
        sa.Column("created_by", sa.UUID(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("lead_id", sa.UUID(), sa.ForeignKey("leads.id"), nullable=True),
        sa.Column("contact_id", sa.UUID(), sa.ForeignKey("contacts.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_otp_verifications_org_status", "otp_verifications",
                    ["organization_id", "status"])


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if "otp_verifications" not in set(inspector.get_table_names()):
        return
    op.drop_index("ix_otp_verifications_org_status", table_name="otp_verifications")
    op.drop_table("otp_verifications")
