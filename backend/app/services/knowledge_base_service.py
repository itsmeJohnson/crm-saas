"""AI Knowledge Base — knowledge repository, FAQ, document indexing,
embedding pipeline, vector/semantic search, RAG context retrieval,
categories, versioning, approval workflow and knowledge analytics.

Embedding pipeline (hash_embed_v1): deterministic 256-dim feature-hashed
term-frequency vectors, L2-normalized. Offline-safe and provider-agnostic;
every chunk is tagged with its embedding_model so a provider-backed embedder
can be introduced later without a schema change. Generated answers always go
through AIGatewayService (multi-provider gateway) — never a provider directly.
"""
import csv
import hashlib
import io
import math
import re
import uuid
from datetime import datetime, timezone, timedelta

from fastapi import HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.knowledge_base import KBCategory, KBArticle, KBArticleVersion, KBChunk, KBEvent
from app.services.audit_service import AuditService

EMBED_DIM = 256
EMBED_MODEL = "hash_embed_v1"
ARTICLE_TYPES = ("article", "faq", "document")
STATUSES = ("draft", "pending_review", "published", "rejected", "archived")
VISIBILITIES = ("all", "managers", "admins")
MANAGER_ROLES = ("SuperAdmin", "OrgAdmin", "Manager")

STOPWORDS = {
    "the", "and", "for", "are", "was", "were", "with", "that", "this", "from",
    "have", "has", "had", "not", "but", "you", "your", "our", "their", "they",
    "them", "its", "can", "will", "would", "should", "could", "about", "into",
    "how", "what", "when", "where", "which", "who", "why", "does", "did", "get",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt):
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _tokenize(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9]{2,}", (text or "").lower()) if t not in STOPWORDS]


def embed_text(text: str) -> list[float]:
    """Deterministic feature-hashed TF embedding: each token is hashed into one
    of EMBED_DIM buckets with weight 1+log(tf), then the vector is L2-normalized."""
    tf: dict[str, int] = {}
    for tok in _tokenize(text):
        tf[tok] = tf.get(tok, 0) + 1
    vec = [0.0] * EMBED_DIM
    for tok, count in tf.items():
        idx = int(hashlib.md5(tok.encode()).hexdigest(), 16) % EMBED_DIM
        vec[idx] += 1.0 + math.log(count)
    norm = math.sqrt(sum(v * v for v in vec))
    if norm > 0:
        vec = [v / norm for v in vec]
    return [round(v, 6) for v in vec]


def cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    return sum(x * y for x, y in zip(a, b))  # vectors are pre-normalized


def chunk_text(text: str, max_chars: int = 900) -> list[str]:
    """Paragraph-preserving chunker: packs paragraphs into ~max_chars chunks,
    hard-splitting any single paragraph longer than max_chars."""
    paras = [p.strip() for p in re.split(r"\n\s*\n", text or "") if p.strip()]
    chunks: list[str] = []
    buf = ""
    for p in paras:
        while len(p) > max_chars:
            if buf:
                chunks.append(buf)
                buf = ""
            chunks.append(p[:max_chars])
            p = p[max_chars:]
        if len(buf) + len(p) + 2 > max_chars and buf:
            chunks.append(buf)
            buf = p
        else:
            buf = f"{buf}\n\n{p}" if buf else p
    if buf:
        chunks.append(buf)
    return chunks


def visible_visibilities(actor: User) -> tuple[str, ...]:
    if actor.role in ("SuperAdmin", "OrgAdmin"):
        return ("all", "managers", "admins")
    if actor.role == "Manager":
        return ("all", "managers")
    return ("all",)


async def retrieve_kb_snippets(db: AsyncSession, actor: User, question: str,
                               limit: int = 6) -> list[dict]:
    """Shared retrieval used by both this module's RAG endpoints and the AI
    gateway's kb_answer grounding: cosine over published, visibility-filtered
    chunks with a keyword-overlap boost."""
    qvec = embed_text(question)
    qtokens = set(_tokenize(question))
    rows = (await db.execute(
        select(KBChunk, KBArticle)
        .join(KBArticle, KBChunk.article_id == KBArticle.id)
        .filter(KBChunk.organization_id == actor.organization_id,
                KBChunk.is_deleted == False,
                KBArticle.is_deleted == False,
                KBArticle.status == "published",
                KBArticle.visibility.in_(visible_visibilities(actor)))
    )).all()
    scored = []
    for chunk, article in rows:
        sim = cosine(qvec, chunk.embedding or [])
        ctokens = set(_tokenize(chunk.content))
        overlap = len(qtokens & ctokens) / max(1, len(qtokens))
        if overlap == 0 and sim < 0.25:
            continue  # hash-bucket collisions alone are not a match
        score = 0.65 * sim + 0.35 * overlap
        if any(t in (article.title or "").lower() for t in qtokens):
            score += 0.15
        if score > 0.05:
            scored.append({"article_id": str(article.id), "title": article.title,
                           "article_type": article.article_type, "chunk_index": chunk.chunk_index,
                           "content": chunk.content, "score": round(score, 4)})
    scored.sort(key=lambda s: s["score"], reverse=True)
    return scored[:limit]


class KnowledgeBaseService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.audit = AuditService(db)

    def _require_manager(self, actor: User):
        if actor.role not in MANAGER_ROLES:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Manager or admin role required")

    async def _get_article(self, actor: User, article_id: uuid.UUID) -> KBArticle:
        a = (await self.db.execute(select(KBArticle).filter(
            KBArticle.id == article_id,
            KBArticle.organization_id == actor.organization_id,
            KBArticle.is_deleted == False))).scalars().first()
        if not a:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Article not found")
        if a.visibility not in visible_visibilities(actor) and a.created_by != actor.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="You cannot view this article")
        return a

    def _can_edit(self, actor: User, article: KBArticle) -> bool:
        return actor.role in MANAGER_ROLES or article.created_by == actor.id

    async def _log(self, actor: User, event_type: str, *, article_id=None, query=None,
                   results_count=None, helpful=None, meta=None):
        self.db.add(KBEvent(organization_id=actor.organization_id, user_id=actor.id,
                            event_type=event_type, article_id=article_id, query=query,
                            results_count=results_count, helpful=helpful,
                            event_metadata=meta or {}))
        await self.db.flush()

    # ---------- categories ----------
    async def list_categories(self, actor: User) -> list[dict]:
        cats = (await self.db.execute(select(KBCategory).filter(
            KBCategory.organization_id == actor.organization_id,
            KBCategory.is_deleted == False).order_by(KBCategory.display_order, KBCategory.name)
        )).scalars().all()
        counts = dict((await self.db.execute(
            select(KBArticle.category_id, func.count(KBArticle.id))
            .filter(KBArticle.organization_id == actor.organization_id,
                    KBArticle.is_deleted == False)
            .group_by(KBArticle.category_id))).all())
        return [{"id": str(c.id), "name": c.name, "description": c.description,
                 "parent_id": str(c.parent_id) if c.parent_id else None,
                 "display_order": c.display_order,
                 "article_count": int(counts.get(c.id, 0))} for c in cats]

    async def create_category(self, actor: User, data: dict) -> dict:
        self._require_manager(actor)
        name = (data.get("name") or "").strip()
        if not name:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="name is required")
        dup = (await self.db.execute(select(KBCategory).filter(
            KBCategory.organization_id == actor.organization_id,
            KBCategory.name == name, KBCategory.is_deleted == False))).scalars().first()
        if dup:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"Category '{name}' already exists")
        parent_id = data.get("parent_id")
        if parent_id:
            parent = (await self.db.execute(select(KBCategory).filter(
                KBCategory.id == parent_id,
                KBCategory.organization_id == actor.organization_id,
                KBCategory.is_deleted == False))).scalars().first()
            if not parent:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Parent category not found")
        cat = KBCategory(organization_id=actor.organization_id, name=name,
                         description=data.get("description"), parent_id=parent_id,
                         display_order=int(data.get("display_order") or 0), created_by=actor.id)
        self.db.add(cat)
        await self.db.commit()
        await self.db.refresh(cat)
        return {"id": str(cat.id), "name": cat.name}

    async def update_category(self, actor: User, category_id: uuid.UUID, data: dict) -> dict:
        self._require_manager(actor)
        cat = (await self.db.execute(select(KBCategory).filter(
            KBCategory.id == category_id, KBCategory.organization_id == actor.organization_id,
            KBCategory.is_deleted == False))).scalars().first()
        if not cat:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
        if data.get("name"):
            cat.name = data["name"].strip()
        if "description" in data:
            cat.description = data["description"]
        if "display_order" in data and data["display_order"] is not None:
            cat.display_order = int(data["display_order"])
        if "parent_id" in data:
            pid = data["parent_id"]
            if pid and uuid.UUID(str(pid)) == cat.id:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                    detail="Category cannot be its own parent")
            cat.parent_id = pid
        await self.db.commit()
        return {"id": str(cat.id), "name": cat.name}

    async def delete_category(self, actor: User, category_id: uuid.UUID) -> dict:
        self._require_manager(actor)
        cat = (await self.db.execute(select(KBCategory).filter(
            KBCategory.id == category_id, KBCategory.organization_id == actor.organization_id,
            KBCategory.is_deleted == False))).scalars().first()
        if not cat:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
        children = (await self.db.execute(select(func.count(KBCategory.id)).filter(
            KBCategory.parent_id == cat.id, KBCategory.is_deleted == False))).scalar() or 0
        arts = (await self.db.execute(select(func.count(KBArticle.id)).filter(
            KBArticle.category_id == cat.id, KBArticle.is_deleted == False))).scalar() or 0
        if children or arts:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Category has sub-categories or articles; move them first")
        cat.is_deleted = True
        cat.deleted_at = _now()
        await self.db.commit()
        return {"deleted": True}

    # ---------- indexing (document/embedding pipeline) ----------
    async def index_article(self, article: KBArticle) -> int:
        """(Re)build the embedding index for one article: chunk title+content,
        embed each chunk, replace previous chunks."""
        old = (await self.db.execute(select(KBChunk).filter(
            KBChunk.article_id == article.id))).scalars().all()
        for c in old:
            await self.db.delete(c)
        chunks = chunk_text(f"{article.title}\n\n{article.content}")
        for i, text in enumerate(chunks):
            self.db.add(KBChunk(organization_id=article.organization_id, article_id=article.id,
                                chunk_index=i, content=text, embedding=embed_text(text),
                                embedding_model=EMBED_MODEL, token_count=len(_tokenize(text))))
        article.is_indexed = True
        article.indexed_at = _now()
        article.chunk_count = len(chunks)
        await self.db.flush()
        return len(chunks)

    async def reindex_all(self, actor: User) -> dict:
        self._require_manager(actor)
        arts = (await self.db.execute(select(KBArticle).filter(
            KBArticle.organization_id == actor.organization_id,
            KBArticle.is_deleted == False))).scalars().all()
        total_chunks = 0
        for a in arts:
            total_chunks += await self.index_article(a)
        await self.db.commit()
        return {"articles": len(arts), "chunks": total_chunks, "embedding_model": EMBED_MODEL}

    # ---------- articles (repository + versioning + approval) ----------
    async def create_article(self, actor: User, data: dict) -> dict:
        title = (data.get("title") or "").strip()
        content = (data.get("content") or "").strip()
        if not title or not content:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="title and content are required")
        article_type = data.get("article_type") or "article"
        if article_type not in ARTICLE_TYPES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"article_type must be one of {list(ARTICLE_TYPES)}")
        visibility = data.get("visibility") or "all"
        if visibility not in VISIBILITIES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"visibility must be one of {list(VISIBILITIES)}")
        category_id = data.get("category_id")
        if category_id:
            cat = (await self.db.execute(select(KBCategory).filter(
                KBCategory.id == category_id,
                KBCategory.organization_id == actor.organization_id,
                KBCategory.is_deleted == False))).scalars().first()
            if not cat:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Category not found")
        a = KBArticle(organization_id=actor.organization_id, title=title, content=content,
                      summary=data.get("summary"), article_type=article_type, status="draft",
                      category_id=category_id, tags=list(data.get("tags") or []),
                      visibility=visibility, language=data.get("language") or "en",
                      source_filename=data.get("source_filename"), created_by=actor.id)
        self.db.add(a)
        await self.db.flush()
        await self.index_article(a)
        await self.db.commit()
        await self.db.refresh(a)
        return self._article_dict(a)

    async def update_article(self, actor: User, article_id: uuid.UUID, data: dict) -> dict:
        a = await self._get_article(actor, article_id)
        if not self._can_edit(actor, a):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Only the author or a manager can edit this article")
        content_change = any(k in data and data[k] is not None and getattr(a, k) != data[k]
                             for k in ("title", "content", "summary"))
        if content_change:
            self.db.add(KBArticleVersion(article_id=a.id, version=a.version, title=a.title,
                                         content=a.content, summary=a.summary, edited_by=actor.id,
                                         change_note=data.get("change_note")))
            a.version += 1
        for field in ("title", "content", "summary", "language", "source_filename"):
            if data.get(field) is not None:
                setattr(a, field, data[field])
        if data.get("article_type"):
            if data["article_type"] not in ARTICLE_TYPES:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                    detail=f"article_type must be one of {list(ARTICLE_TYPES)}")
            a.article_type = data["article_type"]
        if data.get("visibility"):
            if data["visibility"] not in VISIBILITIES:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                    detail=f"visibility must be one of {list(VISIBILITIES)}")
            a.visibility = data["visibility"]
        if "tags" in data and data["tags"] is not None:
            a.tags = list(data["tags"])
        if "category_id" in data:
            a.category_id = data["category_id"]
        a.updated_by = actor.id
        if content_change:
            await self.index_article(a)
        await self.db.commit()
        await self.db.refresh(a)
        return self._article_dict(a)

    async def delete_article(self, actor: User, article_id: uuid.UUID) -> dict:
        a = await self._get_article(actor, article_id)
        if not self._can_edit(actor, a):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Only the author or a manager can delete this article")
        a.is_deleted = True
        a.deleted_at = _now()
        chunks = (await self.db.execute(select(KBChunk).filter(
            KBChunk.article_id == a.id))).scalars().all()
        for c in chunks:
            c.is_deleted = True
        await self.db.commit()
        return {"deleted": True}

    async def list_articles(self, actor: User, *, q: str | None = None, status_f: str | None = None,
                            article_type: str | None = None, category_id: uuid.UUID | None = None,
                            tag: str | None = None, limit: int = 50, offset: int = 0) -> dict:
        query = select(KBArticle).filter(
            KBArticle.organization_id == actor.organization_id,
            KBArticle.is_deleted == False)
        if actor.role in MANAGER_ROLES:
            query = query.filter(KBArticle.visibility.in_(visible_visibilities(actor)))
        else:
            # employees: published visible-to-all articles plus their own drafts
            query = query.filter(
                ((KBArticle.status == "published") & (KBArticle.visibility == "all"))
                | (KBArticle.created_by == actor.id))
        if status_f:
            query = query.filter(KBArticle.status == status_f)
        if article_type:
            query = query.filter(KBArticle.article_type == article_type)
        if category_id:
            query = query.filter(KBArticle.category_id == category_id)
        if q:
            like = f"%{q}%"
            query = query.filter(KBArticle.title.ilike(like) | KBArticle.content.ilike(like))
        arts = (await self.db.execute(query.order_by(KBArticle.updated_at.desc()))).scalars().all()
        if tag:
            arts = [a for a in arts if tag in (a.tags or [])]
        total = len(arts)
        arts = arts[offset:offset + limit]
        return {"total": total, "items": [self._article_dict(a, include_content=False) for a in arts]}

    async def get_article(self, actor: User, article_id: uuid.UUID, record_view: bool = True) -> dict:
        a = await self._get_article(actor, article_id)
        if record_view:
            a.view_count = (a.view_count or 0) + 1
            await self._log(actor, "view", article_id=a.id)
            await self.db.commit()
            await self.db.refresh(a)
        return self._article_dict(a)

    async def list_versions(self, actor: User, article_id: uuid.UUID) -> list[dict]:
        a = await self._get_article(actor, article_id)
        rows = (await self.db.execute(select(KBArticleVersion).filter(
            KBArticleVersion.article_id == a.id, KBArticleVersion.is_deleted == False)
            .order_by(KBArticleVersion.version.desc()))).scalars().all()
        return [{"version": v.version, "title": v.title, "summary": v.summary,
                 "content": v.content, "edited_by": str(v.edited_by) if v.edited_by else None,
                 "change_note": v.change_note,
                 "created_at": _aware(v.created_at).isoformat() if v.created_at else None}
                for v in rows]

    async def restore_version(self, actor: User, article_id: uuid.UUID, version: int) -> dict:
        a = await self._get_article(actor, article_id)
        if not self._can_edit(actor, a):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Only the author or a manager can restore versions")
        snap = (await self.db.execute(select(KBArticleVersion).filter(
            KBArticleVersion.article_id == a.id, KBArticleVersion.version == version,
            KBArticleVersion.is_deleted == False))).scalars().first()
        if not snap:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Version not found")
        self.db.add(KBArticleVersion(article_id=a.id, version=a.version, title=a.title,
                                     content=a.content, summary=a.summary, edited_by=actor.id,
                                     change_note=f"snapshot before restoring v{version}"))
        a.version += 1
        a.title, a.content, a.summary = snap.title, snap.content, snap.summary
        a.updated_by = actor.id
        await self.index_article(a)
        await self.db.commit()
        await self.db.refresh(a)
        return self._article_dict(a)

    # ---------- approval workflow ----------
    async def submit_for_review(self, actor: User, article_id: uuid.UUID) -> dict:
        a = await self._get_article(actor, article_id)
        if not self._can_edit(actor, a):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Only the author or a manager can submit this article")
        if a.status not in ("draft", "rejected"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"Cannot submit an article in status '{a.status}'")
        a.status = "pending_review"
        await self.db.commit()
        return {"id": str(a.id), "status": a.status}

    async def approve_article(self, actor: User, article_id: uuid.UUID, note: str | None = None) -> dict:
        self._require_manager(actor)
        a = await self._get_article(actor, article_id)
        if a.status not in ("draft", "pending_review"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"Cannot approve an article in status '{a.status}'")
        a.status = "published"
        a.reviewed_by = actor.id
        a.reviewed_at = _now()
        a.review_note = note
        a.published_at = _now()
        if not a.is_indexed:
            await self.index_article(a)
        await self.audit.log_event(actor.organization_id, actor_user_id=actor.id,
                                   action="KB_ARTICLE_PUBLISHED", resource_type="knowledge",
                                   resource_id=str(a.id), action_metadata={"title": a.title})
        await self.db.commit()
        return {"id": str(a.id), "status": a.status}

    async def reject_article(self, actor: User, article_id: uuid.UUID, note: str | None = None) -> dict:
        self._require_manager(actor)
        a = await self._get_article(actor, article_id)
        if a.status != "pending_review":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"Cannot reject an article in status '{a.status}'")
        a.status = "rejected"
        a.reviewed_by = actor.id
        a.reviewed_at = _now()
        a.review_note = note
        await self.audit.log_event(actor.organization_id, actor_user_id=actor.id,
                                   action="KB_ARTICLE_REJECTED", resource_type="knowledge",
                                   resource_id=str(a.id), action_metadata={"title": a.title, "note": note})
        await self.db.commit()
        return {"id": str(a.id), "status": a.status}

    async def archive_article(self, actor: User, article_id: uuid.UUID) -> dict:
        a = await self._get_article(actor, article_id)
        if not self._can_edit(actor, a):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Only the author or a manager can archive this article")
        a.status = "archived"
        await self.db.commit()
        return {"id": str(a.id), "status": a.status}

    # ---------- FAQ ----------
    async def faq(self, actor: User, category_id: uuid.UUID | None = None) -> list[dict]:
        query = select(KBArticle).filter(
            KBArticle.organization_id == actor.organization_id,
            KBArticle.is_deleted == False, KBArticle.article_type == "faq",
            KBArticle.status == "published",
            KBArticle.visibility.in_(visible_visibilities(actor)))
        if category_id:
            query = query.filter(KBArticle.category_id == category_id)
        rows = (await self.db.execute(query.order_by(KBArticle.view_count.desc()))).scalars().all()
        cats = {c["id"]: c["name"] for c in await self.list_categories(actor)}
        return [{"id": str(a.id), "question": a.title, "answer": a.content,
                 "category": cats.get(str(a.category_id)) if a.category_id else None,
                 "views": a.view_count, "helpful": a.helpful_count} for a in rows]

    # ---------- search / retrieval / RAG ----------
    async def search(self, actor: User, query: str, *, limit: int = 10,
                     article_type: str | None = None, log: bool = True) -> dict:
        snippets = await retrieve_kb_snippets(self.db, actor, query, limit=max(limit * 3, 20))
        if article_type:
            snippets = [s for s in snippets if s["article_type"] == article_type]
        best: dict[str, dict] = {}
        for s in snippets:
            cur = best.get(s["article_id"])
            if not cur or s["score"] > cur["score"]:
                best[s["article_id"]] = s
        results = sorted(best.values(), key=lambda s: s["score"], reverse=True)[:limit]
        out = [{"article_id": s["article_id"], "title": s["title"],
                "article_type": s["article_type"], "score": s["score"],
                "excerpt": s["content"][:300]} for s in results]
        if log:
            await self._log(actor, "search", query=query, results_count=len(out))
            await self.db.commit()
        return {"query": query, "results": out, "count": len(out),
                "embedding_model": EMBED_MODEL, "search_type": "semantic_hybrid"}

    async def retrieve(self, actor: User, query: str, *, limit: int = 8,
                       max_chars: int = 4000) -> dict:
        """Context Retrieval: the RAG-ready envelope — ranked chunks plus a
        single concatenated context string budgeted to max_chars."""
        snippets = await retrieve_kb_snippets(self.db, actor, query, limit=limit)
        parts, used = [], 0
        for s in snippets:
            block = f"[{s['title']}] {s['content']}"
            if used + len(block) > max_chars:
                block = block[:max_chars - used]
            parts.append(block)
            used += len(block)
            if used >= max_chars:
                break
        return {"query": query, "chunks": snippets, "context": "\n\n".join(parts),
                "embedding_model": EMBED_MODEL, "rag_ready": True}

    async def ask(self, actor: User, question: str) -> dict:
        """RAG answer: retrieve KB context, then generate through the AI
        gateway (kb_answer prompt template). Falls back to the gateway's
        legacy notes/templates grounding when the KB has no matching content."""
        from app.services.ai_gateway_service import AIGatewayService
        gateway = AIGatewayService(self.db)
        retrieval = await self.retrieve(actor, question)
        sources = [{"article_id": s["article_id"], "title": s["title"], "score": s["score"]}
                   for s in retrieval["chunks"]]
        # de-duplicate sources per article, keep best score order
        seen, uniq = set(), []
        for s in sources:
            if s["article_id"] not in seen:
                seen.add(s["article_id"])
                uniq.append(s)
        if retrieval["chunks"]:
            out = await gateway.generate(actor, task_type="knowledge", template_key="kb_answer",
                                         variables={"question": question,
                                                    "snippets": retrieval["context"]})
        else:
            out = await gateway.kb_answer(actor, question)
        await self._log(actor, "ask", query=question, results_count=len(uniq),
                        article_id=uuid.UUID(uniq[0]["article_id"]) if uniq else None)
        await self.db.commit()
        return {"question": question, "answer": out.get("text"), "model": out.get("model"),
                "provider": out.get("provider"), "cached": out.get("cached", False),
                "grounded": bool(retrieval["chunks"]), "sources": uniq,
                "tokens": out.get("tokens"), "embedding_model": EMBED_MODEL}

    async def feedback(self, actor: User, article_id: uuid.UUID, helpful: bool,
                       comment: str | None = None) -> dict:
        a = await self._get_article(actor, article_id)
        if helpful:
            a.helpful_count = (a.helpful_count or 0) + 1
        else:
            a.not_helpful_count = (a.not_helpful_count or 0) + 1
        await self._log(actor, "feedback", article_id=a.id, helpful=helpful,
                        meta={"comment": comment} if comment else None)
        await self.db.commit()
        return {"id": str(a.id), "helpful_count": a.helpful_count,
                "not_helpful_count": a.not_helpful_count}

    # ---------- analytics / dashboard ----------
    async def dashboard(self, actor: User) -> dict:
        org = actor.organization_id
        arts = (await self.db.execute(select(KBArticle).filter(
            KBArticle.organization_id == org, KBArticle.is_deleted == False))).scalars().all()
        by_status: dict[str, int] = {}
        by_type: dict[str, int] = {}
        indexed = helpful = not_helpful = views = 0
        for a in arts:
            by_status[a.status] = by_status.get(a.status, 0) + 1
            by_type[a.article_type] = by_type.get(a.article_type, 0) + 1
            indexed += 1 if a.is_indexed else 0
            helpful += a.helpful_count or 0
            not_helpful += a.not_helpful_count or 0
            views += a.view_count or 0
        chunks = (await self.db.execute(select(func.count(KBChunk.id)).filter(
            KBChunk.organization_id == org, KBChunk.is_deleted == False))).scalar() or 0
        cats = (await self.db.execute(select(func.count(KBCategory.id)).filter(
            KBCategory.organization_id == org, KBCategory.is_deleted == False))).scalar() or 0

        cutoff = _now() - timedelta(days=30)
        events = (await self.db.execute(select(KBEvent).filter(
            KBEvent.organization_id == org, KBEvent.is_deleted == False)
            .order_by(KBEvent.created_at.desc()).limit(2000))).scalars().all()
        recent = [e for e in events if e.created_at and _aware(e.created_at) >= cutoff]
        events_30d: dict[str, int] = {}
        for e in recent:
            events_30d[e.event_type] = events_30d.get(e.event_type, 0) + 1
        searches = [e for e in recent if e.event_type in ("search", "ask")]
        zero_result = {}
        for e in searches:
            if (e.results_count or 0) == 0 and e.query:
                zero_result[e.query] = zero_result.get(e.query, 0) + 1
        top_zero = sorted(zero_result.items(), key=lambda kv: kv[1], reverse=True)[:10]

        top_articles = sorted([a for a in arts if a.status == "published"],
                              key=lambda a: a.view_count or 0, reverse=True)[:5]
        rated = helpful + not_helpful
        return {
            "totals": {"articles": len(arts), "by_status": by_status, "by_type": by_type,
                       "categories": int(cats), "chunks": int(chunks),
                       "indexed": indexed,
                       "indexed_pct": round(indexed * 100 / len(arts), 1) if arts else 0.0,
                       "total_views": views},
            "helpful_rate": round(helpful * 100 / rated, 1) if rated else None,
            "events_30d": events_30d,
            "recent_searches": [{"query": e.query, "results": e.results_count,
                                 "type": e.event_type,
                                 "at": _aware(e.created_at).isoformat() if e.created_at else None}
                                for e in searches[:10]],
            "unanswered_queries": [{"query": q, "count": n} for q, n in top_zero],
            "top_articles": [{"id": str(a.id), "title": a.title, "views": a.view_count,
                              "helpful": a.helpful_count} for a in top_articles],
            "embedding_model": EMBED_MODEL,
        }

    async def export_csv(self, actor: User) -> str:
        self._require_manager(actor)
        arts = (await self.db.execute(select(KBArticle).filter(
            KBArticle.organization_id == actor.organization_id,
            KBArticle.is_deleted == False).order_by(KBArticle.created_at))).scalars().all()
        cats = {c["id"]: c["name"] for c in await self.list_categories(actor)}
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["id", "title", "type", "status", "category", "visibility", "version",
                    "views", "helpful", "not_helpful", "chunks", "created_at"])
        for a in arts:
            w.writerow([str(a.id), a.title, a.article_type, a.status,
                        cats.get(str(a.category_id), "") if a.category_id else "",
                        a.visibility, a.version, a.view_count, a.helpful_count,
                        a.not_helpful_count, a.chunk_count,
                        _aware(a.created_at).isoformat() if a.created_at else ""])
        await self.audit.log_event(actor.organization_id, actor_user_id=actor.id,
                                   action="KB_EXPORTED", resource_type="knowledge",
                                   action_metadata={"rows": len(arts)})
        await self.db.commit()
        return buf.getvalue()

    # ---------- helpers ----------
    def _article_dict(self, a: KBArticle, include_content: bool = True) -> dict:
        d = {"id": str(a.id), "title": a.title, "summary": a.summary,
             "article_type": a.article_type, "status": a.status,
             "category_id": str(a.category_id) if a.category_id else None,
             "tags": a.tags or [], "visibility": a.visibility, "language": a.language,
             "source_filename": a.source_filename, "version": a.version,
             "created_by": str(a.created_by) if a.created_by else None,
             "reviewed_by": str(a.reviewed_by) if a.reviewed_by else None,
             "review_note": a.review_note,
             "published_at": _aware(a.published_at).isoformat() if a.published_at else None,
             "is_indexed": a.is_indexed, "chunk_count": a.chunk_count,
             "view_count": a.view_count, "helpful_count": a.helpful_count,
             "not_helpful_count": a.not_helpful_count,
             "created_at": _aware(a.created_at).isoformat() if a.created_at else None,
             "updated_at": _aware(a.updated_at).isoformat() if a.updated_at else None}
        if include_content:
            d["content"] = a.content
        return d
