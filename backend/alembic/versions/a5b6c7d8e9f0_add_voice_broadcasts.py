"""add voice_broadcasts + voice_broadcast_recipients (BulkSMSPlans OBD/TTS)

Additive, reversible, inspector-guarded. Safe on SQLite (tests) and PostgreSQL
(prod). Does not touch existing tables.

Revision ID: a5b6c7d8e9f0
Revises: f4a5b6c7d8e9
Create Date: 2026-08-28
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a5b6c7d8e9f0"
down_revision: Union[str, Sequence[str], None] = "f4a5b6c7d8e9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = set(inspector.get_table_names())

    if "voice_broadcasts" not in tables:
        op.create_table(
            "voice_broadcasts",
            sa.Column("id", sa.UUID(), primary_key=True),
            sa.Column("organization_id", sa.UUID(), sa.ForeignKey("organizations.id"), nullable=False, index=True),
            sa.Column("name", sa.String(length=150), nullable=False),
            sa.Column("mode", sa.String(length=20), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
            sa.Column("voice_type", sa.String(length=8), nullable=True),
            sa.Column("voice_medias_id", sa.String(length=64), nullable=True),
            sa.Column("tts_content", sa.Text(), nullable=True),
            sa.Column("tts_language", sa.String(length=20), nullable=True),
            sa.Column("tts_gender", sa.String(length=10), nullable=True),
            sa.Column("scheduled", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("scheduled_datetime", sa.DateTime(timezone=True), nullable=True),
            sa.Column("retry_interval", sa.Integer(), nullable=True),
            sa.Column("retry_count", sa.Integer(), nullable=True),
            sa.Column("provider", sa.String(length=30), nullable=False, server_default="bulksmsplans"),
            sa.Column("provider_job_id", sa.String(length=64), nullable=True),
            sa.Column("total_recipients", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("last_error", sa.String(length=500), nullable=True),
            sa.Column("created_by", sa.UUID(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        )

    if "voice_broadcast_recipients" not in tables:
        op.create_table(
            "voice_broadcast_recipients",
            sa.Column("id", sa.UUID(), primary_key=True),
            sa.Column("broadcast_id", sa.UUID(), sa.ForeignKey("voice_broadcasts.id"), nullable=False, index=True),
            sa.Column("organization_id", sa.UUID(), sa.ForeignKey("organizations.id"), nullable=False, index=True),
            sa.Column("number", sa.String(length=32), nullable=False),
            sa.Column("unique_id", sa.String(length=64), nullable=True),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
            sa.Column("vendor_status", sa.String(length=40), nullable=True),
            sa.Column("dtmf", sa.String(length=20), nullable=True),
            sa.Column("call_duration", sa.String(length=20), nullable=True),
            sa.Column("lead_id", sa.UUID(), sa.ForeignKey("leads.id"), nullable=True),
            sa.Column("contact_id", sa.UUID(), sa.ForeignKey("contacts.id"), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
        op.create_index("ix_voice_recipients_broadcast", "voice_broadcast_recipients", ["broadcast_id"])
        op.create_index("ix_voice_recipients_unique", "voice_broadcast_recipients", ["unique_id"])


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = set(inspector.get_table_names())
    if "voice_broadcast_recipients" in tables:
        op.drop_index("ix_voice_recipients_unique", table_name="voice_broadcast_recipients")
        op.drop_index("ix_voice_recipients_broadcast", table_name="voice_broadcast_recipients")
        op.drop_table("voice_broadcast_recipients")
    if "voice_broadcasts" in tables:
        op.drop_table("voice_broadcasts")
