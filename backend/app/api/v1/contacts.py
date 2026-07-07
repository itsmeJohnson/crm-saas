import uuid
import io
from datetime import datetime
from typing import Annotated, List
from fastapi import APIRouter, Depends, Query, status, UploadFile, File, HTTPException, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.models.user import User
from app.schemas.contact import (
    ContactResponse, ContactCreate, ContactUpdate,
    ContactBulkUpdateRequest, ContactBulkDeleteRequest, ContactBulkResult,
    ContactTimelineEvent, ContactCommunication, ContactAttachmentResponse,
    ContactMergeRequest, ContactRelationshipCreate, ContactRelationshipResponse,
    CustomFieldDefinitionCreate, CustomFieldDefinitionUpdate, CustomFieldDefinitionResponse,
    ContactReportResponse,
)
from app.services.contact_service import ContactService
from app.services.custom_field_service import CustomFieldService
from app.middleware.permissions import require_active_user, require_role

# Contact records are an OrgAdmin/Manager surface (matches the frontend route guard).
_oa_or_mgr = require_role(["OrgAdmin", "Manager"])

router = APIRouter()

@router.post("/", response_model=ContactResponse, status_code=status.HTTP_201_CREATED)
async def create_contact(
    contact_in: ContactCreate,
    actor: Annotated[User, Depends(_oa_or_mgr)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Create a new contact linkable to a company."""
    contact_service = ContactService(db)
    return await contact_service.create_contact(actor, contact_in.model_dump())

@router.get("/", response_model=List[ContactResponse])
async def list_contacts(
    actor: Annotated[User, Depends(_oa_or_mgr)],
    db: Annotated[AsyncSession, Depends(get_db)],
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    search: str | None = Query(None),
    company_id: uuid.UUID | None = Query(None),
    assigned_user_id: uuid.UUID | None = Query(None),
    tag: str | None = Query(None),
    has_email: bool | None = Query(None),
    created_from: datetime | None = Query(None),
    created_to: datetime | None = Query(None),
):
    """List paginated, searchable contacts scoped to the organization."""
    contact_service = ContactService(db)
    records, _ = await contact_service.paginate_contacts(
        actor, skip, limit, search, company_id,
        assigned_user_id=assigned_user_id, tag=tag, has_email=has_email,
        created_from=created_from, created_to=created_to,
    )
    return list(records)

# --- Static routes (must precede /{contact_id}) ---

@router.get("/export")
async def export_contacts(
    actor: Annotated[User, Depends(_oa_or_mgr)],
    db: Annotated[AsyncSession, Depends(get_db)],
    format: str = Query("csv", pattern="^(csv|xlsx)$"),
    search: str | None = Query(None),
    company_id: uuid.UUID | None = Query(None),
    assigned_user_id: uuid.UUID | None = Query(None),
    tag: str | None = Query(None),
    has_email: bool | None = Query(None),
    created_from: datetime | None = Query(None),
    created_to: datetime | None = Query(None),
):
    """Export contacts (matching the list filters) as CSV or Excel."""
    contact_service = ContactService(db)
    filters = {
        "search_query": search, "company_id": company_id, "assigned_user_id": assigned_user_id,
        "tag": tag, "has_email": has_email, "created_from": created_from, "created_to": created_to,
    }
    rows = await contact_service.export_contacts(actor, filters)
    if format == "xlsx":
        content = ContactService.build_export_xlsx(rows)
        return StreamingResponse(
            io.BytesIO(content),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=contacts_export.xlsx"},
        )
    csv_text = ContactService.build_export_csv(rows)
    return StreamingResponse(
        io.StringIO(csv_text),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=contacts_export.csv"},
    )

@router.post("/import")
async def import_contacts(
    actor: Annotated[User, Depends(_oa_or_mgr)],
    db: Annotated[AsyncSession, Depends(get_db)],
    file: UploadFile = File(...),
):
    """Bulk-create contacts from a CSV/XLSX file (columns: first_name, last_name, email, phone, job_title, company)."""
    MAX_UPLOAD = 5 * 1024 * 1024
    content = await file.read(MAX_UPLOAD + 1)
    if len(content) > MAX_UPLOAD:
        raise HTTPException(status_code=400, detail="File exceeds the limit of 5.0MB")
    contact_service = ContactService(db)
    return await contact_service.import_contacts(actor, content, file.filename or "contacts.csv")

@router.get("/duplicates", response_model=List[ContactResponse])
async def find_duplicate_contacts(
    actor: Annotated[User, Depends(_oa_or_mgr)],
    db: Annotated[AsyncSession, Depends(get_db)],
    email: str | None = Query(None),
    phone: str | None = Query(None),
    exclude_contact_id: uuid.UUID | None = Query(None),
):
    """Find existing contacts sharing an email or phone."""
    contact_service = ContactService(db)
    return list(await contact_service.find_duplicates(actor, email=email, phone=phone, exclude_contact_id=exclude_contact_id))

@router.post("/bulk-update", response_model=ContactBulkResult)
async def bulk_update_contacts(
    req: ContactBulkUpdateRequest,
    actor: Annotated[User, Depends(_oa_or_mgr)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Apply company/owner/tag changes to many contacts at once."""
    contact_service = ContactService(db)
    fields = req.fields.model_dump(exclude_unset=True)
    result = await contact_service.bulk_update(actor, req.contact_ids, fields)
    return ContactBulkResult(**result)

@router.post("/bulk-delete", response_model=ContactBulkResult)
async def bulk_delete_contacts(
    req: ContactBulkDeleteRequest,
    actor: Annotated[User, Depends(_oa_or_mgr)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Soft-delete many contacts at once."""
    contact_service = ContactService(db)
    result = await contact_service.bulk_delete(actor, req.contact_ids)
    return ContactBulkResult(**result)

@router.get("/reports", response_model=ContactReportResponse)
async def get_contact_reports(
    actor: Annotated[User, Depends(_oa_or_mgr)],
    db: Annotated[AsyncSession, Depends(get_db)],
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
):
    """Contact analytics: coverage + breakdowns by company/owner/tag."""
    contact_service = ContactService(db)
    return await contact_service.get_contact_report(actor, date_from=date_from, date_to=date_to)

@router.get("/tags", response_model=List[str])
async def list_contact_tags(
    actor: Annotated[User, Depends(_oa_or_mgr)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """List all distinct tags used across the org's contacts."""
    contact_service = ContactService(db)
    return await contact_service.get_tags(actor)

@router.post("/merge", response_model=ContactResponse)
async def merge_contacts(
    req: ContactMergeRequest,
    actor: Annotated[User, Depends(_oa_or_mgr)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Merge secondary contact into primary (primary wins, blanks filled), then soft-delete secondary."""
    contact_service = ContactService(db)
    return await contact_service.merge_contacts(actor, req.primary_id, req.secondary_id)

# --- Custom field definitions ---

@router.get("/custom-fields", response_model=List[CustomFieldDefinitionResponse])
async def list_custom_fields(
    actor: Annotated[User, Depends(_oa_or_mgr)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """List custom-field definitions for contacts."""
    return list(await CustomFieldService(db).list_definitions(actor, "contact"))

@router.post("/custom-fields", response_model=CustomFieldDefinitionResponse, status_code=status.HTTP_201_CREATED)
async def create_custom_field(
    req: CustomFieldDefinitionCreate,
    actor: Annotated[User, Depends(_oa_or_mgr)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Define a new contact custom field."""
    return await CustomFieldService(db).create_definition(actor, req.model_dump(), "contact")

@router.patch("/custom-fields/{definition_id}", response_model=CustomFieldDefinitionResponse)
async def update_custom_field(
    definition_id: uuid.UUID,
    req: CustomFieldDefinitionUpdate,
    actor: Annotated[User, Depends(_oa_or_mgr)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Update a custom-field definition."""
    return await CustomFieldService(db).update_definition(actor, definition_id, req.model_dump(exclude_unset=True))

@router.delete("/custom-fields/{definition_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_custom_field(
    definition_id: uuid.UUID,
    actor: Annotated[User, Depends(_oa_or_mgr)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Delete a custom-field definition."""
    await CustomFieldService(db).delete_definition(actor, definition_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

# --- Single contact ---

@router.get("/{contact_id}", response_model=ContactResponse)
async def get_contact(
    contact_id: uuid.UUID,
    actor: Annotated[User, Depends(_oa_or_mgr)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Retrieve detailed contact profile scoped to organization."""
    contact_service = ContactService(db)
    return await contact_service.get_contact(actor, contact_id)

@router.patch("/{contact_id}", response_model=ContactResponse)
async def update_contact(
    contact_id: uuid.UUID,
    contact_in: ContactUpdate,
    actor: Annotated[User, Depends(_oa_or_mgr)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Update properties of a scoped contact."""
    contact_service = ContactService(db)
    return await contact_service.update_contact(actor, contact_id, contact_in.model_dump(exclude_unset=True))

@router.delete("/{contact_id}", response_model=ContactResponse)
async def delete_contact(
    contact_id: uuid.UUID,
    actor: Annotated[User, Depends(_oa_or_mgr)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Soft delete contact from organization database."""
    contact_service = ContactService(db)
    return await contact_service.soft_delete_contact(actor, contact_id)

@router.get("/{contact_id}/timeline", response_model=List[ContactTimelineEvent])
async def get_contact_timeline(
    contact_id: uuid.UUID,
    actor: Annotated[User, Depends(_oa_or_mgr)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Unified chronological feed of notes, activities, and audit events."""
    contact_service = ContactService(db)
    return await contact_service.get_timeline(actor, contact_id)

@router.get("/{contact_id}/communications", response_model=List[ContactCommunication])
async def get_contact_communications(
    contact_id: uuid.UUID,
    actor: Annotated[User, Depends(_oa_or_mgr)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Call/Email communication history for a contact."""
    contact_service = ContactService(db)
    return await contact_service.get_communications(actor, contact_id)

@router.get("/{contact_id}/attachments", response_model=List[ContactAttachmentResponse])
async def list_contact_attachments(
    contact_id: uuid.UUID,
    actor: Annotated[User, Depends(_oa_or_mgr)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """List files attached to a contact."""
    contact_service = ContactService(db)
    return await contact_service.list_attachments(actor, contact_id)

@router.post("/{contact_id}/attachments", response_model=ContactAttachmentResponse, status_code=status.HTTP_201_CREATED)
async def upload_contact_attachment(
    contact_id: uuid.UUID,
    actor: Annotated[User, Depends(_oa_or_mgr)],
    db: Annotated[AsyncSession, Depends(get_db)],
    file: UploadFile = File(...)
):
    """Attach a file (pdf/image/csv/xlsx/docx, max 5MB) to a contact."""
    MAX_UPLOAD = 5 * 1024 * 1024
    content = await file.read(MAX_UPLOAD + 1)
    if len(content) > MAX_UPLOAD:
        raise HTTPException(status_code=400, detail="File exceeds the limit of 5.0MB")
    contact_service = ContactService(db)
    return await contact_service.add_attachment(actor, contact_id, content, file.filename or "attachment")

@router.delete("/{contact_id}/attachments/{stored_name}")
async def delete_contact_attachment(
    contact_id: uuid.UUID,
    stored_name: str,
    actor: Annotated[User, Depends(_oa_or_mgr)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Remove a file attached to a contact."""
    contact_service = ContactService(db)
    return await contact_service.delete_attachment(actor, contact_id, stored_name)

@router.get("/{contact_id}/relationships", response_model=List[ContactRelationshipResponse])
async def list_contact_relationships(
    contact_id: uuid.UUID,
    actor: Annotated[User, Depends(_oa_or_mgr)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """List other contacts related to this one."""
    contact_service = ContactService(db)
    return await contact_service.list_relationships(actor, contact_id)

@router.post("/{contact_id}/relationships", response_model=ContactRelationshipResponse, status_code=status.HTTP_201_CREATED)
async def add_contact_relationship(
    contact_id: uuid.UUID,
    req: ContactRelationshipCreate,
    actor: Annotated[User, Depends(_oa_or_mgr)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Link this contact to another (e.g. reports_to, colleague)."""
    contact_service = ContactService(db)
    return await contact_service.add_relationship(actor, contact_id, req.related_contact_id, req.relationship_type)

@router.delete("/{contact_id}/relationships/{relationship_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_contact_relationship(
    contact_id: uuid.UUID,
    relationship_id: uuid.UUID,
    actor: Annotated[User, Depends(_oa_or_mgr)],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    """Remove a contact relationship."""
    contact_service = ContactService(db)
    await contact_service.delete_relationship(actor, contact_id, relationship_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
