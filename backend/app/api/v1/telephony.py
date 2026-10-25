import logging
import re
import uuid
from typing import Dict, Any, Optional
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, WebSocket, WebSocketDisconnect, Request, Response
from sqlalchemy import select, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.lead import Lead
from app.models.activity import Activity
from app.models.user import User
from app.models.telephony_settings import TelephonySettings
from app.models.pipeline import PipelineStage
from app.schemas.telephony import CallRecordingWebhook, InboundCallWebhook

router = APIRouter()
logger = logging.getLogger(__name__)

# Connection Manager for WebSockets
class ConnectionManager:
    def __init__(self):
        # Maps user_id (str) to WebSocket connection
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, user_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[user_id] = websocket
        logger.info(f"WebSocket connected for user: {user_id}")

    def disconnect(self, user_id: str):
        if user_id in self.active_connections:
            del self.active_connections[user_id]
            logger.info(f"WebSocket disconnected for user: {user_id}")

    async def send_personal_message(self, message: dict, user_id: str):
        if user_id in self.active_connections:
            try:
                await self.active_connections[user_id].send_json(message)
            except Exception as e:
                logger.error(f"Failed to send WS message to {user_id}: {str(e)}")
                self.disconnect(user_id)

    async def broadcast_to_organization(self, message: dict, org_id: uuid.UUID, db: AsyncSession):
        query = select(User.id).filter(User.organization_id == org_id, User.is_active == True)
        res = await db.execute(query)
        user_ids = [str(uid) for uid in res.scalars().all()]
        
        for uid in user_ids:
            if uid in self.active_connections:
                await self.send_personal_message(message, uid)

ws_manager = ConnectionManager()

@router.websocket("/ws/{user_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    user_id: str,
    db: AsyncSession = Depends(get_db)
):
    try:
        user_uuid = uuid.UUID(user_id)
    except ValueError:
        await websocket.accept()
        await websocket.close(code=1008, reason="Invalid User ID format")
        return

    res = await db.execute(select(User).where(User.id == user_uuid, User.is_active == True, User.is_deleted == False))
    user = res.scalar_one_or_none()
    if not user:
        await websocket.accept()
        await websocket.close(code=1008, reason="User not active")
        return

    from app.dependencies.feature_guard import tenant_has_feature
    if not await tenant_has_feature(db, user, "INBOUND_CALLING"):
        await websocket.accept()
        await websocket.close(code=1008, reason="Inbound calling feature not available")
        return

    await ws_manager.connect(user_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(user_id)
    except Exception as e:
        logger.error(f"WebSocket error for user {user_id}: {str(e)}")
        ws_manager.disconnect(user_id)


async def _extract_webhook_data(request: Request) -> dict:
    """Extract parameters from query string, JSON body, or form data."""
    data = {}
    if request.query_params:
        data.update(dict(request.query_params))

    if request.method.upper() == "POST":
        content_type = request.headers.get("content-type", "").lower()
        if "application/json" in content_type:
            try:
                json_data = await request.json()
                if isinstance(json_data, dict):
                    data.update(json_data)
            except Exception:
                pass
        else:
            try:
                form_data = await request.form()
                data.update(dict(form_data))
            except Exception:
                try:
                    json_data = await request.json()
                    if isinstance(json_data, dict):
                        data.update(json_data)
                except Exception:
                    pass
    return data


async def _handle_incoming_call_event(
    *,
    db: AsyncSession,
    caller_phone: str,
    destination_number: str,
    call_sid: str,
    agent_phone: Optional[str] = None,
    call_status: str = "Ringing",
    recording_url: Optional[str] = None,
    duration: int = 0,
    raw_data: Optional[dict] = None,
) -> dict:
    """Handle an inbound call from customer to virtual number / DID."""
    digits = re.sub(r"\D", "", caller_phone or "")
    last_10 = digits[-10:] if len(digits) >= 10 else digits

    if not last_10:
        return {"status": "ignored", "reason": "No valid caller phone"}

    # 0. Check if caller_phone belongs to organization caller ID or agent extension
    t_settings_res = await db.execute(select(TelephonySettings).filter(TelephonySettings.is_active == True))
    all_tele = t_settings_res.scalars().all()
    org_phone_numbers = set()
    for ts in all_tele:
        if ts.default_caller_id:
            org_phone_numbers.add(re.sub(r"\D", "", str(ts.default_caller_id))[-10:])
        if ts.user_uuid:
            org_phone_numbers.add(str(ts.user_uuid).strip().lower())

    if last_10 in org_phone_numbers or str(caller_phone).lower() in org_phone_numbers:
        logger.info(f"Ignored inbound call event: caller {caller_phone} is organization virtual number or agent.")
        return {"status": "ignored", "reason": "Caller is organization caller ID or agent"}

    # 1. Search for existing lead matching the phone
    query = select(Lead).filter(
        Lead.is_deleted == False,
        Lead.phone.like(f"%{last_10}%")
    )
    res = await db.execute(query)
    leads = res.scalars().all()
    lead = leads[0] if leads else None

    # 2. If no lead found, identify tenant organization and auto-create prospective lead
    if not lead:
        dest_digits = re.sub(r"\D", "", destination_number or "")
        dest_last_10 = dest_digits[-10:] if len(dest_digits) >= 10 else dest_digits

        matched_org_id = None
        if dest_last_10:
            org_res = await db.execute(
                select(TelephonySettings.organization_id).where(
                    TelephonySettings.default_caller_id.like(f"%{dest_last_10}%")
                )
            )
            matched_org_id = org_res.scalars().first()

        if not matched_org_id:
            # Fallback to the first active tenant organization
            first_org_res = await db.execute(select(User.organization_id).filter(User.is_active == True).limit(1))
            matched_org_id = first_org_res.scalars().first()

        if matched_org_id:
            # Query default stage & admin user
            stage_res = await db.execute(
                select(PipelineStage.id).where(PipelineStage.organization_id == matched_org_id).order_by(PipelineStage.order_position.asc()).limit(1)
            )
            stage_id = stage_res.scalar_one_or_none()

            admin_user_res = await db.execute(
                select(User.id).where(User.organization_id == matched_org_id, User.is_active == True).limit(1)
            )
            admin_user_id = admin_user_res.scalar_one_or_none()

            if stage_id and admin_user_id:
                lead = Lead(
                    organization_id=matched_org_id,
                    first_name="Inbound",
                    last_name=f"Caller ({last_10})",
                    title=f"Inbound Call from {caller_phone}",
                    phone=caller_phone,
                    source="Inbound Call",
                    status="New",
                    stage_id=stage_id,
                    created_by=admin_user_id,
                )
                db.add(lead)
                await db.flush()
                logger.info(f"Auto-created prospective Lead id={lead.id} for inbound caller {caller_phone}")

    if not lead:
        logger.info(f"Inbound call: no lead found or created for caller={caller_phone}")
        return {"status": "unmatched", "caller": caller_phone}

    org_id = lead.organization_id
    assigned_user_id = lead.assigned_user_id
    created_by_user_id = lead.created_by

    raw = raw_data or {}
    hangup_reason = raw.get("hangup_reason")
    report_type = str(raw.get("type") or "").lower()
    norm_status = str(call_status).lower()

    is_call_ended = (
        bool(recording_url)
        or duration > 0
        or report_type == "cdr"
        or bool(hangup_reason)
        or norm_status in ("completed", "ended", "missed", "cancel", "cancelled", "hangup", "recv_bye", "sent_bye", "failed", "busy", "noanswer")
    )

    # 3. Check if an activity already exists for this call_sid
    act_query = select(Activity).filter(Activity.call_sid == call_sid)
    act_res = await db.execute(act_query)
    activity = act_res.scalars().first()

    if not activity:
        final_status = "Completed" if (duration > 0 or recording_url or norm_status == "answered") else ("Missed" if is_call_ended else "Planned")
        activity = Activity(
            organization_id=org_id,
            activity_type="Call",
            subject=f"Inbound Call from {lead.first_name or ''} {lead.last_name or ''}".strip(),
            description=f"Inbound call via virtual number {destination_number}. Status: {call_status}",
            status=final_status,
            assigned_user_id=assigned_user_id,
            lead_id=lead.id,
            created_by=assigned_user_id or created_by_user_id,
            call_sid=call_sid,
            call_direction="INBOUND",
            recording_url=recording_url,
            call_duration=duration,
        )
        db.add(activity)

        workflow_actor_id = assigned_user_id or created_by_user_id
        if workflow_actor_id:
            actor_res = await db.execute(select(User).filter(User.id == workflow_actor_id))
            workflow_actor = actor_res.scalars().first()
            if workflow_actor:
                from app.services.workflow_service import WorkflowService
                await WorkflowService(db).run("call_logged", lead, workflow_actor)
    else:
        if recording_url:
            activity.recording_url = recording_url
        if duration:
            activity.call_duration = duration
        if is_call_ended:
            activity.status = "Completed" if (duration > 0 or recording_url or norm_status == "answered") else "Missed"
        db.add(activity)

    await db.commit()
    await db.refresh(activity)

    # If call has concluded or caller disconnected, broadcast inbound_call_ended to dismiss ringing popup
    if is_call_ended:
        disconnect_payload = {
            "event": "inbound_call_ended",
            "call_sid": call_sid,
            "lead_id": str(lead.id),
            "phone": lead.phone,
            "status": activity.status,
            "reason": hangup_reason or call_status,
        }
        if assigned_user_id:
            await ws_manager.send_personal_message(disconnect_payload, str(assigned_user_id))
        await ws_manager.broadcast_to_organization(disconnect_payload, org_id, db)

        return {
            "status": "ended",
            "lead_id": str(lead.id),
            "activity_id": str(activity.id),
            "event": "inbound_call_ended"
        }

    # 4. Intelligent Inbound Call Routing:
    # Query lead: if assigned agent is Punched In and Available (IDLE), route directly to them.
    # If assigned agent is offline/busy, or if it is a new lead, route to "Incoming Call Attend Team" queue.
    from datetime import datetime, timezone
    from app.models.attendance import AttendanceRecord
    from app.services.agent_state_service import AgentStateService

    target_user_ids: list[str] = []
    routing_reason: str = "unassigned"

    # Step A: If assigned_user_id exists, check if assigned agent is Punched In and Available
    if assigned_user_id:
        today = datetime.now(timezone.utc).date()
        att_query = select(AttendanceRecord).filter(
            AttendanceRecord.organization_id == org_id,
            AttendanceRecord.user_id == assigned_user_id,
            AttendanceRecord.work_date == today,
            AttendanceRecord.clock_in_at.is_not(None),
            AttendanceRecord.clock_out_at.is_(None),
            AttendanceRecord.status.in_(["present", "late", "half_day"])
        )
        att_res = await db.execute(att_query)
        att_rec = att_res.scalars().first()

        if att_rec:
            agent_state_svc = AgentStateService()
            try:
                st = await agent_state_svc.get_agent_state(org_id, assigned_user_id)
                if st.get("state") == "IDLE":
                    target_user_ids = [str(assigned_user_id)]
                    routing_reason = "assigned_agent"
            except Exception:
                target_user_ids = [str(assigned_user_id)]
                routing_reason = "assigned_agent"

    # Step B: If assigned agent is offline/busy or unassigned, route to "Incoming Call Attend Team" queue
    if not target_user_ids:
        from app.models.team import Team, TeamMember
        team_res = await db.execute(
            select(Team.id).where(
                Team.organization_id == org_id,
                Team.status == "active",
                or_(
                    Team.name.ilike("%incoming%"),
                    Team.name.ilike("%attend%"),
                    Team.name.ilike("%inbound%"),
                )
            )
        )
        attend_team_ids = list(team_res.scalars().all())

        candidate_ids = []
        if attend_team_ids:
            mem_res = await db.execute(
                select(TeamMember.user_id).where(
                    TeamMember.organization_id == org_id,
                    TeamMember.team_id.in_(attend_team_ids)
                )
            )
            candidate_ids = list(mem_res.scalars().all())

        if not candidate_ids:
            # Fall back to active floor agents
            emp_res = await db.execute(
                select(User.id).where(
                    User.organization_id == org_id,
                    User.role.in_(["Employee", "TeamLeader"]),
                    User.is_active == True,
                    User.is_deleted == False
                )
            )
            candidate_ids = list(emp_res.scalars().all())

        # Filter candidate agents who are currently Punched In & Available
        today = datetime.now(timezone.utc).date()
        punched_in_res = await db.execute(
            select(AttendanceRecord.user_id).where(
                AttendanceRecord.organization_id == org_id,
                AttendanceRecord.user_id.in_(candidate_ids),
                AttendanceRecord.work_date == today,
                AttendanceRecord.clock_in_at.is_not(None),
                AttendanceRecord.clock_out_at.is_(None),
                AttendanceRecord.status.in_(["present", "late", "half_day"])
            )
        )
        punched_in_uids = set(punched_in_res.scalars().all())

        agent_state_svc = AgentStateService()
        available_attend_agents = []
        for uid in punched_in_uids:
            try:
                agent_st = await agent_state_svc.get_agent_state(org_id, uid)
                if agent_st.get("state") == "IDLE":
                    available_attend_agents.append(str(uid))
            except Exception:
                available_attend_agents.append(str(uid))

        target_user_ids = available_attend_agents
        routing_reason = "attend_team_queue" if attend_team_ids else "available_agents_queue"

    alert_payload = {
        "event": "inbound_call",
        "call_sid": call_sid,
        "lead_id": str(lead.id),
        "lead_name": f"{lead.first_name or ''} {lead.last_name or ''}".strip() or "Unknown Lead",
        "company_name": lead.company_name or "",
        "phone": lead.phone,
        "activity_id": str(activity.id),
        "status": call_status,
        "virtual_number": destination_number,
        "routing_reason": routing_reason,
        "assigned_user_id": str(assigned_user_id) if assigned_user_id else None,
    }

    if target_user_ids:
        for uid in target_user_ids:
            await ws_manager.send_personal_message(alert_payload, uid)
    else:
        # Fallback to org broadcast if no agents are actively IDLE
        await ws_manager.broadcast_to_organization(alert_payload, org_id, db)

    return {
        "status": "matched",
        "lead_id": str(lead.id),
        "activity_id": str(activity.id),
        "event": "inbound_call",
        "routing_reason": routing_reason,
        "routed_targets_count": len(target_user_ids)
    }


async def _handle_outbound_call_report(
    *,
    db: AsyncSession,
    call_sid: str,
    recording_url: Optional[str] = None,
    duration: int = 0,
    status_label: str = "Completed"
) -> dict:
    """Update completed outbound call activity matching call_sid."""
    query = select(Activity).filter(Activity.call_sid == str(call_sid))
    res = await db.execute(query)
    activity = res.scalars().first()

    if activity:
        if recording_url:
            activity.recording_url = recording_url
        activity.call_duration = duration
        activity.status = "Completed"
        db.add(activity)
        await db.commit()
        logger.info(f"Updated call recording for activity_id={activity.id}, call_sid={call_sid}")
        return {"status": "updated", "activity_id": str(activity.id)}

    logger.warning(f"No existing activity found matching call_sid={call_sid}")
    return {"status": "ignored", "reason": "No matching call_sid"}


async def _process_unified_telephony_webhook(request: Request, db: AsyncSession) -> dict:
    """Universal webhook processor for Callerdesk, Exotel, Knowlarity, MyOperator & custom VoIP."""
    data = await _extract_webhook_data(request)
    logger.info("Telephony webhook received [%s %s]: %s", request.method, request.url.path, data)

    # 1. Normalize field aliases across providers (TeleCMI, Callerdesk, Exotel, generic)
    call_sid = (
        data.get("CallSid")
        or data.get("call_sid")
        or data.get("cmiuuid")
        or data.get("conversation_uuid")
        or data.get("request_id")
        or data.get("Uniqueid")
        or data.get("sid_id")
        or data.get("campid")
        or data.get("call_id")
        or f"call-{uuid.uuid4()}"
    )
    direction = str(data.get("Direction") or data.get("direction") or "").upper()
    source_number = (
        data.get("SourceNumber")
        or data.get("from_number")
        or data.get("caller")
        or data.get("From")
        or data.get("from")
        or data.get("msisdn")
        or data.get("caller_num")
        or ""
    )
    dest_number = (
        data.get("virtual_number")
        or data.get("DestinationNumber")
        or data.get("to_number")
        or data.get("called")
        or data.get("To")
        or data.get("to")
        or data.get("deskphone")
        or data.get("did_no")
        or ""
    )
    agent_info = data.get("agent") or data.get("user")
    agent_number = (
        data.get("DialWhomNumber")
        or data.get("agent_number")
        or data.get("member_num")
        or (agent_info.get("agent_id") if isinstance(agent_info, dict) else str(agent_info or ""))
        or ""
    )
    raw_rec = (
        data.get("CallRecordingUrl")
        or data.get("recording_url")
        or data.get("recording")
        or data.get("RecordingUrl")
        or data.get("file")
        or data.get("filename")
        or ""
    )
    if raw_rec and not str(raw_rec).startswith("http"):
        recording_url = f"https://rest.telecmi.com/v2/recordings/{raw_rec}"
    else:
        recording_url = str(raw_rec) if raw_rec else ""

    raw_duration = (
        data.get("CallDuration")
        or data.get("TalkDuration")
        or data.get("answeredsec")
        or data.get("billsec")
        or data.get("duration")
        or "0"
    )
    try:
        duration = int(float(raw_duration))
    except (ValueError, TypeError):
        duration = 0

    call_status = str(data.get("Status") or data.get("status") or data.get("event") or data.get("callstatus") or "ANSWER")

    # 2. Determine Call Flow: Inbound vs Outbound
    extra = data.get("extra_params") or data.get("custom_params") or {}
    if isinstance(extra, str):
        try:
            import json
            extra = json.loads(extra)
        except Exception:
            extra = {}
    extra_dir = str(extra.get("direction") or extra.get("call_direction") or "").upper()
    raw_type = str(data.get("type") or data.get("call_type") or data.get("event") or "").upper()

    is_explicit_outbound = (
        direction in ("OUTBOUND", "OUT", "C2C", "CLICK2CALL", "DIALER")
        or raw_type in ("OUTBOUND", "C2C", "CLICK2CALL", "DIALER", "OUT")
        or extra_dir in ("OUTBOUND", "OUT")
        or str(extra.get("call_type") or "").lower() == "c2c"
        or bool(data.get("c2c"))
    )

    # Check if source_number or destination_number is our organization's virtual number or agent
    t_res = await db.execute(select(TelephonySettings).filter(TelephonySettings.is_active == True))
    org_numbers = set()
    for ts in t_res.scalars().all():
        if ts.default_caller_id:
            org_numbers.add(re.sub(r"\D", "", str(ts.default_caller_id))[-10:])
        if ts.user_uuid:
            org_numbers.add(str(ts.user_uuid).strip().lower())

    src_digits = re.sub(r"\D", "", str(source_number))[-10:] if source_number else ""
    dst_digits = re.sub(r"\D", "", str(dest_number))[-10:] if dest_number else ""

    # If call originates FROM our virtual number or agent extension, it is ALWAYS an outbound call!
    if (src_digits and src_digits in org_numbers) or str(source_number).lower() in org_numbers:
        is_explicit_outbound = True

    is_matching_outbound = False
    if call_sid:
        act_res = await db.execute(
            select(Activity.id).filter(
                Activity.call_sid == str(call_sid),
                Activity.call_direction == "OUTBOUND"
            ).limit(1)
        )
        if act_res.scalars().first():
            is_matching_outbound = True

    # If call_sid wasn't found directly, check if an outbound call activity was initiated to/from this number in last 10 mins
    if not is_matching_outbound and not is_explicit_outbound:
        recent_cutoff = datetime.now(timezone.utc) - timedelta(minutes=10)

        recent_act_query = select(Activity).filter(
            Activity.call_direction == "OUTBOUND",
            Activity.created_at >= recent_cutoff,
        ).order_by(Activity.created_at.desc())
        recent_res = await db.execute(recent_act_query)
        for act in recent_res.scalars().all():
            if act.lead_id:
                lead_q = await db.execute(select(Lead.phone).filter(Lead.id == act.lead_id))
                lead_phone = lead_q.scalar_one_or_none()
                if lead_phone:
                    lead_digits = re.sub(r"\D", "", lead_phone)[-10:]
                    if (src_digits and lead_digits == src_digits) or (dst_digits and lead_digits == dst_digits):
                        is_matching_outbound = True
                        if act.call_sid != str(call_sid):
                            act.call_sid = str(call_sid)
                            db.add(act)
                            await db.commit()
                        break

    if is_explicit_outbound or is_matching_outbound:
        is_inbound = False
    elif direction in ("IVR", "INBOUND"):
        is_inbound = True
    elif source_number and not direction and not recording_url:
        if (src_digits and src_digits in org_numbers) or str(source_number).lower() in org_numbers:
            is_inbound = False
        else:
            is_inbound = True
    else:
        is_inbound = False

    if is_inbound:
        # Inbound Call Flow (Live ringing notification or inbound call report)
        return await _handle_incoming_call_event(
            db=db,
            caller_phone=str(source_number),
            destination_number=str(dest_number),
            call_sid=str(call_sid),
            agent_phone=str(agent_number),
            call_status=call_status,
            recording_url=recording_url or None,
            duration=duration,
            raw_data=data,
        )
    else:
        # Outbound Call Report / Recording Update Flow
        return await _handle_outbound_call_report(
            db=db,
            call_sid=str(call_sid),
            recording_url=recording_url or None,
            duration=duration,
            status_label=call_status,
        )


@router.api_route("/webhook", methods=["GET", "POST"], status_code=status.HTTP_200_OK)
async def telephony_general_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """General telephony webhook endpoint supporting both GET & POST.
    Handles TeleCMI, Callerdesk, Exotel, Knowlarity, MyOperator Call Reports & Inbound events.
    """
    return await _process_unified_telephony_webhook(request, db)


@router.api_route("/webhook/telecmi", methods=["GET", "POST"], status_code=status.HTTP_200_OK)
async def telephony_telecmi_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Dedicated TeleCMI webhook endpoint for CDR and Notify events."""
    return await _process_unified_telephony_webhook(request, db)


@router.api_route("/callerdesk/webhook", methods=["GET", "POST"], status_code=status.HTTP_200_OK)
async def callerdesk_specific_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Dedicated Callerdesk webhook endpoint (https://api.callerdesk.io/)
    for Live Call and Call Report integrations.
    """
    return await _process_unified_telephony_webhook(request, db)


@router.api_route("/inbound", methods=["GET", "POST"], status_code=status.HTTP_200_OK)
async def inbound_call_trigger(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Inbound call trigger endpoint supporting both GET & POST payloads."""
    return await _process_unified_telephony_webhook(request, db)
