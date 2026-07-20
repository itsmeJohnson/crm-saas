import uuid
from typing import Annotated
from fastapi import APIRouter, Depends, Query, UploadFile, File, Form
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User
from app.middleware.permissions import require_active_user
from app.services.document_intelligence_service import DocumentIntelligenceService, capabilities
from app.schemas.document_intelligence import ProcessTextRequest, DocSearchRequest, SummarizeDocRequest

router = APIRouter()


def _svc(db):
    return DocumentIntelligenceService(db)


@router.get("/capabilities")
async def get_capabilities(actor: Annotated[User, Depends(require_active_user)]):
    return capabilities()


@router.get("/dashboard")
async def dashboard(actor: Annotated[User, Depends(require_active_user)],
                    db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).dashboard(actor)


@router.get("/export", response_class=PlainTextResponse)
async def export_csv(actor: Annotated[User, Depends(require_active_user)],
                     db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).export_csv(actor)


@router.post("/upload", status_code=201)
async def upload(actor: Annotated[User, Depends(require_active_user)],
                 db: Annotated[AsyncSession, Depends(get_db)],
                 file: UploadFile = File(...),
                 context_type: str | None = Form(None),
                 context_id: uuid.UUID | None = Form(None)):
    content = await file.read()
    return await _svc(db).process_bytes(actor, file.filename or "file", content,
                                        content_type=file.content_type, source="upload",
                                        context_type=context_type, context_id=context_id)


@router.post("/process-text", status_code=201)
async def process_text(req: ProcessTextRequest, actor: Annotated[User, Depends(require_active_user)],
                       db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).process_text(actor, req.text, filename=req.filename,
                                       context_type=req.context_type, context_id=req.context_id)


@router.get("/documents")
async def list_documents(actor: Annotated[User, Depends(require_active_user)],
                         db: Annotated[AsyncSession, Depends(get_db)],
                         doc_type: str | None = Query(None), status: str | None = Query(None),
                         q: str | None = Query(None),
                         context_type: str | None = Query(None),
                         context_id: uuid.UUID | None = Query(None),
                         limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0)):
    return await _svc(db).list_documents(actor, doc_type=doc_type, status_f=status, q=q,
                                         context_type=context_type, context_id=context_id,
                                         limit=limit, offset=offset)


@router.get("/documents/{doc_id}")
async def get_document(doc_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)],
                       db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).get_document(actor, doc_id)


@router.delete("/documents/{doc_id}")
async def delete_document(doc_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)],
                          db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).delete_document(actor, doc_id)


@router.post("/documents/{doc_id}/reprocess")
async def reprocess(doc_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)],
                    db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).reprocess(actor, doc_id)


@router.post("/documents/{doc_id}/summarize")
async def summarize(doc_id: uuid.UUID, req: SummarizeDocRequest,
                    actor: Annotated[User, Depends(require_active_user)],
                    db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).summarize(actor, doc_id, length=req.length)


@router.post("/search")
async def search(req: DocSearchRequest, actor: Annotated[User, Depends(require_active_user)],
                 db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).search(actor, req.query, doc_type=req.doc_type, limit=req.limit)
