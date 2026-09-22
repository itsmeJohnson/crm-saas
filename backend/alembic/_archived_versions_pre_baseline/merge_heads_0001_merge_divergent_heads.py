"""Merge two divergent Alembic heads so `alembic upgrade head` is unambiguous.

Before this, the migration graph had two heads:
  - '08f0bd8598d6'          (add allow_additional_seats / users — pre-existing)
  - 'refresh_token_hash_0001' (ADR-001 / H1 refresh-token hashing)

With two heads, `alembic upgrade head` fails ("Multiple head revisions are
present"), which would block deploying the H1 migration. This is a **no-op merge**
(no schema or data change) that unifies both branches into a single head. The
divergence is pre-existing and unrelated to H1's logic; this only makes the graph
deployable.

Revision ID: merge_heads_0001
Revises: 08f0bd8598d6, refresh_token_hash_0001
"""

revision = "merge_heads_0001"
down_revision = ("08f0bd8598d6", "refresh_token_hash_0001")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
