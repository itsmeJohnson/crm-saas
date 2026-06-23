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

        # 2. Scoping Check: verify lead is assigned to current agent
        if lead.assigned_user_id != actor.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not authorized to submit a disposition for this lead."
            )

        previous_stage_id = lead.stage_id

        # 3. Processing logic by status
        if payload.status in {CallDispositionStatus.RNR, CallDispositionStatus.SWITCH_OFF, CallDispositionStatus.BUSY}:
            # System actions: increment count, delay availability, check drop threshold
            lead.call_attempts_count += 1
            lead.available_at = datetime.now(timezone.utc) + timedelta(hours=2)
            
            if lead.call_attempts_count > 4:
                # Auto-move to "Dropped" stage
                dropped_query = select(PipelineStage).filter(
                    PipelineStage.organization_id == lead.organization_id,
                    PipelineStage.name == "Dropped",
                    PipelineStage.is_deleted == False
                )
                dropped_res = await db.execute(dropped_query)
                dropped_stage = dropped_res.scalar()
                if not dropped_stage:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="The system 'Dropped' stage is missing for this organization."
                    )
                lead.stage_id = dropped_stage.id
                
        elif payload.status in {CallDispositionStatus.NOT_EXIST, CallDispositionStatus.OUT_OF_SERVICE}:
            # Invalid entry: immediate drop
            dropped_query = select(PipelineStage).filter(
                PipelineStage.organization_id == lead.organization_id,
                PipelineStage.name == "Dropped",
                PipelineStage.is_deleted == False
            )
            dropped_res = await db.execute(dropped_query)
            dropped_stage = dropped_res.scalar()
            if not dropped_stage:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="The system 'Dropped' stage is missing for this organization."
                )
            lead.stage_id = dropped_stage.id
            
        elif payload.status == CallDispositionStatus.PICKED:
            # Successful connection: advance to specified custom stage
            custom_stage_query = select(PipelineStage).filter(
                PipelineStage.id == payload.custom_pipeline_stage_id,
                PipelineStage.organization_id == lead.organization_id,
                PipelineStage.is_deleted == False
            )
            custom_res = await db.execute(custom_stage_query)
            custom_stage = custom_res.scalar()
            if not custom_stage:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="The specified custom pipeline stage does not exist in this organization."
                )
            lead.stage_id = custom_stage.id

        # Update lead status to match the disposition status
        lead.status = payload.status.value

        # 3.5. Update latest Call activity for this lead
        from app.models.activity import Activity
        activity_query = select(Activity).filter(
            Activity.lead_id == lead.id,
            Activity.activity_type == "Call",
            Activity.assigned_user_id == actor.id
        ).order_by(Activity.created_at.desc()).limit(1)
        
        act_res = await db.execute(activity_query)
        latest_call_activity = act_res.scalar()
        
        remarks_str = payload.remarks or ""
        desc_str = f"Disposition: {payload.status.value}\nRemarks: {remarks_str}"
        
        if latest_call_activity:
            latest_call_activity.status = "Completed"
            latest_call_activity.subject = f"Call: {payload.status.value}"
            latest_call_activity.description = desc_str
            db.add(latest_call_activity)
        else:
            # Fallback: create completed activity
            new_call_activity = Activity(
                organization_id=lead.organization_id,
                activity_type="Call",
                subject=f"Call: {payload.status.value}",
                description=desc_str,
                status="Completed",
                assigned_user_id=actor.id,
                lead_id=lead.id,
                created_by=actor.id,
                call_direction="OUTBOUND"
            )
            db.add(new_call_activity)

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
