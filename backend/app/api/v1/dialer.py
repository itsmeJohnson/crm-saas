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
from app.schemas.dialer import NextLeadRequest, AgentStateUpdate, AgentStateResponse, CallDispositionRequest
from app.services.agent_state_service import AgentStateService
from app.services.disposition_service import DispositionService
from app.dependencies.feature_guard import require_feature

router = APIRouter(dependencies=[Depends(require_feature("OUTBOUND_CALLING"))])
logger = logging.getLogger(__name__)

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

    # 3. Query the single oldest uncalled lead
    filters = [
        Lead.organization_id == actor.organization_id,
        Lead.is_deleted == False,
        Lead.status == "New"
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

    # 4.5. Trigger Knowlarity Click-to-Call if telephony credentials are provided
    call_sid = f"outbound-{uuid.uuid4()}"
    if payload.knowlarity_api_key and payload.agent_phone_number:
        # Integrated calling is a paid feature — plans without it (e.g. Core CRM)
        # can use the dialer console with their own phone but not trigger calls here.
        from app.dependencies.feature_guard import tenant_has_feature
        if not await tenant_has_feature(db, actor, "OUTBOUND_CALLING"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Integrated outbound calling is not included in your plan. Please upgrade to enable click-to-call."
            )
        try:
            from app.services.knowlarity_service import trigger_knowlarity_call
            call_res = await trigger_knowlarity_call(
                api_key=payload.knowlarity_api_key,
                srn=payload.knowlarity_srn or "",
                agent_number=payload.agent_phone_number,
                customer_number=lead.phone
            )
            if call_res and isinstance(call_res, dict):
                success_data = call_res.get("success", {})
                if isinstance(success_data, dict):
                    call_sid = success_data.get("call_id") or call_res.get("call_id") or call_sid
                else:
                    call_sid = call_res.get("call_id") or call_sid
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
