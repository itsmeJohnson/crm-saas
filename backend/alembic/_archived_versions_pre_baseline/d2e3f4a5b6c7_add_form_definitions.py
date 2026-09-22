"""add form definitions (Dynamic Forms — Phase 7 work package)

Additive, reversible, inspector-guarded. Safe on SQLite (tests) and PostgreSQL
(prod). Does not touch existing tables.

Revision ID: d2e3f4a5b6c7
Revises: c1d2e3f4a5b6
Create Date: 2026-08-20
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d2e3f4a5b6c7"
down_revision: Union[str, Sequence[str], None] = "c1d2e3f4a5b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if "form_definitions" not in set(inspector.get_table_names()):
        op.create_table(
            "form_definitions",
            sa.Column("id", sa.UUID(), primary_key=True),
            sa.Column("organization_id", sa.UUID(), sa.ForeignKey("organizations.id"), nullable=False, index=True),
            sa.Column("entity_type", sa.String(length=50), nullable=False, index=True),
            sa.Column("key", sa.String(length=80), nullable=False),
            sa.Column("name", sa.String(length=150), nullable=False),
            sa.Column("description", sa.String(length=500), nullable=True),
            sa.Column("schema", sa.JSON(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_by", sa.UUID(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("updated_by", sa.UUID(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.UniqueConstraint("organization_id", "entity_type", "key", name="uq_form_org_entity_key"),
        )
        op.create_index(
            "ix_form_definitions_org_entity_active",
            "form_definitions",
            ["organization_id", "entity_type", "is_active"],
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if "form_definitions" in set(inspector.get_table_names()):
        op.drop_table("form_definitions")
