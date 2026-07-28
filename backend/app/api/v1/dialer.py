import logging
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.middleware.permissions import require_active_user
from app.models.user import User
from app.models.lead import Lead
from app.schemas.lead import LeadResponse
from app.schemas.dialer import NextLeadRequest, AgentStateUpdate, AgentStateResponse, CallDispositionRequest, CallLeadRequest
from app.services.agent_state_service import AgentStateService
from app.services.disposition_service import DispositionService

# The dialer cockpit (next-lead queue + manual disposition / pipeline updates) is
# available to telecallers on ALL plans. Only the integrated Knowlarity click-to-call
# is feature-gated (see the OUTBOUND_CALLING check inside get_next_lead), so entry
# plans like Core CRM get a manual telecalling workflow without paid calling.
router = APIRouter()
logger = logging.getLogger(__name__)


# ---- Click-to-call provider dispatch (Knowlarity | MyOperator) --------------

def config_ready(cfg: dict | None) -> bool:
    """True when the ORG's decrypted telephony config has enough to place a call.
    Credentials are org-level (Settings → Communication → Calling) — clients never
    send them. MyOperator routes the agent leg via its Public IVR; Knowlarity
    needs the org API key (agent phone comes from the calling user)."""
    if not cfg:
        return False
    provider = (cfg.get("provider") or "myoperator").lower()
    if provider == "myoperator":
        return bool(cfg.get("company_id") and cfg.get("x_api_key")
                    and cfg.get("secret_token") and cfg.get("public_ivr_id"))
    return bool(cfg.get("x_api_key"))


def _extract_call_id(call_res, fallback: str) -> str:
    """Pull a provider call id out of a variety of response shapes."""
    if call_res and isinstance(call_res, dict):
        success = call_res.get("success")
        if isinstance(success, dict) and success.get("call_id"):
            return success["call_id"]
        for key in ("call_id", "id", "request_id", "uid"):
            if call_res.get(key):
                return str(call_res[key])
        data = call_res.get("data")
        if isinstance(data, dict):
            for key in ("call_id", "id", "uid"):
                if data.get(key):
                    return str(data[key])
    return fallback


async def load_org_calling_config(db: AsyncSession, actor: User) -> dict | None:
    """Decrypted org telephony config (server-side only), or None if unconfigured."""
    from app.services.telephony_config_service import TelephonyConfigService
    return await TelephonyConfigService(db).get_decrypted_config(actor.organization_id)


async def trigger_provider_call(cfg: dict, customer_number: str, agent_number: str | None, fallback_sid: str) -> str:
    """Dispatch a click-to-call through the org's configured provider and return a
    call id (or the fallback sid). Raises on provider error — the caller maps it
    to a 400 so a bad gateway response never records a phantom 'placed' call."""
    from app.services.telephony.factory import get_provider
    call_res = await get_provider(cfg).start_call(number=customer_number, agent_number=agent_number)
    return _extract_call_id(call_res, fallback_sid)


async def check_is_telecaller(user: User, db: AsyncSession) -> bool:
    if user.role != "Employee" or not user.reporting_to_id:
        return False
    parent_res = await db.execute(select(User.role).filter(User.id == user.reporting_to_id))
    parent_role = parent_res.scalar()
    return parent_role == "Employee"

@router.post("/next-lead", response_model=LeadResponse)
async def get_next_lead(
    payload: NextLeadRequest = NextLeadRequest(),
    actor: User = Depends(require_active_user),
    db: AsyncSession = Depends(get_db)
):
    # 1. Verify user is a Telecaller
    is_tele = await check_is_telecaller(actor, db)
    if not is_tele:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Telecallers are allowed to fetch the next lead."
        )

    # 2. Verify agent state is IDLE
    state_service = AgentStateService()
    state_data = await state_service.get_agent_state(actor.organization_id, actor.id)
    if state_data["state"] != "IDLE":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Agent must be IDLE to fetch the next lead. Current state: {state_data['state']}"
        )

    # 3. Query the single oldest callable lead: fresh "New" leads, PLUS leads whose
    # last call didn't connect (RNR / Switch Off / Busy) and are due for a retry —
    # cooldown elapsed (available_at) and under the 4-attempt cap. This activates
    # the retry fields the disposition service already maintains, so a not-picked
    # number comes back around instead of being lost after one attempt.
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    RETRYABLE_DISPOSITIONS = ["RNR", "Switch Off", "Busy"]
    filters = [
        Lead.organization_id == actor.organization_id,
        Lead.is_deleted == False,
        or_(
            Lead.status == "New",
            and_(
                Lead.status.in_(RETRYABLE_DISPOSITIONS),
                Lead.call_attempts_count <= 4,
                or_(Lead.available_at.is_(None), Lead.available_at <= now),
            ),
        ),
    ]

    if payload.collective_pooling:
        filters.append(
            or_(
                Lead.assigned_user_id == actor.id,
                and_(
                    Lead.assigned_user_id.is_(None),
                    Lead.created_by == actor.reporting_to_id
                )
            )
        )
    else:
        filters.append(Lead.assigned_user_id == actor.id)

    from sqlalchemy.orm import selectinload
    query = select(Lead).options(selectinload(Lead.stage)).filter(*filters)

    # Dialect-aware locking for high throughput on PostgreSQL and compatibility with SQLite
    dialect_name = getattr(db.bind, "dialect", None)
    is_postgresql = dialect_name and getattr(dialect_name, "name", "") == "postgresql"
    if is_postgresql:
        query = query.with_for_update(skip_locked=True)

    query = query.order_by(Lead.created_at.asc(), Lead.id.asc()).limit(1)

    result = await db.execute(query)
    lead = result.scalars().first()

    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No uncalled leads available."
        )

    # 4. If lead is unassigned, assign it to caller
    if lead.assigned_user_id is None:
        lead.assigned_user_id = actor.id
        db.add(lead)

    # 4.5. Trigger click-to-call via the ORG's telephony config (not client creds).
    call_sid = f"outbound-{uuid.uuid4()}"
    cfg = await load_org_calling_config(db, actor)
    if config_ready(cfg):
        # Integrated calling is a paid feature — plans without it (e.g. Core CRM)
        # can use the dialer console with their own phone but not trigger calls here.
        from app.dependencies.feature_guard import tenant_has_feature
        if not await tenant_has_feature(db, actor, "OUTBOUND_CALLING"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Integrated outbound calling is not included in your plan. Please upgrade to enable click-to-call."
            )
        try:
            call_sid = await trigger_provider_call(cfg, lead.phone, actor.phone, call_sid)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Outbound calling failed to initiate: {str(e)}"
            )

    # Pre-create outbound call activity
    from app.models.activity import Activity
    new_call_activity = Activity(
        organization_id=actor.organization_id,
        activity_type="Call",
        subject=f"Outbound Call to {lead.first_name or ''} {lead.last_name or ''}".strip(),
        description="Outbound call initiated.",
        status="Planned",
        assigned_user_id=actor.id,
        lead_id=lead.id,
        created_by=actor.id,
        call_sid=str(call_sid),
        call_direction="OUTBOUND"
    )
    db.add(new_call_activity)

    # 4.6. Fire call_logged workflow rules against the lead
    from app.services.workflow_service import WorkflowService
    await WorkflowService(db).run("call_logged", lead, actor)

    # 5. Transition agent's Redis state to ACTIVE_CALLING
    await state_service.set_agent_state(actor.organization_id, actor.id, "ACTIVE_CALLING")

    await db.commit()
    
    from sqlalchemy.orm import selectinload
    refetched_query = select(Lead).options(selectinload(Lead.stage)).filter(Lead.id == lead.id)
    refetched_res = await db.execute(refetched_query)
    lead = refetched_res.scalar_one()

    return lead

@router.post("/state", response_model=AgentStateResponse)
async def update_state(
    payload: AgentStateUpdate,
    actor: User = Depends(require_active_user),
    db: AsyncSession = Depends(get_db)
):
    # Verify user is a Telecaller
    is_tele = await check_is_telecaller(actor, db)
    if not is_tele:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Telecallers are allowed to manage their dialer state."
        )

    state_service = AgentStateService()
    try:
        new_state = await state_service.set_agent_state(
            org_id=actor.organization_id,
            user_id=actor.id,
            state=payload.state,
            metadata=payload.metadata
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    return new_state

@router.get("/state", response_model=AgentStateResponse)
async def get_state(
    actor: User = Depends(require_active_user),
    db: AsyncSession = Depends(get_db)
):
    # Verify user is a Telecaller
    is_tele = await check_is_telecaller(actor, db)
    if not is_tele:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Telecallers are allowed to access their dialer state."
        )

    state_service = AgentStateService()
    state_data = await state_service.get_agent_state(actor.organization_id, actor.id)
    return state_data

@router.post("/leads/{lead_id}/call", response_model=LeadResponse)
async def call_lead(
    lead_id: uuid.UUID,
    payload: CallLeadRequest = CallLeadRequest(),
    actor: User = Depends(require_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Manually place a click-to-call to ONE specific lead from the Leads list
    (any status — not just 'New' queue leads). The customer number is dialed
    server-side so it is never revealed to a masked telecaller. Mirrors the
    click-to-call half of get_next_lead but skips the queue fetch."""
    # 1. Verify user is a Telecaller
    is_tele = await check_is_telecaller(actor, db)
    if not is_tele:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Telecallers are allowed to place calls."
        )

    # 2. Fetch the lead, scoped to org + assignment (agents call their own leads)
    from sqlalchemy.orm import selectinload
    res = await db.execute(
        select(Lead).options(selectinload(Lead.stage)).filter(
            Lead.id == lead_id,
            Lead.organization_id == actor.organization_id,
            Lead.is_deleted == False,
        )
    )
    lead = res.scalars().first()
    if not lead:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found.")
    if lead.assigned_user_id != actor.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only call leads assigned to you."
        )
    if not lead.phone:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This lead has no phone number.")

    # 3. Integrated click-to-call is a paid feature and needs org telephony config.
    cfg = await load_org_calling_config(db, actor)
    if not config_ready(cfg):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Calling is not configured for your organization. Ask an administrator to set it up in Settings → Communication → Calling.",
        )
    from app.dependencies.feature_guard import tenant_has_feature
    if not await tenant_has_feature(db, actor, "OUTBOUND_CALLING"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Integrated outbound calling is not included in your plan. Please upgrade to enable click-to-call.",
        )

    call_sid = f"outbound-{uuid.uuid4()}"
    try:
        call_sid = await trigger_provider_call(cfg, lead.phone, actor.phone, call_sid)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Outbound calling failed to initiate: {str(e)}",
        )

    # 4. Record the outbound call attempt as an Activity.
    from app.models.activity import Activity
    db.add(Activity(
        organization_id=actor.organization_id,
        activity_type="Call",
        subject=f"Outbound Call to {lead.first_name or ''} {lead.last_name or ''}".strip(),
        description="Outbound call initiated (manual, from Leads).",
        status="Planned",
        assigned_user_id=actor.id,
        lead_id=lead.id,
        created_by=actor.id,
        call_sid=str(call_sid),
        call_direction="OUTBOUND",
    ))

    # 5. Fire call_logged workflow rules, then flip the agent to ACTIVE_CALLING.
    from app.services.workflow_service import WorkflowService
    await WorkflowService(db).run("call_logged", lead, actor)
    await AgentStateService().set_agent_state(actor.organization_id, actor.id, "ACTIVE_CALLING")

    await db.commit()

    refetched = await db.execute(
        select(Lead).options(selectinload(Lead.stage)).filter(Lead.id == lead.id)
    )
    return refetched.scalar_one()

@router.post("/leads/{lead_id}/disposition", response_model=LeadResponse)
async def submit_disposition(
    lead_id: uuid.UUID,
    payload: CallDispositionRequest,
    actor: User = Depends(require_active_user),
    db: AsyncSession = Depends(get_db)
):
    # Verify user is a Telecaller
    is_tele = await check_is_telecaller(actor, db)
    if not is_tele:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Telecallers are allowed to submit dispositions."
        )

    lead = await DispositionService.submit_disposition(
        db=db,
        lead_id=lead_id,
        payload=payload,
        actor=actor
    )
    return lead
