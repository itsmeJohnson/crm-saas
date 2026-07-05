import uuid
from typing import Annotated, List
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User
from app.schemas.rule import (
    RuleCreate, RuleUpdate, RuleResponse, PriorityRequest, TestRequest, TestResult,
    ResolveRequest, ImportRequest, EvaluationRow, RuleReport, RuleDashboard, SimpleResult,
)
from app.services.rule_service import RuleService
from app.middleware.permissions import require_active_user

router = APIRouter()


# ---------- Catalog / dashboard / reports ----------
@router.get("/catalog")
async def catalog(actor: Annotated[User, Depends(require_active_user)]):
    return RuleService.catalog()


@router.get("/dashboard", response_model=RuleDashboard)
async def dashboard(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await RuleService(db).dashboard(actor)


@router.get("/report", response_model=RuleReport)
async def report(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await RuleService(db).report(actor)


# ---------- Templates ----------
@router.post("/templates/seed", response_model=SimpleResult)
async def seed_templates(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await RuleService(db).seed_templates(actor)


@router.post("/templates/{rule_id}/instantiate", response_model=RuleResponse, status_code=status.HTTP_201_CREATED)
async def instantiate_template(rule_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await RuleService(db).instantiate_template(actor, rule_id)


# ---------- Evaluations / resolve ----------
@router.get("/evaluations", response_model=List[EvaluationRow])
async def evaluations(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                      rule_id: uuid.UUID | None = Query(None), limit: int = Query(50, ge=1, le=200)):
    return await RuleService(db).evaluations(actor, rule_id=rule_id, limit=limit)


@router.post("/resolve")
async def resolve(req: ResolveRequest, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    svc = RuleService(db)
    entity = await svc._load_entity(actor, req.entity_type, req.entity_id)
    return await svc.resolve(actor, req.entity_type, entity, strategy=req.strategy)


# ---------- CRUD ----------
@router.get("", response_model=List[RuleResponse])
async def list_rules(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                     entity_type: str | None = Query(None), is_template: bool | None = Query(None),
                     active_only: bool = Query(False)):
    return await RuleService(db).list_rules(actor, entity_type=entity_type, is_template=is_template, active_only=active_only)


@router.post("", response_model=RuleResponse, status_code=status.HTTP_201_CREATED)
async def create_rule(req: RuleCreate, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await RuleService(db).create(actor, req.model_dump())


@router.post("/import", response_model=RuleResponse, status_code=status.HTTP_201_CREATED)
async def import_rule(req: ImportRequest, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await RuleService(db).import_one(actor, req.model_dump(by_alias=True))


@router.get("/{rule_id}", response_model=RuleResponse)
async def get_rule(rule_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await RuleService(db).get(actor, rule_id)


@router.patch("/{rule_id}", response_model=RuleResponse)
async def update_rule(rule_id: uuid.UUID, req: RuleUpdate, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await RuleService(db).update(actor, rule_id, req.model_dump(exclude_unset=True))


@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rule(rule_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    await RuleService(db).delete(actor, rule_id)


@router.get("/{rule_id}/export")
async def export_rule(rule_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await RuleService(db).export_one(actor, rule_id)


@router.post("/{rule_id}/clone", response_model=RuleResponse, status_code=status.HTTP_201_CREATED)
async def clone_rule(rule_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await RuleService(db).clone(actor, rule_id)


@router.post("/{rule_id}/priority", response_model=RuleResponse)
async def set_priority(rule_id: uuid.UUID, req: PriorityRequest, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await RuleService(db).set_priority(actor, rule_id, req.priority)


@router.post("/{rule_id}/test", response_model=TestResult)
async def test_rule(rule_id: uuid.UUID, req: TestRequest, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await RuleService(db).test(actor, rule_id, sample=req.sample, entity_id=req.entity_id)
