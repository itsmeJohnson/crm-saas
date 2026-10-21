import logging
import re
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.middleware.permissions import require_active_user
from app.models.user import User
from app.models.lead import Lead
from app.models.pipeline import PipelineStage
from app.schemas.lead import LeadResponse
from app.schemas.dialer import NextLeadRequest, AgentStateUpdate, AgentStateResponse, CallDispositionRequest, CallLeadRequest, InboundLeadLookupRequest
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
    elif provider == "callerdesk":
        return bool(
            (cfg.get("authcode") or cfg.get("x_api_key") or cfg.get("authentication_token"))
            and (cfg.get("deskphone") or cfg.get("default_caller_id"))
        )
    elif provider == "telecmi":
        return bool(
            (cfg.get("company_id") or cfg.get("appid"))
            and (cfg.get("secret_token") or cfg.get("x_api_key") or cfg.get("authentication_token"))
            and cfg.get("default_caller_id")
        )
    return bool(cfg.get("x_api_key") or cfg.get("authentication_token"))


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
    if user.role in ("Employee", "TeamLeader", "Telecaller", "Manager", "OrgAdmin"):
        return True
    return False

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

    # 2.5 Priority Slot #1: Callback Engine check for mature scheduled callback leads
    from app.models.lead_reminder import LeadReminder
    cb_stmt = select(LeadReminder).where(
        LeadReminder.user_id == actor.id,
        LeadReminder.is_sent == False,
        LeadReminder.remind_at <= now
    ).order_by(LeadReminder.remind_at.asc()).limit(1)
    cb_res = await db.execute(cb_stmt)
    mature_reminder = cb_res.scalar_one_or_none()

    lead = None
    if mature_reminder:
        from sqlalchemy.orm import selectinload
        cb_lead_res = await db.execute(
            select(Lead).options(selectinload(Lead.stage)).filter(
                Lead.id == mature_reminder.lead_id,
                Lead.organization_id == actor.organization_id,
                Lead.is_deleted == False
            )
        )
        lead = cb_lead_res.scalars().first()
        if lead:
            mature_reminder.is_sent = True
            db.add(mature_reminder)

    if not lead:
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
            agent_phone = payload.agent_phone_number or actor.phone or (cfg or {}).get("user_uuid")
            call_sid = await trigger_provider_call(cfg, lead.phone, agent_phone, call_sid)
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
    await state_service.set_agent_state(
        actor.organization_id, actor.id, "ACTIVE_CALLING", metadata={"lead_id": str(lead.id)}
    )

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
    if lead.assigned_user_id != actor.id and actor.role not in ("SuperAdmin", "OrgAdmin", "TeamLeader"):
        if lead.assigned_user_id is None:
            lead.assigned_user_id = actor.id
            db.add(lead)
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only call leads assigned to you."
            )
    elif lead.assigned_user_id is None:
        lead.assigned_user_id = actor.id
        db.add(lead)
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
        agent_phone = payload.agent_phone_number or actor.phone or (cfg or {}).get("user_uuid")
        call_sid = await trigger_provider_call(cfg, lead.phone, agent_phone, call_sid)
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
    await AgentStateService().set_agent_state(
        actor.organization_id, actor.id, "ACTIVE_CALLING", metadata={"lead_id": str(lead.id)}
    )

    await db.commit()

    refetched = await db.execute(
        select(Lead).options(selectinload(Lead.stage)).filter(Lead.id == lead.id)
    )
    return refetched.scalar_one()

@router.post("/inbound-lead", response_model=LeadResponse)
async def get_or_create_inbound_lead(
    payload: InboundLeadLookupRequest,
    actor: User = Depends(require_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Looks up or auto-creates an active lead for an incoming call from a customer.
    Ensures that disposition logging always has a genuine database Lead record with UUID.
    """
    from sqlalchemy.orm import selectinload
    raw_phone = (payload.phone or "").strip()
    digits = re.sub(r"\D", "", raw_phone)
    last_10 = digits[-10:] if len(digits) >= 10 else digits

    lead = None
    if last_10:
        res = await db.execute(
            select(Lead)
            .options(selectinload(Lead.stage))
            .filter(
                Lead.organization_id == actor.organization_id,
                Lead.is_deleted == False,
                Lead.phone.like(f"%{last_10}%")
            )
            .order_by(Lead.updated_at.desc())
            .limit(1)
        )
        lead = res.scalars().first()

    if not lead:
        stage_res = await db.execute(
            select(PipelineStage.id).where(
                PipelineStage.organization_id == actor.organization_id,
                PipelineStage.is_deleted == False
            ).order_by(PipelineStage.order_position.asc()).limit(1)
        )
        stage_id = stage_res.scalar_one_or_none()
        clean_phone = raw_phone if raw_phone.startswith("+") else (f"+91{last_10}" if last_10 else raw_phone)
        lead = Lead(
            organization_id=actor.organization_id,
            first_name=payload.caller_name or "Inbound",
            last_name=f"Caller ({last_10 or 'Unknown'})",
            title=f"Inbound Call from {clean_phone or 'Unknown'}",
            phone=clean_phone or "+910000000000",
            source="Inbound Call",
            status="New",
            stage_id=stage_id,
            assigned_user_id=actor.id,
            created_by=actor.id,
        )
        db.add(lead)
        await db.commit()
        await db.refresh(lead)

    refetched = await db.execute(
        select(Lead).options(selectinload(Lead.stage)).filter(Lead.id == lead.id)
    )
    return refetched.scalar_one()


@router.post("/leads/{lead_id}/disposition", response_model=LeadResponse)
async def submit_disposition(
    lead_id: str,
    payload: CallDispositionRequest,
    actor: User = Depends(require_active_user),
    db: AsyncSession = Depends(get_db)
):
    # Verify user is allowed to submit dispositions (Telecaller, SuperAdmin, OrgAdmin, or TeamLeader)
    is_tele = await check_is_telecaller(actor, db)
    if not is_tele and actor.role not in ("SuperAdmin", "OrgAdmin", "TeamLeader"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Telecallers are allowed to submit dispositions."
        )

    parsed_uuid = None
    try:
        parsed_uuid = uuid.UUID(lead_id)
    except (ValueError, AttributeError):
        parsed_uuid = None

    if parsed_uuid:
        res = await db.execute(
            select(Lead).filter(
                Lead.id == parsed_uuid,
                Lead.organization_id == actor.organization_id,
                Lead.is_deleted == False
            )
        )
        existing_lead = res.scalars().first()
        if existing_lead:
            lead = await DispositionService.submit_disposition(
                db=db,
                lead_id=parsed_uuid,
                payload=payload,
                actor=actor
            )
            return lead

    # If lead_id is not a valid UUID or wasn't found by UUID (e.g. TeleCMI call_id string was passed),
    # resolve by digits/phone or create prospective lead record so call disposition never gets blocked!
    digits = re.sub(r"\D", "", lead_id or "")
    last_10 = digits[-10:] if len(digits) >= 10 else None
    matched_lead = None
    if last_10:
        res = await db.execute(
            select(Lead).filter(
                Lead.organization_id == actor.organization_id,
                Lead.is_deleted == False,
                Lead.phone.like(f"%{last_10}%")
            ).order_by(Lead.updated_at.desc()).limit(1)
        )
        matched_lead = res.scalars().first()

    if not matched_lead:
        stage_res = await db.execute(
            select(PipelineStage.id).where(
                PipelineStage.organization_id == actor.organization_id,
                PipelineStage.is_deleted == False
            ).order_by(PipelineStage.order_position.asc()).limit(1)
        )
        stage_id = stage_res.scalar_one_or_none()
        clean_phone = f"+91{last_10}" if last_10 else "+910000000000"
        matched_lead = Lead(
            organization_id=actor.organization_id,
            first_name="Call",
            last_name=f"Lead ({last_10 or lead_id[:8]})",
            title=f"Call Session {lead_id[:8]}",
            phone=clean_phone,
            source="Phone Call",
            status="Contacted",
            stage_id=stage_id,
            assigned_user_id=actor.id,
            created_by=actor.id,
        )
        db.add(matched_lead)
        await db.commit()
        await db.refresh(matched_lead)

    lead = await DispositionService.submit_disposition(
        db=db,
        lead_id=matched_lead.id,
        payload=payload,
        actor=actor
    )
    return lead


@router.get("/webrtc-session")
async def get_webrtc_session(
    actor: User = Depends(require_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Returns WebRTC connection parameters for the agent's browser softphone."""
    cfg = await load_org_calling_config(db, actor)
    if not cfg:
        return {"enabled": False, "provider": None}
    provider = cfg.get("provider")
    if provider == "telecmi":
        appid = cfg.get("company_id") or "33339071"
        caller_id = cfg.get("default_caller_id") or "917949817390"
        user_uuid = cfg.get("user_uuid") or f"5001_{appid}"
        agent_password = cfg.get("agent_password") or "admin@123"
        agent_name = f"{actor.first_name or ''} {actor.last_name or ''}".strip() or actor.email or "Telecaller Agent"
        return {
            "enabled": True,
            "provider": "telecmi",
            "user_id": user_uuid,
            "password": agent_password,
            "region": "sbcind.telecmi.com",
            "caller_id": caller_id,
            "agent_name": agent_name
        }
    return {"enabled": False, "provider": provider}

