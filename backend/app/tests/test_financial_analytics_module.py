import pytest
import uuid
from datetime import datetime, date, timezone, timedelta
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, get_password_hash
from app.repositories.organization import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.models.company import Company
from app.models.customer_invoice import CustomerInvoice
from app.models.customer_payment import CustomerPayment
from app.models.contract import Contract
from app.models.expense import Expense
from app.core.redis import redis_client


@pytest.fixture(autouse=True)
def mock_redis(monkeypatch):
    store = {}
    async def g(k): return store.get(k)
    async def s(k, v, ex=300): store[k] = v; return True
    async def d(k): store.pop(k, None); return True
    monkeypatch.setattr(redis_client, "get", g)
    monkeypatch.setattr(redis_client, "set", s)
    monkeypatch.setattr(redis_client, "delete", d)
    from app.dependencies import feature_guard
    async def feats(*a, **k): return ["LEAD_MANAGEMENT","CONTACT_MANAGEMENT","FOLLOW_UP_TASKS","SALES_PIPELINE","CLICK_TO_CALL","BASIC_DASHBOARD","DASHBOARD_REPORTS","BULK_IMPORT","GOOGLE_SHEETS_IMPORT","BULK_ASSIGNMENT","ROLE_BASED_ACCESS","CUSTOM_PIPELINE","LEAD_DISTRIBUTION","KPI_DASHBOARD","TARGET_MANAGEMENT","MANAGER_DASHBOARD","TEAM_LEADER_DASHBOARD","CALL_RECORDING","INBOUND_CALLING","OUTBOUND_CALLING","SMS_MESSAGING","EMAIL_MESSAGING","WHATSAPP_MESSAGING","CAMPAIGN_MANAGEMENT","VOICE_BROADCAST","LEAD_CAPTURE","ADVANCED_PIPELINE","LEAD_TRANSFERS","BULK_TRANSFER","SMART_DISTRIBUTION","TEAM_MONITORING","CALL_DISPOSITION","AI_CALL_SUMMARY","AI_FOLLOW_UP","ADVANCED_ANALYTICS","CONVERSION_ANALYTICS","CUSTOM_REPORTS","PRIORITY_SUPPORT","WHITE_LABEL","API_ACCESS"]
    monkeypatch.setattr(feature_guard, "get_active_features", feats)
    return store


@pytest.fixture
async def setup(db: AsyncSession):
    org = await OrganizationRepository(db).create({"name": "Fin Org", "slug": "fin-org"})
    await db.commit()
    ur = UserRepository(db)
    admin = await ur.create_user(org.id, {"email": "admin@fin.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Ad", "last_name": "Min", "role": "OrgAdmin", "is_active": True})
    await db.commit()
    emp = await ur.create_user(org.id, {"email": "emp@fin.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Em", "last_name": "P", "role": "Employee", "is_active": True, "reporting_to_id": admin.id})
    await db.commit()
    now = datetime.now(timezone.utc)
    cust = Company(organization_id=org.id, name="Acme", company_type="Customer", created_by=admin.id)
    db.add(cust); await db.flush()
    # inv1 paid 1000 (tax 100), inv2 overdue 2000 (tax 200, paid 500, due 40d ago)
    inv1 = CustomerInvoice(organization_id=org.id, company_id=cust.id, invoice_number="I1", status="Paid",
                           subtotal=900, tax_amount=100, total_amount=1000, amount_paid=1000, created_by=admin.id)
    inv2 = CustomerInvoice(organization_id=org.id, company_id=cust.id, invoice_number="I2", status="Overdue",
                           subtotal=1800, tax_amount=200, total_amount=2000, amount_paid=500, created_by=admin.id,
                           due_date=now - timedelta(days=40))
    db.add_all([inv1, inv2]); await db.flush()
    db.add(CustomerPayment(organization_id=org.id, company_id=cust.id, invoice_id=inv1.id, amount=1000,
                           method="BankTransfer", created_by=admin.id, paid_at=now))
    db.add(CustomerPayment(organization_id=org.id, company_id=cust.id, invoice_id=inv2.id, amount=500,
                           method="Card", created_by=admin.id, paid_at=now))
    # active contract value 12000 over 24 months -> MRR 500
    db.add(Contract(organization_id=org.id, company_id=cust.id, contract_number="C1", title="Retainer",
                    status="Active", value=12000, start_date=date.today() - timedelta(days=365),
                    end_date=date.today() + timedelta(days=365), created_by=admin.id))
    # expenses: Marketing 300 (acquisition) + Office 200
    db.add(Expense(organization_id=org.id, category="Marketing", amount=300, incurred_at=date.today(), created_by=admin.id))
    db.add(Expense(organization_id=org.id, category="Office", amount=200, incurred_at=date.today(), created_by=admin.id))
    await db.commit()
    return {"org": org, "admin": admin, "emp": emp, "cust": cust,
            "h_admin": {"Authorization": f"Bearer {create_access_token(admin.id)}"},
            "h_emp": {"Authorization": f"Bearer {create_access_token(emp.id)}"}}


@pytest.mark.asyncio
async def test_overview_and_permissions(client: AsyncClient, setup: dict):
    d = setup
    assert (await client.get("/api/v1/financial-analytics/overview", headers=d["h_emp"])).status_code == 403
    ov = (await client.get("/api/v1/financial-analytics/overview", headers=d["h_admin"])).json()
    assert ov["revenue_billed"] == 3000.0 and ov["revenue_collected"] == 1500.0
    assert ov["expenses"] == 500.0 and ov["gross_profit"] == 2500.0 and ov["profit_margin"] == 83.3
    assert ov["outstanding"] == 1500.0 and ov["overdue"] == 1500.0 and ov["tax_collected"] == 300.0
    assert ov["mrr"] == 500.0 and ov["arr"] == 6000.0 and ov["active_contracts"] == 1


@pytest.mark.asyncio
async def test_collections_outstanding_invoices_payments_taxes(client: AsyncClient, setup: dict):
    d = setup
    col = (await client.get("/api/v1/financial-analytics/collections", headers=d["h_admin"])).json()
    assert col["collected"] == 1500.0 and col["collection_rate"] == 50.0
    assert {m["method"] for m in col["by_method"]} == {"BankTransfer", "Card"}
    out = (await client.get("/api/v1/financial-analytics/outstanding", headers=d["h_admin"])).json()
    assert out["outstanding"] == 1500.0
    b3160 = next(a for a in out["aging"] if a["bucket"] == "31-60")
    assert b3160["amount"] == 1500.0  # due 40 days ago
    inv = (await client.get("/api/v1/financial-analytics/invoices", headers=d["h_admin"])).json()
    assert inv["count"] == 2 and inv["total"] == 3000.0
    pay = (await client.get("/api/v1/financial-analytics/payments", headers=d["h_admin"])).json()
    assert pay["count"] == 2 and pay["total"] == 1500.0
    tax = (await client.get("/api/v1/financial-analytics/taxes", headers=d["h_admin"])).json()
    assert tax["tax_collected"] == 300.0 and tax["taxable_base"] == 2700.0


@pytest.mark.asyncio
async def test_recurring_profitability_forecast(client: AsyncClient, setup: dict):
    d = setup
    rec = (await client.get("/api/v1/financial-analytics/recurring", headers=d["h_admin"])).json()
    assert rec["mrr"] == 500.0 and rec["arr"] == 6000.0 and rec["subscription_revenue"] == 500.0
    assert rec["active_customers"] == 1 and rec["arpa"] == 500.0 and rec["churn_rate"] == 0.0
    assert rec["ltv"] == 3000.0 and rec["cac"] == 300.0 and rec["new_customers"] == 1
    assert rec["ltv_cac_ratio"] == 10.0
    prof = (await client.get("/api/v1/financial-analytics/profitability", headers=d["h_admin"])).json()
    assert prof["revenue"] == 3000.0 and prof["gross_profit"] == 2500.0 and prof["cash_profit"] == 1000.0
    fc = (await client.get("/api/v1/financial-analytics/forecast", headers=d["h_admin"])).json()
    assert fc["mrr"] == 500.0 and "projected_next_month" in fc and fc["projected_arr"] == 6000.0


@pytest.mark.asyncio
async def test_trend_dashboard_export_and_expense_crud(client: AsyncClient, setup: dict):
    d = setup
    tr = (await client.get("/api/v1/financial-analytics/trend", params={"granularity": "monthly"}, headers=d["h_admin"])).json()
    assert tr["granularity"] == "monthly" and sum(b["revenue"] for b in tr["series"]) == 3000.0
    assert (await client.get("/api/v1/financial-analytics/trend", params={"granularity": "yearly"}, headers=d["h_admin"])).status_code == 400
    dash = (await client.get("/api/v1/financial-analytics/dashboard", headers=d["h_admin"])).json()
    assert dash["revenue"] == 3000.0 and dash["mrr"] == 500.0 and dash["gross_profit"] == 2500.0
    exp = await client.get("/api/v1/financial-analytics/export", headers=d["h_admin"])
    assert exp.status_code == 200 and "Financial analytics" in exp.text and "mrr" in exp.text
    # expense CRUD
    assert (await client.post("/api/v1/financial-analytics/expense-records",
            json={"category": "Software", "amount": 50}, headers=d["h_emp"])).status_code == 403
    e = (await client.post("/api/v1/financial-analytics/expense-records", json={
        "category": "Software", "amount": 150, "vendor": "Zoom"}, headers=d["h_admin"])).json()
    assert e["amount"] == 150.0 and e["category"] == "Software"
    # negative amount rejected (schema gt=0)
    assert (await client.post("/api/v1/financial-analytics/expense-records",
            json={"category": "x", "amount": -5}, headers=d["h_admin"])).status_code == 422
    # now expenses total reflects the new record
    er = (await client.get("/api/v1/financial-analytics/expenses", headers=d["h_admin"])).json()
    assert er["total"] == 650.0  # 300 + 200 + 150
    lst = (await client.get("/api/v1/financial-analytics/expense-records", headers=d["h_admin"])).json()
    assert any(x["id"] == e["id"] for x in lst)
    assert (await client.delete(f"/api/v1/financial-analytics/expense-records/{e['id']}", headers=d["h_admin"])).status_code == 204
