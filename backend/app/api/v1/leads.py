import uuid
import io
from datetime import datetime
from typing import Annotated, List
from fastapi import APIRouter, Depends, Query, status, UploadFile, File, Response, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User
from app.schemas.lead import (
    LeadResponse, LeadCreate, LeadUpdate, LeadBulkUpdateRequest, LeadBulkUpdateResponse,
    LeadTimelineEvent, LeadAuditEvent, LeadAttachmentResponse,
    LeadConvertRequest, LeadConvertResponse, LeadReminderCreate, LeadReminderResponse,
    FollowUpCreate,
)
from app.schemas.saved_filter import SavedFilterCreate, SavedFilterUpdate, SavedFilterResponse
from app.schemas.reports import LeadReportResponse
from app.schemas.escalation import EscalationConfigUpdate, EscalationConfigResponse
from app.schemas.workflow import WorkflowRuleCreate, WorkflowRuleUpdate, WorkflowRuleResponse
from app.services.saved_filter_service import SavedFilterService
from app.services.workflow_service import WorkflowService
from app.services.escalation_service import EscalationService
from app.schemas.lead_import import GoogleSheetsPreviewRequest, ImportPreviewResponse, LeadImportProcessRequest, LeadImportResponse
from app.schemas.assignment_config import AssignmentConfigUpdate, AssignmentConfigResponse
from app.schemas.lead_assign import LeadBulkAssignRequest, LeadBulkAssignResponse
from app.schemas.lead_transfer import LeadTransferRequest, LeadTransferResponse
from app.services.lead_service import LeadService
from app.services.lead_import_service import LeadImportService
from app.services.assignment_service import AssignmentService
from app.middleware.permissions import require_active_user, require_role, require_tl_or_above

router = APIRouter()

# --- CRM Leads Core CRUD ---

@router.post("/", response_model=LeadResponse, status_code=status.HTTP_201_CREATED)
async def create_lead(
    lead_in: LeadCreate,
    actor: Annotated[User, Depends(require_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Create a new lead opportunity."""
    lead_service = LeadService(db)
    lead = await lead_service.create_lead(actor, lead_in.model_dump())
    
    # Auto assign if lead is created manually
    assign_service = AssignmentService(db)
    await assign_service.assign_lead(lead)
    
    return lead

@router.get("/", response_model=List[LeadResponse])
async def list_leads(
    actor: Annotated[User, Depends(require_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    search: str | None = Query(None),
    status: str | None = Query(None),
    assigned_user_id: uuid.UUID | None = Query(None),
    name: str | None = Query(None),
    city: str | None = Query(None),
    source: str | None = Query(None),
    stage_id: uuid.UUID | None = Query(None),
    priority: str | None = Query(None),
    min_value: float | None = Query(None),
    max_value: float | None = Query(None),
    created_from: datetime | None = Query(None),
    created_to: datetime | None = Query(None),
    include_archived: bool = Query(False),
    updated_after: datetime | None = Query(None, description="Delta-sync cursor: only leads changed after this timestamp (offline mobile)."),
    custom_fields: str | None = Query(None, description="JSON object of {custom_field_key: value} filters."),
):
    """List paginated, searchable leads scoped to the tenant organization."""
    custom_filters: dict | None = None
    if custom_fields:
        import json
        try:
            parsed = json.loads(custom_fields)
            if isinstance(parsed, dict):
                custom_filters = {str(k): v for k, v in parsed.items() if v not in (None, "")}
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="custom_fields must be a valid JSON object")

    lead_service = LeadService(db)
    records, _ = await lead_service.paginate_leads(
        actor, skip, limit, search, status, assigned_user_id, name, city,
        source=source, stage_id=stage_id, priority=priority, min_value=min_value,
        max_value=max_value, created_from=created_from, created_to=created_to,
        include_archived=include_archived, updated_after=updated_after,
        custom_filters=custom_filters,
    )
    return list(records)

@router.get("/export")
async def export_leads(
    actor: Annotated[User, Depends(require_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    format: str = Query("csv", pattern="^(csv|xlsx)$"),
    search: str | None = Query(None),
    status: str | None = Query(None),
    assigned_user_id: uuid.UUID | None = Query(None),
    name: str | None = Query(None),
    city: str | None = Query(None),
    source: str | None = Query(None),
    stage_id: uuid.UUID | None = Query(None),
    priority: str | None = Query(None),
    min_value: float | None = Query(None),
    max_value: float | None = Query(None),
    created_from: datetime | None = Query(None),
    created_to: datetime | None = Query(None),
    include_archived: bool = Query(False),
):
    """Export the caller's visible leads (matching the same filters as listing) as CSV or Excel."""
    lead_service = LeadService(db)
    filters = {
        "search_query": search, "status": status, "assigned_user_id": assigned_user_id,
        "name": name, "city": city, "source": source, "stage_id": stage_id,
        "priority": priority, "min_value": min_value, "max_value": max_value,
        "created_from": created_from, "created_to": created_to, "include_archived": include_archived,
    }
    leads = await lead_service.export_leads(actor, filters)

    # Append the org's exportable custom-field columns so each tenant's export
    # reflects their own schema.
    from app.services.custom_field_service import CustomFieldService
    all_defs = await CustomFieldService(db).list_definitions(actor, "lead")
    custom_defs = [d for d in all_defs if d.is_active and d.exportable]

    if format == "xlsx":
        content = LeadService.build_export_xlsx(leads, custom_defs)
        return StreamingResponse(
            io.BytesIO(content),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=leads_export.xlsx"},
        )
    csv_text = LeadService.build_export_csv(leads, custom_defs)
    return StreamingResponse(
        io.StringIO(csv_text),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=leads_export.csv"},
    )

@router.get("/duplicates", response_model=List[LeadResponse])
async def find_duplicate_leads(
    actor: Annotated[User, Depends(require_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    email: str | None = Query(None),
    phone: str | None = Query(None),
    exclude_lead_id: uuid.UUID | None = Query(None),
):
    """Find existing leads that share the given email or phone within the organization."""
    lead_service = LeadService(db)
    return list(await lead_service.find_duplicates(actor, email=email, phone=phone, exclude_lead_id=exclude_lead_id))

@router.post("/bulk-update", response_model=LeadBulkUpdateResponse)
async def bulk_update_leads(
    req: LeadBulkUpdateRequest,
    actor: Annotated[User, Depends(require_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Apply the same field changes to multiple scoped leads at once."""
    lead_service = LeadService(db)
    fields = req.fields.model_dump(exclude_unset=True, exclude_none=True)
    result = await lead_service.bulk_update(actor, req.lead_ids, fields)
    return LeadBulkUpdateResponse(**result)

# --- Lead Reports ---

@router.get("/reports", response_model=LeadReportResponse)
async def get_lead_reports(
    actor: Annotated[User, Depends(require_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
):
    """Tenant-scoped lead analytics: totals plus breakdowns by source, status, priority, stage, and owner."""
    lead_service = LeadService(db)
    return await lead_service.get_lead_report(actor, date_from=date_from, date_to=date_to)

# --- Escalation config (OrgAdmin / Manager) ---

@router.get("/escalation/config", response_model=EscalationConfigResponse)
async def get_escalation_config(
    actor: Annotated[User, Depends(require_role(["OrgAdmin", "Manager"]))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Retrieve the org's idle-lead escalation configuration."""
    return await EscalationService(db).get_or_create_config(actor.organization_id)

@router.patch("/escalation/config", response_model=EscalationConfigResponse)
async def update_escalation_config(
    req: EscalationConfigUpdate,
    actor: Annotated[User, Depends(require_role(["OrgAdmin", "Manager"]))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Enable/disable escalation and set the idle-day threshold."""
    return await EscalationService(db).update_config(actor.organization_id, req.model_dump(exclude_unset=True))

# --- Workflow automation rules (OrgAdmin / Manager) ---

@router.get("/workflows", response_model=List[WorkflowRuleResponse])
async def list_workflow_rules(
    actor: Annotated[User, Depends(require_role(["OrgAdmin", "Manager"]))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """List lead-automation rules for the organization."""
    return list(await WorkflowService(db).list_rules(actor))

@router.post("/workflows", response_model=WorkflowRuleResponse, status_code=status.HTTP_201_CREATED)
async def create_workflow_rule(
    req: WorkflowRuleCreate,
    actor: Annotated[User, Depends(require_role(["OrgAdmin", "Manager"]))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Create a lead-automation rule (trigger + conditions + actions)."""
    return await WorkflowService(db).create_rule(actor, req.model_dump())

@router.patch("/workflows/{rule_id}", response_model=WorkflowRuleResponse)
async def update_workflow_rule(
    rule_id: uuid.UUID,
    req: WorkflowRuleUpdate,
    actor: Annotated[User, Depends(require_role(["OrgAdmin", "Manager"]))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Update an automation rule."""
    return await WorkflowService(db).update_rule(actor, rule_id, req.model_dump(exclude_unset=True))

@router.delete("/workflows/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workflow_rule(
    rule_id: uuid.UUID,
    actor: Annotated[User, Depends(require_role(["OrgAdmin", "Manager"]))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Delete an automation rule."""
    await WorkflowService(db).delete_rule(actor, rule_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

# --- Saved Filters ---

@router.get("/saved-filters", response_model=List[SavedFilterResponse])
async def list_saved_filters(
    actor: Annotated[User, Depends(require_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    entity_type: str | None = Query("lead"),
):
    """List the caller's saved filters plus any shared org-wide ones."""
    service = SavedFilterService(db)
    return list(await service.list_filters(actor, entity_type))

@router.post("/saved-filters", response_model=SavedFilterResponse, status_code=status.HTTP_201_CREATED)
async def create_saved_filter(
    req: SavedFilterCreate,
    actor: Annotated[User, Depends(require_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Save a reusable filter definition."""
    service = SavedFilterService(db)
    return await service.create_filter(actor, req.model_dump())

@router.patch("/saved-filters/{filter_id}", response_model=SavedFilterResponse)
async def update_saved_filter(
    filter_id: uuid.UUID,
    req: SavedFilterUpdate,
    actor: Annotated[User, Depends(require_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Rename, re-share, or redefine an owned saved filter."""
    service = SavedFilterService(db)
    return await service.update_filter(actor, filter_id, req.model_dump(exclude_unset=True))

@router.delete("/saved-filters/{filter_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_saved_filter(
    filter_id: uuid.UUID,
    actor: Annotated[User, Depends(require_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Delete an owned saved filter."""
    service = SavedFilterService(db)
    await service.delete_filter(actor, filter_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

@router.get("/{lead_id}", response_model=LeadResponse)
async def get_lead(
    lead_id: uuid.UUID,
    actor: Annotated[User, Depends(require_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Retrieve detailed lead opportunity scoped to organization."""
    lead_service = LeadService(db)
    return await lead_service.get_lead(actor, lead_id)

@router.patch("/{lead_id}", response_model=LeadResponse)
async def update_lead(
    lead_id: uuid.UUID,
    lead_in: LeadUpdate,
    actor: Annotated[User, Depends(require_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Update properties of a scoped lead opportunity."""
    lead_service = LeadService(db)
    return await lead_service.update_lead(actor, lead_id, lead_in.model_dump(exclude_unset=True))

@router.delete("/{lead_id}", response_model=LeadResponse)
async def delete_lead(
    lead_id: uuid.UUID,
    actor: Annotated[User, Depends(require_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Soft delete lead from organization database."""
    lead_service = LeadService(db)
    return await lead_service.soft_delete_lead(actor, lead_id)

@router.post("/{lead_id}/archive", response_model=LeadResponse)
async def archive_lead(
    lead_id: uuid.UUID,
    actor: Annotated[User, Depends(require_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Archive a lead (hidden from default listings, retained for restore)."""
    lead_service = LeadService(db)
    return await lead_service.archive_lead(actor, lead_id)

@router.post("/{lead_id}/restore", response_model=LeadResponse)
async def restore_lead(
    lead_id: uuid.UUID,
    actor: Annotated[User, Depends(require_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Restore an archived or soft-deleted lead back to active state."""
    lead_service = LeadService(db)
    return await lead_service.restore_lead(actor, lead_id)

@router.post("/{lead_id}/recompute-score", response_model=LeadResponse)
async def recompute_lead_score(
    lead_id: uuid.UUID,
    actor: Annotated[User, Depends(require_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Recompute the rule-based score for a lead."""
    lead_service = LeadService(db)
    return await lead_service.recompute_score(actor, lead_id)

@router.post("/{lead_id}/convert", response_model=LeadConvertResponse)
async def convert_lead(
    lead_id: uuid.UUID,
    req: LeadConvertRequest,
    actor: Annotated[User, Depends(require_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Convert a lead into a Contact (+ optional Company); archives and links the lead."""
    lead_service = LeadService(db)
    result = await lead_service.convert_lead(actor, lead_id, create_company=req.create_company)
    return LeadConvertResponse(**result)

@router.get("/{lead_id}/reminders", response_model=List[LeadReminderResponse])
async def list_lead_reminders(
    lead_id: uuid.UUID,
    actor: Annotated[User, Depends(require_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """List reminders set on a lead."""
    lead_service = LeadService(db)
    return list(await lead_service.list_reminders(actor, lead_id))

@router.post("/{lead_id}/reminders", response_model=LeadReminderResponse, status_code=status.HTTP_201_CREATED)
async def create_lead_reminder(
    lead_id: uuid.UUID,
    req: LeadReminderCreate,
    actor: Annotated[User, Depends(require_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Schedule a reminder for a lead; fires an in-app notification when due."""
    lead_service = LeadService(db)
    return await lead_service.create_reminder(actor, lead_id, req.remind_at, req.note, req.user_id)

@router.delete("/{lead_id}/reminders/{reminder_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_lead_reminder(
    lead_id: uuid.UUID,
    reminder_id: uuid.UUID,
    actor: Annotated[User, Depends(require_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Delete a lead reminder."""
    lead_service = LeadService(db)
    await lead_service.delete_reminder(actor, lead_id, reminder_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

@router.get("/{lead_id}/timeline", response_model=List[LeadTimelineEvent])
async def get_lead_timeline(
    lead_id: uuid.UUID,
    actor: Annotated[User, Depends(require_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Unified chronological feed of notes, activities, and audit events for a lead."""
    lead_service = LeadService(db)
    return await lead_service.get_timeline(actor, lead_id)

@router.post("/{lead_id}/follow-up", status_code=status.HTTP_201_CREATED)
async def log_follow_up(
    lead_id: uuid.UUID,
    req: FollowUpCreate,
    actor: Annotated[User, Depends(require_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Log a call/interaction outcome and schedule the next follow-up in one
    shot. Orchestrates: timeline entry, follow-up task (+ reminder), optional
    calendar event, manager notification, audit, and the follow_up_created
    automation trigger."""
    from app.services.follow_up_service import FollowUpService
    return await FollowUpService(db).create_follow_up(actor, lead_id, req.model_dump())


@router.get("/{lead_id}/audit", response_model=List[LeadAuditEvent])
async def get_lead_audit(
    lead_id: uuid.UUID,
    actor: Annotated[User, Depends(require_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Tenant-visible audit trail for a single lead."""
    lead_service = LeadService(db)
    return await lead_service.get_audit_trail(actor, lead_id)

@router.get("/{lead_id}/attachments", response_model=List[LeadAttachmentResponse])
async def list_lead_attachments(
    lead_id: uuid.UUID,
    actor: Annotated[User, Depends(require_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """List files attached to a lead."""
    lead_service = LeadService(db)
    return await lead_service.list_attachments(actor, lead_id)

@router.post("/{lead_id}/attachments", response_model=LeadAttachmentResponse, status_code=status.HTTP_201_CREATED)
async def upload_lead_attachment(
    lead_id: uuid.UUID,
    actor: Annotated[User, Depends(require_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    file: UploadFile = File(...)
):
    """Attach a file (pdf/image/csv/xlsx/docx, max 5MB) to a lead."""
    MAX_UPLOAD = 5 * 1024 * 1024
    content = await file.read(MAX_UPLOAD + 1)
    if len(content) > MAX_UPLOAD:
        raise HTTPException(status_code=400, detail="File exceeds the limit of 5.0MB")
    lead_service = LeadService(db)
    return await lead_service.add_attachment(actor, lead_id, content, file.filename or "attachment")

@router.delete("/{lead_id}/attachments/{stored_name}")
async def delete_lead_attachment(
    lead_id: uuid.UUID,
    stored_name: str,
    actor: Annotated[User, Depends(require_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Remove a file attached to a lead."""
    lead_service = LeadService(db)
    return await lead_service.delete_attachment(actor, lead_id, stored_name)

# --- Bulk Lead Imports ---

@router.get("/import/template/business-types")
async def list_import_template_business_types(
    actor: Annotated[User, Depends(require_tl_or_above)]
):
    """List business verticals with a tailored import template available."""
    return LeadImportService.list_business_templates()

@router.get("/import/template")
async def get_import_template(
    actor: Annotated[User, Depends(require_tl_or_above)],
    format: str = Query("csv", pattern="^(csv|xlsx)$"),
    vertical: str | None = Query(None, description="Business type key for a tailored template, e.g. 'real_estate'")
):
    """Download CSV or Excel template for bulk lead imports, optionally
    tailored to a business vertical with relevant headers and sample rows."""
    filename_suffix = f"_{vertical}" if vertical else ""
    if format == "xlsx":
        xlsx_bytes = LeadImportService.generate_xlsx_template(vertical)
        return StreamingResponse(
            io.BytesIO(xlsx_bytes),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename=leads_template{filename_suffix}.xlsx"}
        )
    else:
        csv_text = LeadImportService.generate_csv_template(vertical)
        return StreamingResponse(
            io.StringIO(csv_text),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=leads_template{filename_suffix}.csv"}
        )

@router.post("/import/upload", response_model=ImportPreviewResponse)
async def upload_import_file(
    actor: Annotated[User, Depends(require_tl_or_above)],
    db: Annotated[AsyncSession, Depends(get_db)],
    file: UploadFile = File(...)
):
    """Upload bulk lead CSV/Excel and retrieve mapping suggestions and preview."""
    import_service = LeadImportService(db)

    from fastapi import HTTPException
    from app.core.storage import validate_and_sanitize_file

    # Bounded read: never pull more than the limit (+1 byte to detect overflow)
    # into memory, so an oversized upload can't exhaust server memory.
    MAX_UPLOAD = 2 * 1024 * 1024
    content = await file.read(MAX_UPLOAD + 1)
    if len(content) > MAX_UPLOAD:
        raise HTTPException(status_code=400, detail="File exceeds the limit of 2.0MB")

    try:
        sanitized_filename, ext = validate_and_sanitize_file(
            content=content,
            filename=file.filename or "leads.csv",
            allowed_extensions={"csv", "xlsx", "xls"},
            max_size=MAX_UPLOAD
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
        
    return await import_service.get_preview_from_file(sanitized_filename, content)

@router.post("/import/google-sheets", response_model=ImportPreviewResponse)
async def google_sheets_import_preview(
    req: GoogleSheetsPreviewRequest,
    actor: Annotated[User, Depends(require_tl_or_above)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Fetch shared Google Sheets URL and retrieve mapping suggestions and preview."""
    import_service = LeadImportService(db)
    return await import_service.get_preview_from_google_sheets(req.url)

@router.post("/import/process", response_model=LeadImportResponse)
async def process_import_batch(
    req: LeadImportProcessRequest,
    actor: Annotated[User, Depends(require_tl_or_above)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Execute validation and lead creations based on mapped headers."""
    import_service = LeadImportService(db)
    return await import_service.process_import_batch(
        actor=actor,
        file_token=req.file_token,
        source_type=req.source_type,
        column_mapping=req.column_mapping,
        auto_assign=req.auto_assign,
        assignment_mode=req.assignment_mode,
        assigned_user_id=req.assigned_user_id,
        assigned_user_ids=req.assigned_user_ids
    )

@router.get("/import/history", response_model=List[LeadImportResponse])
async def list_import_history(
    actor: Annotated[User, Depends(require_tl_or_above)],
    db: Annotated[AsyncSession, Depends(get_db)],
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100)
):
    """List details of previous bulk lead imports."""
    import_service = LeadImportService(db)
    records = await import_service.import_repo.list_imports(actor.organization_id, skip, limit)
    return list(records)

@router.get("/import/{import_id}/failed-rows")
async def download_failed_rows(
    import_id: uuid.UUID,
    actor: Annotated[User, Depends(require_tl_or_above)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Download CSV file of failed validation rows for a specific import job."""
    import_service = LeadImportService(db)
    csv_report = await import_service.get_failed_rows_report(actor.organization_id, import_id)
    return Response(
        content=csv_report,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=failed_rows_{import_id}.csv"}
    )

# --- Lead Auto-Assignment Configuration ---

@router.get("/assignment/config", response_model=AssignmentConfigResponse)
async def get_assignment_config(
    actor: Annotated[User, Depends(require_role(["OrgAdmin", "Manager"]))],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Retrieve auto-assignment configuration for the tenant."""
    assign_service = AssignmentService(db)
    return await assign_service.get_or_create_config(actor.organization_id)

@router.patch("/assignment/config", response_model=AssignmentConfigResponse)
async def update_assignment_config(
    req: AssignmentConfigUpdate,
    actor: Annotated[User, Depends(require_role(["OrgAdmin", "Manager"]))],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Enable or disable auto-assignment configuration."""
    assign_service = AssignmentService(db)
    return await assign_service.toggle_assignment(actor.organization_id, req.is_active)

@router.post("/assign-bulk", response_model=LeadBulkAssignResponse)
async def assign_leads_bulk(
    req: LeadBulkAssignRequest,
    actor: Annotated[User, Depends(require_tl_or_above)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Bulk assign leads using SPLIT or RANGE strategy among downline users."""
    assign_service = AssignmentService(db)
    return await assign_service.assign_leads_bulk(actor, req)

@router.post("/transfer", response_model=LeadTransferResponse)
async def transfer_leads(
    req: LeadTransferRequest,
    actor: Annotated[User, Depends(require_tl_or_above)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """
    Transfer a segment of leads from a source user to one or more destination users.
    """
    from app.services.user_service import UserService
    from app.services.audit_service import AuditService
    from app.services.notification_service import NotificationService
    from app.models.lead import Lead
    from sqlalchemy import select

    user_service = UserService(db)
    audit_service = AuditService(db)
    notification_service = NotificationService(db)

    # 1. Users the actor may assign to / transfer from. Admins & managers get
    #    org-wide authority; a team leader gets their downline plus themselves.
    assignable_ids = await user_service.get_assignable_user_ids(actor)

    # 2. Validate source user id
    if req.source_user_id not in assignable_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Source user is not yourself or within your assignable users"
        )

    # 3. Validate destination user ids
    for dest_id in req.destination_user_ids:
        if dest_id not in assignable_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Destination user {dest_id} is not within your assignable users"
            )

    # 4. Fetch destination users from database to ensure active status
    dest_query = select(User).filter(
        User.id.in_(req.destination_user_ids),
        User.is_deleted == False,
        User.is_active == True,
        User.organization_id == actor.organization_id
    )
    dest_res = await db.execute(dest_query)
    dest_users = {u.id: u for u in dest_res.scalars().all()}
    for dest_id in req.destination_user_ids:
        if dest_id not in dest_users:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Destination user {dest_id} is inactive, deleted, or does not exist"
            )

    # 5. Fetch leads assigned to source user with FOR UPDATE locking
    if req.lead_ids is not None:
        leads_query = select(Lead).filter(
            Lead.id.in_(req.lead_ids),
            Lead.assigned_user_id == req.source_user_id,
            Lead.organization_id == actor.organization_id
        ).with_for_update().order_by(Lead.id)
    elif req.quantity is not None:
        leads_query = select(Lead).filter(
            Lead.assigned_user_id == req.source_user_id,
            Lead.organization_id == actor.organization_id
        ).order_by(Lead.id).limit(req.quantity).with_for_update()
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either quantity or lead_ids must be provided"
        )

    leads_res = await db.execute(leads_query)
    leads = list(leads_res.scalars().all())

    if not leads:
        return LeadTransferResponse(
            transferred_count=0,
            lead_ids=[],
            destination_user_ids=req.destination_user_ids
        )

    # 6. Apply chunk-split re-assignment
    num_leads = len(leads)
    num_destinations = len(req.destination_user_ids)
    k = num_leads // num_destinations
    r = num_leads % num_destinations

    idx = 0
    transferred_lead_ids = []
    for i, dest_id in enumerate(req.destination_user_ids):
        chunk_size = k + (1 if i < r else 0)
        dest_user = dest_users[dest_id]
        for _ in range(chunk_size):
            lead = leads[idx]
            lead.assigned_user_id = dest_id
            db.add(lead)
            transferred_lead_ids.append(lead.id)
            
            # Log audit event for each transfer
            await audit_service.log_event(
                organization_id=actor.organization_id,
                actor_user_id=actor.id,
                action="LEAD_ASSIGNED",
                resource_type="lead",
                resource_id=str(lead.id),
                action_metadata={
                    "assigned_user_id": str(dest_id),
                    "assigned_email": dest_user.email,
                    "previous_user_id": str(req.source_user_id),
                    "reason": "lead_transfer",
                    "actor_id": str(actor.id)
                }
            )
            idx += 1

        if chunk_size > 0 and dest_id != actor.id:
            await notification_service.create_notification(
                organization_id=actor.organization_id,
                user_id=dest_id,
                category="lead",
                title="Leads transferred to you",
                body=f"{chunk_size} lead(s) have been transferred to you.",
                link_url="/leads",
                action_metadata={"count": chunk_size, "source_user_id": str(req.source_user_id)},
            )

    await db.flush()

    return LeadTransferResponse(
        transferred_count=len(transferred_lead_ids),
        lead_ids=transferred_lead_ids,
        destination_user_ids=req.destination_user_ids
    )
