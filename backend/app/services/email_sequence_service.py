"""Auto-email follow-up sequences (Feature 4).

A sequence is an ordered set of steps, each an editable subject/body template
with {{placeholders}} and a delay. Leads are enrolled (manually or auto on
lead_created) and walked through the steps by ``process_due_enrollments`` on the
minute-cadence cron. Rendering is deliberately simple placeholder substitution —
no arbitrary template execution — over a safe allowlist of lead fields.
"""
import re
import uuid
import logging
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.user import User
from app.models.lead import Lead
from app.models.email_sequence import EmailSequence, EmailSequenceStep, SequenceEnrollment

logger = logging.getLogger("app.services.email_sequence")

_PLACEHOLDER = re.compile(r"\{\{\s*([a-zA-Z0-9_.]+)\s*\}\}")
_MAX_STEPS = 25


def render_template(text: str, lead: Lead) -> str:
    """Substitute {{lead.first_name}} / {{first_name}} style tokens from a safe
    allowlist of lead attributes. Unknown tokens render empty (never crash)."""
    fields = {
        "first_name": lead.first_name or "there",
        "last_name": lead.last_name or "",
        "full_name": f"{lead.first_name or ''} {lead.last_name or ''}".strip() or "there",
        "email": lead.email or "",
        "phone": lead.phone or "",
        "company": lead.company_name or "",
        "title": lead.title or "",
        "source": lead.source or "",
    }

    def _sub(m: re.Match) -> str:
        key = m.group(1).split(".")[-1].lower()
        return str(fields.get(key, ""))

    return _PLACEHOLDER.sub(_sub, text or "")


class EmailSequenceService:
    def __init__(self, db: AsyncSession):
        self.db = db

    def _privileged(self, actor: User) -> bool:
        return actor.role in ("SuperAdmin", "OrgAdmin", "Manager")

    # ---------------- CRUD ----------------
    async def create_sequence(self, actor: User, data: dict) -> EmailSequence:
        if not self._privileged(actor):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins/managers manage sequences")
        trigger = data.get("trigger") or "manual"
        if trigger not in ("manual", "lead_created"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="trigger must be 'manual' or 'lead_created'")
        seq = EmailSequence(
            organization_id=actor.organization_id, name=(data.get("name") or "Follow-up")[:150],
            description=data.get("description"), trigger=trigger,
            is_active=data.get("is_active", True), created_by=actor.id)
        self.db.add(seq)
        await self.db.flush()
        await self._replace_steps(actor, seq, data.get("steps") or [])
        await self.db.flush()
        return await self.get_sequence(actor, seq.id)

    async def _replace_steps(self, actor: User, seq: EmailSequence, steps: list[dict]) -> None:
        if len(steps) > _MAX_STEPS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"A sequence may have at most {_MAX_STEPS} steps")
        existing = (await self.db.execute(select(EmailSequenceStep).filter(
            EmailSequenceStep.sequence_id == seq.id))).scalars().all()
        for s in existing:
            await self.db.delete(s)
        await self.db.flush()
        for i, step in enumerate(steps):
            subject = (step.get("subject") or "").strip()
            body = (step.get("body") or "").strip()
            if not subject or not body:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Step {i + 1} needs a subject and body")
            self.db.add(EmailSequenceStep(
                organization_id=seq.organization_id, sequence_id=seq.id, step_order=i,
                delay_hours=max(0, int(step.get("delay_hours") or 0)),
                subject=subject[:255], body=body, is_active=step.get("is_active", True)))

    async def get_sequence(self, actor: User, seq_id: uuid.UUID) -> EmailSequence:
        seq = (await self.db.execute(select(EmailSequence).options(selectinload(EmailSequence.steps)).filter(
            EmailSequence.id == seq_id, EmailSequence.organization_id == actor.organization_id,
            EmailSequence.is_deleted == False))).scalars().first()
        if not seq:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sequence not found")
        return seq

    async def list_sequences(self, actor: User) -> list[EmailSequence]:
        return list((await self.db.execute(select(EmailSequence).options(selectinload(EmailSequence.steps)).filter(
            EmailSequence.organization_id == actor.organization_id, EmailSequence.is_deleted == False
        ).order_by(EmailSequence.created_at.desc()))).scalars().all())

    async def update_sequence(self, actor: User, seq_id: uuid.UUID, data: dict) -> EmailSequence:
        if not self._privileged(actor):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins/managers manage sequences")
        seq = await self.get_sequence(actor, seq_id)
        for f in ("name", "description", "is_active"):
            if f in data and data[f] is not None:
                setattr(seq, f, data[f])
        if data.get("trigger"):
            if data["trigger"] not in ("manual", "lead_created"):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid trigger")
            seq.trigger = data["trigger"]
        if data.get("steps") is not None:
            await self._replace_steps(actor, seq, data["steps"])
        self.db.add(seq)
        await self.db.flush()
        return await self.get_sequence(actor, seq_id)

    async def delete_sequence(self, actor: User, seq_id: uuid.UUID) -> None:
        if not self._privileged(actor):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admins/managers manage sequences")
        seq = await self.get_sequence(actor, seq_id)
        seq.is_deleted = True
        self.db.add(seq)
        # Stop any in-flight enrollments.
        active = (await self.db.execute(select(SequenceEnrollment).filter(
            SequenceEnrollment.sequence_id == seq.id, SequenceEnrollment.status == "active"))).scalars().all()
        for e in active:
            e.status = "cancelled"
            self.db.add(e)
        await self.db.flush()

    # ---------------- enrollment ----------------
    async def enroll(self, actor: User, seq_id: uuid.UUID, lead_id: uuid.UUID) -> SequenceEnrollment:
        seq = await self.get_sequence(actor, seq_id)
        # get_lead enforces org + visibility scoping.
        from app.services.lead_service import LeadService
        lead = await LeadService(self.db, actor.organization_id).get_lead(actor, lead_id)
        return await self._enroll_lead(seq, lead, enrolled_by=actor.id)

    async def _enroll_lead(self, seq: EmailSequence, lead: Lead, enrolled_by: uuid.UUID | None) -> SequenceEnrollment:
        steps = sorted([s for s in seq.steps if s.is_active], key=lambda s: s.step_order)
        if not steps:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Sequence has no active steps")
        existing = (await self.db.execute(select(SequenceEnrollment).filter(
            SequenceEnrollment.sequence_id == seq.id, SequenceEnrollment.lead_id == lead.id))).scalars().first()
        if existing and existing.status == "active":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Lead is already enrolled in this sequence")
        now = datetime.now(timezone.utc)
        first_due = now + timedelta(hours=steps[0].delay_hours)
        if existing:  # re-enroll a completed/cancelled lead
            existing.status = "active"
            existing.current_step = 0
            existing.next_run_at = first_due
            existing.last_sent_at = None
            existing.enrolled_by = enrolled_by
            self.db.add(existing)
            await self.db.flush()
            return existing
        enrollment = SequenceEnrollment(
            organization_id=seq.organization_id, sequence_id=seq.id, lead_id=lead.id,
            current_step=0, status="active", next_run_at=first_due, enrolled_by=enrolled_by)
        self.db.add(enrollment)
        await self.db.flush()
        return enrollment

    async def cancel_enrollment(self, actor: User, enrollment_id: uuid.UUID) -> None:
        e = (await self.db.execute(select(SequenceEnrollment).filter(
            SequenceEnrollment.id == enrollment_id,
            SequenceEnrollment.organization_id == actor.organization_id))).scalars().first()
        if not e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Enrollment not found")
        e.status = "cancelled"
        self.db.add(e)
        await self.db.flush()

    async def list_enrollments(self, actor: User, seq_id: uuid.UUID) -> list[SequenceEnrollment]:
        await self.get_sequence(actor, seq_id)  # scope check
        return list((await self.db.execute(select(SequenceEnrollment).filter(
            SequenceEnrollment.sequence_id == seq_id).order_by(SequenceEnrollment.created_at.desc()))).scalars().all())

    async def auto_enroll_new_lead(self, lead: Lead) -> None:
        """Best-effort: enroll a just-created lead into every active
        lead_created-triggered sequence in its org. Never raises."""
        if not lead.email:
            return
        try:
            seqs = (await self.db.execute(select(EmailSequence).options(selectinload(EmailSequence.steps)).filter(
                EmailSequence.organization_id == lead.organization_id,
                EmailSequence.trigger == "lead_created",
                EmailSequence.is_active == True, EmailSequence.is_deleted == False))).scalars().all()
            for seq in seqs:
                if not [s for s in seq.steps if s.is_active]:
                    continue
                exists = (await self.db.execute(select(SequenceEnrollment.id).filter(
                    SequenceEnrollment.sequence_id == seq.id, SequenceEnrollment.lead_id == lead.id))).first()
                if exists:
                    continue
                await self._enroll_lead(seq, lead, enrolled_by=None)
        except Exception as e:  # pragma: no cover - defensive
            logger.warning("auto_enroll_new_lead failed for lead %s: %s", lead.id, e)


# ---------------- cron dispatcher ----------------
async def process_due_enrollments(db: AsyncSession) -> int:
    """Send the next due step for every active enrollment whose next_run_at has
    passed, advance it, and complete it when steps run out. Returns emails sent.
    Idempotent per tick: each send advances current_step/next_run_at."""
    from app.services.email_service import send_email

    now = datetime.now(timezone.utc)
    due = (await db.execute(select(SequenceEnrollment).filter(
        SequenceEnrollment.status == "active",
        SequenceEnrollment.next_run_at.isnot(None),
        SequenceEnrollment.next_run_at <= now,
    ).limit(200))).scalars().all()

    sent = 0
    for e in due:
        seq = (await db.execute(select(EmailSequence).options(selectinload(EmailSequence.steps)).filter(
            EmailSequence.id == e.sequence_id))).scalars().first()
        if not seq or not seq.is_active or seq.is_deleted:
            e.status = "cancelled"
            db.add(e)
            continue
        steps = sorted([s for s in seq.steps if s.is_active], key=lambda s: s.step_order)
        if e.current_step >= len(steps):
            e.status = "completed"
            e.next_run_at = None
            db.add(e)
            continue
        lead = (await db.execute(select(Lead).filter(Lead.id == e.lead_id, Lead.is_deleted == False))).scalars().first()
        if not lead or not lead.email:
            e.status = "cancelled"
            db.add(e)
            continue

        step = steps[e.current_step]
        try:
            send_email(lead.email, render_template(step.subject, lead), "sequence_step.html",
                       {"body_html": render_template(step.body, lead).replace("\n", "<br>"),
                        "first_name": lead.first_name or "there"})
            sent += 1
        except Exception as exc:  # pragma: no cover - provider errors shouldn't wedge the cron
            logger.error("sequence step send failed (enrollment %s): %s", e.id, exc)

        e.last_sent_at = now
        e.current_step += 1
        if e.current_step >= len(steps):
            e.status = "completed"
            e.next_run_at = None
        else:
            e.next_run_at = now + timedelta(hours=steps[e.current_step].delay_hours)
        db.add(e)

    if due:
        await db.commit()
    return sent
