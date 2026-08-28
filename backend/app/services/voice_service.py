"""Voice broadcast service (BulkSMSPlans OBD + TTS).

Owns the create → send → track lifecycle for bulk voice campaigns on top of
:class:`BulkSmsPlansVoiceProvider`. Credentials come from the org's SMS settings
(same vendor account). Per-number delivery is tracked in
``VoiceBroadcastRecipient`` and refreshed from the vendor voice DLR.
"""
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.user import User
from app.models.lead import Lead
from app.models.contact import Contact
from app.models.sms_settings import SmsSettings
from app.models.voice_broadcast import VoiceBroadcast, VoiceBroadcastRecipient
from app.services.audit_service import AuditService
from app.services.sms_providers import normalize_indian_msisdn
from app.services.voice_providers import build_voice_provider, map_voice_status

MAX_RECIPIENTS = 1000


class VoiceService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.audit = AuditService(db)

    def _require_admin(self, actor: User):
        if actor.role not in ("SuperAdmin", "OrgAdmin", "Manager"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized for voice broadcasts.")

    async def _settings(self, actor: User) -> SmsSettings | None:
        res = await self.db.execute(select(SmsSettings).filter(
            SmsSettings.organization_id == actor.organization_id, SmsSettings.is_deleted == False))
        return res.scalars().first()

    async def _provider(self, actor: User):
        provider = build_voice_provider(await self._settings(actor))
        if provider is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Voice broadcasts require the BulkSMSPlans provider configured in SMS settings.")
        return provider

    # ---------- Numbers ----------
    async def _resolve_numbers(self, actor: User, data: dict) -> list[tuple[str, dict]]:
        """Return [(normalized_number, {lead_id, contact_id})]. Sources: explicit
        `numbers` list and/or lead/contact ids."""
        out: list[tuple[str, dict]] = []
        seen: set[str] = set()

        def add(n: str, links: dict):
            norm = normalize_indian_msisdn(n)
            if norm and norm not in seen:
                seen.add(norm)
                out.append((norm, links))

        for n in (data.get("numbers") or []):
            add(str(n), {})
        for lid in (data.get("lead_ids") or []):
            lead = (await self.db.execute(select(Lead).filter(
                Lead.id == lid, Lead.organization_id == actor.organization_id))).scalars().first()
            if lead and lead.phone:
                add(lead.phone, {"lead_id": lead.id})
        for cid in (data.get("contact_ids") or []):
            c = (await self.db.execute(select(Contact).filter(
                Contact.id == cid, Contact.organization_id == actor.organization_id))).scalars().first()
            if c and c.phone:
                add(c.phone, {"contact_id": c.id})

        if not out:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="No valid recipients: provide numbers or leads/contacts with phones.")
        if len(out) > MAX_RECIPIENTS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"Too many recipients ({len(out)}); max {MAX_RECIPIENTS} per broadcast.")
        return out

    # ---------- Create / send ----------
    async def create_and_send(self, actor: User, data: dict) -> VoiceBroadcast:
        self._require_admin(actor)
        mode = (data.get("mode") or "").lower()
        if mode not in ("voice_note", "tts"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="mode must be 'voice_note' or 'tts'.")
        provider = await self._provider(actor)
        recipients = await self._resolve_numbers(actor, data)
        numbers = [n for n, _ in recipients]

        bc = VoiceBroadcast(
            organization_id=actor.organization_id,
            name=(data.get("name") or f"{mode} broadcast").strip()[:150],
            mode=mode, status="queued",
            voice_type=str(data.get("voice_type")) if data.get("voice_type") is not None else None,
            voice_medias_id=str(data.get("voice_medias_id")) if data.get("voice_medias_id") is not None else None,
            tts_content=data.get("tts_content"),
            tts_language=data.get("tts_language") or ("English" if mode == "tts" else None),
            tts_gender=data.get("tts_gender") or ("Male" if mode == "tts" else None),
            scheduled=bool(data.get("scheduled")),
            scheduled_datetime=data.get("scheduled_datetime"),
            retry_interval=data.get("retry_interval"), retry_count=data.get("retry_count"),
            total_recipients=len(numbers), created_by=actor.id,
        )
        self.db.add(bc)
        await self.db.flush()

        rec_rows = [
            VoiceBroadcastRecipient(
                broadcast_id=bc.id, organization_id=actor.organization_id, number=n,
                status="pending", lead_id=links.get("lead_id"), contact_id=links.get("contact_id"))
            for n, links in recipients
        ]
        self.db.add_all(rec_rows)
        await self.db.flush()

        # Dispatch
        if mode == "voice_note":
            if not (bc.voice_type and bc.voice_medias_id):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                    detail="voice_note mode requires voice_type and voice_medias_id.")
            result = await provider.send_voice_note(
                numbers=numbers, voice_type=bc.voice_type, voice_medias_id=bc.voice_medias_id,
                scheduled=bc.scheduled, scheduled_datetime=_fmt_dt(bc.scheduled_datetime),
                obd_type=data.get("obd_type"), retry_interval=bc.retry_interval, retry_count=bc.retry_count)
        else:
            if not bc.tts_content:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="tts mode requires tts_content.")
            result = await provider.send_tts(
                numbers=numbers, content=bc.tts_content,
                language=bc.tts_language or "English", gender=bc.tts_gender or "Male")

        if result.get("success"):
            bc.provider_job_id = str(result.get("job_id")) if result.get("job_id") is not None else None
            bc.status = "scheduled" if bc.scheduled else "sent"
            bc.sent_at = datetime.now(timezone.utc)
            # Map unique_ids to recipients positionally when the vendor returns them.
            uids = result.get("unique_ids") or []
            for row, uid in zip(rec_rows, uids):
                row.unique_id = uid
        else:
            bc.status = "failed"
            bc.last_error = (result.get("message") or "send failed")[:500]
            for row in rec_rows:
                row.status = "failed"
                row.vendor_status = "send failed"
        self.db.add(bc)
        self.db.add_all(rec_rows)
        await self.db.flush()

        await self.audit.log_event(
            organization_id=actor.organization_id, actor_user_id=actor.id,
            action="VOICE_BROADCAST_SENT", resource_type="voice_broadcast", resource_id=str(bc.id),
            action_metadata={"mode": mode, "recipients": len(numbers), "status": bc.status})

        if bc.status == "failed":
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Voice broadcast failed: {bc.last_error}")
        return await self.get(actor, bc.id)

    # ---------- Read ----------
    async def list(self, actor: User, skip: int = 0, limit: int = 50) -> dict:
        self._require_admin(actor)
        base = select(VoiceBroadcast).filter(
            VoiceBroadcast.organization_id == actor.organization_id, VoiceBroadcast.is_deleted == False)
        total = (await self.db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0
        rows = list((await self.db.execute(
            base.order_by(VoiceBroadcast.created_at.desc()).offset(skip).limit(limit))).scalars().all())
        return {"items": [self._item(r) for r in rows], "total": total}

    async def get(self, actor: User, broadcast_id: uuid.UUID) -> VoiceBroadcast:
        self._require_admin(actor)
        row = (await self.db.execute(select(VoiceBroadcast).options(
            selectinload(VoiceBroadcast.recipients)).filter(
            VoiceBroadcast.id == broadcast_id, VoiceBroadcast.organization_id == actor.organization_id,
            VoiceBroadcast.is_deleted == False))).scalars().first()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Broadcast not found.")
        return row

    def _item(self, r: VoiceBroadcast) -> dict:
        return {"id": str(r.id), "name": r.name, "mode": r.mode, "status": r.status,
                "voice_type": r.voice_type, "voice_medias_id": r.voice_medias_id,
                "tts_language": r.tts_language, "tts_gender": r.tts_gender,
                "total_recipients": r.total_recipients, "provider_job_id": r.provider_job_id,
                "scheduled": r.scheduled, "sent_at": r.sent_at, "last_error": r.last_error,
                "created_at": r.created_at}

    def detail(self, r: VoiceBroadcast) -> dict:
        d = self._item(r)
        d["tts_content"] = r.tts_content
        d["recipients"] = [
            {"id": str(x.id), "number": x.number, "unique_id": x.unique_id, "status": x.status,
             "vendor_status": x.vendor_status, "dtmf": x.dtmf, "call_duration": x.call_duration,
             "lead_id": str(x.lead_id) if x.lead_id else None,
             "contact_id": str(x.contact_id) if x.contact_id else None}
            for x in r.recipients]
        return d

    # ---------- DLR refresh ----------
    async def refresh_dlr(self, actor: User, broadcast_id: uuid.UUID) -> VoiceBroadcast:
        bc = await self.get(actor, broadcast_id)
        provider = await self._provider(actor)
        # Prefer unique-id lookup; fall back to per-number VoiceDLRReport.
        with_uid = [r for r in bc.recipients if r.unique_id]
        by_uid: dict[str, dict] = {}
        if with_uid:
            rep = await provider.fetch_report([r.unique_id for r in with_uid])
            for row in rep.get("rows") or []:
                uid = row.get("unique_id") or row.get("id")
                if uid:
                    by_uid[str(uid)] = row
        for r in bc.recipients:
            row = by_uid.get(r.unique_id) if r.unique_id else None
            if row is None:
                single = await provider.voice_dlr_report(phone_number=r.number)
                rows = single.get("rows") or []
                row = rows[0] if rows else None
            if row:
                self._apply_dlr(r, row)
        self.db.add_all(bc.recipients)
        await self.db.flush()
        return await self.get(actor, broadcast_id)

    @staticmethod
    def _apply_dlr(recipient: VoiceBroadcastRecipient, row: dict):
        vendor_status = row.get("status")
        mapped = map_voice_status(vendor_status)
        if mapped:
            recipient.status = mapped
        if vendor_status:
            recipient.vendor_status = str(vendor_status)[:40]
        if row.get("dtmf"):
            recipient.dtmf = str(row["dtmf"])[:20]
        if row.get("call_duration"):
            recipient.call_duration = str(row["call_duration"])[:20]

    # ---------- Media & reports (passthrough) ----------
    async def list_media(self, actor: User) -> dict:
        return await (await self._provider(actor)).list_voice_media()

    async def upload_media(self, actor: User, *, title: str, vendor_account_id: str, duration: str,
                           file_bytes: bytes, filename: str, content_type: str) -> dict:
        self._require_admin(actor)
        return await (await self._provider(actor)).add_voice_media(
            title=title, vendor_account_id=vendor_account_id, duration=duration,
            file_bytes=file_bytes, filename=filename, content_type=content_type)

    async def missed_call_report(self, actor: User, *, did_number: str, start_date: str, end_date: str) -> dict:
        self._require_admin(actor)
        return await (await self._provider(actor)).missed_call_report(
            did_number=did_number, start_date=start_date, end_date=end_date)


def _fmt_dt(dt: datetime | None) -> str | None:
    return dt.strftime("%Y-%m-%d %H:%M:%S") if dt else None
