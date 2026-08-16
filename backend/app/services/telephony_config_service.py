import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import crypto
from app.models.telephony_settings import TelephonySettings
from app.models.user import User
from app.schemas.telephony_settings import TelephonyConfigResponse, TelephonyConfigUpdate
from app.services.audit_service import AuditService

# (update field, model secret column) pairs.
_SECRET_FIELDS = [
    ("authentication_token", "authentication_token_enc"),
    ("x_api_key", "x_api_key_enc"),
    ("secret_token", "secret_token_enc"),
    ("webhook_secret", "webhook_secret_enc"),
]
_PLAIN_FIELDS = [
    "provider", "is_active", "company_id", "public_ivr_id", "call_type", "user_uuid",
    "default_caller_id", "std_code", "webhook_url", "call_recording", "power_dialer",
    "predictive_dialer", "auto_assignment", "call_retry_count", "retry_interval_seconds",
    "max_call_duration_seconds",
]


class TelephonyConfigService:
    """Organization-level telephony config. Encrypts secrets at rest, returns only
    masked views to clients, and exposes decrypted creds ONLY to server-side
    provider calls via :meth:`get_decrypted_config`."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get(self, organization_id: uuid.UUID) -> Optional[TelephonySettings]:
        res = await self.db.execute(
            select(TelephonySettings).where(
                TelephonySettings.organization_id == organization_id,
                TelephonySettings.is_deleted == False,  # noqa: E712
            )
        )
        return res.scalars().first()

    async def get_or_create(self, organization_id: uuid.UUID) -> TelephonySettings:
        row = await self.get(organization_id)
        if row is None:
            row = TelephonySettings(organization_id=organization_id)
            self.db.add(row)
            await self.db.flush()
        return row

    @staticmethod
    def to_masked_response(row: TelephonySettings) -> TelephonyConfigResponse:
        return TelephonyConfigResponse(
            provider=row.provider,
            is_active=row.is_active,
            is_connected=row.is_connected,
            company_id=row.company_id,
            public_ivr_id=row.public_ivr_id,
            call_type=row.call_type,
            user_uuid=row.user_uuid,
            default_caller_id=row.default_caller_id,
            std_code=row.std_code,
            webhook_url=row.webhook_url,
            has_authentication_token=bool(row.authentication_token_enc),
            has_x_api_key=bool(row.x_api_key_enc),
            has_secret_token=bool(row.secret_token_enc),
            has_webhook_secret=bool(row.webhook_secret_enc),
            call_recording=row.call_recording,
            power_dialer=row.power_dialer,
            predictive_dialer=row.predictive_dialer,
            auto_assignment=row.auto_assignment,
            call_retry_count=row.call_retry_count,
            retry_interval_seconds=row.retry_interval_seconds,
            max_call_duration_seconds=row.max_call_duration_seconds,
        )

    @staticmethod
    def _audit_snapshot(row: TelephonySettings) -> dict:
        """Non-secret snapshot for the audit trail (secrets → set/unset only)."""
        snap = {f: getattr(row, f) for f in _PLAIN_FIELDS}
        snap["is_connected"] = row.is_connected
        for field, col in _SECRET_FIELDS:
            snap[field] = "set" if getattr(row, col) else None
        return snap

    async def update(
        self, actor: User, req: TelephonyConfigUpdate,
        ip_address: str | None = None, browser_info: str | None = None,
    ) -> TelephonySettings:
        row = await self.get_or_create(actor.organization_id)
        before = self._audit_snapshot(row)

        data = req.model_dump(exclude_unset=True)
        for f in _PLAIN_FIELDS:
            if f in data and data[f] is not None:
                setattr(row, f, data[f])
        # Secrets: encrypt when a non-blank value is supplied; blank leaves unchanged.
        for field, col in _SECRET_FIELDS:
            if field in data and data[field] is not None and data[field] != "":
                setattr(row, col, crypto.encrypt(data[field]))

        await self.db.flush()
        after = self._audit_snapshot(row)

        changed = {k: {"from": before[k], "to": after[k]} for k in after if before.get(k) != after.get(k)}
        await AuditService(self.db).log_event(
            organization_id=actor.organization_id,
            actor_user_id=actor.id,
            action="TELEPHONY_CONFIG_UPDATED",
            resource_type="TelephonyConfig",
            resource_id=str(row.id),
            action_metadata={"changed": changed},
            ip_address=ip_address,
            browser_info=browser_info,
        )
        return row

    async def clear(self, actor: User, ip_address: str | None = None, browser_info: str | None = None) -> None:
        row = await self.get(actor.organization_id)
        if row is None:
            return
        for _, col in _SECRET_FIELDS:
            setattr(row, col, None)
        row.is_active = False
        row.is_connected = False
        await self.db.flush()
        await AuditService(self.db).log_event(
            organization_id=actor.organization_id,
            actor_user_id=actor.id,
            action="TELEPHONY_CONFIG_CLEARED",
            resource_type="TelephonyConfig",
            resource_id=str(row.id),
            ip_address=ip_address,
            browser_info=browser_info,
        )

    async def get_decrypted_config(self, organization_id: uuid.UUID) -> Optional[dict]:
        """Server-side ONLY. Returns decrypted creds for a provider call, or None
        if telephony isn't configured/active. Never expose this to any response."""
        row = await self.get(organization_id)
        if row is None or not row.is_active:
            return None
        return {
            "provider": row.provider,
            "company_id": row.company_id,
            "public_ivr_id": row.public_ivr_id,
            "call_type": row.call_type,
            "user_uuid": row.user_uuid,
            "default_caller_id": row.default_caller_id,
            "std_code": row.std_code,
            "webhook_url": row.webhook_url,
            "authentication_token": crypto.decrypt(row.authentication_token_enc),
            "x_api_key": crypto.decrypt(row.x_api_key_enc),
            "secret_token": crypto.decrypt(row.secret_token_enc),
            "webhook_secret": crypto.decrypt(row.webhook_secret_enc),
        }
