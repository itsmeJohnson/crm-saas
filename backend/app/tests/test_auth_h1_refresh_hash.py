"""H1 / ADR-001 — refresh tokens are stored as SHA-256 hashes at rest.

The client keeps sending the original refresh token; the server hashes it before
lookup. Existing plaintext rows are migrated in place (see
alembic/versions/refresh_token_hash_0001_*), so active sessions survive.
"""
from datetime import datetime, timezone, timedelta

from sqlalchemy import select

from app.core.security import get_password_hash, hash_token
from app.repositories.organization import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.repositories.session import UserSessionRepository
from app.services.auth_service import AuthService
from app.models.session import UserSession

import pytest


@pytest.fixture
async def user(db):
    org = await OrganizationRepository(db).create({"name": "H1 Org", "slug": "h1-org"})
    await db.commit()
    u = await UserRepository(db).create_user(org.id, {
        "email": "h1@example.com", "hashed_password": get_password_hash("password123"),
        "first_name": "H", "last_name": "One", "role": "OrgAdmin", "is_active": True})
    await db.commit()
    return u


async def test_session_stores_hash_not_raw(db, user):
    tokens = await AuthService(db).create_user_session(user.id)
    await db.commit()
    row = (await db.execute(select(UserSession).where(UserSession.user_id == user.id))).scalars().first()
    assert row is not None
    assert row.refresh_token == hash_token(tokens.refresh_token)   # stored value is the hash
    assert row.refresh_token != tokens.refresh_token               # raw token never persisted
    assert "." not in row.refresh_token and len(row.refresh_token) == 64  # sha256 hex, not a JWT


async def test_refresh_lookup_by_raw_token_works(db, user):
    tokens = await AuthService(db).create_user_session(user.id)
    await db.commit()
    found = await UserSessionRepository(db).get_by_refresh_token(tokens.refresh_token)
    assert found is not None and found.user_id == user.id


async def test_presenting_the_stored_hash_does_not_authenticate(db, user):
    tokens = await AuthService(db).create_user_session(user.id)
    await db.commit()
    # A hash exfiltrated from the DB is useless as a refresh token (it gets re-hashed).
    assert await UserSessionRepository(db).get_by_refresh_token(hash_token(tokens.refresh_token)) is None


async def test_full_refresh_rotation(db, user):
    svc = AuthService(db)
    tokens = await svc.create_user_session(user.id)
    await db.commit()
    new_tokens = await svc.refresh_session(tokens.refresh_token)
    await db.commit()
    assert new_tokens.refresh_token and new_tokens.refresh_token != tokens.refresh_token
    repo = UserSessionRepository(db)
    assert await repo.get_by_refresh_token(tokens.refresh_token) is None      # old revoked
    assert await repo.get_by_refresh_token(new_tokens.refresh_token) is not None  # new works


async def test_logout_revokes_session(db, user):
    svc = AuthService(db)
    tokens = await svc.create_user_session(user.id)
    await db.commit()
    await svc.logout_session(tokens.refresh_token)
    await db.commit()
    assert await UserSessionRepository(db).get_by_refresh_token(tokens.refresh_token) is None


async def test_backward_compat_existing_plaintext_token_after_migration(db, user):
    # Simulate a pre-migration row that holds a RAW JWT-like token (contains '.').
    raw = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ1In0.signature_part_ABCdef"
    db.add(UserSession(user_id=user.id, refresh_token=raw,
                       expires_at=datetime.now(timezone.utc) + timedelta(days=7), is_revoked=False))
    await db.commit()
    repo = UserSessionRepository(db)

    # Before migration the hashing lookup can't match the plaintext row...
    assert await repo.get_by_refresh_token(raw) is None
    # ...run the migration's transformation (hash rows containing '.')...
    row = (await db.execute(select(UserSession).where(UserSession.refresh_token == raw))).scalars().first()
    row.refresh_token = hash_token(raw)
    await db.commit()
    # ...and the client's ORIGINAL token keeps working.
    found = await repo.get_by_refresh_token(raw)
    assert found is not None and found.user_id == user.id
