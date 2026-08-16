"""Sprint 2 — Lead Management Hardening (P0): Lead Security Matrix.

Verifies the cross-tenant FK-injection fixes:
  * create_lead / update_lead reject stage_id / branch_id / territory_id /
    company_id that are foreign-org or soft-deleted (B1).
  * bulk_update rejects an assigned_user_id that is foreign-org, deleted,
    inactive, or non-assignable — atomically, with HTTP 400 (B2).

Tests exercise LeadService directly (service boundary) with two isolated orgs.
"""
import uuid
import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.core.security import get_password_hash
from app.repositories.organization import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.repositories.lead_repository import LeadRepository
from app.services.lead_service import LeadService
from app.models.pipeline import PipelineStage
from app.models.branch import Branch, Territory
from app.models.company import Company
from app.models.lead import Lead


# ---------------------------------------------------------------------------
# Fixtures — two fully isolated organizations
# ---------------------------------------------------------------------------

async def _make_user(db, org_id, email, role="Employee", is_active=True,
                     is_deleted=False, reporting_to_id=None):
    user = await UserRepository(db).create_user(org_id, {
        "email": email,
        "hashed_password": get_password_hash("password123"),
        "first_name": "U", "last_name": email.split("@")[0],
        "role": role, "is_active": is_active,
        "reporting_to_id": reporting_to_id,
    })
    if is_deleted:
        user.is_deleted = True
        db.add(user)
    await db.flush()
    return user


async def _make_org(db, slug):
    org = await OrganizationRepository(db).create({"name": slug, "slug": slug})
    await db.flush()
    stage_row = (await db.execute(select(PipelineStage).filter(
        PipelineStage.organization_id == org.id,
        PipelineStage.is_system_default == True,
    ))).scalars().first()
    stage_id = stage_row.id
    pipeline_id = stage_row.pipeline_id
    admin = await _make_user(db, org.id, f"admin@{slug}.com", role="OrgAdmin")

    branch = Branch(organization_id=org.id, name="Branch", created_by=admin.id)
    territory = Territory(organization_id=org.id, name="Territory", created_by=admin.id)
    company = Company(organization_id=org.id, name="Company", created_by=admin.id)
    # Soft-deleted siblings (same org, but is_deleted=True → must be rejected)
    del_stage = PipelineStage(organization_id=org.id, pipeline_id=pipeline_id, name="ZDeletedStage",
                              order_position=99, is_system_default=False, is_deleted=True)
    del_branch = Branch(organization_id=org.id, name="ZDelBranch", created_by=admin.id, is_deleted=True)
    del_territory = Territory(organization_id=org.id, name="ZDelTerritory", created_by=admin.id, is_deleted=True)
    del_company = Company(organization_id=org.id, name="ZDelCompany", created_by=admin.id, is_deleted=True)
    for o in (branch, territory, company, del_stage, del_branch, del_territory, del_company):
        db.add(o)
    await db.flush()

    return {
        "org": org, "admin": admin, "stage_id": stage_id,
        "branch": branch, "territory": territory, "company": company,
        "del_stage": del_stage, "del_branch": del_branch,
        "del_territory": del_territory, "del_company": del_company,
    }


@pytest.fixture
async def orgs(db):
    a = await _make_org(db, "org-a")
    b = await _make_org(db, "org-b")
    await db.commit()
    return {"a": a, "b": b}


def _base_lead(**extra):
    return {"last_name": "Test", "title": "Opportunity", **extra}


async def _assert_400(coro):
    with pytest.raises(HTTPException) as exc:
        await coro
    assert exc.value.status_code == 400
    return exc.value


# ===========================================================================
# CREATE LEAD — Stage
# ===========================================================================

async def test_create_valid_stage(orgs, db):
    a = orgs["a"]
    lead = await LeadService(db, a["org"].id).create_lead(a["admin"], _base_lead(stage_id=a["stage_id"]))
    assert lead.id is not None and lead.stage_id == a["stage_id"]


async def test_create_foreign_org_stage(orgs, db):
    a, b = orgs["a"], orgs["b"]
    await _assert_400(LeadService(db, a["org"].id).create_lead(a["admin"], _base_lead(stage_id=b["stage_id"])))


async def test_create_deleted_stage(orgs, db):
    a = orgs["a"]
    await _assert_400(LeadService(db, a["org"].id).create_lead(a["admin"], _base_lead(stage_id=a["del_stage"].id)))


# ===========================================================================
# CREATE LEAD — Branch
# ===========================================================================

async def test_create_valid_branch(orgs, db):
    a = orgs["a"]
    lead = await LeadService(db, a["org"].id).create_lead(a["admin"], _base_lead(branch_id=a["branch"].id))
    assert lead.branch_id == a["branch"].id


async def test_create_foreign_org_branch(orgs, db):
    a, b = orgs["a"], orgs["b"]
    await _assert_400(LeadService(db, a["org"].id).create_lead(a["admin"], _base_lead(branch_id=b["branch"].id)))


async def test_create_deleted_branch(orgs, db):
    a = orgs["a"]
    await _assert_400(LeadService(db, a["org"].id).create_lead(a["admin"], _base_lead(branch_id=a["del_branch"].id)))


# ===========================================================================
# CREATE LEAD — Territory
# ===========================================================================

async def test_create_valid_territory(orgs, db):
    a = orgs["a"]
    lead = await LeadService(db, a["org"].id).create_lead(a["admin"], _base_lead(territory_id=a["territory"].id))
    assert lead.territory_id == a["territory"].id


async def test_create_foreign_org_territory(orgs, db):
    a, b = orgs["a"], orgs["b"]
    await _assert_400(LeadService(db, a["org"].id).create_lead(a["admin"], _base_lead(territory_id=b["territory"].id)))


async def test_create_deleted_territory(orgs, db):
    a = orgs["a"]
    await _assert_400(LeadService(db, a["org"].id).create_lead(a["admin"], _base_lead(territory_id=a["del_territory"].id)))


# ===========================================================================
# CREATE LEAD — Company
# ===========================================================================

async def test_create_valid_company(orgs, db):
    a = orgs["a"]
    lead = await LeadService(db, a["org"].id).create_lead(a["admin"], _base_lead(company_id=a["company"].id))
    assert lead.company_id == a["company"].id


async def test_create_foreign_org_company(orgs, db):
    a, b = orgs["a"], orgs["b"]
    await _assert_400(LeadService(db, a["org"].id).create_lead(a["admin"], _base_lead(company_id=b["company"].id)))


async def test_create_deleted_company(orgs, db):
    a = orgs["a"]
    await _assert_400(LeadService(db, a["org"].id).create_lead(a["admin"], _base_lead(company_id=a["del_company"].id)))


# ===========================================================================
# UPDATE LEAD — foreign/deleted refs rejected; partial PATCH unaffected
# ===========================================================================

async def _make_lead(db, org_id, stage_id, owner_id):
    lead = Lead(organization_id=org_id, last_name="L", title="T",
                stage_id=stage_id, created_by=owner_id, assigned_user_id=owner_id)
    db.add(lead)
    await db.flush()
    return lead


async def test_update_foreign_org_stage_rejected(orgs, db):
    a, b = orgs["a"], orgs["b"]
    lead = await _make_lead(db, a["org"].id, a["stage_id"], a["admin"].id)
    await _assert_400(LeadService(db, a["org"].id).update_lead(a["admin"], lead.id, {"stage_id": b["stage_id"]}))


async def test_update_deleted_company_rejected(orgs, db):
    a = orgs["a"]
    lead = await _make_lead(db, a["org"].id, a["stage_id"], a["admin"].id)
    await _assert_400(LeadService(db, a["org"].id).update_lead(a["admin"], lead.id, {"company_id": a["del_company"].id}))


async def test_update_partial_without_fk_unaffected(orgs, db):
    a = orgs["a"]
    lead = await _make_lead(db, a["org"].id, a["stage_id"], a["admin"].id)
    updated = await LeadService(db, a["org"].id).update_lead(a["admin"], lead.id, {"title": "Renamed"})
    assert updated.title == "Renamed"


async def test_update_valid_same_org_stage(orgs, db):
    a = orgs["a"]
    lead = await _make_lead(db, a["org"].id, a["stage_id"], a["admin"].id)
    other_stage = (await db.execute(select(PipelineStage.id).filter(
        PipelineStage.organization_id == a["org"].id,
        PipelineStage.is_system_default == False,
        PipelineStage.is_deleted == False,
    ).limit(1))).scalar()
    updated = await LeadService(db, a["org"].id).update_lead(a["admin"], lead.id, {"stage_id": other_stage})
    assert updated.stage_id == other_stage


# ===========================================================================
# BULK ASSIGN — org + active + assignable, atomic 400
# ===========================================================================

async def test_bulk_assign_same_org_user(orgs, db):
    a = orgs["a"]
    user2 = await _make_user(db, a["org"].id, "u2@org-a.com")
    await db.flush()
    lead = await _make_lead(db, a["org"].id, a["stage_id"], a["admin"].id)
    res = await LeadService(db, a["org"].id).bulk_update(a["admin"], [lead.id], {"assigned_user_id": user2.id})
    assert res["updated_count"] == 1
    refetched = await LeadRepository(db, a["org"].id).get_lead_by_id(lead.id)
    assert refetched.assigned_user_id == user2.id


async def test_bulk_assign_foreign_org_user_atomic_400(orgs, db):
    a, b = orgs["a"], orgs["b"]
    lead = await _make_lead(db, a["org"].id, a["stage_id"], a["admin"].id)
    await _assert_400(LeadService(db, a["org"].id).bulk_update(a["admin"], [lead.id], {"assigned_user_id": b["admin"].id}))
    # Atomic: original assignee unchanged.
    refetched = await LeadRepository(db, a["org"].id).get_lead_by_id(lead.id)
    assert refetched.assigned_user_id == a["admin"].id


async def test_bulk_assign_deleted_user_400(orgs, db):
    a = orgs["a"]
    deleted = await _make_user(db, a["org"].id, "gone@org-a.com", is_deleted=True)
    await db.flush()
    lead = await _make_lead(db, a["org"].id, a["stage_id"], a["admin"].id)
    await _assert_400(LeadService(db, a["org"].id).bulk_update(a["admin"], [lead.id], {"assigned_user_id": deleted.id}))


async def test_bulk_assign_inactive_user_400(orgs, db):
    a = orgs["a"]
    inactive = await _make_user(db, a["org"].id, "inactive@org-a.com", is_active=False)
    await db.flush()
    lead = await _make_lead(db, a["org"].id, a["stage_id"], a["admin"].id)
    await _assert_400(LeadService(db, a["org"].id).bulk_update(a["admin"], [lead.id], {"assigned_user_id": inactive.id}))


async def test_bulk_assign_non_assignable_user_400(orgs, db):
    """A team leader may only assign within their downline+self; a peer outside
    that chain is non-assignable even though same-org and active."""
    a = orgs["a"]
    tl = await _make_user(db, a["org"].id, "tl@org-a.com", role="Employee",
                          reporting_to_id=a["admin"].id)
    await db.flush()
    report = await _make_user(db, a["org"].id, "report@org-a.com", role="Employee",
                              reporting_to_id=tl.id)
    peer = await _make_user(db, a["org"].id, "peer@org-a.com", role="Employee",
                            reporting_to_id=a["admin"].id)
    await db.flush()
    # Lead owned by the TL (in the TL's own scope) so it passes row-scoping.
    lead = await _make_lead(db, a["org"].id, a["stage_id"], tl.id)
    # Sanity: a downline report IS assignable.
    ok = await LeadService(db, a["org"].id).bulk_update(tl, [lead.id], {"assigned_user_id": report.id})
    assert ok["updated_count"] == 1
    # A peer (not in the TL's downline) is NOT assignable → atomic 400.
    await _assert_400(LeadService(db, a["org"].id).bulk_update(tl, [lead.id], {"assigned_user_id": peer.id}))
    refetched = await LeadRepository(db, a["org"].id).get_lead_by_id(lead.id)
    assert refetched.assigned_user_id == report.id  # unchanged by the rejected call
