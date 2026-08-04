import pytest
import uuid
from httpx import AsyncClient
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import patch

from app.models.organization import Organization
from app.models.user import User
from app.models.trial_request import TrialRequest
from app.models.tenant_subscription import TenantSubscription
from app.models.team import Team, TeamMember
from app.models.pipeline import PipelineStage
from app.core.security import create_access_token, get_password_hash
import app.services.email_service as email_service_mod

@pytest.fixture
def capture_email(monkeypatch):
    sent = {}
    def fake_send_email(to_email, subject, template_name, context):
        sent["to"] = to_email
        sent["subject"] = subject
        sent["template_name"] = template_name
        sent["context"] = context
    monkeypatch.setattr(email_service_mod, "send_email", fake_send_email)
    return sent

@pytest.fixture
async def setup_users(db: AsyncSession):
    # Create SuperAdmin
    super_org = Organization(name="SuperAdmin Org", slug="super-admin-org-trial")
    db.add(super_org)
    await db.flush()

    pwd_hash = get_password_hash("password123")
    super_admin = User(
        organization_id=super_org.id,
        email="superadmin@trialtest.com",
        hashed_password=pwd_hash,
        first_name="Super",
        last_name="Admin",
        role="SuperAdmin",
        is_active=True,
        is_verified=True
    )
    db.add(super_admin)

    # Create a regular OrgAdmin for auth checks
    regular_org = Organization(name="Regular Org", slug="regular-org-trial")
    db.add(regular_org)
    await db.flush()

    regular_user = User(
        organization_id=regular_org.id,
        email="regular@trialtest.com",
        hashed_password=pwd_hash,
        first_name="Regular",
        last_name="User",
        role="OrgAdmin",
        is_active=True,
        is_verified=True
    )
    db.add(regular_user)
    await db.flush()
    await db.commit()

    super_token = create_access_token(super_admin.id)
    regular_token = create_access_token(regular_user.id)

    return {
        "super_headers": {"Authorization": f"Bearer {super_token}"},
        "regular_headers": {"Authorization": f"Bearer {regular_token}"},
        "super_admin": super_admin,
        "regular_user": regular_user
    }

@pytest.mark.asyncio
async def test_trial_registration_public_flow(client: AsyncClient, db: AsyncSession):
    payload = {
        "full_name": "  Alice Johnson  ",
        "company_name": "Alice Inc.",
        "email": "   ALICE@ALICEINC.COM  ",
        "phone": "+91 99999 88888"
    }

    # 1. Submit request
    response = await client.post("/api/v1/auth/trial-register", json=payload)
    assert response.status_code == 201
    assert response.json()["detail"] == "Thank you! Your trial request has been received and is under review."

    # Verify model is created with normalized email
    stmt = select(TrialRequest).where(TrialRequest.company_name == "Alice Inc.")
    res = await db.execute(stmt)
    req = res.scalar_one_or_none()
    assert req is not None
    assert req.full_name == "  Alice Johnson  "
    assert req.email == "alice@aliceinc.com"  # Normalized lowercased
    assert req.status == "PENDING"

    # 2. Re-submit same email raises 400
    response2 = await client.post("/api/v1/auth/trial-register", json=payload)
    assert response2.status_code == 400
    assert response2.json()["detail"] == "A trial request for this email has already been submitted."

@pytest.mark.asyncio
async def test_trial_requests_authorization(client: AsyncClient, setup_users: dict):
    # Anonymous gets 401/403
    response = await client.get("/api/v1/super-admin/trial-requests")
    assert response.status_code in (401, 403)

    # Regular user gets 403
    response = await client.get("/api/v1/super-admin/trial-requests", headers=setup_users["regular_headers"])
    assert response.status_code == 403

    # SuperAdmin can view
    response = await client.get("/api/v1/super-admin/trial-requests", headers=setup_users["super_headers"])
    assert response.status_code == 200

@pytest.mark.asyncio
async def test_trial_requests_approval_flow(client: AsyncClient, setup_users: dict, db: AsyncSession, capture_email: dict):
    # 1. Create a pending request
    req = TrialRequest(
        full_name="Bob Smith",
        company_name="Bob Logistics",
        email="bob@boblogistics.com",
        phone="555-0199",
        status="PENDING"
    )
    db.add(req)
    await db.commit()

    # 2. Approve request
    response = await client.post(
        f"/api/v1/super-admin/trial-requests/{req.id}/approve",
        headers=setup_users["super_headers"]
    )
    assert response.status_code == 200
    assert response.json()["status"] == "APPROVED"

    # 3. Assert Organization exists with default pipelines
    org_stmt = select(Organization).where(Organization.name == "Bob Logistics")
    org_res = await db.execute(org_stmt)
    org = org_res.scalar_one_or_none()
    assert org is not None
    assert org.slug == "bob-logistics"
    assert org.subscription_status == "trial"

    # Assert 5 pipeline stages are created
    pipeline_stmt = select(PipelineStage).where(PipelineStage.organization_id == org.id)
    stages = (await db.execute(pipeline_stmt)).scalars().all()
    assert len(stages) == 5
    stage_names = {s.name for s in stages}
    assert "Fresh Leads" in stage_names
    assert "Converted" in stage_names

    # 4. Assert User (Owner) exists
    user_stmt = select(User).where(User.email == "bob@boblogistics.com")
    user = (await db.execute(user_stmt)).scalar_one_or_none()
    assert user is not None
    assert user.first_name == "Bob"
    assert user.last_name == "Smith"
    assert user.role == "OrgAdmin"
    assert user.seat_number == "Seat-001"
    assert user.reset_token is not None  # Setup token generated

    # 5. Assert Subscription exists for 14 days
    sub_stmt = select(TenantSubscription).where(TenantSubscription.organization_id == org.id)
    sub = (await db.execute(sub_stmt)).scalar_one_or_none()
    assert sub is not None
    assert sub.status == "trial"
    days_left = (sub.end_date.date() - sub.start_date.date()).days
    assert days_left == 14

    # 6. Assert Team exists
    team_stmt = select(Team).where(Team.organization_id == org.id)
    team = (await db.execute(team_stmt)).scalar_one_or_none()
    assert team is not None
    assert team.name == "Sales Team"
    assert team.team_leader_id == user.id

    member_stmt = select(TeamMember).where(TeamMember.team_id == team.id)
    member = (await db.execute(member_stmt)).scalar_one_or_none()
    assert member is not None
    assert member.user_id == user.id
    assert member.role_in_team == "leader"

    # 7. Assert Setup Email captured
    assert capture_email["to"] == "bob@boblogistics.com"
    assert capture_email["subject"] == "Welcome to Johnson Softwares CRM - Setup Your Password"
    assert capture_email["template_name"] == "trial_approved.html"
    assert "token" in capture_email["context"]["reset_url"]

@pytest.mark.asyncio
async def test_trial_requests_rejection_flow(client: AsyncClient, setup_users: dict, db: AsyncSession):
    # 1. Create a pending request
    req = TrialRequest(
        full_name="Charlie Brown",
        company_name="Charlie Toys",
        email="charlie@charlietoys.com",
        phone="555-0200",
        status="PENDING"
    )
    db.add(req)
    await db.commit()

    # 2. Reject request
    response = await client.post(
        f"/api/v1/super-admin/trial-requests/{req.id}/reject",
        headers=setup_users["super_headers"]
    )
    assert response.status_code == 200
    assert response.json()["status"] == "REJECTED"

    # Verify DB update
    stmt = select(TrialRequest).where(TrialRequest.id == req.id)
    req_db = (await db.execute(stmt)).scalar_one_or_none()
    assert req_db.status == "REJECTED"


@pytest.mark.asyncio
async def test_trial_requests_resend_activation_flow(client: AsyncClient, setup_users: dict, db: AsyncSession, capture_email: dict):
    # 1. Create an approved request and corresponding user
    req = TrialRequest(
        full_name="David Miller",
        company_name="David Tech",
        email="david@davidtech.com",
        phone="555-0300",
        status="APPROVED"
    )
    db.add(req)
    await db.flush()

    # Create user for that trial request
    user = User(
        organization_id=setup_users["regular_user"].organization_id,  # just link to any org for test
        email="david@davidtech.com",
        hashed_password=get_password_hash("password123"),
        first_name="David",
        last_name="Miller",
        role="OrgAdmin",
        is_active=True,
        is_verified=True
    )
    db.add(user)
    await db.commit()

    # 2. Resend activation
    response = await client.post(
        f"/api/v1/super-admin/trial-requests/{req.id}/resend-activation",
        headers=setup_users["super_headers"]
    )
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert "resent" in response.json()["message"]

    # 3. Assert new token generated on the user in the database
    await db.refresh(user)
    assert user.reset_token is not None
    assert user.reset_token_expires is not None

    # 4. Assert welcome email captured
    assert capture_email["to"] == "david@davidtech.com"
    assert capture_email["subject"] == "Welcome to Johnson Softwares CRM - Setup Your Password"
    assert capture_email["template_name"] == "trial_approved.html"
    assert "token" in capture_email["context"]["reset_url"]
