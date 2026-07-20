import uuid
from datetime import datetime
from typing import Annotated, List
from fastapi import APIRouter, Depends, Query, status, Response
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.models.user import User
from fastapi.responses import StreamingResponse
import io
from app.schemas.customer import (
    OrderCreate, OrderUpdate, OrderResponse,
    InvoiceCreate, InvoiceUpdate, InvoiceResponse, InvoiceFromOrderRequest,
    PaymentCreate, PaymentResponse,
    ContractCreate, ContractUpdate, ContractResponse,
    CustomerListItem, CustomerSummary, CustomerReportResponse, TimelineEvent,
)
from app.services.customer_service import CustomerService
from app.middleware.permissions import require_role

_oa_or_mgr = require_role(["OrgAdmin", "Manager"])

router = APIRouter()


def _invoice_out(inv) -> dict:
    """Serialize an invoice including its computed balance_due property."""
    return {
        "id": inv.id, "organization_id": inv.organization_id, "company_id": inv.company_id,
        "contact_id": inv.contact_id, "order_id": inv.order_id, "invoice_number": inv.invoice_number,
        "status": inv.status, "currency": inv.currency, "issue_date": inv.issue_date, "due_date": inv.due_date,
        "items": inv.items or [], "subtotal": inv.subtotal, "tax_amount": inv.tax_amount,
        "discount_amount": inv.discount_amount, "total_amount": inv.total_amount,
        "amount_paid": inv.amount_paid, "balance_due": inv.balance_due, "notes": inv.notes,
        "created_at": inv.created_at, "updated_at": inv.updated_at,
    }


# ================= Customers 360 =================

@router.get("/", response_model=List[CustomerListItem])
async def list_customers(
    actor: Annotated[User, Depends(_oa_or_mgr)],
    db: Annotated[AsyncSession, Depends(get_db)],
    search: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
):
    """List companies flagged as customers with order/AR rollups."""
    return await CustomerService(db).list_customers(actor, search=search, skip=skip, limit=limit)

@router.get("/reports", response_model=CustomerReportResponse)
async def customer_reports(
    actor: Annotated[User, Depends(_oa_or_mgr)],
    db: Annotated[AsyncSession, Depends(get_db)],
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
):
    """Order-to-cash analytics: orders, invoiced, collected, outstanding + overdue AR."""
    return await CustomerService(db).get_report(actor, date_from=date_from, date_to=date_to)

# ================= Orders =================

@router.post("/orders", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
async def create_order(req: OrderCreate, actor: Annotated[User, Depends(_oa_or_mgr)], db: Annotated[AsyncSession, Depends(get_db)]):
    """Create a customer sales order."""
    return await CustomerService(db).create_order(actor, req.model_dump())

@router.get("/orders", response_model=List[OrderResponse])
async def list_orders(
    actor: Annotated[User, Depends(_oa_or_mgr)], db: Annotated[AsyncSession, Depends(get_db)],
    company_id: uuid.UUID | None = Query(None), status_filter: str | None = Query(None, alias="status"),
    skip: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100),
):
    """List customer orders."""
    return list(await CustomerService(db).list_orders(actor, company_id=company_id, status_filter=status_filter, skip=skip, limit=limit))

@router.get("/orders/{order_id}", response_model=OrderResponse)
async def get_order(order_id: uuid.UUID, actor: Annotated[User, Depends(_oa_or_mgr)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await CustomerService(db).get_order(actor, order_id)

@router.patch("/orders/{order_id}", response_model=OrderResponse)
async def update_order(order_id: uuid.UUID, req: OrderUpdate, actor: Annotated[User, Depends(_oa_or_mgr)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await CustomerService(db).update_order(actor, order_id, req.model_dump(exclude_unset=True))

@router.delete("/orders/{order_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_order(order_id: uuid.UUID, actor: Annotated[User, Depends(_oa_or_mgr)], db: Annotated[AsyncSession, Depends(get_db)]):
    await CustomerService(db).delete_order(actor, order_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

# ================= Invoices =================

@router.post("/invoices", response_model=InvoiceResponse, status_code=status.HTTP_201_CREATED)
async def create_invoice(req: InvoiceCreate, actor: Annotated[User, Depends(_oa_or_mgr)], db: Annotated[AsyncSession, Depends(get_db)]):
    """Create a customer invoice (accounts receivable)."""
    inv = await CustomerService(db).create_invoice(actor, req.model_dump())
    return _invoice_out(inv)

@router.post("/invoices/from-order", response_model=InvoiceResponse, status_code=status.HTTP_201_CREATED)
async def create_invoice_from_order(req: InvoiceFromOrderRequest, actor: Annotated[User, Depends(_oa_or_mgr)], db: Annotated[AsyncSession, Depends(get_db)]):
    """Generate an invoice from an existing order."""
    inv = await CustomerService(db).create_invoice_from_order(actor, req.order_id, due_date=req.due_date)
    return _invoice_out(inv)

@router.get("/invoices", response_model=List[InvoiceResponse])
async def list_invoices(
    actor: Annotated[User, Depends(_oa_or_mgr)], db: Annotated[AsyncSession, Depends(get_db)],
    company_id: uuid.UUID | None = Query(None), status_filter: str | None = Query(None, alias="status"),
    skip: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100),
):
    """List customer invoices."""
    invoices = await CustomerService(db).list_invoices(actor, company_id=company_id, status_filter=status_filter, skip=skip, limit=limit)
    return [_invoice_out(i) for i in invoices]

@router.get("/invoices/{invoice_id}", response_model=InvoiceResponse)
async def get_invoice(invoice_id: uuid.UUID, actor: Annotated[User, Depends(_oa_or_mgr)], db: Annotated[AsyncSession, Depends(get_db)]):
    return _invoice_out(await CustomerService(db).get_invoice(actor, invoice_id))

@router.patch("/invoices/{invoice_id}", response_model=InvoiceResponse)
async def update_invoice(invoice_id: uuid.UUID, req: InvoiceUpdate, actor: Annotated[User, Depends(_oa_or_mgr)], db: Annotated[AsyncSession, Depends(get_db)]):
    return _invoice_out(await CustomerService(db).update_invoice(actor, invoice_id, req.model_dump(exclude_unset=True)))

@router.post("/invoices/{invoice_id}/send", response_model=InvoiceResponse)
async def send_invoice(invoice_id: uuid.UUID, actor: Annotated[User, Depends(_oa_or_mgr)], db: Annotated[AsyncSession, Depends(get_db)]):
    """Mark a draft invoice as sent and notify the account owner."""
    return _invoice_out(await CustomerService(db).send_invoice(actor, invoice_id))

@router.get("/invoices/{invoice_id}/pdf")
async def invoice_pdf(invoice_id: uuid.UUID, actor: Annotated[User, Depends(_oa_or_mgr)], db: Annotated[AsyncSession, Depends(get_db)]):
    """Download the invoice as a PDF."""
    pdf = await CustomerService(db).render_invoice_pdf(actor, invoice_id)
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f"attachment; filename=invoice_{invoice_id}.pdf"})

@router.delete("/invoices/{invoice_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_invoice(invoice_id: uuid.UUID, actor: Annotated[User, Depends(_oa_or_mgr)], db: Annotated[AsyncSession, Depends(get_db)]):
    await CustomerService(db).delete_invoice(actor, invoice_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

# ================= Payments =================

@router.post("/invoices/{invoice_id}/payments", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
async def record_payment(invoice_id: uuid.UUID, req: PaymentCreate, actor: Annotated[User, Depends(_oa_or_mgr)], db: Annotated[AsyncSession, Depends(get_db)]):
    """Record a payment received against an invoice (updates its balance/status)."""
    return await CustomerService(db).record_payment(actor, invoice_id, req.model_dump())

@router.get("/invoices/{invoice_id}/payments", response_model=List[PaymentResponse])
async def list_invoice_payments(invoice_id: uuid.UUID, actor: Annotated[User, Depends(_oa_or_mgr)], db: Annotated[AsyncSession, Depends(get_db)]):
    return list(await CustomerService(db).list_payments(actor, invoice_id=invoice_id))

@router.get("/payments", response_model=List[PaymentResponse])
async def list_payments(
    actor: Annotated[User, Depends(_oa_or_mgr)], db: Annotated[AsyncSession, Depends(get_db)],
    company_id: uuid.UUID | None = Query(None),
):
    return list(await CustomerService(db).list_payments(actor, company_id=company_id))

# ================= Contracts =================

@router.post("/contracts", response_model=ContractResponse, status_code=status.HTTP_201_CREATED)
async def create_contract(req: ContractCreate, actor: Annotated[User, Depends(_oa_or_mgr)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await CustomerService(db).create_contract(actor, req.model_dump())

@router.get("/contracts", response_model=List[ContractResponse])
async def list_contracts(
    actor: Annotated[User, Depends(_oa_or_mgr)], db: Annotated[AsyncSession, Depends(get_db)],
    company_id: uuid.UUID | None = Query(None), status_filter: str | None = Query(None, alias="status"),
):
    return list(await CustomerService(db).list_contracts(actor, company_id=company_id, status_filter=status_filter))

@router.get("/contracts/{contract_id}", response_model=ContractResponse)
async def get_contract(contract_id: uuid.UUID, actor: Annotated[User, Depends(_oa_or_mgr)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await CustomerService(db).get_contract(actor, contract_id)

@router.patch("/contracts/{contract_id}", response_model=ContractResponse)
async def update_contract(contract_id: uuid.UUID, req: ContractUpdate, actor: Annotated[User, Depends(_oa_or_mgr)], db: Annotated[AsyncSession, Depends(get_db)]):
    return await CustomerService(db).update_contract(actor, contract_id, req.model_dump(exclude_unset=True))

@router.delete("/contracts/{contract_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_contract(contract_id: uuid.UUID, actor: Annotated[User, Depends(_oa_or_mgr)], db: Annotated[AsyncSession, Depends(get_db)]):
    await CustomerService(db).delete_contract(actor, contract_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

# ================= Customer detail (last: two-segment path) =================

@router.get("/{company_id}/summary", response_model=CustomerSummary)
async def customer_summary(company_id: uuid.UUID, actor: Annotated[User, Depends(_oa_or_mgr)], db: Annotated[AsyncSession, Depends(get_db)]):
    """360 rollup for a customer account: orders, invoices, payments, contracts."""
    return await CustomerService(db).customer_summary(actor, company_id)

@router.get("/{company_id}/timeline", response_model=List[TimelineEvent])
async def customer_timeline(
    company_id: uuid.UUID,
    actor: Annotated[User, Depends(_oa_or_mgr)],
    db: Annotated[AsyncSession, Depends(get_db)],
    types: str | None = Query(None, description="Comma-separated event types to include"),
    search: str | None = Query(None),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
):
    """The ONE unified timeline for a customer: every activity, note, audit, invoice,
    payment, order, contract, workflow event and notification across the account."""
    type_set = {t.strip() for t in types.split(",") if t.strip()} if types else None
    return await CustomerService(db).get_timeline(actor, company_id, types=type_set, search=search, date_from=date_from, date_to=date_to)

@router.get("/{company_id}/timeline/export")
async def export_customer_timeline(
    company_id: uuid.UUID,
    actor: Annotated[User, Depends(_oa_or_mgr)],
    db: Annotated[AsyncSession, Depends(get_db)],
    types: str | None = Query(None),
    search: str | None = Query(None),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
):
    """Export the customer timeline (matching the same filters) as CSV."""
    type_set = {t.strip() for t in types.split(",") if t.strip()} if types else None
    svc = CustomerService(db)
    events = await svc.get_timeline(actor, company_id, types=type_set, search=search, date_from=date_from, date_to=date_to)
    csv_text = svc.build_timeline_csv(events)
    return StreamingResponse(io.StringIO(csv_text), media_type="text/csv",
                             headers={"Content-Disposition": f"attachment; filename=timeline_{company_id}.csv"})
