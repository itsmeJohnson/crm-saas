"""add custom objects (definitions + records)

Phase 4.2. Additive and reversible. Idempotent + safe on SQLite (tests) and
PostgreSQL (prod) via table inspection. Does not touch existing tables.

Revision ID: c1d2e3f4a5b6
Revises: 7b9a4002721f
Create Date: 2026-08-19
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c1d2e3f4a5b6"
down_revision: Union[str, Sequence[str], None] = "7b9a4002721f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = set(inspector.get_table_names())

    if "custom_object_definitions" not in tables:
        op.create_table(
            "custom_object_definitions",
            sa.Column("id", sa.UUID(), primary_key=True),
            sa.Column("organization_id", sa.UUID(), sa.ForeignKey("organizations.id"), nullable=False, index=True),
            sa.Column("key", sa.String(length=50), nullable=False),
            sa.Column("label", sa.String(length=150), nullable=False),
            sa.Column("label_plural", sa.String(length=150), nullable=True),
            sa.Column("description", sa.String(length=500), nullable=True),
            sa.Column("icon", sa.String(length=50), nullable=True),
            sa.Column("color", sa.String(length=20), nullable=True),
            sa.Column("display_field_key", sa.String(length=80), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_by", sa.UUID(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("updated_by", sa.UUID(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.UniqueConstraint("organization_id", "key", name="uq_custom_object_org_key"),
        )

    if "custom_object_records" not in tables:
        op.create_table(
            "custom_object_records",
            sa.Column("id", sa.UUID(), primary_key=True),
            sa.Column("organization_id", sa.UUID(), sa.ForeignKey("organizations.id"), nullable=False, index=True),
            sa.Column("object_definition_id", sa.UUID(), sa.ForeignKey("custom_object_definitions.id"), nullable=False, index=True),
            sa.Column("data", sa.JSON(), nullable=True),
            sa.Column("created_by", sa.UUID(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("updated_by", sa.UUID(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
        op.create_index(
            "ix_custom_object_records_org_obj_deleted",
            "custom_object_records",
            ["organization_id", "object_definition_id", "is_deleted"],
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = set(inspector.get_table_names())
    if "custom_object_records" in tables:
        op.drop_table("custom_object_records")
    if "custom_object_definitions" in tables:
        op.drop_table("custom_object_definitions")
