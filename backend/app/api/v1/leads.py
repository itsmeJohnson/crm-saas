import uuid
import io
from typing import Annotated, List
from fastapi import APIRouter, Depends, Query, status, UploadFile, File, Response, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User
from app.schemas.lead import LeadResponse, LeadCreate, LeadUpdate
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
    city: str | None = Query(None)
):
    """List paginated, searchable leads scoped to the tenant organization."""
    lead_service = LeadService(db)
    records, _ = await lead_service.paginate_leads(
        actor, skip, limit, search, status, assigned_user_id, name, city
    )
    return list(records)

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
    from app.models.lead import Lead
    from sqlalchemy import select

    user_service = UserService(db)
    audit_service = AuditService(db)

    # 1. Fetch actor downline ids recursively
    downline_ids = await user_service.get_downline_user_ids(actor)

    # 2. Validate source user id
    if req.source_user_id != actor.id and req.source_user_id not in downline_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Source user is not yourself or in your downline reporting chain"
        )

    # 3. Validate destination user ids
    for dest_id in req.destination_user_ids:
        if dest_id not in downline_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Destination user {dest_id} is not in your downline reporting chain"
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

    await db.flush()

    return LeadTransferResponse(
        transferred_count=len(transferred_lead_ids),
        lead_ids=transferred_lead_ids,
        destination_user_ids=req.destination_user_ids
    )
