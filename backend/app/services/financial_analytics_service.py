"""Financial Analytics — org-level financial analytics over the order-to-cash
data (customer invoices/payments/orders/contracts) plus a small Expense input.

Covers billed & collected revenue, expenses, profitability, collections,
outstanding AR with aging, invoices, payments, taxes, recurring metrics
(subscription revenue / MRR / ARR / churn / LTV / CAC) from contracts, and a
near-term revenue forecast. Org-scoped; managers and admins only. The only new
data source is `expenses`; everything else is reused.
"""
from __future__ import annotations
import csv
import io
import uuid
from datetime import date, datetime, time, timedelta, timezone
from fastapi import HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.company import Company
from app.models.customer_invoice import CustomerInvoice
from app.models.customer_payment import CustomerPayment
from app.models.contract import Contract
from app.models.expense import Expense

GRANULARITIES = ("daily", "weekly", "monthly")
ACQUISITION_CATEGORIES = ("Marketing", "Sales", "Acquisition")
EXPENSE_CATEGORIES = ("Marketing", "Sales", "Payroll", "Software", "Office", "General")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt):
    if dt is None:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def _f(v) -> float:
    return float(v or 0)


class FinancialAnalyticsService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ---------- permissions / window ----------
    def _require_manager(self, actor: User):
        if actor.role not in ("SuperAdmin", "OrgAdmin", "Manager"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Financial analytics are available to managers and admins only.")

    def _window(self, date_from: date | None, date_to: date | None) -> tuple[datetime, datetime, int]:
        today = date.today()
        to_d = date_to or today
        from_d = date_from or (to_d - timedelta(days=89))
        start = datetime.combine(from_d, time.min).replace(tzinfo=timezone.utc)
        end = datetime.combine(to_d, time.max).replace(tzinfo=timezone.utc)
        return start, end, max(1, (to_d - from_d).days + 1)

    @staticmethod
    def _rate(part, whole) -> float:
        return round(part * 100 / whole, 1) if whole else 0.0

    # ---------- data fetch ----------
    async def _invoices(self, org, start, end, window=True) -> list[CustomerInvoice]:
        q = select(CustomerInvoice).filter(CustomerInvoice.organization_id == org,
                                           CustomerInvoice.is_deleted == False, CustomerInvoice.status != "Void")
        if window:
            q = q.filter(CustomerInvoice.created_at >= start, CustomerInvoice.created_at <= end)
        return list((await self.db.execute(q)).scalars().all())

    async def _payments(self, org, start, end) -> list[CustomerPayment]:
        return list((await self.db.execute(select(CustomerPayment).filter(
            CustomerPayment.organization_id == org, CustomerPayment.is_deleted == False,
            CustomerPayment.created_at >= start, CustomerPayment.created_at <= end))).scalars().all())

    async def _expenses(self, org, fd: date, td: date) -> list[Expense]:
        return list((await self.db.execute(select(Expense).filter(
            Expense.organization_id == org, Expense.is_deleted == False,
            Expense.incurred_at >= fd, Expense.incurred_at <= td))).scalars().all())

    async def _contracts(self, org) -> list[Contract]:
        return list((await self.db.execute(select(Contract).filter(
            Contract.organization_id == org, Contract.is_deleted == False))).scalars().all())

    @staticmethod
    def _mrr_of(c: Contract) -> float:
        """Monthly recurring value of an active contract = value spread over its term."""
        if c.value is None or not c.start_date or not c.end_date:
            return 0.0
        months = max(1, (c.end_date.year - c.start_date.year) * 12 + (c.end_date.month - c.start_date.month))
        return _f(c.value) / months

    # ================= headline overview =================
    async def overview(self, actor: User, date_from=None, date_to=None) -> dict:
        self._require_manager(actor)
        org = actor.organization_id
        start, end, days = self._window(date_from, date_to)
        invs = await self._invoices(org, start, end)
        pays = await self._payments(org, start, end)
        exps = await self._expenses(org, start.date(), end.date())
        contracts = await self._contracts(org)
        open_invs = await self._invoices(org, start, end, window=False)

        billed = sum(_f(i.total_amount) for i in invs)
        collected = sum(_f(p.amount) for p in pays)
        tax = sum(_f(i.tax_amount) for i in invs)
        expense_total = sum(_f(e.amount) for e in exps)
        outstanding = sum(_f(i.total_amount) - _f(i.amount_paid) for i in open_invs)
        overdue = sum(_f(i.total_amount) - _f(i.amount_paid) for i in open_invs if i.status == "Overdue")
        gross_profit = round(billed - expense_total, 2)
        active_contracts = [c for c in contracts if c.status in ("Active", "Renewed")]
        mrr = round(sum(self._mrr_of(c) for c in active_contracts), 2)
        return {
            "from": start.date().isoformat(), "to": end.date().isoformat(),
            "revenue_billed": round(billed, 2), "revenue_collected": round(collected, 2),
            "expenses": round(expense_total, 2), "gross_profit": gross_profit,
            "profit_margin": self._rate(gross_profit, billed),
            "collections": round(collected, 2), "outstanding": round(outstanding, 2), "overdue": round(overdue, 2),
            "tax_collected": round(tax, 2), "invoice_count": len(invs), "payment_count": len(pays),
            "mrr": mrr, "arr": round(mrr * 12, 2), "active_contracts": len(active_contracts),
        }

    # ================= revenue / expenses / profitability =================
    async def revenue(self, actor: User, date_from=None, date_to=None) -> dict:
        self._require_manager(actor)
        org = actor.organization_id
        start, end, _ = self._window(date_from, date_to)
        invs = await self._invoices(org, start, end)
        billed = sum(_f(i.total_amount) for i in invs)
        by_customer: dict = {}
        for i in invs:
            by_customer[i.company_id] = by_customer.get(i.company_id, 0.0) + _f(i.total_amount)
        names = await self._company_names(list(by_customer.keys()))
        top = sorted(([{"company": names.get(cid, "—"), "revenue": round(v, 2)} for cid, v in by_customer.items()]),
                     key=lambda r: -r["revenue"])[:10]
        pays = await self._payments(org, start, end)
        return {"billed": round(billed, 2), "collected": round(sum(_f(p.amount) for p in pays), 2),
                "invoice_count": len(invs), "avg_invoice": round(billed / len(invs), 2) if invs else 0.0,
                "top_customers": top}

    async def expenses_report(self, actor: User, date_from=None, date_to=None) -> dict:
        self._require_manager(actor)
        org = actor.organization_id
        start, end, _ = self._window(date_from, date_to)
        exps = await self._expenses(org, start.date(), end.date())
        total = sum(_f(e.amount) for e in exps)
        by_cat: dict = {}
        for e in exps:
            by_cat[e.category] = by_cat.get(e.category, 0.0) + _f(e.amount)
        return {"total": round(total, 2), "count": len(exps),
                "by_category": [{"category": k, "amount": round(v, 2)} for k, v in sorted(by_cat.items(), key=lambda kv: -kv[1])]}

    async def profitability(self, actor: User, date_from=None, date_to=None) -> dict:
        self._require_manager(actor)
        org = actor.organization_id
        start, end, _ = self._window(date_from, date_to)
        invs = await self._invoices(org, start, end)
        exps = await self._expenses(org, start.date(), end.date())
        revenue = sum(_f(i.total_amount) for i in invs)
        expense_total = sum(_f(e.amount) for e in exps)
        collected = sum(_f(p.amount) for p in await self._payments(org, start, end))
        gross = round(revenue - expense_total, 2)
        return {"revenue": round(revenue, 2), "expenses": round(expense_total, 2), "gross_profit": gross,
                "profit_margin": self._rate(gross, revenue),
                "cash_profit": round(collected - expense_total, 2), "collected": round(collected, 2)}

    # ================= collections / outstanding / invoices / payments =================
    async def collections(self, actor: User, date_from=None, date_to=None) -> dict:
        self._require_manager(actor)
        org = actor.organization_id
        start, end, _ = self._window(date_from, date_to)
        pays = await self._payments(org, start, end)
        invs = await self._invoices(org, start, end)
        billed = sum(_f(i.total_amount) for i in invs)
        collected = sum(_f(p.amount) for p in pays)
        by_method: dict = {}
        for p in pays:
            by_method[p.method] = by_method.get(p.method, 0.0) + _f(p.amount)
        return {"collected": round(collected, 2), "billed": round(billed, 2),
                "collection_rate": self._rate(collected, billed),
                "by_method": [{"method": k, "amount": round(v, 2)} for k, v in sorted(by_method.items(), key=lambda kv: -kv[1])]}

    async def outstanding(self, actor: User, date_from=None, date_to=None) -> dict:
        self._require_manager(actor)
        org = actor.organization_id
        open_invs = await self._invoices(org, None, None, window=False)
        now = _now()
        buckets = {"current": 0.0, "1-30": 0.0, "31-60": 0.0, "61-90": 0.0, "90+": 0.0}
        total = overdue = 0.0
        for i in open_invs:
            bal = _f(i.total_amount) - _f(i.amount_paid)
            if bal <= 0:
                continue
            total += bal
            if i.status == "Overdue":
                overdue += bal
            due = _aware(i.due_date)
            if not due or due >= now:
                buckets["current"] += bal
            else:
                d = (now - due).days
                key = "1-30" if d <= 30 else "31-60" if d <= 60 else "61-90" if d <= 90 else "90+"
                buckets[key] += bal
        return {"outstanding": round(total, 2), "overdue": round(overdue, 2),
                "aging": [{"bucket": k, "amount": round(v, 2)} for k, v in buckets.items()]}

    async def invoices_report(self, actor: User, date_from=None, date_to=None) -> dict:
        self._require_manager(actor)
        org = actor.organization_id
        start, end, _ = self._window(date_from, date_to)
        invs = await self._invoices(org, start, end)
        by_status: dict = {}
        for i in invs:
            b = by_status.setdefault(i.status, {"count": 0, "amount": 0.0})
            b["count"] += 1
            b["amount"] += _f(i.total_amount)
        total = sum(_f(i.total_amount) for i in invs)
        return {"count": len(invs), "total": round(total, 2),
                "avg": round(total / len(invs), 2) if invs else 0.0,
                "by_status": [{"status": k, "count": v["count"], "amount": round(v["amount"], 2)}
                              for k, v in sorted(by_status.items(), key=lambda kv: -kv[1]["amount"])]}

    async def payments_report(self, actor: User, date_from=None, date_to=None) -> dict:
        self._require_manager(actor)
        org = actor.organization_id
        start, end, _ = self._window(date_from, date_to)
        pays = await self._payments(org, start, end)
        total = sum(_f(p.amount) for p in pays)
        by_method: dict = {}
        for p in pays:
            b = by_method.setdefault(p.method, {"count": 0, "amount": 0.0})
            b["count"] += 1
            b["amount"] += _f(p.amount)
        return {"count": len(pays), "total": round(total, 2),
                "avg": round(total / len(pays), 2) if pays else 0.0,
                "by_method": [{"method": k, "count": v["count"], "amount": round(v["amount"], 2)}
                              for k, v in sorted(by_method.items(), key=lambda kv: -kv[1]["amount"])]}

    async def taxes(self, actor: User, date_from=None, date_to=None) -> dict:
        self._require_manager(actor)
        org = actor.organization_id
        start, end, _ = self._window(date_from, date_to)
        invs = await self._invoices(org, start, end)
        tax = sum(_f(i.tax_amount) for i in invs)
        subtotal = sum(_f(i.subtotal) for i in invs)
        return {"tax_collected": round(tax, 2), "taxable_base": round(subtotal, 2),
                "effective_rate": round(tax * 100 / subtotal, 2) if subtotal else 0.0, "invoice_count": len(invs)}

    # ================= recurring: subscription / MRR / ARR / churn / LTV / CAC =================
    async def recurring(self, actor: User, date_from=None, date_to=None) -> dict:
        self._require_manager(actor)
        org = actor.organization_id
        start, end, _ = self._window(date_from, date_to)
        contracts = await self._contracts(org)
        active = [c for c in contracts if c.status in ("Active", "Renewed")]
        mrr = sum(self._mrr_of(c) for c in active)
        active_customers = len({c.company_id for c in active})
        arpa = round(mrr / active_customers, 2) if active_customers else 0.0
        # churn over the window (contracts ended Terminated/Expired with end_date in window)
        churned = [c for c in contracts if c.status in ("Terminated", "Expired")
                   and c.end_date and start.date() <= c.end_date <= end.date()]
        base = len(active) + len(churned)
        churn_rate = self._rate(len(churned), base)
        # LTV: lifetime invoiced revenue per paying customer; plus SaaS ARPA/churn view
        invs = await self._invoices(org, None, None, window=False)
        by_cust: dict = {}
        for i in invs:
            by_cust[i.company_id] = by_cust.get(i.company_id, 0.0) + _f(i.total_amount)
        ltv_lifetime = round(sum(by_cust.values()) / len(by_cust), 2) if by_cust else 0.0
        monthly_churn = churn_rate / 100
        ltv_saas = round(arpa / monthly_churn, 2) if monthly_churn else round(arpa * 24, 2)
        # CAC = acquisition spend / new customers in window
        exps = await self._expenses(org, start.date(), end.date())
        acq_spend = sum(_f(e.amount) for e in exps if e.category in ACQUISITION_CATEGORIES)
        new_customers = (await self.db.execute(select(func.count(Company.id)).filter(
            Company.organization_id == org, Company.is_deleted == False, Company.company_type == "Customer",
            Company.created_at >= start, Company.created_at <= end))).scalar() or 0
        cac = round(acq_spend / new_customers, 2) if new_customers else 0.0
        return {
            "subscription_revenue": round(mrr, 2), "mrr": round(mrr, 2), "arr": round(mrr * 12, 2),
            "active_contracts": len(active), "active_customers": active_customers, "arpa": arpa,
            "churned_contracts": len(churned), "churn_rate": churn_rate,
            "ltv": ltv_lifetime, "ltv_saas": ltv_saas,
            "cac": cac, "acquisition_spend": round(acq_spend, 2), "new_customers": new_customers,
            "ltv_cac_ratio": round(ltv_lifetime / cac, 2) if cac else 0.0,
        }

    # ================= forecast / trend =================
    async def forecast(self, actor: User, date_from=None, date_to=None) -> dict:
        self._require_manager(actor)
        org = actor.organization_id
        start, end, days = self._window(date_from, date_to)
        pays = await self._payments(org, start, end)
        collected = sum(_f(p.amount) for p in pays)
        monthly_run_rate = round(collected / days * 30, 2)
        contracts = await self._contracts(org)
        mrr = round(sum(self._mrr_of(c) for c in contracts if c.status in ("Active", "Renewed")), 2)
        open_invs = await self._invoices(org, None, None, window=False)
        outstanding = sum(_f(i.total_amount) - _f(i.amount_paid) for i in open_invs)
        overdue = sum(_f(i.total_amount) - _f(i.amount_paid) for i in open_invs if i.status == "Overdue")
        expected_ar = max(0.0, outstanding - overdue)
        projected_next_month = round(monthly_run_rate + mrr + expected_ar * 0.5, 2)
        return {"monthly_run_rate": monthly_run_rate, "mrr": mrr, "expected_ar_collection": round(expected_ar, 2),
                "projected_next_month": projected_next_month, "projected_arr": round(mrr * 12, 2)}

    async def trend(self, actor: User, granularity="monthly", date_from=None, date_to=None) -> dict:
        self._require_manager(actor)
        if granularity not in GRANULARITIES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"granularity must be one of {list(GRANULARITIES)}")
        org = actor.organization_id
        start, end, _ = self._window(date_from, date_to)

        def bkey(d: date) -> str:
            if granularity == "daily":
                return d.isoformat()
            if granularity == "weekly":
                return (d - timedelta(days=d.weekday())).isoformat()
            return d.replace(day=1).isoformat()

        buckets: dict = {}

        def cell(k):
            return buckets.setdefault(k, {"bucket": k, "revenue": 0.0, "collected": 0.0, "expenses": 0.0, "profit": 0.0})

        for i in await self._invoices(org, start, end):
            cell(bkey(_aware(i.created_at).date()))["revenue"] += _f(i.total_amount)
        for p in await self._payments(org, start, end):
            cell(bkey(_aware(p.created_at).date()))["collected"] += _f(p.amount)
        for e in await self._expenses(org, start.date(), end.date()):
            cell(bkey(e.incurred_at))["expenses"] += _f(e.amount)
        series = []
        for k in sorted(buckets):
            b = buckets[k]
            b["profit"] = round(b["revenue"] - b["expenses"], 2)
            for m in ("revenue", "collected", "expenses"):
                b[m] = round(b[m], 2)
            series.append(b)
        return {"granularity": granularity, "from": start.date().isoformat(), "to": end.date().isoformat(), "series": series}

    async def dashboard(self, actor: User) -> dict:
        ov = await self.overview(actor, None, None)
        rec = await self.recurring(actor, None, None)
        return {"revenue": ov["revenue_billed"], "collected": ov["collections"], "expenses": ov["expenses"],
                "gross_profit": ov["gross_profit"], "profit_margin": ov["profit_margin"],
                "outstanding": ov["outstanding"], "mrr": rec["mrr"], "arr": rec["arr"], "churn_rate": rec["churn_rate"]}

    # ================= expenses CRUD =================
    async def list_expenses(self, actor: User, date_from=None, date_to=None, category=None) -> list[dict]:
        self._require_manager(actor)
        q = select(Expense).filter(Expense.organization_id == actor.organization_id, Expense.is_deleted == False)
        if date_from:
            q = q.filter(Expense.incurred_at >= date_from)
        if date_to:
            q = q.filter(Expense.incurred_at <= date_to)
        if category:
            q = q.filter(Expense.category == category)
        rows = (await self.db.execute(q.order_by(Expense.incurred_at.desc()))).scalars().all()
        return [self._serialize_expense(e) for e in rows]

    async def create_expense(self, actor: User, data: dict) -> dict:
        self._require_manager(actor)
        if _f(data.get("amount")) <= 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="amount must be positive.")
        e = Expense(organization_id=actor.organization_id, category=data.get("category") or "General",
                    amount=data["amount"], description=data.get("description"), vendor=data.get("vendor"),
                    incurred_at=data.get("incurred_at") or date.today(), created_by=actor.id)
        self.db.add(e)
        await self.db.flush()
        await self.db.refresh(e)
        return self._serialize_expense(e)

    async def update_expense(self, actor: User, expense_id: uuid.UUID, data: dict) -> dict:
        self._require_manager(actor)
        e = await self._get_expense(actor, expense_id)
        for f in ("category", "amount", "description", "vendor", "incurred_at"):
            if f in data and data[f] is not None:
                setattr(e, f, data[f])
        self.db.add(e)
        await self.db.flush()
        await self.db.refresh(e)
        return self._serialize_expense(e)

    async def delete_expense(self, actor: User, expense_id: uuid.UUID) -> None:
        self._require_manager(actor)
        e = await self._get_expense(actor, expense_id)
        e.is_deleted = True
        self.db.add(e)
        await self.db.flush()

    async def _get_expense(self, actor: User, expense_id: uuid.UUID) -> Expense:
        e = (await self.db.execute(select(Expense).filter(
            Expense.id == expense_id, Expense.organization_id == actor.organization_id,
            Expense.is_deleted == False))).scalars().first()
        if not e:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Expense not found")
        return e

    def _serialize_expense(self, e: Expense) -> dict:
        return {"id": str(e.id), "category": e.category, "amount": _f(e.amount), "description": e.description,
                "vendor": e.vendor, "incurred_at": e.incurred_at.isoformat() if e.incurred_at else None,
                "created_at": e.created_at.isoformat() if e.created_at else None}

    # ---------- helpers / export ----------
    async def _company_names(self, ids) -> dict:
        ids = [i for i in ids if i]
        if not ids:
            return {}
        rows = await self.db.execute(select(Company.id, Company.name).filter(Company.id.in_(ids)))
        return {cid: nm for cid, nm in rows.all()}

    async def export_csv(self, actor: User, date_from=None, date_to=None) -> str:
        ov = await self.overview(actor, date_from, date_to)
        rec = await self.recurring(actor, date_from, date_to)
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["Financial analytics", f"{ov['from']} → {ov['to']}"])
        w.writerow([])
        w.writerow(["Metric", "Value"])
        for k in ("revenue_billed", "revenue_collected", "expenses", "gross_profit", "profit_margin",
                  "collections", "outstanding", "overdue", "tax_collected", "invoice_count"):
            w.writerow([k, ov[k]])
        for k in ("subscription_revenue", "mrr", "arr", "churn_rate", "ltv", "cac", "ltv_cac_ratio"):
            w.writerow([k, rec[k]])
        return buf.getvalue()
