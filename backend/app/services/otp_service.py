"""OTP verification service (send code → user enters → verify).

Sits on top of the SMS provider layer. The gateway (BulkSMSPlans `verify` /
`verify_status`) generates and validates the code; we persist only the vendor
message id plus lifecycle state in ``OtpVerification`` so any CRM feature can
drive phone verification without touching the gateway. Providers that don't
support OTP (Mock/Twilio/Bhash) return a clear "not supported" error rather than
silently succeeding.
"""
import uuid
from datetime import datetime, timezone, timedelta

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.lead import Lead
from app.models.contact import Contact
from app.models.otp_verification import OtpVerification
from app.models.sms_settings import SmsSettings
from app.services.audit_service import AuditService
from app.services.sms_providers import get_provider

DEFAULT_TTL_MINUTES = 10
DEFAULT_MESSAGE = "Your verification code is {{otp}}. It is valid for 10 minutes."


class OtpService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.audit = AuditService(db)

    async def _settings(self, actor: User) -> SmsSettings | None:
        res = await self.db.execute(select(SmsSettings).filter(
            SmsSettings.organization_id == actor.organization_id, SmsSettings.is_deleted == False))
        return res.scalars().first()

    async def _resolve_number(self, actor: User, data: dict) -> str:
        number = (data.get("number") or "").strip()
        if not number and data.get("lead_id"):
            lead = (await self.db.execute(select(Lead).filter(
                Lead.id == data["lead_id"], Lead.organization_id == actor.organization_id))).scalars().first()
            if lead:
                number = (lead.phone or "").strip()
        if not number and data.get("contact_id"):
            c = (await self.db.execute(select(Contact).filter(
                Contact.id == data["contact_id"], Contact.organization_id == actor.organization_id))).scalars().first()
            if c:
                number = (c.phone or "").strip()
        if not number:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="No number: provide `number` or a lead/contact with a phone.")
        return number

    async def send(self, actor: User, data: dict) -> OtpVerification:
        settings_row = await self._settings(actor)
        provider = get_provider(settings_row)
        if not hasattr(provider, "send_otp"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"OTP verification is not supported by provider '{provider.name}'. Configure BulkSMSPlans.")
        number = await self._resolve_number(actor, data)
        message = (data.get("message") or DEFAULT_MESSAGE).strip()
        if "{{otp}}" not in message:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="OTP message must contain the {{otp}} placeholder.")
        sender = (settings_row.sender_id if settings_row else None) or ""

        rec = OtpVerification(
            organization_id=actor.organization_id, number=number,
            purpose=data.get("purpose"), provider=provider.name,
            status="pending",
            max_attempts=int(data.get("max_attempts") or 5),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=int(data.get("ttl_minutes") or DEFAULT_TTL_MINUTES)),
            created_by=actor.id, lead_id=data.get("lead_id"), contact_id=data.get("contact_id"),
        )
        self.db.add(rec)
        await self.db.flush()

        result = await provider.send_otp(number=number, message=message, sender=sender)
        if result.get("success"):
            rec.provider_message_id = result.get("message_id")
        else:
            rec.status = "failed"
            rec.last_error = (result.get("error") or "send failed")[:300]
        self.db.add(rec)
        await self.db.flush()

        await self.audit.log_event(
            organization_id=actor.organization_id, actor_user_id=actor.id,
            action="OTP_SENT", resource_type="otp_verification", resource_id=str(rec.id),
            action_metadata={"number": number, "purpose": rec.purpose, "status": rec.status})

        if rec.status == "failed":
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY,
                                detail=f"OTP send failed: {rec.last_error}")
        return rec

    async def _get(self, actor: User, verification_id: uuid.UUID) -> OtpVerification:
        rec = (await self.db.execute(select(OtpVerification).filter(
            OtpVerification.id == verification_id,
            OtpVerification.organization_id == actor.organization_id,
            OtpVerification.is_deleted == False))).scalars().first()
        if not rec:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Verification not found.")
        return rec

    async def verify(self, actor: User, verification_id: uuid.UUID, otp: str) -> OtpVerification:
        rec = await self._get(actor, verification_id)
        if rec.status == "verified":
            return rec
        if rec.expires_at and datetime.now(timezone.utc) > rec.expires_at:
            rec.status = "expired"
            self.db.add(rec)
            await self.db.flush()
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This code has expired. Request a new one.")
        if rec.status == "failed" or not rec.provider_message_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This verification cannot be completed. Request a new code.")
        if rec.attempts >= rec.max_attempts:
            rec.status = "failed"
            self.db.add(rec)
            await self.db.flush()
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many attempts. Request a new code.")

        provider = get_provider(await self._settings(actor))
        if not hasattr(provider, "verify_otp"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"OTP verification is not supported by provider '{provider.name}'.")
        rec.attempts += 1
        result = await provider.verify_otp(message_id=rec.provider_message_id, otp=(otp or "").strip())
        if result.get("verified"):
            rec.status = "verified"
            rec.verified_at = datetime.now(timezone.utc)
        else:
            rec.last_error = (result.get("message") or "Invalid code")[:300]
            if rec.attempts >= rec.max_attempts:
                rec.status = "failed"
        self.db.add(rec)
        await self.db.flush()

        await self.audit.log_event(
            organization_id=actor.organization_id, actor_user_id=actor.id,
            action="OTP_VERIFIED" if rec.status == "verified" else "OTP_VERIFY_FAILED",
            resource_type="otp_verification", resource_id=str(rec.id),
            action_metadata={"number": rec.number, "attempts": rec.attempts, "status": rec.status})

        if rec.status != "verified":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail=rec.last_error or "Invalid code.")
        return rec
