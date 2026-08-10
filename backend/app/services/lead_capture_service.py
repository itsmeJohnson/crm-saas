import hmac
import hashlib
import secrets
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lead_capture import LeadCaptureSource, LeadCaptureEvent
from app.models.user import User
from app.models.pipeline import Pipeline
from app.services.lead_service import LeadService


def _new_token() -> str:
    return secrets.token_urlsafe(24)


def _split_name(full: str | None) -> tuple[str | None, str]:
    """Return (first_name, last_name). Lead.last_name is required, so a single
    token becomes the last name; empty input falls back to 'Lead'."""
    full = (full or "").strip()
    if not full:
        return None, "Lead"
    parts = full.split()
    if len(parts) == 1:
        return None, parts[0]
    return parts[0], " ".join(parts[1:])


# Aliases mapped onto Lead fields for flat/generic payloads.
_ALIASES = {
    "first_name": "first_name", "firstname": "first_name", "fname": "first_name",
    "last_name": "last_name", "lastname": "last_name", "lname": "last_name", "surname": "last_name",
    "email": "email", "email_address": "email", "e-mail": "email",
    "phone": "phone", "phone_number": "phone", "mobile": "phone", "contact_number": "phone",
    "company": "company_name", "company_name": "company_name", "organization": "company_name",
    "city": "city", "town": "city",
    "value": "value", "budget": "value", "deal_value": "value",
    "title": "title", "subject": "title", "message": "title", "treatment": "title", "service": "title",
    "source": "source",
}


class LeadCaptureService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ---------------- admin CRUD ----------------
    async def create_source(self, actor: User, data: dict) -> LeadCaptureSource:
        pipeline_id = data.get("default_pipeline_id")
        if pipeline_id:
            ok = (await self.db.execute(select(Pipeline.id).filter(
                Pipeline.id == pipeline_id, Pipeline.organization_id == actor.organization_id,
                Pipeline.is_deleted == False))).scalar()
            if not ok:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Pipeline not found in your organization")
        owner_id = data.get("owner_user_id") or actor.id
        owner_ok = (await self.db.execute(select(User.id).filter(
            User.id == owner_id, User.organization_id == actor.organization_id, User.is_active == True))).scalar()
        if not owner_ok:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Owner user not found or inactive in your organization")
        src = LeadCaptureSource(
            organization_id=actor.organization_id,
            name=data["name"],
            provider=data.get("provider", "generic"),
            token=_new_token(),
            secret=data.get("secret"),
            meta_verify_token=data.get("meta_verify_token"),
            source_label=data.get("source_label") or "Web Lead",
            default_pipeline_id=pipeline_id,
            owner_user_id=owner_id,
            field_mapping=data.get("field_mapping"),
            created_by=actor.id,
        )
        self.db.add(src)
        await self.db.commit()
        await self.db.refresh(src)
        return src

    async def list_sources(self, actor: User) -> list[LeadCaptureSource]:
        rows = (await self.db.execute(select(LeadCaptureSource).filter(
            LeadCaptureSource.organization_id == actor.organization_id,
            LeadCaptureSource.is_deleted == False).order_by(LeadCaptureSource.created_at.desc()))).scalars().all()
        return list(rows)

    async def get_source(self, actor: User, source_id: uuid.UUID) -> LeadCaptureSource:
        src = (await self.db.execute(select(LeadCaptureSource).filter(
            LeadCaptureSource.id == source_id,
            LeadCaptureSource.organization_id == actor.organization_id,
            LeadCaptureSource.is_deleted == False))).scalar_one_or_none()
        if not src:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead capture source not found")
        return src

    async def update_source(self, actor: User, source_id: uuid.UUID, data: dict) -> LeadCaptureSource:
        src = await self.get_source(actor, source_id)
        for k, v in data.items():
            if v is not None and hasattr(src, k):
                setattr(src, k, v)
        await self.db.commit()
        await self.db.refresh(src)
        return src

    async def rotate_token(self, actor: User, source_id: uuid.UUID) -> LeadCaptureSource:
        src = await self.get_source(actor, source_id)
        src.token = _new_token()
        await self.db.commit()
        await self.db.refresh(src)
        return src

    async def delete_source(self, actor: User, source_id: uuid.UUID) -> None:
        src = await self.get_source(actor, source_id)
        src.is_deleted = True
        src.deleted_at = datetime.now(timezone.utc)
        await self.db.commit()

    async def list_events(self, actor: User, source_id: uuid.UUID | None = None, limit: int = 50) -> list[LeadCaptureEvent]:
        q = select(LeadCaptureEvent).filter(LeadCaptureEvent.organization_id == actor.organization_id)
        if source_id:
            q = q.filter(LeadCaptureEvent.source_id == source_id)
        q = q.order_by(LeadCaptureEvent.created_at.desc()).limit(limit)
        return list((await self.db.execute(q)).scalars().all())

    # ---------------- public webhook ----------------
    async def _source_by_token(self, token: str) -> LeadCaptureSource:
        src = (await self.db.execute(select(LeadCaptureSource).filter(
            LeadCaptureSource.token == token, LeadCaptureSource.is_deleted == False))).scalar_one_or_none()
        if not src or not src.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown or inactive capture endpoint")
        return src

    async def verify_meta(self, token: str, verify_token: str | None, challenge: str | None) -> str:
        """Meta GET subscription handshake — echo the challenge only if the
        source's verify token matches."""
        src = await self._source_by_token(token)
        if verify_token and challenge and src.meta_verify_token and hmac.compare_digest(verify_token, src.meta_verify_token):
            return challenge
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Verification failed")

    def _check_signature(self, src: LeadCaptureSource, raw_body: bytes, signature: str | None) -> None:
        """Verify HMAC-SHA256 of the raw body when the source has a shared secret.
        Accepts a bare hex digest or a `sha256=` prefixed one (Meta style)."""
        if not src.secret:
            return  # no secret configured -> open endpoint (token is the only gate)
        if not signature:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing signature")
        provided = signature.split("=", 1)[1] if signature.startswith("sha256=") else signature
        expected = hmac.new(src.secret.encode(), raw_body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(provided, expected):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature")

    def _extract(self, src: LeadCaptureSource, payload: dict) -> tuple[str | None, dict]:
        """Return (external_id, lead_data) normalized from a provider payload."""
        prov = src.provider
        fields: dict = {}
        external_id = None

        if prov == "meta_lead_ads":
            value = {}
            try:
                value = payload["entry"][0]["changes"][0]["value"]
            except (KeyError, IndexError, TypeError):
                value = payload.get("value", payload)
            external_id = value.get("leadgen_id") or payload.get("leadgen_id")
            fd = value.get("field_data") or []
            flat = {}
            for item in fd:
                name = (item.get("name") or "").lower()
                vals = item.get("values") or []
                flat[name] = vals[0] if vals else None
            if "full_name" in flat or "name" in flat:
                fn, ln = _split_name(flat.get("full_name") or flat.get("name"))
                fields["first_name"], fields["last_name"] = fn, ln
            if flat.get("first_name"): fields["first_name"] = flat["first_name"]
            if flat.get("last_name"): fields["last_name"] = flat["last_name"]
            fields["email"] = flat.get("email")
            fields["phone"] = flat.get("phone_number") or flat.get("phone")
            fields["city"] = flat.get("city")
            fields["company_name"] = flat.get("company_name")
            if not fd and not external_id:
                raise ValueError("Meta payload had no field_data or leadgen_id")

        elif prov == "google_ads":
            external_id = payload.get("lead_id") or payload.get("id")
            flat = {}
            for col in payload.get("user_column_data", []) or []:
                key = (col.get("column_id") or col.get("column_name") or "").lower().replace(" ", "_")
                flat[key] = col.get("string_value")
            fn, ln = _split_name(flat.get("full_name") or flat.get("name"))
            fields["first_name"] = flat.get("first_name") or fn
            fields["last_name"] = flat.get("last_name") or ln
            fields["email"] = flat.get("email")
            fields["phone"] = flat.get("phone_number") or flat.get("phone")
            fields["city"] = flat.get("city")

        else:  # generic / web_form / zapier — flat dict, optional field_mapping
            external_id = payload.get("external_id") or payload.get("lead_id") or payload.get("id")
            mapping = src.field_mapping or {}
            norm: dict = {}
            for k, v in payload.items():
                lk = str(k).strip().lower()
                target = mapping.get(k) or mapping.get(lk) or _ALIASES.get(lk)
                if target:
                    norm[target] = v
            if "last_name" not in norm and ("name" in payload or "full_name" in payload):
                fn, ln = _split_name(payload.get("full_name") or payload.get("name"))
                norm.setdefault("first_name", fn)
                norm["last_name"] = ln
            fields.update(norm)

        # required-field fallbacks
        if not fields.get("last_name"):
            fields["last_name"] = "Lead"
        if not fields.get("title"):
            fields["title"] = f"{src.source_label} enquiry"
        fields["source"] = src.source_label
        if src.default_pipeline_id:
            fields["pipeline_id"] = src.default_pipeline_id
        # drop Nones so create_lead uses its own defaults
        fields = {k: v for k, v in fields.items() if v is not None}
        return external_id, fields

    async def ingest(self, token: str, payload: dict, raw_body: bytes, signature: str | None) -> dict:
        src = await self._source_by_token(token)
        self._check_signature(src, raw_body, signature)
        external_id, lead_data = None, {}
        try:
            external_id, lead_data = self._extract(src, payload)
        except Exception as e:
            self.db.add(LeadCaptureEvent(organization_id=src.organization_id, source_id=src.id,
                                         external_id=None, status="error", error=str(e)[:500], raw_payload=payload))
            await self.db.commit()
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Could not parse lead payload: {e}")

        # idempotency: same external_id from the same source is a no-op
        if external_id:
            existing = (await self.db.execute(select(LeadCaptureEvent).filter(
                LeadCaptureEvent.source_id == src.id, LeadCaptureEvent.external_id == external_id))).scalar_one_or_none()
            if existing:
                return {"status": "duplicate", "lead_id": str(existing.lead_id) if existing.lead_id else None,
                        "event_id": str(existing.id)}

        owner = (await self.db.execute(select(User).filter(User.id == src.owner_user_id))).scalar_one_or_none()
        if not owner or not owner.is_active:
            self.db.add(LeadCaptureEvent(organization_id=src.organization_id, source_id=src.id, external_id=external_id,
                                         status="error", error="Owner user missing/inactive", raw_payload=payload))
            await self.db.commit()
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Capture source owner is inactive; reassign the source owner")

        lead = await LeadService(self.db).create_lead(owner, lead_data)

        src.leads_captured = (src.leads_captured or 0) + 1
        src.last_received_at = datetime.now(timezone.utc)
        event = LeadCaptureEvent(organization_id=src.organization_id, source_id=src.id, external_id=external_id,
                                 lead_id=lead.id, status="created", raw_payload=payload)
        self.db.add(event)
        self.db.add(src)
        await self.db.commit()
        await self.db.refresh(event)
        return {"status": "created", "lead_id": str(lead.id), "event_id": str(event.id)}
