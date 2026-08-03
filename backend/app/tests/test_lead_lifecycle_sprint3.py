"""Sprint 3 — Lead Lifecycle Completion (backend).

Covers:
  D — the unified lead timeline now includes Notes, Activities, Audit events,
      Tasks, and Reminders, sorted chronologically.
  B — reassigning a lead notifies the new owner, and ONLY when ownership
      actually changes (no self-assign spam, no no-op spam); bulk reassignment
      sends a single aggregated notification.
"""
import uuid
from datetime import datetime, timezone, timedelta

import pytest
from sqlalchemy import select

from app.core.security import get_password_hash
from app.repositories.organization import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.services.lead_service import LeadService
from app.services.note_service import NoteService
from app.models.pipeline import PipelineStage
from app.models.lead import Lead
from app.models.activity import Activity
from app.models.task import Task
from app.models.notification import Notification


async def _user(db, org_id, email, role="Employee", active=True):
    return await UserRepository(db).create_user(org_id, {
        "email": email, "hashed_password": get_password_hash("password123"),
        "first_name": "U", "last_name": email.split("@")[0],
        "role": role, "is_active": active,
    })


@pytest.fixture
async def env(db):
    org = await OrganizationRepository(db).create({"name": "LC Org", "slug": "lc-org"})
    await db.flush()
    stage_id = (await db.execute(select(PipelineStage.id).filter(
        PipelineStage.organization_id == org.id, PipelineStage.is_system_default == True,
    ))).scalar()
    admin = await _user(db, org.id, "admin@lc.com", role="OrgAdmin")
    owner2 = await _user(db, org.id, "owner2@lc.com", role="OrgAdmin")  # org-wide → assignable
    await db.commit()
    return {"org": org, "admin": admin, "owner2": owner2, "stage_id": stage_id}


async def _make_lead(db, org_id, stage_id, owner_id, title="Opp"):
    lead = Lead(organization_id=org_id, last_name="L", title=title,
                stage_id=stage_id, created_by=owner_id, assigned_user_id=owner_id)
    db.add(lead)
    await db.flush()
    return lead


async def _notif_count(db, user_id):
    rows = (await db.execute(
        select(Notification).filter(Notification.user_id == user_id, Notification.category == "lead")
    )).scalars().all()
    return rows


# ---------------------------------------------------------------------------
# D — Timeline aggregation includes all event types, chronologically
# ---------------------------------------------------------------------------

async def test_timeline_includes_all_event_types(env, db):
    a = env
    svc = LeadService(db)
    lead = await _make_lead(db, a["org"].id, a["stage_id"], a["admin"].id)  # no audit yet

    # Note
    await NoteService(db).create_note(a["admin"], {"lead_id": lead.id, "content": "A note"})
    # Activity
    db.add(Activity(organization_id=a["org"].id, activity_type="Call", subject="Rang",
                    lead_id=lead.id, created_by=a["admin"].id, assigned_user_id=a["admin"].id))
    # Task linked to the lead
    db.add(Task(organization_id=a["org"].id, title="Send quote", status="Todo",
                priority="High", lead_id=lead.id, created_by=a["admin"].id,
                assigned_user_id=a["admin"].id))
    # Reminder
    await svc.create_reminder(a["admin"], lead.id,
                              datetime.now(timezone.utc) + timedelta(days=1), "Call back")
    await db.flush()
    # Audit — an update generates a LEAD_UPDATED audit event
    await svc.update_lead(a["admin"], lead.id, {"title": "Renamed Opp"})

    events = await svc.get_timeline(a["admin"], lead.id)
    types = {e["type"] for e in events}
    assert {"note", "activity", "audit", "task", "reminder"} <= types, f"missing: {types}"

    # Chronological (descending) ordering preserved across the merged feed.
    ts = [e["timestamp"] for e in events]
    assert ts == sorted(ts, reverse=True)

    # The task and reminder events carry useful metadata.
    task_ev = next(e for e in events if e["type"] == "task")
    assert task_ev["title"] == "Task: Send quote" and task_ev["event_metadata"]["status"] == "Todo"
    rem_ev = next(e for e in events if e["type"] == "reminder")
    assert rem_ev["title"] == "Reminder set" and rem_ev["event_metadata"]["is_sent"] is False


async def test_timeline_scoping_unchanged(env, db):
    """get_timeline still enforces lead scoping (unchanged behavior)."""
    from fastapi import HTTPException
    a = env
    # A telecaller with no downline cannot see a lead owned by someone else.
    tele = await _user(db, a["org"].id, "tele@lc.com", role="Employee")
    await db.flush()
    lead = await _make_lead(db, a["org"].id, a["stage_id"], a["admin"].id)
    with pytest.raises(HTTPException) as exc:
        await LeadService(db).get_timeline(tele, lead.id)
    assert exc.value.status_code == 404


# ---------------------------------------------------------------------------
# B — Assignment notifications on reassignment only
# ---------------------------------------------------------------------------

async def test_reassign_notifies_new_owner(env, db):
    a = env
    lead = await _make_lead(db, a["org"].id, a["stage_id"], a["admin"].id)
    assert len(await _notif_count(db, a["owner2"].id)) == 0
    await LeadService(db).update_lead(a["admin"], lead.id, {"assigned_user_id": a["owner2"].id})
    notes = await _notif_count(db, a["owner2"].id)
    assert len(notes) == 1
    assert "assigned" in notes[0].title.lower()
    assert str(lead.id) in (notes[0].link_url or "")


async def test_no_notify_when_owner_unchanged(env, db):
    a = env
    lead = await _make_lead(db, a["org"].id, a["stage_id"], a["admin"].id)
    # Update a non-owner field; assigned_user_id not in payload → no notification.
    await LeadService(db).update_lead(a["admin"], lead.id, {"title": "Just a rename"})
    assert len(await _notif_count(db, a["admin"].id)) == 0
    assert len(await _notif_count(db, a["owner2"].id)) == 0
    # Re-send the SAME owner explicitly → still no change → no notification.
    await LeadService(db).update_lead(a["admin"], lead.id, {"assigned_user_id": a["admin"].id})
    assert len(await _notif_count(db, a["admin"].id)) == 0


async def test_no_notify_on_self_assign(env, db):
    a = env
    # Lead owned by owner2; admin re-assigns it to admin (self) → no notification.
    lead = await _make_lead(db, a["org"].id, a["stage_id"], a["owner2"].id)
    await LeadService(db).update_lead(a["admin"], lead.id, {"assigned_user_id": a["admin"].id})
    assert len(await _notif_count(db, a["admin"].id)) == 0


async def test_bulk_reassign_sends_single_notification(env, db):
    a = env
    l1 = await _make_lead(db, a["org"].id, a["stage_id"], a["admin"].id, title="L1")
    l2 = await _make_lead(db, a["org"].id, a["stage_id"], a["admin"].id, title="L2")
    res = await LeadService(db).bulk_update(
        a["admin"], [l1.id, l2.id], {"assigned_user_id": a["owner2"].id})
    assert res["updated_count"] == 2
    notes = await _notif_count(db, a["owner2"].id)
    assert len(notes) == 1                       # aggregated, not one-per-lead
    assert "2" in notes[0].body                  # count surfaced
