import uuid
from datetime import date
from typing import Annotated, List
from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User
from app.schemas.financial_analytics import ExpenseCreate, ExpenseUpdate, ExpenseResponse
from app.services.financial_analytics_service import FinancialAnalyticsService
from app.middleware.permissions import require_active_user

router = APIRouter()


def _svc(db):
    return FinancialAnalyticsService(db)


DF = Query(None)


@router.get("/overview")
async def overview(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                   date_from: date | None = DF, date_to: date | None = DF):
    return await _svc(db).overview(actor, date_from, date_to)


@router.get("/dashboard")
async def dashboard(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).dashboard(actor)


@router.get("/revenue")
async def revenue(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                  date_from: date | None = DF, date_to: date | None = DF):
    return await _svc(db).revenue(actor, date_from, date_to)


@router.get("/expenses")
async def expenses_report(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                          date_from: date | None = DF, date_to: date | None = DF):
    return await _svc(db).expenses_report(actor, date_from, date_to)


@router.get("/profitability")
async def profitability(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                        date_from: date | None = DF, date_to: date | None = DF):
    return await _svc(db).profitability(actor, date_from, date_to)


@router.get("/collections")
async def collections(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                      date_from: date | None = DF, date_to: date | None = DF):
    return await _svc(db).collections(actor, date_from, date_to)


@router.get("/outstanding")
async def outstanding(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).outstanding(actor)


@router.get("/invoices")
async def invoices_report(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                          date_from: date | None = DF, date_to: date | None = DF):
    return await _svc(db).invoices_report(actor, date_from, date_to)


@router.get("/payments")
async def payments_report(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                          date_from: date | None = DF, date_to: date | None = DF):
    return await _svc(db).payments_report(actor, date_from, date_to)


@router.get("/taxes")
async def taxes(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                date_from: date | None = DF, date_to: date | None = DF):
    return await _svc(db).taxes(actor, date_from, date_to)


@router.get("/recurring")
async def recurring(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                    date_from: date | None = DF, date_to: date | None = DF):
    return await _svc(db).recurring(actor, date_from, date_to)


@router.get("/forecast")
async def forecast(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                   date_from: date | None = DF, date_to: date | None = DF):
    return await _svc(db).forecast(actor, date_from, date_to)


@router.get("/trend")
async def trend(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                granularity: str = Query("monthly"), date_from: date | None = DF, date_to: date | None = DF):
    return await _svc(db).trend(actor, granularity=granularity, date_from=date_from, date_to=date_to)


@router.get("/export", response_class=PlainTextResponse)
async def export_csv(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                     date_from: date | None = DF, date_to: date | None = DF):
    csv_text = await _svc(db).export_csv(actor, date_from, date_to)
    return PlainTextResponse(content=csv_text, media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=financial-analytics.csv"})


# ---------- expenses CRUD ----------
@router.get("/expense-records", response_model=List[ExpenseResponse])
async def list_expenses(actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)],
                        date_from: date | None = DF, date_to: date | None = DF, category: str | None = Query(None)):
    return await _svc(db).list_expenses(actor, date_from, date_to, category)


@router.post("/expense-records", response_model=ExpenseResponse, status_code=status.HTTP_201_CREATED)
async def create_expense(req: ExpenseCreate, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).create_expense(actor, req.model_dump())


@router.patch("/expense-records/{expense_id}", response_model=ExpenseResponse)
async def update_expense(expense_id: uuid.UUID, req: ExpenseUpdate, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await _svc(db).update_expense(actor, expense_id, req.model_dump(exclude_unset=True))


@router.delete("/expense-records/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_expense(expense_id: uuid.UUID, actor: Annotated[User, Depends(require_active_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    await _svc(db).delete_expense(actor, expense_id)
