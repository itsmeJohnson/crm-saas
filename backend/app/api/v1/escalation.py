import uuid
from typing import Annotated, List
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User
from app.schemas.escalation_engine import (
    RuleCreate, RuleUpdate, RuleResponse, EventResponse, EnableRequest, ScanResult,
    EscalationReport, EscalationDashboard,
)
from app.services.escalation_engine_service import EscalationEngineService
from app.middleware.permissions import require_active_user

router = APIRouter()


# ---------- catalog / monitoring ----------
@router.get("/catalog")
async def catalog(actor: Annotated[User, Depends(require_active_user)]):
    return EscalationEngineService.catalog()


@router.get("/dashboard", response_model=EscalationDashboard)
async def dashboard(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await EscalationEngineService(db).dashboard(actor)


@router.get("/report", response_model=EscalationReport)
async def report(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await EscalationEngineService(db).report(actor)


# ---------- rules ----------
@router.get("/rules", response_model=List[RuleResponse])
async def list_rules(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await EscalationEngineService(db).list_rules(actor)


@router.post("/rules", response_model=RuleResponse, status_code=status.HTTP_201_CREATED)
async def create_rule(req: RuleCreate, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await EscalationEngineService(db).create_rule(actor, req.model_dump())


@router.patch("/rules/{rule_id}", response_model=RuleResponse)
async def update_rule(rule_id: uuid.UUID, req: RuleUpdate, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await EscalationEngineService(db).update_rule(actor, rule_id, req.model_dump(exclude_unset=True))


@router.delete("/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rule(rule_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    await EscalationEngineService(db).delete_rule(actor, rule_id)


@router.post("/rules/{rule_id}/enable", response_model=RuleResponse)
async def enable_rule(rule_id: uuid.UUID, req: EnableRequest, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await EscalationEngineService(db).set_enabled(actor, rule_id, req.enabled)


# ---------- events / scan ----------
@router.get("/events", response_model=List[EventResponse])
async def events(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                 rule_id: uuid.UUID | None = Query(None), entity_type: str | None = Query(None),
                 limit: int = Query(50, ge=1, le=200)):
    return await EscalationEngineService(db).events(actor, rule_id=rule_id, entity_type=entity_type, limit=limit)


@router.post("/scan", response_model=ScanResult)
async def scan_now(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return {"escalations": await EscalationEngineService(db).scan(actor.organization_id)}
