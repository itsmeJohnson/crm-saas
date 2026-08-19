import uuid
from typing import Annotated, List, Any
from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.models.user import User
from app.models.organization import Organization
from app.middleware.permissions import require_active_user, require_role
from app.schemas.custom_field import (
    CustomFieldDefinitionCreate,
    CustomFieldDefinitionUpdate,
    CustomFieldDefinitionResponse
)
from app.services.custom_field_service import CustomFieldService
from app.services.pipeline_service import list_pipelines
from app.schemas.pipeline import PipelineResponse
from app.services.metadata_cache_service import MetadataCacheService
from app.services.tenant_config_service import TenantConfigurationResolver

router = APIRouter()


# ── Consolidated Metadata Bootstrap Endpoint ───────────────────────────────────

@router.get("/bootstrap", status_code=status.HTTP_200_OK)
async def bootstrap_metadata(
    actor: Annotated[User, Depends(require_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """
    Consolidated metadata bootstrap endpoint.
    Allows frontend to fetch organization's metadata version, custom fields, and pipelines in a single call.
    """
    # Fetch organization metadata_version
    org = await db.get(Organization, actor.organization_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    # Fetch custom field definitions per supported entity (utilizes caching).
    # `custom_fields` stays as the flat lead list for backward compatibility;
    # `custom_fields_by_entity` is the per-entity map the frontend now consumes.
    from app.core.reserved_fields import SUPPORTED_ENTITY_TYPES
    cf_service = CustomFieldService(db)
    custom_fields_by_entity: dict[str, list] = {}
    for entity in sorted(SUPPORTED_ENTITY_TYPES):
        defs = await cf_service.list_definitions(actor, entity)
        custom_fields_by_entity[entity] = [
            CustomFieldDefinitionResponse.model_validate(cf) for cf in defs
        ]
    custom_fields = custom_fields_by_entity.get("lead", [])

    # Fetch pipelines and their stages (utilizes caching)
    pipelines = await list_pipelines(db, actor)

    # Custom object definitions — eager (their FIELD defs load lazily per object
    # via /metadata/custom-fields?entity_type=<key>, to keep bootstrap lean).
    from app.services.custom_object_service import CustomObjectService
    from app.schemas.custom_object import CustomObjectDefinitionResponse
    objects = await CustomObjectService(db).list_objects(actor)
    custom_objects = [CustomObjectDefinitionResponse.model_validate(o) for o in objects]

    # Resolve tenant config
    crm_config = await TenantConfigurationResolver(db).resolve_config(actor.organization_id)

    return {
        "metadata_version": org.metadata_version,
        "custom_fields": custom_fields,
        "custom_fields_by_entity": custom_fields_by_entity,
        "custom_objects": custom_objects,
        "pipelines": [PipelineResponse.model_validate(p) for p in pipelines],
        "crm_config": crm_config
    }


# ── Custom Field Definitions CRUD ──────────────────────────────────────────────

@router.get("/custom-fields", response_model=List[CustomFieldDefinitionResponse])
async def list_custom_field_definitions(
    actor: Annotated[User, Depends(require_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    entity_type: str = "lead"
):
    """
    List all active custom field definitions for the organization.
    """
    cf_service = CustomFieldService(db)
    return await cf_service.list_definitions(actor, entity_type)

@router.post("/custom-fields", response_model=CustomFieldDefinitionResponse, status_code=status.HTTP_201_CREATED)
async def create_custom_field_definition(
    req: CustomFieldDefinitionCreate,
    actor: Annotated[User, Depends(require_role(["OrgAdmin"]))],
    db: Annotated[AsyncSession, Depends(get_db)],
    entity_type: str = "lead"
):
    """
    Create a new custom field definition. Admin only.
    """
    cf_service = CustomFieldService(db)
    try:
        cf = await cf_service.create_definition(actor, req.model_dump(), entity_type)
        await db.commit()
        return cf
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.patch("/custom-fields/{definition_id}", response_model=CustomFieldDefinitionResponse)
async def update_custom_field_definition(
    definition_id: uuid.UUID,
    req: CustomFieldDefinitionUpdate,
    actor: Annotated[User, Depends(require_role(["OrgAdmin"]))],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """
    Update an existing custom field definition. Admin only.
    """
    cf_service = CustomFieldService(db)
    try:
        cf = await cf_service.update_definition(actor, definition_id, req.model_dump(exclude_unset=True))
        await db.commit()
        return cf
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.delete("/custom-fields/{definition_id}", status_code=status.HTTP_200_OK)
async def delete_custom_field_definition(
    definition_id: uuid.UUID,
    actor: Annotated[User, Depends(require_role(["OrgAdmin"]))],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """
    Soft-delete a custom field definition. Admin only.
    """
    cf_service = CustomFieldService(db)
    try:
        await cf_service.delete_definition(actor, definition_id)
        await db.commit()
        return {"status": "success", "message": "Custom field definition deleted"}
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
