import uuid
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lead import Lead
from app.models.pipeline import PipelineStage
from app.models.user import User
from app.schemas.dialer import CallDispositionRequest, CallDispositionStatus
from app.services.agent_state_service import AgentStateService
from app.services.audit_service import AuditService

class DispositionService:
    @staticmethod
    async def submit_disposition(
        db: AsyncSession,
        lead_id: uuid.UUID,
        payload: CallDispositionRequest,
        actor: User
    ) -> Lead:
        # 1. Scoping Check: find lead
        query = select(Lead).filter(
            Lead.id == lead_id,
            Lead.organization_id == actor.organization_id,
            Lead.is_deleted == False
        )
        res = await db.execute(query)
        lead = res.scalars().first()
        if not lead:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Lead not found."
            )

        # 2. Scoping Check: verify lead is assigned to current agent or allow admin/TL/unassigned takeover
        if lead.assigned_user_id != actor.id and actor.role not in ("SuperAdmin", "OrgAdmin", "TeamLeader"):
            if lead.assigned_user_id is None:
                lead.assigned_user_id = actor.id
                db.add(lead)
            else:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You are not authorized to submit a disposition for this lead."
                )
        elif lead.assigned_user_id is None:
            lead.assigned_user_id = actor.id
            db.add(lead)

        previous_stage_id = lead.stage_id
        status_val = payload.status.value

        # 3. Processing logic by status
        is_unanswered_retry = status_val in (
            "RNR — Ringing No Response", "RNR", "Busy", "Switched Off", "Switch Off",
            "Not Reachable", "Call Rejected"
        )
        is_invalid_number = status_val in (
            "Number Does Not Exist", "Not Exist", "Wrong Number", "Out of Service", "Spam / Junk"
        )
        is_followup = status_val in ("Follow-up Required", "Callback Scheduled", "Callback Requested")
        is_interested = status_val in ("Interested", "Picked — Connected", "Picked", "Answered", "Converted / Successful")
        is_lost = status_val in ("Not Interested", "Do Not Call")

        if is_unanswered_retry:
            lead.call_attempts_count += 1
            lead.available_at = datetime.now(timezone.utc) + timedelta(hours=2)
            if lead.call_attempts_count > 4:
                dropped_query = select(PipelineStage).filter(
                    PipelineStage.organization_id == lead.organization_id,
                    PipelineStage.name.ilike("%dropped%"),
                    PipelineStage.is_deleted == False
                ).limit(1)
                dropped_res = await db.execute(dropped_query)
                dropped_stage = dropped_res.scalar_one_or_none()
                if dropped_stage:
                    lead.stage_id = dropped_stage.id
        elif is_invalid_number:
            dropped_query = select(PipelineStage).filter(
                PipelineStage.organization_id == lead.organization_id,
                PipelineStage.name.ilike("%dropped%") | PipelineStage.name.ilike("%lost%"),
                PipelineStage.is_deleted == False
            ).limit(1)
            dropped_res = await db.execute(dropped_query)
            dropped_stage = dropped_res.scalar_one_or_none()
            if dropped_stage:
                lead.stage_id = dropped_stage.id
        elif status_val == "Not Interested":
            lost_query = select(PipelineStage).filter(
                PipelineStage.organization_id == lead.organization_id,
                PipelineStage.name.ilike("%not interested%") | PipelineStage.name.ilike("%lost%"),
                PipelineStage.is_deleted == False
            ).limit(1)
            lost_res = await db.execute(lost_query)
            lost_stage = lost_res.scalar_one_or_none()
            if lost_stage:
                lead.stage_id = lost_stage.id
        elif status_val == "Converted / Successful":
            won_query = select(PipelineStage).filter(
                PipelineStage.organization_id == lead.organization_id,
                PipelineStage.name.ilike("%won%") | PipelineStage.name.ilike("%converted%"),
                PipelineStage.is_deleted == False
            ).limit(1)
            won_res = await db.execute(won_query)
            won_stage = won_res.scalar_one_or_none()
            if won_stage:
                lead.stage_id = won_stage.id
        elif status_val == "Interested" and not payload.custom_pipeline_stage_id:
            int_query = select(PipelineStage).filter(
                PipelineStage.organization_id == lead.organization_id,
                PipelineStage.name.ilike("%interested%") | PipelineStage.name.ilike("%qualified%"),
                PipelineStage.is_deleted == False
            ).limit(1)
            int_res = await db.execute(int_query)
            int_stage = int_res.scalar_one_or_none()
            if int_stage:
                lead.stage_id = int_stage.id

        if payload.custom_pipeline_stage_id:
            custom_stage_query = select(PipelineStage).filter(
                PipelineStage.id == payload.custom_pipeline_stage_id,
                PipelineStage.organization_id == lead.organization_id,
                PipelineStage.is_deleted == False
            )
            custom_res = await db.execute(custom_stage_query)
            custom_stage = custom_res.scalar_one_or_none()
            if not custom_stage:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="The specified custom pipeline stage does not exist in this organization."
                )
            lead.stage_id = custom_stage.id

        # Update lead status
        lead.status = status_val

        # Handle scheduled follow-up
        follow_up_dt = None
        follow_up_display = ""
        if payload.follow_up_date and payload.follow_up_time:
            follow_up_display = f"{payload.follow_up_date} at {payload.follow_up_time}"
            try:
                dt_raw = f"{str(payload.follow_up_date).strip()}T{str(payload.follow_up_time).strip()}"
                follow_up_dt = datetime.fromisoformat(dt_raw).replace(tzinfo=timezone.utc)
                lead.available_at = follow_up_dt
                
                # Create LeadReminder for notification & callback engine
                from app.models.lead_reminder import LeadReminder
                reminder = LeadReminder(
                    organization_id=lead.organization_id,
                    lead_id=lead.id,
                    user_id=actor.id,
                    remind_at=follow_up_dt,
                    note=f"Scheduled Callback ({status_val}): {payload.remarks}",
                    is_sent=False,
                    created_by=actor.id
                )
                db.add(reminder)
            except Exception as dt_err:
                pass

        # 3.5. Update latest Call activity for this lead (or find by call_sid for idempotency)
        from app.models.activity import Activity
        latest_call_activity = None
        if payload.call_sid:
            act_by_sid = await db.execute(
                select(Activity).filter(
                    Activity.call_sid == str(payload.call_sid),
                    Activity.organization_id == actor.organization_id
                )
            )
            latest_call_activity = act_by_sid.scalars().first()

        if not latest_call_activity:
            activity_query = select(Activity).filter(
                Activity.lead_id == lead.id,
                Activity.activity_type == "Call",
                Activity.organization_id == actor.organization_id
            ).order_by(Activity.created_at.desc()).limit(1)
            act_res = await db.execute(activity_query)
            latest_call_activity = act_res.scalar_one_or_none()

        mins = (payload.call_duration or 0) // 60
        secs = (payload.call_duration or 0) % 60
        dur_str = f"{mins:02d}:{secs:02d}"
        follow_up_line = f"\nFollow-up: {follow_up_display}" if follow_up_display else ""
        desc_str = f"Outcome: {status_val}\nDuration: {dur_str}\nRemarks: {payload.remarks}{follow_up_line}"

        if latest_call_activity:
            latest_call_activity.status = "Completed"
            latest_call_activity.subject = f"{payload.call_direction or latest_call_activity.call_direction or 'Outbound'} Call — {status_val}"
            latest_call_activity.description = desc_str
            latest_call_activity.call_disposition = status_val
            if payload.call_duration is not None and payload.call_duration > 0:
                latest_call_activity.call_duration = payload.call_duration
            if follow_up_dt:
                latest_call_activity.due_date = follow_up_dt
            db.add(latest_call_activity)
        else:
            # Fallback: create completed activity
            new_call_activity = Activity(
                organization_id=lead.organization_id,
                activity_type="Call",
                subject=f"{payload.call_direction or 'Outbound'} Call — {status_val}",
                description=desc_str,
                status="Completed",
                assigned_user_id=actor.id,
                lead_id=lead.id,
                created_by=actor.id,
                call_direction=payload.call_direction or "OUTBOUND",
                call_disposition=status_val,
                call_duration=payload.call_duration or 0,
                call_sid=str(payload.call_sid) if payload.call_sid else None,
                due_date=follow_up_dt
            )
            db.add(new_call_activity)

        # 3.6. Fire call_disposition workflow rules against the lead
        from app.services.workflow_service import WorkflowService
        await WorkflowService(db).run("call_disposition", lead, actor)

        # 3.8. Automated Omnichannel Follow-Up (WhatsApp Rich Dispatch with SMS carrier fallback)
        if getattr(payload, "dispatch_omnichannel_followup", False) and lead.phone:
            try:
                import logging
                _log = logging.getLogger(__name__)
                from app.services.whatsapp_service import WhatsAppService
                from app.services.sms_service import SmsService
                wa_service = WhatsAppService(db)
                customer_name = f"{lead.first_name or ''} {lead.last_name}".strip()
                followup_body = (
                    payload.followup_custom_note
                    or f"Hi {customer_name}, thank you for your time today. Let us know if you need any further assistance!"
                )
                wa_dispatched = False
                try:
                    await wa_service.send_text(actor, {
                        "to": lead.phone,
                        "body": followup_body,
                        "lead_id": str(lead.id)
                    })
                    wa_dispatched = True
                except Exception as wa_err:
                    _log.info("WhatsApp delivery check failed (%s). Triggering intelligent SMS carrier fallback.", wa_err)

                if not wa_dispatched:
                    sms_service = SmsService(db)
                    await sms_service.send_sms(actor, {
                        "to": lead.phone,
                        "body": followup_body[:160],
                        "lead_id": str(lead.id)
                    })
            except Exception as omni_err:
                import logging
                logging.getLogger(__name__).warning("Omnichannel follow-up execution error: %s", omni_err)

        # 4. Transition agent's Redis state to IDLE
        state_service = AgentStateService()
        await state_service.set_agent_state(actor.organization_id, actor.id, "IDLE")

        # 5. Generate LEAD_DISPOSITION_SUBMITTED audit log
        audit_service = AuditService(db)
        await audit_service.log_event(
            organization_id=lead.organization_id,
            actor_user_id=actor.id,
            action="LEAD_DISPOSITION_SUBMITTED",
            resource_type="Lead",
            resource_id=str(lead.id),
            action_metadata={
                "status": payload.status.value,
                "remarks": payload.remarks,
                "previous_stage_id": str(previous_stage_id) if previous_stage_id else None,
                "new_stage_id": str(lead.stage_id),
                "call_attempts_count": lead.call_attempts_count,
                "available_at": lead.available_at.isoformat() if lead.available_at else None
            }
        )

        db.add(lead)
        await db.commit()

        # Invalidate dashboard metrics cache immediately
        from app.services.dashboard_service import DashboardService
        await DashboardService.invalidate_cache(lead.organization_id)

        # Re-fetch lead eagerly loading the updated stage relationship
        from sqlalchemy.orm import selectinload
        refetched_query = select(Lead).options(selectinload(Lead.stage)).filter(Lead.id == lead.id)
        refetched_res = await db.execute(refetched_query)
        lead = refetched_res.scalar_one()

        return lead
