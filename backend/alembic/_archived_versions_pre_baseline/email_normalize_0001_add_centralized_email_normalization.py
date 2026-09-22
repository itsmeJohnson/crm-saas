"""add_centralized_email_normalization

Revision ID: email_normalize_0001
Revises: reset_token_tz_0001
Create Date: 2026-08-03 04:41:56.216918

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'email_normalize_0001'
down_revision: Union[str, Sequence[str], None] = 'reset_token_tz_0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    connection = op.get_bind()
    dialect_name = connection.dialect.name

    # Step A: Pre-flight check for duplicate normalized emails (fail loud, never lose data)
    if dialect_name == "postgresql":
        query = (
            "SELECT lower(btrim(email)) AS canon, count(*), array_agg(id) "
            "FROM users GROUP BY 1 HAVING count(*) > 1;"
        )
    else:
        # SQLite/others
        query = (
            "SELECT lower(trim(email)) AS canon, count(*), group_concat(id) "
            "FROM users GROUP BY 1 HAVING count(*) > 1;"
        )

    result = connection.execute(sa.text(query)).fetchall()
    if result:
        duplicates = []
        for row in result:
            canon = row[0]
            count = row[1]
            ids = row[2]
            duplicates.append(f"Normalized email '{canon}' has {count} occurrences (IDs: {ids})")
        raise Exception(
            "Migration failed because duplicate normalized emails were found in the users table:\n"
            f"{chr(10).join(duplicates)}\n"
            "Please resolve these case-variant duplicate emails manually before running the migration."
        )

    # Step B: De-duplicate pending user invitations (keep newest)
    if dialect_name == "postgresql":
        now_expr = "NOW()"
        trim_func = "btrim"
    else:
        now_expr = "datetime('now')"
        trim_func = "trim"

    select_invites = sa.text(
        f"SELECT id, lower({trim_func}(email)) as canon, created_at "
        f"FROM user_invitations "
        f"WHERE accepted = false AND revoked = false AND expires_at > {now_expr} "
        f"ORDER BY canon, created_at DESC"
    )
    rows = connection.execute(select_invites).fetchall()
    seen = set()
    ids_to_delete = []
    for row in rows:
        invite_id = row[0]
        canon = row[1]
        if canon in seen:
            ids_to_delete.append(invite_id)
        else:
            seen.add(canon)

    if ids_to_delete:
        for chunk_idx in range(0, len(ids_to_delete), 500):
            chunk = ids_to_delete[chunk_idx:chunk_idx+500]
            placeholders = ", ".join(f":id_{i}" for i in range(len(chunk)))
            params = {f"id_{i}": str(val) for i, val in enumerate(chunk)}
            connection.execute(
                sa.text(f"DELETE FROM user_invitations WHERE id IN ({placeholders})"),
                params
            )

    # Step C: Backfill user and invitation emails (idempotent lowercasing/trimming)
    if dialect_name == "postgresql":
        connection.execute(sa.text("UPDATE users SET email = lower(btrim(email)) WHERE email <> lower(btrim(email));"))
        connection.execute(sa.text("UPDATE user_invitations SET email = lower(btrim(email)) WHERE email <> lower(btrim(email));"))
    else:
        connection.execute(sa.text("UPDATE users SET email = lower(trim(email)) WHERE email <> lower(trim(email));"))
        connection.execute(sa.text("UPDATE user_invitations SET email = lower(trim(email)) WHERE email <> lower(trim(email));"))

    # Step D: Create functional unique index on lower(email)
    # Using raw SQL is dialect-safe for both Postgres and SQLite
    connection.execute(sa.text("CREATE UNIQUE INDEX uq_users_email_lower ON users (lower(email));"))


def downgrade() -> None:
    # Downgrading lowercased values is a no-op (leaving them lowercase is harmless/correct)
    # We only drop the functional unique index
    op.drop_index("uq_users_email_lower", table_name="users")
