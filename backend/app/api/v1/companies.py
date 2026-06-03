import uuid
from typing import Annotated, List
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.models.user import User
from app.schemas.company import CompanyResponse, CompanyCreate, CompanyUpdate
from app.services.company_service import CompanyService
from app.middleware.permissions import require_active_user

router = APIRouter()

@router.post("/", response_model=CompanyResponse, status_code=status.HTTP_201_CREATED)
async def create_company(
    company_in: CompanyCreate,
    actor: Annotated[User, Depends(require_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Create a new company for the organization."""
    company_service = CompanyService(db)
    return await company_service.create_company(actor, company_in.model_dump())

@router.get("/", response_model=List[CompanyResponse])
async def list_companies(
    actor: Annotated[User, Depends(require_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    search: str | None = Query(None)
):
    """List paginated, searchable companies scoped to the tenant organization."""
    company_service = CompanyService(db)
    records, _ = await company_service.paginate_companies(actor, skip, limit, search)
    return list(records)

@router.get("/{company_id}", response_model=CompanyResponse)
async def get_company(
    company_id: uuid.UUID,
    actor: Annotated[User, Depends(require_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Retrieve detailed company profile scoped to organization."""
    company_service = CompanyService(db)
    return await company_service.get_company(actor, company_id)

@router.patch("/{company_id}", response_model=CompanyResponse)
async def update_company(
    company_id: uuid.UUID,
    company_in: CompanyUpdate,
    actor: Annotated[User, Depends(require_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Update properties of a scoped company."""
    company_service = CompanyService(db)
    return await company_service.update_company(actor, company_id, company_in.model_dump(exclude_unset=True))

@router.delete("/{company_id}", response_model=CompanyResponse)
async def delete_company(
    company_id: uuid.UUID,
    actor: Annotated[User, Depends(require_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Soft delete company from organization database."""
    company_service = CompanyService(db)
    return await company_service.soft_delete_company(actor, company_id)
