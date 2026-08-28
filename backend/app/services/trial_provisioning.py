"""Shared trial-tenant provisioning used by BOTH the manual SuperAdmin approval
and the public auto-approve signup flow, so they behave identically:
org + owner (OrgAdmin) + trial subscription (Professional/is_trial plan) +
default team + password-setup email."""
import re
import secrets
import uuid
from datetime import datetime, timezone, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.trial_request import TrialRequest
from app.models.user import User
from app.models.plan import Plan
from app.models.plan_feature import PlanFeature
from app.models.tenant_subscription import TenantSubscription
from app.models.seat_history import SeatAssignmentHistory
from app.models.team import Team, TeamMember
from app.core.security import generate_random_token, hash_token, get_password_hash
from app.services.email_service import send_email
from app.services.audit_service import AuditService
from app.repositories.organization import OrganizationRepository
from app.repositories.user import UserRepository
from app.core.config import settings


async def _pick_trial_plan(db: AsyncSession) -> Plan:
    all_plans = list((await db.execute(select(Plan).where(Plan.is_deleted == False))).scalars().all())
    plan = next((p for p in all_plans if getattr(p, "is_trial", False)), None)
    if not plan:
        PREF = ["convert", "scale", "enterprise", "connect"]
        featured = set((await db.execute(
            select(PlanFeature.plan_id).where(PlanFeature.enabled == True))).scalars().all())
        pool = [p for p in all_plans if p.id in featured] or all_plans
        plan = sorted(pool, key=lambda p: PREF.index((p.name or "").lower()) if (p.name or "").lower() in PREF else len(PREF))[0] if pool else None
    if not plan:
        plan = Plan(
            name="Convert", display_name="Convert", price_inr=1299.0, monthly_price=1299.0,
            max_users=1000, minimum_users=3, maximum_users=1000, minimum_contract_months=3,
            extra_user_price=1299.0, allow_additional_seats=True, storage_limit_gb=10,
            recording_retention_days=90, priority_support=True, api_access=False,
            is_active=True, plan_active=True, is_trial=True, trial_days=7, features={},
        )
        db.add(plan)
        await db.flush()
    return plan


async def provision_trial_tenant(db: AsyncSession, trial_req: TrialRequest,
                                 performed_by_actor_id: uuid.UUID | None = None) -> tuple:
    """Provision a full tenant from a TrialRequest. Marks it APPROVED, commits,
    and emails the owner a set-password link. Returns (org, user)."""
    # Guard: email must not already belong to a user.
    if (await db.execute(select(User).where(User.email == trial_req.email, User.is_deleted == False))).scalars().first():
        raise ValueError("A user with this email is already registered")

    # Unique slug from company name.
    base = re.sub(r"\s+", "-", re.sub(r"[^a-z0-9\s-]", "", trial_req.company_name.lower().strip()))
    org_repo = OrganizationRepository(db)
    slug, n = base, 0
    while await org_repo.get_by_slug(slug):
        n += 1
        slug = f"{base}-{n}"

    org = await org_repo.create({"name": trial_req.company_name, "slug": slug})

    plan = await _pick_trial_plan(db)

    now_utc = datetime.now(timezone.utc)
    trial_days = getattr(plan, "trial_days", None) or 14
    trial_end = now_utc + timedelta(days=trial_days)
    db.add(TenantSubscription(
        organization_id=org.id, plan_id=plan.id, status="trial",
        start_date=now_utc, end_date=trial_end, trial_end_date=trial_end,
        auto_renew=True, billing_cycle="monthly", users_purchased=10, users_active=1,
    ))
    await db.flush()

    org.subscription_plan = plan.name
    org.max_users = 10
    org.subscription_expires_at = trial_end.replace(tzinfo=None)
    org.subscription_status = "trial"
    db.add(org)

    parts = trial_req.full_name.strip().split(" ", 1)
    first_name, last_name = parts[0], (parts[1] if len(parts) > 1 else "")
    user = await UserRepository(db).create({
        "organization_id": org.id, "email": trial_req.email,
        "hashed_password": get_password_hash(secrets.token_urlsafe(32)),
        "first_name": first_name, "last_name": last_name, "role": "OrgAdmin",
        "is_verified": True, "is_active": True, "phone": trial_req.phone,
    })
    user.seat_number = "Seat-001"
    db.add(user)
    db.add(SeatAssignmentHistory(
        organization_id=org.id, seat_number="Seat-001", user_id=user.id,
        action="Assigned", performed_by_id=performed_by_actor_id or user.id,
        remarks="Initial trial admin seat assignment",
    ))

    team = Team(organization_id=org.id, name="Sales Team", code="SLS",
                description="Default sales working group", team_leader_id=user.id,
                status="active", created_by=user.id)
    db.add(team)
    await db.flush()
    db.add(TeamMember(organization_id=org.id, team_id=team.id, user_id=user.id, role_in_team="leader"))

    token = generate_random_token()
    user.reset_token = hash_token(token)
    user.reset_token_expires = now_utc + timedelta(hours=24)
    db.add(user)

    trial_req.status = "APPROVED"
    db.add(trial_req)
    await db.commit()

    frontend_url = (settings.FRONTEND_URL
                    or (settings.BACKEND_CORS_ORIGINS[0] if settings.BACKEND_CORS_ORIGINS else None)
                    or "http://localhost:5173").rstrip("/")
    try:
        send_email(
            to_email=user.email,
            subject="Welcome to Johnson Softwares CRM - Setup Your Password",
            template_name="trial_approved.html",
            context={"reset_url": f"{frontend_url}/login?token={token}",
                     "full_name": trial_req.full_name, "company_name": trial_req.company_name},
        )
    except Exception:
        pass  # provisioning already committed; email is best-effort

    await AuditService(db).log_event(
        actor_id=performed_by_actor_id, organization_id=org.id,
        event_type="TRIAL_REQUEST_APPROVED",
        description=f"Trial provisioned for '{trial_req.company_name}' ({slug})",
    )
    return org, user
