import uuid
from typing import Annotated
from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User
from app.middleware.permissions import require_active_user
from app.services.knowledge_base_service import KnowledgeBaseService
from app.schemas.knowledge_base import (
    CategoryCreate, CategoryUpdate, ArticleCreate, ArticleUpdate, ReviewRequest,
    FeedbackRequest, SearchRequest, RetrieveRequest, AskRequest,
)

router = APIRouter()


def _svc(db):
    return KnowledgeBaseService(db)


@router.get("/dashboard")
async def dashboard(actor: Annotated[User, Depends(require_active_user)],
                    db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).dashboard(actor)


@router.get("/export", response_class=PlainTextResponse)
async def export_csv(actor: Annotated[User, Depends(require_active_user)],
                     db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).export_csv(actor)


# ---------- categories ----------
@router.get("/categories")
async def list_categories(actor: Annotated[User, Depends(require_active_user)],
                          db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).list_categories(actor)


@router.post("/categories", status_code=201)
async def create_category(req: CategoryCreate, actor: Annotated[User, Depends(require_active_user)],
                          db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).create_category(actor, req.model_dump())


@router.patch("/categories/{category_id}")
async def update_category(category_id: uuid.UUID, req: CategoryUpdate,
                          actor: Annotated[User, Depends(require_active_user)],
                          db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).update_category(actor, category_id, req.model_dump(exclude_unset=True))


@router.delete("/categories/{category_id}")
async def delete_category(category_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)],
                          db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).delete_category(actor, category_id)


# ---------- articles ----------
@router.get("/articles")
async def list_articles(actor: Annotated[User, Depends(require_active_user)],
                        db: Annotated[AsyncSession, Depends(get_db)],
                        q: str | None = Query(None), status: str | None = Query(None),
                        article_type: str | None = Query(None),
                        category_id: uuid.UUID | None = Query(None),
                        tag: str | None = Query(None),
                        limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0)):
    return await _svc(db).list_articles(actor, q=q, status_f=status, article_type=article_type,
                                        category_id=category_id, tag=tag, limit=limit, offset=offset)


@router.post("/articles", status_code=201)
async def create_article(req: ArticleCreate, actor: Annotated[User, Depends(require_active_user)],
                         db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).create_article(actor, req.model_dump())


@router.get("/articles/{article_id}")
async def get_article(article_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)],
                      db: Annotated[AsyncSession, Depends(get_db)],
                      record_view: bool = Query(True)):
    return await _svc(db).get_article(actor, article_id, record_view=record_view)


@router.patch("/articles/{article_id}")
async def update_article(article_id: uuid.UUID, req: ArticleUpdate,
                         actor: Annotated[User, Depends(require_active_user)],
                         db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).update_article(actor, article_id, req.model_dump(exclude_unset=True))


@router.delete("/articles/{article_id}")
async def delete_article(article_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)],
                         db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).delete_article(actor, article_id)


@router.get("/articles/{article_id}/versions")
async def list_versions(article_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)],
                        db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).list_versions(actor, article_id)


@router.post("/articles/{article_id}/versions/{version}/restore")
async def restore_version(article_id: uuid.UUID, version: int,
                          actor: Annotated[User, Depends(require_active_user)],
                          db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).restore_version(actor, article_id, version)


# ---------- approval workflow ----------
@router.post("/articles/{article_id}/submit")
async def submit_for_review(article_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)],
                            db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).submit_for_review(actor, article_id)


@router.post("/articles/{article_id}/approve")
async def approve_article(article_id: uuid.UUID, req: ReviewRequest,
                          actor: Annotated[User, Depends(require_active_user)],
                          db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).approve_article(actor, article_id, req.note)


@router.post("/articles/{article_id}/reject")
async def reject_article(article_id: uuid.UUID, req: ReviewRequest,
                         actor: Annotated[User, Depends(require_active_user)],
                         db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).reject_article(actor, article_id, req.note)


@router.post("/articles/{article_id}/archive")
async def archive_article(article_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)],
                          db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).archive_article(actor, article_id)


@router.post("/articles/{article_id}/feedback")
async def feedback(article_id: uuid.UUID, req: FeedbackRequest,
                   actor: Annotated[User, Depends(require_active_user)],
                   db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).feedback(actor, article_id, req.helpful, req.comment)


# ---------- FAQ ----------
@router.get("/faq")
async def faq(actor: Annotated[User, Depends(require_active_user)],
              db: Annotated[AsyncSession, Depends(get_db)],
              category_id: uuid.UUID | None = Query(None)):
    return await _svc(db).faq(actor, category_id)


# ---------- search / retrieval / RAG ----------
@router.post("/search")
async def search(req: SearchRequest, actor: Annotated[User, Depends(require_active_user)],
                 db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).search(actor, req.query, limit=req.limit, article_type=req.article_type)


@router.post("/retrieve")
async def retrieve(req: RetrieveRequest, actor: Annotated[User, Depends(require_active_user)],
                   db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).retrieve(actor, req.query, limit=req.limit, max_chars=req.max_chars)


@router.post("/ask")
async def ask(req: AskRequest, actor: Annotated[User, Depends(require_active_user)],
              db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).ask(actor, req.question)


@router.post("/reindex")
async def reindex(actor: Annotated[User, Depends(require_active_user)],
                  db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).reindex_all(actor)
