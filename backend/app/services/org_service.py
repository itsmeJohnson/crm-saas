from typing import Any
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.organization import OrganizationRepository
from app.schemas.organization import OrganizationCreate, OrganizationUpdate
from app.models.organization import Organization

class OrganizationService:
    def __init__(self, db: AsyncSession):
        self.org_repo = OrganizationRepository(db)

    async def get_org(self, org_id: Any) -> Organization:
        org = await self.org_repo.get(org_id)
        if not org:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organization not found"
            )
        return org

    async def get_by_slug(self, slug: str) -> Organization | None:
        return await self.org_repo.get_by_slug(slug)

    async def create_org(self, org_in: OrganizationCreate) -> Organization:
        existing = await self.org_repo.get_by_slug(org_in.slug)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="An organization with this slug already exists"
            )
        return await self.org_repo.create(org_in)

    async def update_org(self, org_id: Any, org_in: OrganizationUpdate) -> Organization:
        org = await self.get_org(org_id)
        return await self.org_repo.update(org, org_in)
