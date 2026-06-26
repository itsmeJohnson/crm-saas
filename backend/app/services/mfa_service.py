"""
MFA / TOTP Service
------------------
Handles Google Authenticator-compatible TOTP multi-factor authentication.

Flow:
  1. User calls POST /auth/mfa/setup  → gets secret + QR URI (not yet active)
  2. User scans QR, enters 6-digit code, calls POST /auth/mfa/enable  → MFA activated
  3. On login, if mfa_enabled: login returns {mfa_required: true, mfa_token: <short-lived JWT>}
  4. Frontend calls POST /auth/mfa/verify with mfa_token + totp_code  → gets full tokens
  5. User can call POST /auth/mfa/disable (requires current TOTP or backup code)

Backup codes: 10 single-use codes, stored as SHA-256 hashes.
"""

import json
import secrets
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Tuple

import pyotp
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.user import UserRepository
from app.core.config import settings


BACKUP_CODE_COUNT = 10
BACKUP_CODE_LENGTH = 8  # e.g. "AB12CD34"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _hash_backup_code(raw: str) -> str:
    return hashlib.sha256(raw.upper().encode()).hexdigest()


def _generate_backup_codes() -> Tuple[list[str], list[str]]:
    """Return (raw_codes, hashed_codes). Store hashed, show raw once."""
    raw = [secrets.token_hex(4).upper() for _ in range(BACKUP_CODE_COUNT)]
    hashed = [_hash_backup_code(c) for c in raw]
    return raw, hashed


def _get_issuer() -> str:
    return getattr(settings, "MFA_ISSUER", "Johnson Softwares CRM")


# ---------------------------------------------------------------------------
# MFA Service
# ---------------------------------------------------------------------------

class MFAService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.user_repo = UserRepository(db)

    async def generate_setup(self, user_id) -> dict:
        """
        Generate a new TOTP secret and provisioning URI for QR code display.
        Does NOT enable MFA yet — user must verify with a code first.
        Returns: {secret, qr_uri, issuer}
        """
        user = await self.user_repo.get(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        secret = pyotp.random_base32()
        totp = pyotp.TOTP(secret)
        qr_uri = totp.provisioning_uri(
            name=user.email,
            issuer_name=_get_issuer()
        )

        # Store the pending secret (not yet enabled)
        user.mfa_secret = secret
        await self.db.commit()

        return {
            "secret": secret,
            "qr_uri": qr_uri,
            "issuer": _get_issuer(),
            "message": "Scan the QR code in Google Authenticator, then verify with a code to enable MFA."
        }

    async def enable_mfa(self, user_id, totp_code: str) -> dict:
        """
        Verify a TOTP code against the pending secret and activate MFA.
        Returns backup codes (shown once, never again).
        """
        user = await self.user_repo.get(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        if not user.mfa_secret:
            raise HTTPException(
                status_code=400,
                detail="MFA setup not initiated. Call /auth/mfa/setup first."
            )
        if user.mfa_enabled:
            raise HTTPException(status_code=400, detail="MFA is already enabled")

        totp = pyotp.TOTP(user.mfa_secret)
        if not totp.verify(totp_code, valid_window=1):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid TOTP code. Please try again."
            )

        raw_codes, hashed_codes = _generate_backup_codes()
        user.mfa_enabled = True
        user.mfa_backup_codes = json.dumps(hashed_codes)
        await self.db.commit()

        return {
            "message": "MFA enabled successfully.",
            "backup_codes": raw_codes,  # shown once
            "warning": "Save these backup codes. They cannot be retrieved again."
        }

    async def disable_mfa(self, user_id, totp_code: str | None = None, backup_code: str | None = None) -> dict:
        """
        Disable MFA for a user. Requires either a valid TOTP code or a backup code.
        """
        user = await self.user_repo.get(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        if not user.mfa_enabled:
            raise HTTPException(status_code=400, detail="MFA is not enabled")

        verified = False

        if totp_code and user.mfa_secret:
            totp = pyotp.TOTP(user.mfa_secret)
            verified = totp.verify(totp_code, valid_window=1)

        if not verified and backup_code:
            verified = await self._consume_backup_code(user, backup_code)

        if not verified:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid TOTP code or backup code."
            )

        user.mfa_enabled = False
        user.mfa_secret = None
        user.mfa_backup_codes = None
        await self.db.commit()

        return {"message": "MFA has been disabled."}

    async def verify_totp(self, user_id, totp_code: str) -> bool:
        """
        Verify a TOTP code during the login MFA challenge.
        Returns True if valid, False otherwise.
        """
        user = await self.user_repo.get(user_id)
        if not user or not user.mfa_enabled or not user.mfa_secret:
            return False

        totp = pyotp.TOTP(user.mfa_secret)
        return totp.verify(totp_code, valid_window=1)

    async def verify_backup_code(self, user_id, backup_code: str) -> bool:
        """
        Verify and consume a backup code during MFA challenge.
        Each code is single-use.
        """
        user = await self.user_repo.get(user_id)
        if not user or not user.mfa_enabled:
            return False
        return await self._consume_backup_code(user, backup_code)

    async def _consume_backup_code(self, user, raw_code: str) -> bool:
        """Check and consume one backup code. Returns True if found."""
        if not user.mfa_backup_codes:
            return False

        try:
            hashed_list: list[str] = json.loads(user.mfa_backup_codes)
        except (json.JSONDecodeError, TypeError):
            return False

        target = _hash_backup_code(raw_code)
        if target not in hashed_list:
            return False

        # Consume it — remove from list
        hashed_list.remove(target)
        user.mfa_backup_codes = json.dumps(hashed_list)
        await self.db.commit()
        return True

    async def regenerate_backup_codes(self, user_id, totp_code: str) -> dict:
        """
        Regenerate all backup codes (requires valid TOTP).
        """
        user = await self.user_repo.get(user_id)
        if not user or not user.mfa_enabled or not user.mfa_secret:
            raise HTTPException(status_code=400, detail="MFA is not enabled")

        totp = pyotp.TOTP(user.mfa_secret)
        if not totp.verify(totp_code, valid_window=1):
            raise HTTPException(status_code=400, detail="Invalid TOTP code")

        raw_codes, hashed_codes = _generate_backup_codes()
        user.mfa_backup_codes = json.dumps(hashed_codes)
        await self.db.commit()

        return {
            "backup_codes": raw_codes,
            "warning": "Old backup codes are now invalid. Save these new ones."
        }
