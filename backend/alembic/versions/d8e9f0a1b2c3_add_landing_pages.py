"""add landing_pages (Website Engine phase 1)

Additive, reversible, inspector-guarded.

Revision ID: d8e9f0a1b2c3
Revises: c7d8e9f0a1b2
Create Date: 2026-08-29
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d8e9f0a1b2c3"
down_revision: Union[str, Sequence[str], None] = "c7d8e9f0a1b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    if "landing_pages" in set(sa.inspect(conn).get_table_names()):
        return
    op.create_table(
        "landing_pages",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("organization_id", sa.UUID(), sa.ForeignKey("organizations.id"), nullable=False, index=True),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False, index=True),
        sa.Column("config", sa.JSON(), nullable=True),
        sa.Column("is_published", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("owner_user_id", sa.UUID(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("views", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("submissions", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_by", sa.UUID(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.UniqueConstraint("slug", name="uq_landing_pages_slug"),
    )


def downgrade() -> None:
    conn = op.get_bind()
    if "landing_pages" in set(sa.inspect(conn).get_table_names()):
        op.drop_table("landing_pages")
