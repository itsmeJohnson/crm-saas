"""Feature 4 — auto-email follow-up sequences.

Covers editable multi-step templates, manual + auto (lead_created) enrollment,
placeholder rendering, and the cron that advances a lead through the steps on
schedule and completes it.
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException

from app.core.security import get_password_hash
from app.repositories.organization import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.models.pipeline import Pipeline, PipelineStage
from app.models.email_sequence import SequenceEnrollment
from app.services.lead_service import LeadService
from app.services.email_sequence_service import (
    EmailSequenceService, process_due_enrollments, render_template,
)


async def _seed(db: AsyncSession, slug: str):
    org = await OrganizationRepository(db).create({"name": slug, "slug": slug})
    await db.commit()
    admin = await UserRepository(db).create_user(org.id, {
        "email": f"admin@{slug}.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Ada", "last_name": "Admin", "role": "OrgAdmin", "is_active": True})
    await db.commit()
    pipe = Pipeline(organization_id=org.id, name="Sales", is_default=True, is_active=True)
    db.add(pipe)
    await db.commit()
    stage = PipelineStage(organization_id=org.id, pipeline_id=pipe.id, name="New",
                          order_position=0, is_system_default=True)
    db.add(stage)
    await db.commit()
    return org, admin, stage


async def _lead(db, org, admin, stage, email="p@x.com"):
    lead = await LeadService(db, org.id).create_lead(admin, {
        "first_name": "Pat", "last_name": "Prospect", "email": email, "title": "T",
        "stage_id": stage.id, "pipeline_id": stage.pipeline_id})
    await db.commit()
    return lead


def test_render_template_substitutes_and_survives_unknown():
    class L:  # duck-typed lead
        first_name = "Sam"; last_name = "Lee"; email = "s@x.com"; phone = None
        company_name = "Acme"; title = "Deal"; source = "Web"
    out = render_template("Hi {{first_name}} at {{company}} — {{nope}}", L())
    assert out == "Hi Sam at Acme — "


@pytest.mark.asyncio
async def test_manual_enroll_and_cron_walks_steps(db: AsyncSession):
    org, admin, stage = await _seed(db, "seq-a")
    svc = EmailSequenceService(db)
    seq = await svc.create_sequence(admin, {
        "name": "Welcome drip", "trigger": "manual", "steps": [
            {"subject": "Hi {{first_name}}", "body": "Thanks for reaching out.", "delay_hours": 0},
            {"subject": "Following up", "body": "Any questions?", "delay_hours": 48},
        ]})
    await db.commit()
    assert len(seq.steps) == 2

    lead = await _lead(db, org, admin, stage)
    enr = await svc.enroll(admin, seq.id, lead.id)
    await db.commit()
    assert enr.status == "active" and enr.current_step == 0

    # Step 0 is due immediately → cron sends it and schedules step 1.
    sent = await process_due_enrollments(db)
    assert sent == 1
    row = (await db.execute(select(SequenceEnrollment).filter(SequenceEnrollment.id == enr.id))).scalar_one()
    assert row.current_step == 1 and row.status == "active"
    assert row.next_run_at > datetime.now(timezone.utc)  # ~48h out

    # Not due yet → nothing sent.
    assert await process_due_enrollments(db) == 0

    # Force step 1 due → cron sends final step and completes.
    row.next_run_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db.add(row)
    await db.commit()
    assert await process_due_enrollments(db) == 1
    done = (await db.execute(select(SequenceEnrollment).filter(SequenceEnrollment.id == enr.id))).scalar_one()
    assert done.status == "completed" and done.next_run_at is None


@pytest.mark.asyncio
async def test_lead_created_trigger_auto_enrolls(db: AsyncSession):
    org, admin, stage = await _seed(db, "seq-b")
    svc = EmailSequenceService(db)
    seq = await svc.create_sequence(admin, {
        "name": "New lead nurture", "trigger": "lead_created",
        "steps": [{"subject": "Welcome {{first_name}}", "body": "Glad you're here.", "delay_hours": 0}]})
    await db.commit()

    lead = await _lead(db, org, admin, stage, email="auto@x.com")
    enr = (await db.execute(select(SequenceEnrollment).filter(
        SequenceEnrollment.sequence_id == seq.id, SequenceEnrollment.lead_id == lead.id))).scalar_one()
    assert enr.status == "active"


@pytest.mark.asyncio
async def test_double_enroll_conflicts(db: AsyncSession):
    org, admin, stage = await _seed(db, "seq-c")
    svc = EmailSequenceService(db)
    seq = await svc.create_sequence(admin, {"name": "S", "steps": [
        {"subject": "A", "body": "B", "delay_hours": 0}]})
    await db.commit()
    lead = await _lead(db, org, admin, stage, email="dup@x.com")
    await svc.enroll(admin, seq.id, lead.id)
    await db.commit()
    with pytest.raises(HTTPException) as ei:
        await svc.enroll(admin, seq.id, lead.id)
    assert ei.value.status_code == 409


@pytest.mark.asyncio
async def test_employee_cannot_create_sequence(db: AsyncSession):
    org, admin, stage = await _seed(db, "seq-d")
    emp = await UserRepository(db).create_user(org.id, {
        "email": "emp@seq-d.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Ed", "last_name": "Emp", "role": "Employee", "is_active": True})
    await db.commit()
    with pytest.raises(HTTPException) as ei:
        await EmailSequenceService(db).create_sequence(emp, {"name": "X", "steps": [
            {"subject": "A", "body": "B"}]})
    assert ei.value.status_code == 403
