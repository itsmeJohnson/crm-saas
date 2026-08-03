"""Hash existing refresh tokens at rest (ADR-001 / H1).

Refresh tokens were stored in plaintext in user_sessions.refresh_token. Per
ADR-001 we now store only the SHA-256 hash; the client keeps sending the original
token and the server hashes it before lookup. This one-time data migration hashes
any pre-existing plaintext rows in place, so active sessions keep working after
deploy (the client's raw token hashes to the migrated value).

No schema change: a 64-char SHA-256 hex fits the existing String(500) column.
Idempotent: only rows that still look like a JWT (contain '.') are hashed;
SHA-256 hex never contains a '.'.

Revision ID: refresh_token_hash_0001
Revises: telephony_settings_0001
"""
import hashlib
from alembic import op
import sqlalchemy as sa

revision = "refresh_token_hash_0001"
down_revision = "telephony_settings_0001"
branch_labels = None
depends_on = None


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def upgrade() -> None:
    bind = op.get_bind()
    # Only plaintext JWTs (which contain '.') — already-hashed rows are skipped,
    # making this safe to re-run.
    rows = bind.execute(
        sa.text("SELECT refresh_token FROM user_sessions WHERE refresh_token LIKE '%.%'")
    ).fetchall()
    for (raw_token,) in rows:
        bind.execute(
            sa.text("UPDATE user_sessions SET refresh_token = :h WHERE refresh_token = :old"),
            {"h": _sha256(raw_token), "old": raw_token},
        )


def downgrade() -> None:
    # Irreversible: SHA-256 is one-way. Rolling back would leave hashes in place;
    # affected users simply re-authenticate. No action taken.
    pass
