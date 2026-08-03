"""Make users.reset_token_expires timezone-aware (C3 / Launch Sprint 0).

The password-reset code writes tz-aware UTC datetimes into
users.reset_token_expires and compares them against tz-aware `now`. The column
was created as `TIMESTAMP WITHOUT TIME ZONE`, so on PostgreSQL/asyncpg both the
write (forgot-password) and the comparison (reset-password) raise
`DataError: can't subtract offset-naive and offset-aware datetimes` — a verified,
reproducible 500 that breaks the entire flow in production. SQLite (tests/dev)
does not enforce tzinfo, which is why it slipped through.

This aligns the column with the rest of the app's timestamps
(base.py created_at/updated_at are `timestamp with time zone`). Existing naive
values are interpreted as UTC — correct, since the app only ever wrote UTC.
Reset tokens are ephemeral (15-min TTL), so there is no meaningful data at risk.

Revision ID: reset_token_tz_0001
Revises: merge_heads_0001
"""
from alembic import op
import sqlalchemy as sa

revision = "reset_token_tz_0001"
down_revision = "merge_heads_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Postgres path: convert in place, treating stored naive values as UTC.
    # `postgresql_using` is ignored by dialects (e.g. SQLite) that don't need it.
    op.alter_column(
        "users",
        "reset_token_expires",
        type_=sa.DateTime(timezone=True),
        existing_type=sa.DateTime(timezone=False),
        existing_nullable=True,
        postgresql_using="reset_token_expires AT TIME ZONE 'UTC'",
    )


def downgrade() -> None:
    op.alter_column(
        "users",
        "reset_token_expires",
        type_=sa.DateTime(timezone=False),
        existing_type=sa.DateTime(timezone=True),
        existing_nullable=True,
        postgresql_using="reset_token_expires AT TIME ZONE 'UTC'",
    )
