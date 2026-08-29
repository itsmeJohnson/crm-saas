"""Website Engine — landing pages + lead-capture forms.

A tenant builds public landing pages; each is served (unauthenticated) at
``/lp/<slug>`` and its form submission creates a Lead in the tenant's org with
UTM attribution stored on the lead's ``custom_fields``. The number of pages a
tenant may create is capped by their plan's ``website_limit``.
"""
import re
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.lead import Lead
from app.models.plan import Plan
from app.models.tenant_subscription import TenantSubscription
from app.models.landing_page import LandingPage
from app.services.audit_service import AuditService

_DEFAULT_FORM_FIELDS = [
    {"key": "name", "label": "Full Name", "type": "text", "required": True},
    {"key": "email", "label": "Email", "type": "email", "required": False},
    {"key": "phone", "label": "Phone", "type": "tel", "required": True},
    {"key": "message", "label": "Message", "type": "textarea", "required": False},
]


def _slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return s or f"page-{uuid.uuid4().hex[:6]}"


def _split_name(full: str | None) -> tuple[str | None, str]:
    parts = (full or "").strip().split()
    if not parts:
        return None, "Lead"
    if len(parts) == 1:
        return None, parts[0]
    return parts[0], " ".join(parts[1:])


class LandingPageService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.audit = AuditService(db)

    # ---------- plan limit ----------
    async def _website_limit(self, org_id: uuid.UUID) -> int:
        sub = (await self.db.execute(select(TenantSubscription).where(
            TenantSubscription.organization_id == org_id,
            TenantSubscription.is_deleted == False))).scalars().first()
        if not sub:
            return 1
        plan = (await self.db.execute(select(Plan).where(Plan.id == sub.plan_id))).scalars().first()
        return int(getattr(plan, "website_limit", 1) or 1) if plan else 1

    async def _count(self, org_id: uuid.UUID) -> int:
        return (await self.db.execute(select(func.count(LandingPage.id)).where(
            LandingPage.organization_id == org_id, LandingPage.is_deleted == False))).scalar() or 0

    async def _unique_slug(self, base: str) -> str:
        slug = _slugify(base)
        n = 0
        while True:
            candidate = slug if n == 0 else f"{slug}-{n}"
            exists = (await self.db.execute(select(LandingPage.id).where(
                LandingPage.slug == candidate, LandingPage.is_deleted == False))).scalars().first()
            if not exists:
                return candidate
            n += 1

    # ---------- CRUD (tenant) ----------
    async def list(self, actor: User) -> list[dict]:
        rows = (await self.db.execute(select(LandingPage).where(
            LandingPage.organization_id == actor.organization_id, LandingPage.is_deleted == False
        ).order_by(LandingPage.created_at.desc()))).scalars().all()
        limit = await self._website_limit(actor.organization_id)
        return {"items": [self._item(r) for r in rows], "count": len(rows), "website_limit": limit}

    async def create(self, actor: User, data: dict) -> dict:
        if actor.role not in ("SuperAdmin", "OrgAdmin", "Manager"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to create landing pages.")
        limit = await self._website_limit(actor.organization_id)
        if actor.role != "SuperAdmin" and await self._count(actor.organization_id) >= limit:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail=f"Your plan allows {limit} website(s). Upgrade to add more.")
        name = (data.get("name") or "Landing Page").strip()[:150]
        slug = await self._unique_slug(data.get("slug") or name)
        config = data.get("config") or {}
        config.setdefault("form_fields", _DEFAULT_FORM_FIELDS)
        page = LandingPage(
            organization_id=actor.organization_id, name=name, slug=slug, config=config,
            is_published=bool(data.get("is_published")),
            owner_user_id=data.get("owner_user_id") or actor.id, created_by=actor.id,
            published_at=datetime.now(timezone.utc) if data.get("is_published") else None,
        )
        self.db.add(page)
        await self.db.flush()
        await self.audit.log_event(organization_id=actor.organization_id, actor_user_id=actor.id,
                                   action="LANDING_PAGE_CREATED", resource_type="landing_page",
                                   resource_id=str(page.id), action_metadata={"slug": slug})
        return self._item(page)

    async def _get(self, actor: User, page_id: uuid.UUID) -> LandingPage:
        page = (await self.db.execute(select(LandingPage).where(
            LandingPage.id == page_id, LandingPage.organization_id == actor.organization_id,
            LandingPage.is_deleted == False))).scalars().first()
        if not page:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Landing page not found.")
        return page

    async def get(self, actor: User, page_id: uuid.UUID) -> dict:
        return self._item(await self._get(actor, page_id), full=True)

    async def update(self, actor: User, page_id: uuid.UUID, data: dict) -> dict:
        page = await self._get(actor, page_id)
        if "name" in data and data["name"]:
            page.name = data["name"].strip()[:150]
        if "config" in data and data["config"] is not None:
            page.config = data["config"]
        if "owner_user_id" in data and data["owner_user_id"]:
            page.owner_user_id = data["owner_user_id"]
        if "is_published" in data:
            page.is_published = bool(data["is_published"])
            page.published_at = datetime.now(timezone.utc) if page.is_published else None
        self.db.add(page)
        await self.db.flush()
        return self._item(page, full=True)

    async def delete(self, actor: User, page_id: uuid.UUID) -> None:
        page = await self._get(actor, page_id)
        page.is_deleted = True
        self.db.add(page)
        await self.db.flush()

    def _item(self, p: LandingPage, full: bool = False) -> dict:
        d = {"id": str(p.id), "name": p.name, "slug": p.slug, "is_published": p.is_published,
             "views": p.views, "submissions": p.submissions, "created_at": p.created_at,
             "owner_user_id": str(p.owner_user_id) if p.owner_user_id else None}
        if full:
            d["config"] = p.config or {}
        return d

    # ---------- Public (no auth) ----------
    async def public_get(self, slug: str) -> dict:
        page = (await self.db.execute(select(LandingPage).where(
            LandingPage.slug == slug, LandingPage.is_published == True,
            LandingPage.is_deleted == False))).scalars().first()
        if not page:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Page not found.")
        page.views = (page.views or 0) + 1
        self.db.add(page)
        await self.db.flush()
        return {"name": page.name, "slug": page.slug, "config": page.config or {"form_fields": _DEFAULT_FORM_FIELDS}}

    async def submit(self, slug: str, form: dict, utm: dict) -> dict:
        page = (await self.db.execute(select(LandingPage).where(
            LandingPage.slug == slug, LandingPage.is_published == True,
            LandingPage.is_deleted == False))).scalars().first()
        if not page:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Page not found.")

        # Resolve an owner (required created_by): the page owner, else any active OrgAdmin.
        owner_id = page.owner_user_id
        if not owner_id:
            owner_id = (await self.db.execute(select(User.id).where(
                User.organization_id == page.organization_id, User.role.in_(["OrgAdmin", "Manager"]),
                User.is_active == True, User.is_deleted == False).limit(1))).scalars().first()
        if not owner_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No CRM owner configured for this page.")

        fn, ln = _split_name(form.get("name") or form.get("full_name") or form.get("first_name"))
        if form.get("last_name"):
            ln = form["last_name"]
        known = {"name", "full_name", "first_name", "last_name", "email", "phone", "message"}
        extra = {k: v for k, v in form.items() if k not in known and v}
        cf = {k: v for k, v in {
            "utm_source": utm.get("utm_source"), "utm_medium": utm.get("utm_medium"),
            "utm_campaign": utm.get("utm_campaign"), "utm_term": utm.get("utm_term"),
            "utm_content": utm.get("utm_content"), "landing_page": page.slug,
            "message": form.get("message"), **extra,
        }.items() if v}

        lead = Lead(
            organization_id=page.organization_id, first_name=fn, last_name=ln or "Lead",
            email=(form.get("email") or None), phone=(form.get("phone") or None),
            title=f"Website Lead - {page.name}"[:255], status="New",
            source=f"Landing Page: {page.name}"[:100],
            assigned_user_id=owner_id, created_by=owner_id, custom_fields=cf or None,
        )
        self.db.add(lead)
        page.submissions = (page.submissions or 0) + 1
        self.db.add(page)
        await self.db.flush()

        # Fire lead-created automation for the owner, best-effort.
        try:
            owner = await self.db.get(User, owner_id)
            if owner:
                from app.services.workflow_service import WorkflowService
                await WorkflowService(self.db).run("lead_created", lead, owner)
        except Exception:
            pass

        return {"status": "success", "lead_id": str(lead.id)}
