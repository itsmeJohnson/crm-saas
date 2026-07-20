import pytest
import uuid
from datetime import datetime, timezone, timedelta
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.security import create_access_token, get_password_hash
from app.repositories.organization import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.models.lead import Lead
from app.models.contact import Contact
from app.models.notification import Notification
from app.models.audit_log import AuditLog
from app.models.pipeline import PipelineStage


@pytest.fixture
async def setup(db: AsyncSession):
    org_repo = OrganizationRepository(db)
    user_repo = UserRepository(db)

    org = await org_repo.create({"name": "Auto Org", "slug": "auto-org"})
    await db.commit()

    admin = await user_repo.create_user(org.id, {
        "email": "admin@auto.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Admin", "last_name": "One", "role": "OrgAdmin", "is_active": True,
    })
    manager = await user_repo.create_user(org.id, {
        "email": "mgr@auto.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Man", "last_name": "Ager", "role": "Manager", "is_active": True,
        "reporting_to_id": admin.id,
    })
    emp = await user_repo.create_user(org.id, {
        "email": "emp@auto.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Emp", "last_name": "Loyee", "role": "Employee", "is_active": True,
        "reporting_to_id": manager.id,
    })
    await db.commit()

    res_stage = await db.execute(
        select(PipelineStage.id).filter(
            PipelineStage.organization_id == org.id, PipelineStage.is_system_default == True,
        )
    )
    stage_id = res_stage.scalar()

    return {
        "org": org, "admin": admin, "manager": manager, "emp": emp, "stage_id": stage_id,
        "headers": {"Authorization": f"Bearer {create_access_token(admin.id)}"},
    }


# --- Convert ---

@pytest.mark.asyncio
async def test_convert_lead_creates_contact_and_archives(client: AsyncClient, db: AsyncSession, setup: dict):
    data = setup
    res = await client.post("/api/v1/leads/", json={
        "last_name": "Buyer", "first_name": "Bob", "title": "CEO",
        "email": "bob@acme.com", "phone": "+15551000", "company_name": "Acme Inc",
    }, headers=data["headers"])
    lead_id = res.json()["id"]

    res = await client.post(f"/api/v1/leads/{lead_id}/convert", json={"create_company": True}, headers=data["headers"])
    assert res.status_code == 200
    body = res.json()
    assert body["contact_id"]
    assert body["company_id"]

    # Contact exists
    c = await db.get(Contact, uuid.UUID(body["contact_id"]))
    assert c is not None
    assert c.last_name == "Buyer"

    # Lead archived + linked, excluded from default list
    lead = await db.get(Lead, uuid.UUID(lead_id))
    await db.refresh(lead)
    assert lead.is_archived is True
    assert str(lead.converted_contact_id) == body["contact_id"]

    listed = await client.get("/api/v1/leads/", headers=data["headers"])
    assert lead_id not in [l["id"] for l in listed.json()]


@pytest.mark.asyncio
async def test_convert_twice_rejected(client: AsyncClient, setup: dict):
    data = setup
    res = await client.post("/api/v1/leads/", json={"last_name": "X", "title": "T", "company_name": "Y"}, headers=data["headers"])
    lead_id = res.json()["id"]
    await client.post(f"/api/v1/leads/{lead_id}/convert", json={}, headers=data["headers"])
    again = await client.post(f"/api/v1/leads/{lead_id}/convert", json={}, headers=data["headers"])
    assert again.status_code == 400


# --- Reminders ---

@pytest.mark.asyncio
async def test_reminder_crud_and_dispatch(client: AsyncClient, db: AsyncSession, setup: dict):
    from app.cron.lead_cron import dispatch_due_reminders
    data = setup
    res = await client.post("/api/v1/leads/", json={"last_name": "R", "title": "T"}, headers=data["headers"])
    lead_id = res.json()["id"]

    # create a reminder due in the past
    past = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    res = await client.post(f"/api/v1/leads/{lead_id}/reminders",
                            json={"remind_at": past, "note": "Follow up"}, headers=data["headers"])
    assert res.status_code == 201
    rid = res.json()["id"]

    # list
    res = await client.get(f"/api/v1/leads/{lead_id}/reminders", headers=data["headers"])
    assert len(res.json()) == 1

    # dispatch
    sent = await dispatch_due_reminders(db)
    await db.commit()
    assert sent == 1
    notif = await db.execute(select(Notification).filter(Notification.category == "lead", Notification.title == "Lead reminder"))
    assert notif.scalars().first() is not None

    # second dispatch does nothing (already sent)
    assert await dispatch_due_reminders(db) == 0

    # delete
    res = await client.request("DELETE", f"/api/v1/leads/{lead_id}/reminders/{rid}", headers=data["headers"])
    assert res.status_code == 204


# --- Escalation ---

@pytest.mark.asyncio
async def test_escalation_config_and_scan(client: AsyncClient, db: AsyncSession, setup: dict):
    from app.cron.lead_cron import run_escalation_scan
    data = setup

    # enable escalation
    res = await client.patch("/api/v1/leads/escalation/config",
                             json={"is_active": True, "idle_days": 3}, headers=data["headers"])
    assert res.status_code == 200
    assert res.json()["is_active"] is True

    # a stale lead assigned to emp (whose manager is 'manager'), created 10 days ago
    stale = Lead(
        organization_id=data["org"].id, last_name="Old", title="Stale deal",
        assigned_user_id=data["emp"].id, created_by=data["admin"].id, stage_id=data["stage_id"],
        created_at=datetime.now(timezone.utc) - timedelta(days=10),
    )
    db.add(stale)
    await db.commit()

    escalated = await run_escalation_scan(db)
    await db.commit()
    assert escalated == 1

    # manager got a notification + audit recorded
    notif = await db.execute(select(Notification).filter(
        Notification.user_id == data["manager"].id, Notification.title == "Lead escalation"))
    assert notif.scalars().first() is not None
    audit = await db.execute(select(AuditLog).filter(AuditLog.action == "LEAD_ESCALATED"))
    assert audit.scalars().first() is not None

    # second scan is deduped within the window
    assert await run_escalation_scan(db) == 0


# --- Workflow ---

@pytest.mark.asyncio
async def test_workflow_rule_crud_and_validation(client: AsyncClient, setup: dict):
    data = setup
    # invalid action type rejected
    bad = await client.post("/api/v1/leads/workflows", json={
        "name": "Bad", "trigger_event": "lead_created",
        "conditions": [], "actions": [{"type": "delete_everything"}],
    }, headers=data["headers"])
    assert bad.status_code == 400

    # valid rule
    good = await client.post("/api/v1/leads/workflows", json={
        "name": "Tag hot", "trigger_event": "lead_created",
        "conditions": [{"field": "source", "op": "eq", "value": "Referral"}],
        "actions": [{"type": "set_priority", "value": "Urgent"}],
    }, headers=data["headers"])
    assert good.status_code == 201
    rid = good.json()["id"]

    lst = await client.get("/api/v1/leads/workflows", headers=data["headers"])
    assert any(r["id"] == rid for r in lst.json())

    await client.delete(f"/api/v1/leads/workflows/{rid}", headers=data["headers"])


@pytest.mark.asyncio
async def test_workflow_runs_on_lead_create(client: AsyncClient, setup: dict):
    data = setup
    await client.post("/api/v1/leads/workflows", json={
        "name": "Referral urgent", "trigger_event": "lead_created",
        "conditions": [{"field": "source", "op": "eq", "value": "Referral"}],
        "actions": [{"type": "set_priority", "value": "Urgent"}, {"type": "set_status", "value": "Qualified"}],
    }, headers=data["headers"])

    # Referral lead -> rule fires
    res = await client.post("/api/v1/leads/", json={
        "last_name": "Ref", "title": "T", "source": "Referral", "priority": "Low",
    }, headers=data["headers"])
    assert res.status_code == 201
    assert res.json()["priority"] == "Urgent"
    assert res.json()["status"] == "Qualified"

    # Non-referral lead -> unchanged
    res2 = await client.post("/api/v1/leads/", json={
        "last_name": "Web", "title": "T", "source": "Website", "priority": "Low",
    }, headers=data["headers"])
    assert res2.json()["priority"] == "Low"


@pytest.mark.asyncio
async def test_workflow_runs_on_update(client: AsyncClient, setup: dict):
    data = setup
    await client.post("/api/v1/leads/workflows", json={
        "name": "High value note", "trigger_event": "lead_updated",
        "conditions": [{"field": "value", "op": "gte", "value": 50000}],
        "actions": [{"type": "set_priority", "value": "High"}],
    }, headers=data["headers"])

    res = await client.post("/api/v1/leads/", json={"last_name": "V", "title": "T", "priority": "Low"}, headers=data["headers"])
    lead_id = res.json()["id"]

    upd = await client.patch(f"/api/v1/leads/{lead_id}", json={"value": 80000}, headers=data["headers"])
    assert upd.status_code == 200
    assert upd.json()["priority"] == "High"
