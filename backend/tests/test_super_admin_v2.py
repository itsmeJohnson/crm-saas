"""
Unit tests for Super Admin Control Center v2.
These tests run without a live DB using mocking.
"""
import uuid
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def make_currency(code="INR", name="Indian Rupee", symbol="₹",
                  exchange_rate=1.0, is_base=True, is_active=True):
    c = MagicMock()
    c.code = code
    c.name = name
    c.symbol = symbol
    c.exchange_rate = exchange_rate
    c.is_base = is_base
    c.is_active = is_active
    c.source = "manual"
    c.last_updated = datetime.now(timezone.utc)
    return c


def make_tax_config(country_code="IN", tax_type="GST", tax_rate=18.0,
                    is_default=True, is_deleted=False):
    t = MagicMock()
    t.id = uuid.uuid4()
    t.country_code = country_code
    t.country_name = "India"
    t.tax_type = tax_type
    t.tax_rate = tax_rate
    t.tax_label = f"{tax_type} @{tax_rate}%"
    t.tax_inclusive = False
    t.is_active = True
    t.is_default = is_default
    t.is_deleted = is_deleted
    t.state_code = None
    t.created_at = datetime.now(timezone.utc)
    return t


def make_gateway(name="razorpay", is_enabled=False, is_deleted=False):
    g = MagicMock()
    g.id = uuid.uuid4()
    g.name = name
    g.display_name = name.title()
    g.is_enabled = is_enabled
    g.is_sandbox = True
    g.api_key = None
    g.api_secret = None
    g.webhook_secret = None
    g.extra_config = None
    g.sort_order = 1
    g.description = f"{name} gateway"
    g.is_deleted = is_deleted
    return g


def make_template(key="trial_reminder", channel="email", is_deleted=False):
    t = MagicMock()
    t.id = uuid.uuid4()
    t.template_key = key
    t.template_name = key.replace("_", " ").title()
    t.channel = channel
    t.subject = f"Subject for {key}"
    t.body = f"Body for {key}"
    t.variables = ["org_name"]
    t.is_active = True
    t.category = "billing"
    t.description = None
    t.is_deleted = is_deleted
    t.created_at = datetime.now(timezone.utc)
    t.updated_at = datetime.now(timezone.utc)
    return t


def make_coupon(code="SAVE10", discount_type="percentage",
                discount_value=10.0, is_deleted=False):
    c = MagicMock()
    c.id = uuid.uuid4()
    c.code = code
    c.description = "Test coupon"
    c.discount_type = discount_type
    c.discount_value = discount_value
    c.max_uses = None
    c.uses_count = 0
    c.valid_from = datetime.now(timezone.utc)
    c.valid_until = None
    c.min_order_value = 0.0
    c.applicable_plans = None
    c.is_active = True
    c.notes = None
    c.is_deleted = is_deleted
    c.created_at = datetime.now(timezone.utc)
    return c


# ─────────────────────────────────────────────────────────────────────────────
# Schema tests (no DB needed)
# ─────────────────────────────────────────────────────────────────────────────

class TestCurrencySchemas:
    def test_currency_create_defaults(self):
        from app.schemas.currency import CurrencyCreate
        schema = CurrencyCreate(code="USD", name="US Dollar", symbol="$")
        assert schema.exchange_rate == 1.0
        assert schema.is_base is False
        assert schema.is_active is True
        assert schema.source == "manual"

    def test_currency_update_partial(self):
        from app.schemas.currency import CurrencyUpdate
        schema = CurrencyUpdate(exchange_rate=0.012)
        assert schema.exchange_rate == 0.012
        assert schema.name is None

    def test_currency_response_from_attributes(self):
        from app.schemas.currency import CurrencyResponse
        c = make_currency()
        resp = CurrencyResponse.model_validate(c, from_attributes=True)
        assert resp.code == "INR"
        assert resp.is_base is True


class TestTaxConfigSchemas:
    def test_tax_config_create_defaults(self):
        from app.schemas.tax_config import TaxConfigCreate
        schema = TaxConfigCreate(country_code="IN", country_name="India")
        assert schema.tax_type == "GST"
        assert schema.tax_rate == 0.0
        assert schema.tax_inclusive is False
        assert schema.is_default is False

    def test_tax_config_response_from_attributes(self):
        from app.schemas.tax_config import TaxConfigResponse
        t = make_tax_config()
        resp = TaxConfigResponse.model_validate(t, from_attributes=True)
        assert resp.country_code == "IN"
        assert resp.tax_rate == 18.0


class TestPaymentGatewaySchemas:
    def test_gateway_response_hides_secrets(self):
        from app.schemas.payment_gateway import PaymentGatewayResponse
        gw = make_gateway()
        gw.api_key = "sk_live_secret"
        gw.api_secret = "secret_value"
        gw.webhook_secret = "wh_secret"
        resp = PaymentGatewayResponse.from_model(gw)
        assert resp.api_key_set is True
        assert resp.webhook_secret_set is True
        assert not hasattr(resp, "api_secret")
        assert not hasattr(resp, "api_key")

    def test_gateway_response_no_secrets(self):
        from app.schemas.payment_gateway import PaymentGatewayResponse
        gw = make_gateway()
        resp = PaymentGatewayResponse.from_model(gw)
        assert resp.api_key_set is False
        assert resp.webhook_secret_set is False


class TestCouponSchemas:
    def test_coupon_create_validation_negative_discount(self):
        from app.schemas.coupon import CouponCreate
        with pytest.raises(Exception):
            CouponCreate(
                code="BAD",
                discount_value=-5.0,
                valid_from=datetime.now(timezone.utc)
            )

    def test_coupon_create_valid(self):
        from app.schemas.coupon import CouponCreate
        schema = CouponCreate(
            code="SAVE10",
            discount_type="percentage",
            discount_value=10.0,
            valid_from=datetime.now(timezone.utc)
        )
        assert schema.code == "SAVE10"
        assert schema.discount_value == 10.0

    def test_coupon_response_from_attributes(self):
        from app.schemas.coupon import CouponResponse
        c = make_coupon()
        resp = CouponResponse.model_validate(c, from_attributes=True)
        assert resp.code == "SAVE10"
        assert resp.uses_count == 0


class TestNotificationTemplateSchemas:
    def test_template_create_defaults(self):
        from app.schemas.notification_template import NotificationTemplateCreate
        schema = NotificationTemplateCreate(
            template_key="test_key",
            template_name="Test Template"
        )
        assert schema.channel == "email"
        assert schema.category == "billing"
        assert schema.is_active is True

    def test_template_response_from_attributes(self):
        from app.schemas.notification_template import NotificationTemplateResponse
        t = make_template()
        resp = NotificationTemplateResponse.model_validate(t, from_attributes=True)
        assert resp.template_key == "trial_reminder"
        assert resp.channel == "email"


class TestDashboardSchemas:
    def test_dashboard_response_structure(self):
        from app.schemas.dashboard import (
            SuperAdminDashboardResponse, OrgMetrics, RevenueMetrics,
            LicensingMetrics, InfraMetrics, ActivityMetrics
        )
        resp = SuperAdminDashboardResponse(
            orgs=OrgMetrics(total=10, active=8, trial=1, expired=0, suspended=1, new_today=2),
            revenue=RevenueMetrics(mrr=50000.0, arr=600000.0, total_collected=200000.0,
                                   pending=10000.0, failed_count=2, overdue_count=1),
            licensing=LicensingMetrics(total_licensed_seats=500, active_seats=420,
                                       available_seats=80, utilization_percent=84.0),
            infra=InfraMetrics(total_storage_gb=150.5, call_recording_gb=20.0,
                               db_status="healthy", redis_status="healthy"),
            activity=ActivityMetrics(new_orgs_today=2, renewals_due_7days=3,
                                      trials_expiring_7days=1, new_invoices_today=5,
                                      payments_today=4),
            generated_at=datetime.now(timezone.utc)
        )
        assert resp.orgs.total == 10
        assert resp.revenue.arr == 600000.0
        assert resp.licensing.utilization_percent == 84.0
        assert resp.infra.db_status == "healthy"


class TestReportsSchemas:
    def test_monthly_revenue(self):
        from app.schemas.reports import MonthlyRevenue
        m = MonthlyRevenue(month="2026-01", mrr=50000.0, collections=45000.0, new_subscriptions=3)
        assert m.mrr == 50000.0

    def test_tenant_summary_report(self):
        from app.schemas.reports import TenantSummaryReport
        r = TenantSummaryReport(total=20, active=15, trial=3, expired=1, suspended=1,
                                by_plan=[{"plan": "Starter", "count": 10}])
        assert r.total == 20
        assert len(r.by_plan) == 1


# ─────────────────────────────────────────────────────────────────────────────
# Currency Service tests (mock DB)
# ─────────────────────────────────────────────────────────────────────────────

class TestCurrencyService:
    @pytest.mark.asyncio
    async def test_get_all_returns_currencies(self):
        from app.services.currency_service import CurrencyService
        db = AsyncMock()
        mock_result = MagicMock()
        currencies = [make_currency("INR"), make_currency("USD", is_base=False, exchange_rate=0.012)]
        mock_result.scalars.return_value.all.return_value = currencies
        db.execute = AsyncMock(return_value=mock_result)

        service = CurrencyService(db)
        result = await service.get_all()
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_get_existing_currency(self):
        from app.services.currency_service import CurrencyService
        db = AsyncMock()
        inr = make_currency("INR")
        db.get = AsyncMock(return_value=inr)

        service = CurrencyService(db)
        result = await service.get("INR")
        assert result.code == "INR"

    @pytest.mark.asyncio
    async def test_get_missing_currency_raises_404(self):
        from app.services.currency_service import CurrencyService
        from fastapi import HTTPException
        db = AsyncMock()
        db.get = AsyncMock(return_value=None)

        service = CurrencyService(db)
        with pytest.raises(HTTPException) as exc:
            await service.get("XYZ")
        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_convert_same_currency_returns_same_amount(self):
        from app.services.currency_service import CurrencyService
        db = AsyncMock()
        service = CurrencyService(db)
        result = await service.convert(100.0, "INR", "INR")
        assert result == 100.0

    @pytest.mark.asyncio
    async def test_convert_inr_to_usd(self):
        from app.services.currency_service import CurrencyService
        db = AsyncMock()
        inr = make_currency("INR", exchange_rate=1.0, is_base=True)
        usd = make_currency("USD", exchange_rate=0.012, is_base=False)

        service = CurrencyService(db)
        service.get = AsyncMock(side_effect=lambda code: inr if code.upper() == "INR" else usd)
        result = await service.convert(1000.0, "INR", "USD")
        # 1000 / 1.0 * 0.012 = 12.0
        assert result == 12.0

    @pytest.mark.asyncio
    async def test_delete_base_currency_raises_400(self):
        from app.services.currency_service import CurrencyService
        from fastapi import HTTPException
        db = AsyncMock()
        base = make_currency("INR", is_base=True)

        service = CurrencyService(db)
        service.get = AsyncMock(return_value=base)

        with pytest.raises(HTTPException) as exc:
            await service.delete("INR")
        assert exc.value.status_code == 400

    @pytest.mark.asyncio
    async def test_delete_non_base_currency_succeeds(self):
        from app.services.currency_service import CurrencyService
        db = AsyncMock()
        db.commit = AsyncMock()
        usd = make_currency("USD", is_base=False)

        service = CurrencyService(db)
        service.get = AsyncMock(return_value=usd)

        await service.delete("USD")
        assert usd.is_active is False
        db.commit.assert_called_once()


# ─────────────────────────────────────────────────────────────────────────────
# Seeds tests
# ─────────────────────────────────────────────────────────────────────────────

class TestSeedDefaults:
    @pytest.mark.asyncio
    async def test_seed_function_is_importable(self):
        from app.seeds.super_admin_defaults import seed_super_admin_defaults
        assert callable(seed_super_admin_defaults)

    @pytest.mark.asyncio
    async def test_seed_skips_existing_records(self):
        """Seed should skip insert when records already exist."""
        from app.seeds.super_admin_defaults import seed_super_admin_defaults
        db = AsyncMock()
        db.get = AsyncMock(return_value=MagicMock())  # currencies exist
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = MagicMock()  # others exist
        db.execute = AsyncMock(return_value=mock_result)
        db.commit = AsyncMock()

        await seed_super_admin_defaults(db)
        db.commit.assert_called_once()
        db.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_seed_inserts_when_empty(self):
        """Seed should insert records when they do not exist."""
        from app.seeds.super_admin_defaults import seed_super_admin_defaults
        db = AsyncMock()
        db.get = AsyncMock(return_value=None)  # currencies don't exist
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None  # others don't exist
        db.execute = AsyncMock(return_value=mock_result)
        db.commit = AsyncMock()

        await seed_super_admin_defaults(db)
        db.commit.assert_called_once()
        assert db.add.call_count > 0  # records were inserted


# ─────────────────────────────────────────────────────────────────────────────
# Model field existence tests
# ─────────────────────────────────────────────────────────────────────────────

class TestModelFields:
    def test_plan_has_phase3_fields(self):
        from app.models.plan import Plan
        cols = {c.key for c in Plan.__table__.columns}
        required = {
            "quarterly_discount", "annual_discount", "allow_seat_reduction",
            "replace_employee_enabled", "included_minutes", "ai_minutes",
            "extra_storage_price", "sla_hours", "dedicated_manager",
            "base_currency", "price_per_seat"
        }
        missing = required - cols
        assert not missing, f"Missing plan columns: {missing}"

    def test_organization_has_new_fields(self):
        from app.models.organization import Organization
        cols = {c.key for c in Organization.__table__.columns}
        required = {
            "country", "country_code", "plan_id", "onboarding_completed",
            "suspended_at", "suspension_reason", "trial_extended_days"
        }
        missing = required - cols
        assert not missing, f"Missing organization columns: {missing}"

    def test_invoice_has_multicurrency_fields(self):
        from app.models.invoice import Invoice
        cols = {c.key for c in Invoice.__table__.columns}
        required = {
            "base_currency", "invoice_currency", "exchange_rate",
            "base_amount", "converted_amount",
        }
        missing = required - cols
        assert not missing, f"Missing invoice currency columns: {missing}"

    def test_invoice_has_tax_fields(self):
        from app.models.invoice import Invoice
        cols = {c.key for c in Invoice.__table__.columns}
        required = {"tax_type", "tax_label", "tax_rate", "tax_inclusive"}
        missing = required - cols
        assert not missing, f"Missing invoice tax columns: {missing}"

    def test_invoice_has_credit_note_fields(self):
        from app.models.invoice import Invoice
        cols = {c.key for c in Invoice.__table__.columns}
        required = {"is_credit_note", "parent_invoice_id", "credit_reason"}
        missing = required - cols
        assert not missing, f"Missing invoice credit note columns: {missing}"

    def test_invoice_has_billing_detail_fields(self):
        from app.models.invoice import Invoice
        cols = {c.key for c in Invoice.__table__.columns}
        required = {
            "billing_cycle", "billing_period_start", "billing_period_end",
            "seats_billed", "invoice_notes", "emailed_at",
            "coupon_code", "coupon_discount"
        }
        missing = required - cols
        assert not missing, f"Missing invoice billing columns: {missing}"

    def test_payment_has_new_fields(self):
        from app.models.payment import Payment
        cols = {c.key for c in Payment.__table__.columns}
        required = {"amount", "currency", "payment_method", "notes"}
        missing = required - cols
        assert not missing, f"Missing payment columns: {missing}"

    def test_currency_model_structure(self):
        from app.models.currency import Currency
        cols = {c.key for c in Currency.__table__.columns}
        required = {"code", "name", "symbol", "exchange_rate", "is_base", "is_active", "source"}
        missing = required - cols
        assert not missing, f"Missing currency columns: {missing}"

    def test_tax_config_model_structure(self):
        from app.models.tax_config import TaxConfig
        cols = {c.key for c in TaxConfig.__table__.columns}
        required = {"country_code", "country_name", "tax_type", "tax_rate",
                    "tax_label", "tax_inclusive", "is_active", "is_default"}
        missing = required - cols
        assert not missing, f"Missing tax_config columns: {missing}"

    def test_payment_gateway_model_structure(self):
        from app.models.payment_gateway import PaymentGateway
        cols = {c.key for c in PaymentGateway.__table__.columns}
        required = {"name", "display_name", "is_enabled", "is_sandbox",
                    "api_key", "api_secret", "webhook_secret", "sort_order"}
        missing = required - cols
        assert not missing, f"Missing payment_gateway columns: {missing}"

    def test_notification_template_model_structure(self):
        from app.models.notification_template import NotificationTemplate
        cols = {c.key for c in NotificationTemplate.__table__.columns}
        required = {"template_key", "template_name", "channel", "subject",
                    "body", "variables", "is_active", "category"}
        missing = required - cols
        assert not missing, f"Missing notification_template columns: {missing}"

    def test_coupon_model_structure(self):
        from app.models.coupon import Coupon
        cols = {c.key for c in Coupon.__table__.columns}
        required = {"code", "discount_type", "discount_value", "uses_count",
                    "valid_from", "is_active", "created_by"}
        missing = required - cols
        assert not missing, f"Missing coupon columns: {missing}"

    def test_models_init_exports_all_new_models(self):
        from app.models import (
            Currency, TaxConfig, PaymentGateway,
            NotificationTemplate, Coupon
        )
        assert Currency is not None
        assert TaxConfig is not None
        assert PaymentGateway is not None
        assert NotificationTemplate is not None
        assert Coupon is not None
