import uuid
from datetime import datetime, timezone, date
from decimal import Decimal
from fastapi import HTTPException, status
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.company import Company
from app.models.customer_order import CustomerOrder
from app.models.customer_invoice import CustomerInvoice
from app.models.customer_payment import CustomerPayment
from app.models.contract import Contract
from app.services.audit_service import AuditService
from app.services.notification_service import NotificationService
from app.services.dashboard_service import DashboardService

OPEN_INVOICE_STATUSES = ("Draft", "Sent", "PartiallyPaid", "Overdue")


def _num(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"


def _d(v) -> Decimal:
    if v is None:
        return Decimal("0")
    return v if isinstance(v, Decimal) else Decimal(str(v))


def _compute_totals(items: list[dict], discount, tax) -> tuple[Decimal, Decimal]:
    """Return (subtotal, total). Fills each item's amount in place."""
    subtotal = Decimal("0")
    for it in items:
        qty = _d(it.get("quantity", 1))
        price = _d(it.get("unit_price", 0))
        amount = _d(it.get("amount")) if it.get("amount") not in (None, "") else qty * price
        it["amount"] = float(amount)
        it["quantity"] = float(qty)
        it["unit_price"] = float(price)
        subtotal += amount
    total = subtotal + _d(tax) - _d(discount)
    if total < 0:
        total = Decimal("0")
    return subtotal, total


class CustomerService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.audit = AuditService(db)
        self.notifier = NotificationService(db)

    async def _get_company(self, actor: User, company_id: uuid.UUID) -> Company:
        res = await self.db.execute(
            select(Company).filter(
                Company.id == company_id,
                Company.organization_id == actor.organization_id,
                Company.is_deleted == False,
            )
        )
        company = res.scalars().first()
        if not company:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Customer (company) not found in your organization")
        return company

    # ================= ORDERS =================
    async def create_order(self, actor: User, data: dict) -> CustomerOrder:
        await self._get_company(actor, data["company_id"])
        items = [dict(i) for i in data.get("items", [])]
        subtotal, total = _compute_totals(items, data.get("discount_amount", 0), data.get("tax_amount", 0))
        order = CustomerOrder(
            organization_id=actor.organization_id,
            company_id=data["company_id"],
            contact_id=data.get("contact_id"),
            order_number=_num("ORD"),
            status=data.get("status", "Draft"),
            currency=data.get("currency", "USD"),
            order_date=data.get("order_date") or datetime.now(timezone.utc),
            items=items,
            subtotal=subtotal,
            tax_amount=_d(data.get("tax_amount", 0)),
            discount_amount=_d(data.get("discount_amount", 0)),
            total_amount=total,
            notes=data.get("notes"),
            created_by=actor.id,
        )
        self.db.add(order)
        await self.db.flush()
        await self.audit.log_event(organization_id=actor.organization_id, actor_user_id=actor.id,
                                   action="ORDER_CREATED", resource_type="customer_order", resource_id=str(order.id),
                                   action_metadata={"total": float(total), "company_id": str(order.company_id)})
        await self.db.refresh(order)
        return order

    async def list_orders(self, actor: User, company_id: uuid.UUID | None = None, status_filter: str | None = None,
                          skip: int = 0, limit: int = 50) -> list[CustomerOrder]:
        q = select(CustomerOrder).filter(
            CustomerOrder.organization_id == actor.organization_id,
            CustomerOrder.is_deleted == False,
        )
        if company_id:
            q = q.filter(CustomerOrder.company_id == company_id)
        if status_filter:
            q = q.filter(CustomerOrder.status == status_filter)
        q = q.order_by(CustomerOrder.created_at.desc()).offset(skip).limit(limit)
        return list((await self.db.execute(q)).scalars().all())

    async def get_order(self, actor: User, order_id: uuid.UUID) -> CustomerOrder:
        res = await self.db.execute(
            select(CustomerOrder).filter(
                CustomerOrder.id == order_id,
                CustomerOrder.organization_id == actor.organization_id,
                CustomerOrder.is_deleted == False,
            )
        )
        order = res.scalars().first()
        if not order:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
        return order

    async def update_order(self, actor: User, order_id: uuid.UUID, data: dict) -> CustomerOrder:
        order = await self.get_order(actor, order_id)
        if "items" in data or "tax_amount" in data or "discount_amount" in data:
            items = [dict(i) for i in (data.get("items") if data.get("items") is not None else order.items or [])]
            tax = data.get("tax_amount", order.tax_amount)
            disc = data.get("discount_amount", order.discount_amount)
            subtotal, total = _compute_totals(items, disc, tax)
            order.items = items
            order.subtotal = subtotal
            order.tax_amount = _d(tax)
            order.discount_amount = _d(disc)
            order.total_amount = total
        for key in ("contact_id", "status", "currency", "order_date", "notes"):
            if key in data and data[key] is not None:
                setattr(order, key, data[key])
        self.db.add(order)
        await self.db.flush()
        await self.audit.log_event(organization_id=actor.organization_id, actor_user_id=actor.id,
                                   action="ORDER_UPDATED", resource_type="customer_order", resource_id=str(order_id))
        await self.db.refresh(order)
        return order

    async def delete_order(self, actor: User, order_id: uuid.UUID) -> None:
        order = await self.get_order(actor, order_id)
        order.is_deleted = True
        order.deleted_at = datetime.now(timezone.utc)
        self.db.add(order)
        await self.db.flush()
        await self.audit.log_event(organization_id=actor.organization_id, actor_user_id=actor.id,
                                   action="ORDER_DELETED", resource_type="customer_order", resource_id=str(order_id))

    # ================= INVOICES =================
    def _recompute_invoice_status(self, invoice: CustomerInvoice) -> None:
        paid = float(invoice.amount_paid or 0)
        total = float(invoice.total_amount or 0)
        if invoice.status == "Void":
            return
        if paid <= 0:
            if invoice.due_date and invoice.due_date < datetime.now(timezone.utc) and invoice.status != "Draft":
                invoice.status = "Overdue"
            elif invoice.status not in ("Draft", "Sent"):
                invoice.status = "Sent"
        elif paid < total:
            invoice.status = "PartiallyPaid"
        else:
            invoice.status = "Paid"

    async def create_invoice(self, actor: User, data: dict) -> CustomerInvoice:
        await self._get_company(actor, data["company_id"])
        items = [dict(i) for i in data.get("items", [])]
        subtotal, total = _compute_totals(items, data.get("discount_amount", 0), data.get("tax_amount", 0))
        invoice = CustomerInvoice(
            organization_id=actor.organization_id,
            company_id=data["company_id"],
            contact_id=data.get("contact_id"),
            order_id=data.get("order_id"),
            invoice_number=_num("INV"),
            status="Draft",
            currency=data.get("currency", "USD"),
            issue_date=data.get("issue_date") or datetime.now(timezone.utc),
            due_date=data.get("due_date"),
            items=items,
            subtotal=subtotal,
            tax_amount=_d(data.get("tax_amount", 0)),
            discount_amount=_d(data.get("discount_amount", 0)),
            total_amount=total,
            amount_paid=Decimal("0"),
            notes=data.get("notes"),
            created_by=actor.id,
        )
        self.db.add(invoice)
        await self.db.flush()
        await self.audit.log_event(organization_id=actor.organization_id, actor_user_id=actor.id,
                                   action="CUSTOMER_INVOICE_CREATED", resource_type="customer_invoice", resource_id=str(invoice.id),
                                   action_metadata={"total": float(total)})
        await self.db.refresh(invoice)
        # Orchestration workflows subscribed to invoice_created.
        from app.services.workflow_engine_service import WorkflowEngineService
        await WorkflowEngineService(self.db).dispatch("invoice_created", invoice, actor, "customer")
        return invoice

    async def create_invoice_from_order(self, actor: User, order_id: uuid.UUID, due_date=None) -> CustomerInvoice:
        order = await self.get_order(actor, order_id)
        return await self.create_invoice(actor, {
            "company_id": order.company_id, "contact_id": order.contact_id, "order_id": order.id,
            "currency": order.currency, "due_date": due_date, "items": list(order.items or []),
            "discount_amount": order.discount_amount, "tax_amount": order.tax_amount,
        })

    async def list_invoices(self, actor: User, company_id: uuid.UUID | None = None, status_filter: str | None = None,
                            skip: int = 0, limit: int = 50) -> list[CustomerInvoice]:
        q = select(CustomerInvoice).filter(
            CustomerInvoice.organization_id == actor.organization_id,
            CustomerInvoice.is_deleted == False,
        )
        if company_id:
            q = q.filter(CustomerInvoice.company_id == company_id)
        if status_filter:
            q = q.filter(CustomerInvoice.status == status_filter)
        q = q.order_by(CustomerInvoice.created_at.desc()).offset(skip).limit(limit)
        return list((await self.db.execute(q)).scalars().all())

    async def get_invoice(self, actor: User, invoice_id: uuid.UUID) -> CustomerInvoice:
        res = await self.db.execute(
            select(CustomerInvoice).filter(
                CustomerInvoice.id == invoice_id,
                CustomerInvoice.organization_id == actor.organization_id,
                CustomerInvoice.is_deleted == False,
            )
        )
        invoice = res.scalars().first()
        if not invoice:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
        return invoice

    async def update_invoice(self, actor: User, invoice_id: uuid.UUID, data: dict) -> CustomerInvoice:
        invoice = await self.get_invoice(actor, invoice_id)
        if "items" in data or "tax_amount" in data or "discount_amount" in data:
            items = [dict(i) for i in (data.get("items") if data.get("items") is not None else invoice.items or [])]
            tax = data.get("tax_amount", invoice.tax_amount)
            disc = data.get("discount_amount", invoice.discount_amount)
            subtotal, total = _compute_totals(items, disc, tax)
            invoice.items = items
            invoice.subtotal = subtotal
            invoice.tax_amount = _d(tax)
            invoice.discount_amount = _d(disc)
            invoice.total_amount = total
        for key in ("contact_id", "currency", "issue_date", "due_date", "notes"):
            if key in data and data[key] is not None:
                setattr(invoice, key, data[key])
        # explicit status change (e.g. Send / Void) if provided
        if data.get("status"):
            # Voiding an invoice is destructive (writes off the receivable) —
            # restrict it to OrgAdmin/Manager even though staff can edit invoices.
            if data["status"] == "Void" and actor.role not in ("OrgAdmin", "Manager"):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                    detail="Only an OrgAdmin or Manager can void an invoice")
            invoice.status = data["status"]
        self._recompute_invoice_status(invoice)
        self.db.add(invoice)
        await self.db.flush()
        await self.audit.log_event(organization_id=actor.organization_id, actor_user_id=actor.id,
                                   action="CUSTOMER_INVOICE_UPDATED", resource_type="customer_invoice", resource_id=str(invoice_id))
        await self.db.refresh(invoice)
        return invoice

    async def send_invoice(self, actor: User, invoice_id: uuid.UUID) -> CustomerInvoice:
        invoice = await self.get_invoice(actor, invoice_id)
        if invoice.status == "Draft":
            invoice.status = "Sent"
        self.db.add(invoice)
        await self.db.flush()
        # Notify the account owner
        company = await self._get_company(actor, invoice.company_id)
        if company.assigned_user_id:
            await self.notifier.create_notification(
                organization_id=actor.organization_id, user_id=company.assigned_user_id,
                category="invoice", title="Invoice sent",
                body=f"Invoice {invoice.invoice_number} ({invoice.currency} {float(invoice.total_amount):.2f}) sent to {company.name}.",
                link_url=f"/customers?companyId={company.id}",
                action_metadata={"invoice_id": str(invoice.id)},
            )
        await self.audit.log_event(organization_id=actor.organization_id, actor_user_id=actor.id,
                                   action="CUSTOMER_INVOICE_SENT", resource_type="customer_invoice", resource_id=str(invoice_id))
        await self.db.refresh(invoice)
        return invoice

    async def delete_invoice(self, actor: User, invoice_id: uuid.UUID) -> None:
        invoice = await self.get_invoice(actor, invoice_id)
        invoice.is_deleted = True
        invoice.deleted_at = datetime.now(timezone.utc)
        self.db.add(invoice)
        await self.db.flush()

    async def render_invoice_pdf(self, actor: User, invoice_id: uuid.UUID) -> bytes:
        invoice = await self.get_invoice(actor, invoice_id)
        company = await self._get_company(actor, invoice.company_id)
        from app.services.customer_invoice_pdf import build_invoice_pdf
        return build_invoice_pdf(invoice, company)

    # ================= PAYMENTS =================
    async def record_payment(self, actor: User, invoice_id: uuid.UUID, data: dict) -> CustomerPayment:
        invoice = await self.get_invoice(actor, invoice_id)
        if invoice.status == "Void":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot record a payment on a void invoice")
        amount = _d(data["amount"])
        # Reject payments that exceed the outstanding balance so amount_paid can
        # never overshoot the total (which would drive balance_due negative and
        # corrupt AR aging / outstanding-revenue reports). An explicit
        # allow_overpayment flag opts into recording an advance / credit.
        outstanding = _d(invoice.total_amount) - _d(invoice.amount_paid)
        if not data.get("allow_overpayment") and amount > outstanding:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Payment of {invoice.currency} {float(amount):.2f} exceeds the outstanding "
                    f"balance of {invoice.currency} {float(outstanding):.2f} on invoice "
                    f"{invoice.invoice_number}. Set allow_overpayment to record an advance."
                ),
            )
        payment = CustomerPayment(
            organization_id=actor.organization_id,
            company_id=invoice.company_id,
            invoice_id=invoice.id,
            amount=amount,
            currency=invoice.currency,
            method=data.get("method", "BankTransfer"),
            reference=data.get("reference"),
            paid_at=data.get("paid_at") or datetime.now(timezone.utc),
            notes=data.get("notes"),
            created_by=actor.id,
        )
        self.db.add(payment)
        invoice.amount_paid = _d(invoice.amount_paid) + amount
        self._recompute_invoice_status(invoice)
        self.db.add(invoice)
        await self.db.flush()
        await self.audit.log_event(organization_id=actor.organization_id, actor_user_id=actor.id,
                                   action="CUSTOMER_PAYMENT_RECORDED", resource_type="customer_payment", resource_id=str(payment.id),
                                   action_metadata={"invoice_id": str(invoice.id), "amount": float(amount), "new_status": invoice.status})
        # notify account owner
        company = await self._get_company(actor, invoice.company_id)
        if company.assigned_user_id and company.assigned_user_id != actor.id:
            await self.notifier.create_notification(
                organization_id=actor.organization_id, user_id=company.assigned_user_id,
                category="payment", title="Payment received",
                body=f"{invoice.currency} {float(amount):.2f} received from {company.name} on {invoice.invoice_number}.",
                link_url=f"/customers?companyId={company.id}",
                action_metadata={"invoice_id": str(invoice.id)},
            )
        await self.db.refresh(payment)
        # Orchestration workflows subscribed to payment_received.
        from app.services.workflow_engine_service import WorkflowEngineService
        await WorkflowEngineService(self.db).dispatch("payment_received", payment, actor, "customer")
        return payment

    async def list_payments(self, actor: User, invoice_id: uuid.UUID | None = None, company_id: uuid.UUID | None = None) -> list[CustomerPayment]:
        q = select(CustomerPayment).filter(
            CustomerPayment.organization_id == actor.organization_id,
            CustomerPayment.is_deleted == False,
        )
        if invoice_id:
            q = q.filter(CustomerPayment.invoice_id == invoice_id)
        if company_id:
            q = q.filter(CustomerPayment.company_id == company_id)
        q = q.order_by(CustomerPayment.created_at.desc())
        return list((await self.db.execute(q)).scalars().all())

    # ================= CONTRACTS =================
    async def create_contract(self, actor: User, data: dict) -> Contract:
        await self._get_company(actor, data["company_id"])
        contract = Contract(
            organization_id=actor.organization_id,
            company_id=data["company_id"],
            contact_id=data.get("contact_id"),
            contract_number=_num("CTR"),
            title=data["title"],
            status=data.get("status", "Draft"),
            start_date=data.get("start_date"),
            end_date=data.get("end_date"),
            value=data.get("value"),
            currency=data.get("currency", "USD"),
            renewal_terms=data.get("renewal_terms"),
            document_url=data.get("document_url"),
            notes=data.get("notes"),
            created_by=actor.id,
        )
        self.db.add(contract)
        await self.db.flush()
        await self.audit.log_event(organization_id=actor.organization_id, actor_user_id=actor.id,
                                   action="CONTRACT_CREATED", resource_type="contract", resource_id=str(contract.id))
        await self.db.refresh(contract)
        return contract

    async def list_contracts(self, actor: User, company_id: uuid.UUID | None = None, status_filter: str | None = None) -> list[Contract]:
        q = select(Contract).filter(
            Contract.organization_id == actor.organization_id,
            Contract.is_deleted == False,
        )
        if company_id:
            q = q.filter(Contract.company_id == company_id)
        if status_filter:
            q = q.filter(Contract.status == status_filter)
        q = q.order_by(Contract.created_at.desc())
        return list((await self.db.execute(q)).scalars().all())

    async def get_contract(self, actor: User, contract_id: uuid.UUID) -> Contract:
        res = await self.db.execute(
            select(Contract).filter(
                Contract.id == contract_id,
                Contract.organization_id == actor.organization_id,
                Contract.is_deleted == False,
            )
        )
        contract = res.scalars().first()
        if not contract:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contract not found")
        return contract

    async def update_contract(self, actor: User, contract_id: uuid.UUID, data: dict) -> Contract:
        contract = await self.get_contract(actor, contract_id)
        for key, val in data.items():
            setattr(contract, key, val)
        self.db.add(contract)
        await self.db.flush()
        await self.audit.log_event(organization_id=actor.organization_id, actor_user_id=actor.id,
                                   action="CONTRACT_UPDATED", resource_type="contract", resource_id=str(contract_id))
        await self.db.refresh(contract)
        return contract

    async def delete_contract(self, actor: User, contract_id: uuid.UUID) -> None:
        contract = await self.get_contract(actor, contract_id)
        contract.is_deleted = True
        contract.deleted_at = datetime.now(timezone.utc)
        self.db.add(contract)
        await self.db.flush()

    # ================= CUSTOMER 360 =================
    async def list_customers(self, actor: User, search: str | None = None, skip: int = 0, limit: int = 50) -> list[dict]:
        """Companies flagged as customers, with order/AR rollups."""
        q = select(Company).filter(
            Company.organization_id == actor.organization_id,
            Company.is_deleted == False,
            Company.company_type == "Customer",
        )
        if search:
            q = q.filter(Company.name.ilike(f"%{search}%"))
        q = q.order_by(Company.name.asc()).offset(skip).limit(limit)
        companies = list((await self.db.execute(q)).scalars().all())

        out = []
        for c in companies:
            oc = (await self.db.execute(
                select(func.count(CustomerOrder.id)).filter(
                    CustomerOrder.company_id == c.id, CustomerOrder.is_deleted == False)
            )).scalar() or 0
            inv_rows = (await self.db.execute(
                select(func.coalesce(func.sum(CustomerInvoice.total_amount), 0),
                       func.coalesce(func.sum(CustomerInvoice.amount_paid), 0)).filter(
                    CustomerInvoice.company_id == c.id, CustomerInvoice.is_deleted == False,
                    CustomerInvoice.status != "Void")
            )).one()
            total_invoiced = float(inv_rows[0] or 0)
            total_paid = float(inv_rows[1] or 0)
            out.append({
                "company_id": c.id, "name": c.name, "industry": c.industry,
                "annual_revenue": c.annual_revenue, "order_count": oc,
                "total_invoiced": total_invoiced, "outstanding_balance": total_invoiced - total_paid,
            })
        return out

    async def customer_summary(self, actor: User, company_id: uuid.UUID) -> dict:
        company = await self._get_company(actor, company_id)

        # orders
        order_rows = (await self.db.execute(
            select(func.count(CustomerOrder.id), func.coalesce(func.sum(CustomerOrder.total_amount), 0)).filter(
                CustomerOrder.company_id == company_id, CustomerOrder.is_deleted == False)
        )).one()
        # invoices
        inv_rows = (await self.db.execute(
            select(func.count(CustomerInvoice.id),
                   func.coalesce(func.sum(CustomerInvoice.total_amount), 0),
                   func.coalesce(func.sum(CustomerInvoice.amount_paid), 0)).filter(
                CustomerInvoice.company_id == company_id, CustomerInvoice.is_deleted == False,
                CustomerInvoice.status != "Void")
        )).one()
        total_invoiced = float(inv_rows[1] or 0)
        total_paid = float(inv_rows[2] or 0)
        # overdue
        overdue = (await self.db.execute(
            select(func.coalesce(func.sum(CustomerInvoice.total_amount - CustomerInvoice.amount_paid), 0)).filter(
                CustomerInvoice.company_id == company_id, CustomerInvoice.is_deleted == False,
                CustomerInvoice.status == "Overdue")
        )).scalar() or 0
        # contracts
        contract_rows = (await self.db.execute(
            select(func.count(Contract.id)).filter(
                Contract.company_id == company_id, Contract.is_deleted == False)
        )).scalar() or 0
        active_contracts = (await self.db.execute(
            select(func.count(Contract.id)).filter(
                Contract.company_id == company_id, Contract.is_deleted == False, Contract.status == "Active")
        )).scalar() or 0

        return {
            "company_id": company.id, "name": company.name, "company_type": company.company_type,
            "orders": {"count": order_rows[0], "total_value": float(order_rows[1] or 0)},
            "invoices": {"count": inv_rows[0], "total_invoiced": total_invoiced,
                         "total_paid": total_paid, "outstanding": total_invoiced - total_paid,
                         "overdue": float(overdue)},
            "payments": {"total_collected": total_paid},
            "contracts": {"count": contract_rows, "active": active_contracts},
        }

    # ================= UNIFIED TIMELINE =================
    _AUDIT_SKIP = {"CUSTOMER_INVOICE_CREATED", "CUSTOMER_PAYMENT_RECORDED", "ORDER_CREATED", "CONTRACT_CREATED"}

    @staticmethod
    def _audit_type(action: str, meta: dict | None) -> str:
        a = (action or "").upper()
        meta = meta or {}
        if "ASSIGNED" in a:
            return "assignment"
        if a == "LEAD_DISPOSITION_SUBMITTED":
            return "status_change"
        if a.endswith("_UPDATED"):
            fields = meta.get("updated_fields") or []
            return "status_change" if "status" in fields or "stage_id" in fields else "update"
        if "ATTACHMENT" in a:
            return "file"
        if a == "WORKFLOW_EXECUTED":
            return "workflow"
        if a in ("LEAD_ESCALATED", "CUSTOMER_INVOICE_OVERDUE"):
            return "automation"
        if "INVOICE" in a:
            return "invoice"
        if "PAYMENT" in a:
            return "payment"
        if "ORDER" in a:
            return "order"
        if "CONTRACT" in a:
            return "contract"
        return "audit"

    async def get_timeline(self, actor: User, company_id: uuid.UUID, types: set[str] | None = None,
                           search: str | None = None, date_from=None, date_to=None, limit: int = 500) -> list[dict]:
        """One aggregated timeline for a customer account: activities, notes, audit,
        invoices, payments, orders, contracts, and notifications across the company
        and its associated contacts & leads."""
        from app.models.contact import Contact
        from app.models.lead import Lead
        from app.models.note import Note
        from app.models.activity import Activity
        from app.models.audit_log import AuditLog
        from app.models.notification import Notification

        company = await self._get_company(actor, company_id)
        org = actor.organization_id

        # Related record ids
        contact_ids = set((await self.db.execute(
            select(Contact.id).filter(Contact.company_id == company_id, Contact.organization_id == org, Contact.is_deleted == False)
        )).scalars().all())
        lead_clause = [Lead.company_id == company_id]
        if company.name:
            lead_clause.append(func.lower(Lead.company_name) == company.name.lower())
        lead_ids = set((await self.db.execute(
            select(Lead.id).filter(Lead.organization_id == org, Lead.is_deleted == False, or_(*lead_clause))
        )).scalars().all())
        order_ids = set((await self.db.execute(select(CustomerOrder.id).filter(CustomerOrder.company_id == company_id, CustomerOrder.is_deleted == False))).scalars().all())
        invoice_ids = set((await self.db.execute(select(CustomerInvoice.id).filter(CustomerInvoice.company_id == company_id, CustomerInvoice.is_deleted == False))).scalars().all())
        payment_ids = set((await self.db.execute(select(CustomerPayment.id).filter(CustomerPayment.company_id == company_id, CustomerPayment.is_deleted == False))).scalars().all())
        contract_ids = set((await self.db.execute(select(Contract.id).filter(Contract.company_id == company_id, Contract.is_deleted == False))).scalars().all())

        all_ids = {str(company_id)} | {str(i) for i in contact_ids | lead_ids | order_ids | invoice_ids | payment_ids | contract_ids}

        events: list[dict] = []
        actor_ids: set = set()

        # 1. Activities (communications + meetings/tasks)
        act_filters = [Activity.company_id == company_id]
        if contact_ids:
            act_filters.append(Activity.contact_id.in_(contact_ids))
        if lead_ids:
            act_filters.append(Activity.lead_id.in_(lead_ids))
        acts = (await self.db.execute(
            select(Activity).filter(Activity.organization_id == org, Activity.is_deleted == False, or_(*act_filters))
        )).scalars().all()
        for a in acts:
            uid = a.assigned_user_id or a.created_by
            actor_ids.add(uid)
            events.append({"type": (a.activity_type or "activity").lower(), "id": str(a.id), "timestamp": a.created_at,
                           "title": f"{a.activity_type}: {a.subject}", "description": a.description,
                           "actor_user_id": str(uid) if uid else None, "source": "activity",
                           "metadata": {"status": a.status, "direction": a.call_direction, "recording_url": a.recording_url}})

        # 2. Notes
        note_filters = [Note.company_id == company_id]
        if contact_ids:
            note_filters.append(Note.contact_id.in_(contact_ids))
        if lead_ids:
            note_filters.append(Note.lead_id.in_(lead_ids))
        notes = (await self.db.execute(
            select(Note).filter(Note.organization_id == org, Note.is_deleted == False, or_(*note_filters))
        )).scalars().all()
        for n in notes:
            actor_ids.add(n.created_by)
            events.append({"type": "note", "id": str(n.id), "timestamp": n.created_at, "title": "Note",
                           "description": n.content, "actor_user_id": str(n.created_by) if n.created_by else None,
                           "source": "note", "metadata": None})

        # 3. Audit logs (status/assignments/files/workflow/automation + invoice/order/contract lifecycle)
        audits = (await self.db.execute(
            select(AuditLog).filter(AuditLog.organization_id == org, AuditLog.resource_id.in_(all_ids))
        )).scalars().all()
        for al in audits:
            if al.action in self._AUDIT_SKIP:
                continue
            if al.actor_user_id:
                actor_ids.add(al.actor_user_id)
            events.append({"type": self._audit_type(al.action, al.action_metadata), "id": str(al.id), "timestamp": al.created_at,
                           "title": al.action.replace("_", " ").title(), "description": None,
                           "actor_user_id": str(al.actor_user_id) if al.actor_user_id else None,
                           "source": "audit", "metadata": al.action_metadata})

        # 4. Invoices (creation)
        invoices = (await self.db.execute(select(CustomerInvoice).filter(CustomerInvoice.company_id == company_id, CustomerInvoice.is_deleted == False))).scalars().all()
        for inv in invoices:
            actor_ids.add(inv.created_by)
            events.append({"type": "invoice", "id": str(inv.id), "timestamp": inv.issue_date or inv.created_at,
                           "title": f"Invoice {inv.invoice_number} · {inv.status}", "description": None,
                           "actor_user_id": str(inv.created_by) if inv.created_by else None, "source": "invoice",
                           "metadata": {"total": float(inv.total_amount or 0), "balance_due": inv.balance_due, "currency": inv.currency}})

        # 5. Payments
        payments = (await self.db.execute(select(CustomerPayment).filter(CustomerPayment.company_id == company_id, CustomerPayment.is_deleted == False))).scalars().all()
        for p in payments:
            actor_ids.add(p.created_by)
            events.append({"type": "payment", "id": str(p.id), "timestamp": p.paid_at or p.created_at,
                           "title": f"Payment {p.currency} {float(p.amount):.2f} · {p.method}", "description": p.reference,
                           "actor_user_id": str(p.created_by) if p.created_by else None, "source": "payment",
                           "metadata": {"amount": float(p.amount), "method": p.method}})

        # 6. Orders (creation)
        orders = (await self.db.execute(select(CustomerOrder).filter(CustomerOrder.company_id == company_id, CustomerOrder.is_deleted == False))).scalars().all()
        for o in orders:
            actor_ids.add(o.created_by)
            events.append({"type": "order", "id": str(o.id), "timestamp": o.order_date or o.created_at,
                           "title": f"Order {o.order_number} · {o.status}", "description": None,
                           "actor_user_id": str(o.created_by) if o.created_by else None, "source": "order",
                           "metadata": {"total": float(o.total_amount or 0), "currency": o.currency}})

        # 7. Contracts (creation)
        contracts = (await self.db.execute(select(Contract).filter(Contract.company_id == company_id, Contract.is_deleted == False))).scalars().all()
        for ctr in contracts:
            actor_ids.add(ctr.created_by)
            events.append({"type": "contract", "id": str(ctr.id), "timestamp": ctr.created_at,
                           "title": f"Contract {ctr.contract_number}: {ctr.title} · {ctr.status}", "description": ctr.notes,
                           "actor_user_id": str(ctr.created_by) if ctr.created_by else None, "source": "contract",
                           "metadata": {"value": float(ctr.value) if ctr.value is not None else None}})

        # 8. Notifications referencing any of this customer's records
        notifs = (await self.db.execute(
            select(Notification).filter(Notification.organization_id == org).order_by(Notification.created_at.desc()).limit(limit)
        )).scalars().all()
        for nt in notifs:
            meta_vals = {str(v) for v in (nt.action_metadata or {}).values()}
            link = nt.link_url or ""
            if meta_vals & all_ids or any(rid in link for rid in all_ids):
                events.append({"type": "notification", "id": str(nt.id), "timestamp": nt.created_at, "title": nt.title,
                               "description": nt.body, "actor_user_id": None, "source": "notification",
                               "metadata": {"category": nt.category}})

        # Resolve actor names
        names: dict = {}
        actor_ids = {a for a in actor_ids if a}
        if actor_ids:
            from app.models.user import User as UserModel
            u_res = await self.db.execute(select(UserModel.id, UserModel.first_name, UserModel.last_name, UserModel.email).filter(UserModel.id.in_(actor_ids)))
            for uid, fn, ln, em in u_res.all():
                names[str(uid)] = f"{fn or ''} {ln or ''}".strip() or em
        for e in events:
            e["actor_name"] = names.get(e.get("actor_user_id")) if e.get("actor_user_id") else None

        # Filters
        if types:
            events = [e for e in events if e["type"] in types]
        if search:
            s = search.lower()
            events = [e for e in events if s in (e["title"] or "").lower() or s in (e.get("description") or "").lower()]
        if date_from is not None:
            events = [e for e in events if e["timestamp"] and e["timestamp"] >= date_from]
        if date_to is not None:
            events = [e for e in events if e["timestamp"] and e["timestamp"] <= date_to]

        events.sort(key=lambda e: e["timestamp"] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
        for e in events:
            e["group"] = e["timestamp"].date().isoformat() if e["timestamp"] else "unknown"
        return events[:limit]

    @staticmethod
    def build_timeline_csv(events: list[dict]) -> str:
        import csv, io
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["date", "type", "source", "title", "description", "actor"])
        for e in events:
            w.writerow([
                e["timestamp"].isoformat() if e.get("timestamp") else "",
                e.get("type", ""), e.get("source", ""), e.get("title", ""),
                (e.get("description") or "").replace("\n", " "), e.get("actor_name") or "",
            ])
        return buf.getvalue()

    # ================= REPORTS =================
    async def get_report(self, actor: User, date_from=None, date_to=None) -> dict:
        org = actor.organization_id

        total_customers = (await self.db.execute(
            select(func.count(Company.id)).filter(
                Company.organization_id == org, Company.is_deleted == False, Company.company_type == "Customer")
        )).scalar() or 0

        def order_base(*cols):
            q = select(*cols).filter(CustomerOrder.organization_id == org, CustomerOrder.is_deleted == False)
            if date_from is not None:
                q = q.filter(CustomerOrder.created_at >= date_from)
            if date_to is not None:
                q = q.filter(CustomerOrder.created_at <= date_to)
            return q

        order_agg = (await self.db.execute(order_base(func.count(CustomerOrder.id), func.coalesce(func.sum(CustomerOrder.total_amount), 0)))).one()

        def inv_base(*cols):
            q = select(*cols).filter(CustomerInvoice.organization_id == org, CustomerInvoice.is_deleted == False, CustomerInvoice.status != "Void")
            if date_from is not None:
                q = q.filter(CustomerInvoice.created_at >= date_from)
            if date_to is not None:
                q = q.filter(CustomerInvoice.created_at <= date_to)
            return q

        inv_agg = (await self.db.execute(inv_base(
            func.coalesce(func.sum(CustomerInvoice.total_amount), 0),
            func.coalesce(func.sum(CustomerInvoice.amount_paid), 0)))).one()
        total_invoiced = float(inv_agg[0] or 0)
        total_collected = float(inv_agg[1] or 0)
        overdue_ar = float((await self.db.execute(inv_base(
            func.coalesce(func.sum(CustomerInvoice.total_amount - CustomerInvoice.amount_paid), 0)).filter(
            CustomerInvoice.status == "Overdue"))).scalar() or 0)

        status_rows = (await self.db.execute(inv_base(CustomerInvoice.status, func.count(CustomerInvoice.id)).group_by(CustomerInvoice.status))).all()
        invoices_by_status = [{"label": r[0], "count": r[1]} for r in status_rows]

        active_contracts = (await self.db.execute(
            select(func.count(Contract.id)).filter(Contract.organization_id == org, Contract.is_deleted == False, Contract.status == "Active")
        )).scalar() or 0

        # top customers by invoiced
        top_rows = (await self.db.execute(
            select(Company.name, func.coalesce(func.sum(CustomerInvoice.total_amount), 0))
            .join(CustomerInvoice, CustomerInvoice.company_id == Company.id)
            .filter(CustomerInvoice.organization_id == org, CustomerInvoice.is_deleted == False, CustomerInvoice.status != "Void")
            .group_by(Company.name).order_by(func.coalesce(func.sum(CustomerInvoice.total_amount), 0).desc()).limit(5)
        )).all()
        top_customers = [{"name": r[0], "invoiced": float(r[1])} for r in top_rows]

        return {
            "total_customers": total_customers,
            "total_orders": order_agg[0],
            "total_order_value": float(order_agg[1] or 0),
            "total_invoiced": total_invoiced,
            "total_collected": total_collected,
            "outstanding_ar": total_invoiced - total_collected,
            "overdue_ar": overdue_ar,
            "active_contracts": active_contracts,
            "invoices_by_status": invoices_by_status,
            "top_customers": top_customers,
        }
