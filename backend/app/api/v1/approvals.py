import uuid
from typing import Annotated, List
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User
from app.schemas.approval import (
    ChainCreate, ChainUpdate, ChainResponse, RequestCreate, ActRequest, RequestResponse, RequestList,
    HistoryRow, DelegationCreate, DelegationResponse, ApprovalDashboardResponse, ApprovalReportResponse,
    EscalateResult,
)
from app.services.approval_service import ApprovalService
from app.middleware.permissions import require_active_user

router = APIRouter()


def _chain_payload(model) -> dict:
    d = model.model_dump(exclude_unset=True)
    if d.get("steps") is not None:
        d["steps"] = [{"approver_role": s.get("approver_role"),
                       "approver_user_id": str(s["approver_user_id"]) if s.get("approver_user_id") else None}
                      for s in d["steps"]]
    return d


# ---------- Dashboard / report / escalate ----------
@router.get("/dashboard", response_model=ApprovalDashboardResponse)
async def dashboard(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await ApprovalService(db).dashboard(actor)


@router.get("/report", response_model=ApprovalReportResponse)
async def report(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                 request_type: str | None = Query(None)):
    return await ApprovalService(db).report(actor, request_type=request_type)


@router.post("/escalate-overdue", response_model=EscalateResult)
async def escalate_overdue(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await ApprovalService(db).escalate_overdue(actor)


# ---------- Chains ----------
@router.get("/chains", response_model=List[ChainResponse])
async def list_chains(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                      request_type: str | None = Query(None)):
    return await ApprovalService(db).list_chains(actor, request_type=request_type)


@router.post("/chains", response_model=ChainResponse, status_code=status.HTTP_201_CREATED)
async def create_chain(req: ChainCreate, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    payload = req.model_dump()
    payload["steps"] = [{"approver_role": s.get("approver_role"),
                         "approver_user_id": str(s["approver_user_id"]) if s.get("approver_user_id") else None}
                        for s in payload["steps"]]
    return await ApprovalService(db).create_chain(actor, payload)


@router.patch("/chains/{chain_id}", response_model=ChainResponse)
async def update_chain(chain_id: uuid.UUID, req: ChainUpdate, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await ApprovalService(db).update_chain(actor, chain_id, _chain_payload(req))


@router.delete("/chains/{chain_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chain(chain_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    await ApprovalService(db).delete_chain(actor, chain_id)


# ---------- Delegation ----------
@router.get("/delegations", response_model=List[DelegationResponse])
async def list_delegations(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await ApprovalService(db).list_delegations(actor)


@router.post("/delegations", response_model=DelegationResponse, status_code=status.HTTP_201_CREATED)
async def create_delegation(req: DelegationCreate, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await ApprovalService(db).create_delegation(actor, req.model_dump())


@router.post("/delegations/{delegation_id}/revoke", response_model=DelegationResponse)
async def revoke_delegation(delegation_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await ApprovalService(db).revoke_delegation(actor, delegation_id)


# ---------- Requests ----------
@router.get("", response_model=RequestList)
async def list_requests(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                        box: str = Query("mine"), request_type: str | None = Query(None),
                        status_filter: str | None = Query(None, alias="status"),
                        skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=200)):
    return await ApprovalService(db).list_requests(actor, box=box, request_type=request_type,
                                                   status_filter=status_filter, skip=skip, limit=limit)


@router.post("", response_model=RequestResponse, status_code=status.HTTP_201_CREATED)
async def create_request(req: RequestCreate, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await ApprovalService(db).create_request(actor, req.model_dump())


@router.get("/{request_id}/history", response_model=List[HistoryRow])
async def history(request_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await ApprovalService(db).history(actor, request_id)


@router.post("/{request_id}/act", response_model=RequestResponse)
async def act(request_id: uuid.UUID, req: ActRequest, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await ApprovalService(db).act(actor, request_id, req.approve, note=req.note)


@router.post("/{request_id}/cancel", response_model=RequestResponse)
async def cancel(request_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await ApprovalService(db).cancel(actor, request_id)
