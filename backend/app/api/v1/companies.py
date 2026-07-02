import uuid
from typing import Annotated, List
from fastapi import APIRouter, Depends, Query, status, UploadFile, File, HTTPException, Response
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.models.user import User
from app.schemas.company import (
    CompanyResponse, CompanyCreate, CompanyUpdate,
    CompanyContactSummary, CompanyLeadSummary, CompanyDealsSummary,
    CompanyTimelineEvent, CompanyCommunication, CompanyAttachmentResponse,
    CompanyReportResponse,
)
from app.services.company_service import CompanyService
from app.middleware.permissions import require_active_user, require_role

# Company records are an OrgAdmin/Manager surface (matches the frontend route guard).
_oa_or_mgr = require_role(["OrgAdmin", "Manager"])

router = APIRouter()

@router.post("/", response_model=CompanyResponse, status_code=status.HTTP_201_CREATED)
async def create_company(
    company_in: CompanyCreate,
    actor: Annotated[User, Depends(_oa_or_mgr)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Create a new company for the organization."""
    company_service = CompanyService(db)
    return await company_service.create_company(actor, company_in.model_dump())

@router.get("/", response_model=List[CompanyResponse])
async def list_companies(
    actor: Annotated[User, Depends(_oa_or_mgr)],
    db: Annotated[AsyncSession, Depends(get_db)],
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    search: str | None = Query(None),
    industry: str | None = Query(None),
    company_type: str | None = Query(None),
    source: str | None = Query(None),
    assigned_user_id: uuid.UUID | None = Query(None),
    tag: str | None = Query(None),
):
    """List paginated, searchable companies scoped to the tenant organization."""
    company_service = CompanyService(db)
    records, _ = await company_service.paginate_companies(
        actor, skip, limit, search,
        industry=industry, company_type=company_type, source=source,
        assigned_user_id=assigned_user_id, tag=tag,
    )
    return list(records)

# --- Static routes (before /{company_id}) ---

@router.get("/reports", response_model=CompanyReportResponse)
async def get_company_reports(
    actor: Annotated[User, Depends(_oa_or_mgr)],
    db: Annotated[AsyncSession, Depends(get_db)],
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
):
    """Company analytics: revenue/employee totals, lifecycle mix, breakdowns."""
    company_service = CompanyService(db)
    return await company_service.get_company_report(actor, date_from=date_from, date_to=date_to)

@router.get("/tags", response_model=List[str])
async def list_company_tags(
    actor: Annotated[User, Depends(_oa_or_mgr)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """List all distinct tags used across the org's companies."""
    company_service = CompanyService(db)
    return await company_service.get_tags(actor)

# --- Single company ---

@router.get("/{company_id}", response_model=CompanyResponse)
async def get_company(
    company_id: uuid.UUID,
    actor: Annotated[User, Depends(_oa_or_mgr)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Retrieve detailed company profile scoped to organization."""
    company_service = CompanyService(db)
    return await company_service.get_company(actor, company_id)

@router.patch("/{company_id}", response_model=CompanyResponse)
async def update_company(
    company_id: uuid.UUID,
    company_in: CompanyUpdate,
    actor: Annotated[User, Depends(_oa_or_mgr)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Update properties of a scoped company."""
    company_service = CompanyService(db)
    return await company_service.update_company(actor, company_id, company_in.model_dump(exclude_unset=True))

@router.delete("/{company_id}", response_model=CompanyResponse)
async def delete_company(
    company_id: uuid.UUID,
    actor: Annotated[User, Depends(_oa_or_mgr)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Soft delete company from organization database."""
    company_service = CompanyService(db)
    return await company_service.soft_delete_company(actor, company_id)

# --- Associations ---

@router.get("/{company_id}/contacts", response_model=List[CompanyContactSummary])
async def get_company_contacts(
    company_id: uuid.UUID,
    actor: Annotated[User, Depends(_oa_or_mgr)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """People (contacts / employees) that belong to this company."""
    company_service = CompanyService(db)
    return await company_service.get_contacts(actor, company_id)

@router.get("/{company_id}/leads", response_model=List[CompanyLeadSummary])
async def get_company_leads(
    company_id: uuid.UUID,
    actor: Annotated[User, Depends(_oa_or_mgr)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Leads/opportunities associated with this company (by id or matching name)."""
    company_service = CompanyService(db)
    return await company_service.get_leads(actor, company_id)

@router.get("/{company_id}/deals", response_model=CompanyDealsSummary)
async def get_company_deals(
    company_id: uuid.UUID,
    actor: Annotated[User, Depends(_oa_or_mgr)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Deal rollup for this company; won == Converted (associated customers)."""
    company_service = CompanyService(db)
    return await company_service.get_deals_summary(actor, company_id)

@router.get("/{company_id}/timeline", response_model=List[CompanyTimelineEvent])
async def get_company_timeline(
    company_id: uuid.UUID,
    actor: Annotated[User, Depends(_oa_or_mgr)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Unified chronological feed of notes, activities, and audit events."""
    company_service = CompanyService(db)
    return await company_service.get_timeline(actor, company_id)

@router.get("/{company_id}/communications", response_model=List[CompanyCommunication])
async def get_company_communications(
    company_id: uuid.UUID,
    actor: Annotated[User, Depends(_oa_or_mgr)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Call/Email communication history for a company."""
    company_service = CompanyService(db)
    return await company_service.get_communications(actor, company_id)

@router.get("/{company_id}/attachments", response_model=List[CompanyAttachmentResponse])
async def list_company_attachments(
    company_id: uuid.UUID,
    actor: Annotated[User, Depends(_oa_or_mgr)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """List files attached to a company."""
    company_service = CompanyService(db)
    return await company_service.list_attachments(actor, company_id)

@router.post("/{company_id}/attachments", response_model=CompanyAttachmentResponse, status_code=status.HTTP_201_CREATED)
async def upload_company_attachment(
    company_id: uuid.UUID,
    actor: Annotated[User, Depends(_oa_or_mgr)],
    db: Annotated[AsyncSession, Depends(get_db)],
    file: UploadFile = File(...)
):
    """Attach a file (pdf/image/csv/xlsx/docx, max 5MB) to a company."""
    MAX_UPLOAD = 5 * 1024 * 1024
    content = await file.read(MAX_UPLOAD + 1)
    if len(content) > MAX_UPLOAD:
        raise HTTPException(status_code=400, detail="File exceeds the limit of 5.0MB")
    company_service = CompanyService(db)
    return await company_service.add_attachment(actor, company_id, content, file.filename or "attachment")

@router.delete("/{company_id}/attachments/{stored_name}")
async def delete_company_attachment(
    company_id: uuid.UUID,
    stored_name: str,
    actor: Annotated[User, Depends(_oa_or_mgr)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Remove a file attached to a company."""
    company_service = CompanyService(db)
    return await company_service.delete_attachment(actor, company_id, stored_name)
