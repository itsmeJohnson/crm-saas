import uuid
from typing import Annotated, List
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User
from app.schemas.notification_automation import (
    RuleCreate, RuleUpdate, RuleResponse, DeliveryResponse, TemplateCreate, TemplateUpdate,
    TemplateResponse, EnableRequest, AutomationReport, AutomationDashboard, DigestResult,
)
from app.services.notification_automation_service import NotificationAutomationService
from app.middleware.permissions import require_active_user

router = APIRouter()


# ---------- catalog / monitoring ----------
@router.get("/catalog")
async def catalog(actor: Annotated[User, Depends(require_active_user)]):
    return NotificationAutomationService.catalog()


@router.get("/dashboard", response_model=AutomationDashboard)
async def dashboard(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await NotificationAutomationService(db).dashboard(actor)


@router.get("/report", response_model=AutomationReport)
async def report(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await NotificationAutomationService(db).report(actor)


# ---------- rules ----------
@router.get("/rules", response_model=List[RuleResponse])
async def list_rules(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await NotificationAutomationService(db).list_rules(actor)


@router.post("/rules", response_model=RuleResponse, status_code=status.HTTP_201_CREATED)
async def create_rule(req: RuleCreate, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await NotificationAutomationService(db).create_rule(actor, req.model_dump())


@router.patch("/rules/{rule_id}", response_model=RuleResponse)
async def update_rule(rule_id: uuid.UUID, req: RuleUpdate, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await NotificationAutomationService(db).update_rule(actor, rule_id, req.model_dump(exclude_unset=True))


@router.delete("/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rule(rule_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    await NotificationAutomationService(db).delete_rule(actor, rule_id)


@router.post("/rules/{rule_id}/enable", response_model=RuleResponse)
async def enable_rule(rule_id: uuid.UUID, req: EnableRequest, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await NotificationAutomationService(db).set_enabled(actor, rule_id, req.enabled)


# ---------- deliveries (tracking + retry) ----------
@router.get("/deliveries", response_model=List[DeliveryResponse])
async def deliveries(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                     status_filter: str | None = Query(None, alias="status"), channel: str | None = Query(None),
                     rule_id: uuid.UUID | None = Query(None), limit: int = Query(50, ge=1, le=200)):
    return await NotificationAutomationService(db).deliveries(actor, status_filter=status_filter, channel=channel,
                                                              rule_id=rule_id, limit=limit)


@router.post("/deliveries/{delivery_id}/retry", response_model=DeliveryResponse)
async def retry_delivery(delivery_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await NotificationAutomationService(db).retry_delivery(actor, delivery_id)


# ---------- digests ----------
@router.post("/digests/flush", response_model=DigestResult)
async def flush_digests(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await NotificationAutomationService(db).run_digest_now(actor)


# ---------- templates ----------
@router.get("/templates", response_model=List[TemplateResponse])
async def list_templates(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await NotificationAutomationService(db).list_templates(actor)


@router.post("/templates", response_model=TemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_template(req: TemplateCreate, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await NotificationAutomationService(db).create_template(actor, req.model_dump())


@router.patch("/templates/{template_key}", response_model=TemplateResponse)
async def update_template(template_key: str, req: TemplateUpdate, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await NotificationAutomationService(db).update_template(actor, template_key, req.model_dump(exclude_unset=True))


@router.delete("/templates/{template_key}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(template_key: str, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    await NotificationAutomationService(db).delete_template(actor, template_key)
