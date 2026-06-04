import uuid
import io
from typing import Annotated, List
from fastapi import APIRouter, Depends, Query, status, UploadFile, File, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User
from app.schemas.lead import LeadResponse, LeadCreate, LeadUpdate
from app.schemas.lead_import import GoogleSheetsPreviewRequest, ImportPreviewResponse, LeadImportProcessRequest, LeadImportResponse
from app.schemas.assignment_config import AssignmentConfigUpdate, AssignmentConfigResponse
from app.services.lead_service import LeadService
from app.services.lead_import_service import LeadImportService
from app.services.assignment_service import AssignmentService
from app.middleware.permissions import require_active_user

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
    assigned_user_id: uuid.UUID | None = Query(None)
):
    """List paginated, searchable leads scoped to the tenant organization."""
    lead_service = LeadService(db)
    records, _ = await lead_service.paginate_leads(
        actor, skip, limit, search, status, assigned_user_id
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

@router.get("/import/template")
async def get_import_template(
    format: str = Query("csv", pattern="^(csv|xlsx)$"),
    actor: Annotated[User, Depends(require_active_user)] = None
):
    """Download CSV or Excel template for bulk lead imports."""
    if format == "xlsx":
        xlsx_bytes = LeadImportService.generate_xlsx_template()
        return StreamingResponse(
            io.BytesIO(xlsx_bytes),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=leads_template.xlsx"}
        )
    else:
        csv_text = LeadImportService.generate_csv_template()
        return StreamingResponse(
            io.StringIO(csv_text),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=leads_template.csv"}
        )

@router.post("/import/upload", response_model=ImportPreviewResponse)
async def upload_import_file(
    file: UploadFile = File(...),
    actor: Annotated[User, Depends(require_active_user)] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None
):
    """Upload bulk lead CSV/Excel and retrieve mapping suggestions and preview."""
    import_service = LeadImportService(db)
    content = await file.read()
    return await import_service.get_preview_from_file(file.filename, content)

@router.post("/import/google-sheets", response_model=ImportPreviewResponse)
async def google_sheets_import_preview(
    req: GoogleSheetsPreviewRequest,
    actor: Annotated[User, Depends(require_active_user)] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None
):
    """Fetch shared Google Sheets URL and retrieve mapping suggestions and preview."""
    import_service = LeadImportService(db)
    return await import_service.get_preview_from_google_sheets(req.url)

@router.post("/import/process", response_model=LeadImportResponse)
async def process_import_batch(
    req: LeadImportProcessRequest,
    actor: Annotated[User, Depends(require_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Execute validation and lead creations based on mapped headers."""
    import_service = LeadImportService(db)
    return await import_service.process_import_batch(
        actor=actor,
        file_token=req.file_token,
        source_type=req.source_type,
        column_mapping=req.column_mapping,
        auto_assign=req.auto_assign
    )

@router.get("/import/history", response_model=List[LeadImportResponse])
async def list_import_history(
    actor: Annotated[User, Depends(require_active_user)],
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
    actor: Annotated[User, Depends(require_active_user)],
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
    actor: Annotated[User, Depends(require_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Retrieve auto-assignment configuration for the tenant."""
    assign_service = AssignmentService(db)
    return await assign_service.get_or_create_config(actor.organization_id)

@router.patch("/assignment/config", response_model=AssignmentConfigResponse)
async def update_assignment_config(
    req: AssignmentConfigUpdate,
    actor: Annotated[User, Depends(require_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Enable or disable auto-assignment configuration."""
    assign_service = AssignmentService(db)
    return await assign_service.toggle_assignment(actor.organization_id, req.is_active)
