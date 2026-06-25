from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select


async def seed_super_admin_defaults(db: AsyncSession):
    """Seed default currencies, tax configs, payment gateways, and notification templates."""
    from app.models.currency import Currency
    from app.models.tax_config import TaxConfig
    from app.models.payment_gateway import PaymentGateway
    from app.models.notification_template import NotificationTemplate

    # Currencies
    default_currencies = [
        {"code": "INR", "name": "Indian Rupee", "symbol": "₹", "exchange_rate": 1.0, "is_base": True},
        {"code": "USD", "name": "US Dollar", "symbol": "$", "exchange_rate": 0.012},
        {"code": "EUR", "name": "Euro", "symbol": "€", "exchange_rate": 0.011},
        {"code": "GBP", "name": "British Pound", "symbol": "£", "exchange_rate": 0.0095},
        {"code": "AED", "name": "UAE Dirham", "symbol": "د.إ", "exchange_rate": 0.044},
        {"code": "SGD", "name": "Singapore Dollar", "symbol": "S$", "exchange_rate": 0.016},
        {"code": "AUD", "name": "Australian Dollar", "symbol": "A$", "exchange_rate": 0.018},
    ]

    # Tax configs
    default_taxes = [
        {"country_code": "IN", "country_name": "India", "tax_type": "GST", "tax_rate": 18.0, "tax_label": "GST @18%", "is_default": True},
        {"country_code": "US", "country_name": "United States", "tax_type": "SALES_TAX", "tax_rate": 10.0, "tax_label": "Sales Tax"},
        {"country_code": "GB", "country_name": "United Kingdom", "tax_type": "VAT", "tax_rate": 20.0, "tax_label": "VAT @20%"},
        {"country_code": "AE", "country_name": "United Arab Emirates", "tax_type": "VAT", "tax_rate": 5.0, "tax_label": "VAT @5%"},
        {"country_code": "AU", "country_name": "Australia", "tax_type": "GST", "tax_rate": 10.0, "tax_label": "GST @10%"},
        {"country_code": "SG", "country_name": "Singapore", "tax_type": "GST", "tax_rate": 9.0, "tax_label": "GST @9%"},
    ]

    # Payment gateways
    default_gateways = [
        {"name": "razorpay", "display_name": "Razorpay", "sort_order": 1, "description": "India's leading payment gateway"},
        {"name": "stripe", "display_name": "Stripe", "sort_order": 2, "description": "Global payment processing"},
        {"name": "paypal", "display_name": "PayPal", "sort_order": 3, "description": "PayPal payments"},
        {"name": "cashfree", "display_name": "Cashfree", "sort_order": 4, "description": "Cashfree payments for India"},
        {"name": "bank_transfer", "display_name": "Bank Transfer", "sort_order": 5, "description": "Direct bank transfer / NEFT / RTGS"},
        {"name": "manual", "display_name": "Manual Payment", "sort_order": 6, "description": "Manual payment recording"},
    ]

    # Notification templates
    default_templates = [
        {
            "template_key": "trial_reminder",
            "template_name": "Trial Ending Reminder",
            "channel": "email",
            "category": "trial",
            "subject": "Your trial ends in {days_remaining} days",
            "body": "Dear {organization_name},\n\nYour trial period ends on {trial_end_date}. Upgrade now to continue using all features.\n\nBest regards,\nCRM Enterprise Team",
            "variables": ["organization_name", "days_remaining", "trial_end_date", "upgrade_url"]
        },
        {
            "template_key": "trial_expired",
            "template_name": "Trial Expired",
            "channel": "email",
            "category": "trial",
            "subject": "Your trial has expired",
            "body": "Dear {organization_name},\n\nYour trial period has ended. Please upgrade your plan to continue.\n\nBest regards,\nCRM Enterprise Team",
            "variables": ["organization_name", "upgrade_url"]
        },
        {
            "template_key": "invoice_generated",
            "template_name": "Invoice Generated",
            "channel": "email",
            "category": "billing",
            "subject": "Invoice #{invoice_number} from CRM Enterprise",
            "body": "Dear {organization_name},\n\nInvoice #{invoice_number} for {amount} has been generated.\nDue date: {due_date}\n\nBest regards,\nCRM Enterprise Team",
            "variables": ["organization_name", "invoice_number", "amount", "due_date", "invoice_url"]
        },
        {
            "template_key": "payment_success",
            "template_name": "Payment Received",
            "channel": "email",
            "category": "billing",
            "subject": "Payment Confirmed - Invoice #{invoice_number}",
            "body": "Dear {organization_name},\n\nWe've received your payment of {amount} for invoice #{invoice_number}. Thank you!\n\nBest regards,\nCRM Enterprise Team",
            "variables": ["organization_name", "invoice_number", "amount", "payment_date"]
        },
        {
            "template_key": "payment_failed",
            "template_name": "Payment Failed",
            "channel": "email",
            "category": "billing",
            "subject": "Payment Failed - Action Required",
            "body": "Dear {organization_name},\n\nYour payment of {amount} for invoice #{invoice_number} has failed. Please update your payment details.\n\nBest regards,\nCRM Enterprise Team",
            "variables": ["organization_name", "invoice_number", "amount", "payment_url"]
        },
        {
            "template_key": "renewal_reminder",
            "template_name": "Subscription Renewal Reminder",
            "channel": "email",
            "category": "billing",
            "subject": "Your subscription renews on {renewal_date}",
            "body": "Dear {organization_name},\n\nYour subscription will auto-renew on {renewal_date}. Invoice amount: {amount}.\n\nBest regards,\nCRM Enterprise Team",
            "variables": ["organization_name", "renewal_date", "amount", "plan_name"]
        },
        {
            "template_key": "welcome",
            "template_name": "Welcome Email",
            "channel": "email",
            "category": "onboarding",
            "subject": "Welcome to CRM Enterprise - {organization_name}",
            "body": "Dear {admin_name},\n\nWelcome to CRM Enterprise! Your account is ready.\n\nLogin: {login_url}\nPlan: {plan_name}\n\nBest regards,\nCRM Enterprise Team",
            "variables": ["admin_name", "organization_name", "login_url", "plan_name", "seats"]
        },
        {
            "template_key": "seat_limit_warning",
            "template_name": "Seat Limit Warning",
            "channel": "email",
            "category": "usage",
            "subject": "Seat limit reached - {organization_name}",
            "body": "Dear {organization_name},\n\nYou have used {active_seats} of {licensed_seats} licensed seats. Consider upgrading.\n\nBest regards,\nCRM Enterprise Team",
            "variables": ["organization_name", "active_seats", "licensed_seats", "upgrade_url"]
        },
    ]

    # Seed currencies
    for c in default_currencies:
        existing = await db.get(Currency, c["code"])
        if not existing:
            db.add(Currency(**c))

    # Seed tax configs
    for t in default_taxes:
        res = await db.execute(
            select(TaxConfig).where(TaxConfig.country_code == t["country_code"], TaxConfig.is_deleted == False)
        )
        if not res.scalar_one_or_none():
            db.add(TaxConfig(**t))

    # Seed gateways
    for g in default_gateways:
        res = await db.execute(
            select(PaymentGateway).where(PaymentGateway.name == g["name"], PaymentGateway.is_deleted == False)
        )
        if not res.scalar_one_or_none():
            db.add(PaymentGateway(**g))

    # Seed notification templates
    for tmpl in default_templates:
        res = await db.execute(
            select(NotificationTemplate).where(
                NotificationTemplate.template_key == tmpl["template_key"],
                NotificationTemplate.is_deleted == False
            )
        )
        if not res.scalar_one_or_none():
            db.add(NotificationTemplate(**tmpl))

    await db.commit()
