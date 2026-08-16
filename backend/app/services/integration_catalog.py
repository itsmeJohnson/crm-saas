"""Integration Hub connector catalog.

Every connector is DATA, not a bespoke client: a category, an auth type, a base
URL, a health-check endpoint and the credential fields it needs. The generic
connector runtime in `integration_service.py` reads these entries, so adding a
provider is a catalog edit rather than a new module.

`managed_by` marks a category whose credentials already live in a first-class
module (SMS, WhatsApp, email, payment, BI storage, event webhooks). Those appear
in the hub as read-only mirror rows — the hub gives one inventory and one health
view without ever duplicating or overriding the owning module.

No provider is privileged: an org picks whichever it uses, and `custom` exists in
every category for anything not listed.
"""

# category key -> label + the module that owns credentials (None = the hub owns them)
CATEGORIES: dict[str, dict] = {
    "payment": {"label": "Payment Providers", "managed_by": "payment_gateways"},
    "calling": {"label": "Calling Providers", "managed_by": None},
    "sms": {"label": "SMS Providers", "managed_by": "sms_settings"},
    "whatsapp": {"label": "WhatsApp Providers", "managed_by": "whatsapp_settings"},
    "email": {"label": "Email Providers", "managed_by": "email_settings"},
    "calendar": {"label": "Calendar Providers", "managed_by": None},
    "storage": {"label": "Cloud Storage", "managed_by": None},
    "erp": {"label": "ERP", "managed_by": None},
    "accounting": {"label": "Accounting", "managed_by": None},
    "hrms": {"label": "HRMS", "managed_by": None},
    "ecommerce": {"label": "E-commerce", "managed_by": None},
    "marketing": {"label": "Marketing", "managed_by": None},
    "social": {"label": "Social Media", "managed_by": None},
    "crm": {"label": "CRM Connectors", "managed_by": None},
    "identity": {"label": "Identity Providers", "managed_by": None},
    "webhook": {"label": "Webhook Connectors", "managed_by": None},
    "api": {"label": "API Connectors", "managed_by": None},
}

AUTH_TYPES = ("api_key", "basic", "bearer", "oauth2", "ldap", "saml", "none")

# Credential field sets by auth type — drives the UI form and validation.
AUTH_FIELDS: dict[str, list[str]] = {
    "api_key": ["api_key"],
    "basic": ["username", "password"],
    "bearer": ["token"],
    "oauth2": ["client_id", "client_secret", "refresh_token"],
    "ldap": ["bind_dn", "bind_password"],
    "saml": ["idp_metadata_url", "certificate"],
    "none": [],
}


def _c(key, label, category, auth_type, *, base_url=None, health_path=None,
       capabilities=None, docs=None, config_fields=None):
    return {
        "key": key, "label": label, "category": category, "auth_type": auth_type,
        "base_url": base_url, "health_path": health_path,
        "capabilities": capabilities or [], "docs": docs,
        "credential_fields": AUTH_FIELDS.get(auth_type, []),
        "config_fields": config_fields or [],
    }


CONNECTORS: list[dict] = [
    # ---------------- Calling ----------------
    _c("twilio_voice", "Twilio Voice", "calling", "basic",
       base_url="https://api.twilio.com/2010-04-01", health_path="/Accounts.json",
       capabilities=["outbound_call", "recording", "call_status"], docs="https://www.twilio.com/docs/voice",
       config_fields=["account_sid", "caller_id"]),
    _c("exotel", "Exotel", "calling", "basic",
       base_url="https://api.exotel.com/v1", health_path="/Accounts",
       capabilities=["outbound_call", "call_status"], config_fields=["account_sid", "caller_id"]),
    _c("knowlarity", "Knowlarity", "calling", "api_key",
       base_url="https://kpi.knowlarity.com/Basic/v1/account",
       capabilities=["outbound_call", "call_status"], config_fields=["caller_id"]),
    _c("plivo", "Plivo", "calling", "basic",
       base_url="https://api.plivo.com/v1", capabilities=["outbound_call", "recording"],
       config_fields=["auth_id", "caller_id"]),

    # ---------------- Calendar ----------------
    _c("google_calendar", "Google Calendar", "calendar", "oauth2",
       base_url="https://www.googleapis.com/calendar/v3", health_path="/users/me/calendarList",
       capabilities=["two_way_sync", "free_busy", "invites"],
       docs="https://developers.google.com/calendar", config_fields=["calendar_id", "sync_direction"]),
    _c("outlook_calendar", "Outlook / Microsoft 365", "calendar", "oauth2",
       base_url="https://graph.microsoft.com/v1.0", health_path="/me/calendars",
       capabilities=["two_way_sync", "free_busy", "invites"], config_fields=["calendar_id", "sync_direction"]),
    _c("caldav", "CalDAV", "calendar", "basic",
       capabilities=["two_way_sync"], config_fields=["caldav_url"]),

    # ---------------- Cloud storage ----------------
    _c("aws_s3", "Amazon S3", "storage", "api_key",
       capabilities=["upload", "download", "archive"], config_fields=["bucket", "region", "prefix"]),
    _c("azure_blob", "Azure Blob Storage", "storage", "api_key",
       capabilities=["upload", "download"], config_fields=["container", "account_name"]),
    _c("gcs", "Google Cloud Storage", "storage", "oauth2",
       capabilities=["upload", "download"], config_fields=["bucket", "prefix"]),
    _c("dropbox", "Dropbox", "storage", "bearer",
       base_url="https://api.dropboxapi.com/2", capabilities=["upload", "download"],
       config_fields=["folder"]),
    _c("google_drive", "Google Drive", "storage", "oauth2",
       base_url="https://www.googleapis.com/drive/v3", health_path="/about?fields=user",
       capabilities=["upload", "download"], config_fields=["folder_id"]),

    # ---------------- ERP ----------------
    _c("sap_business_one", "SAP Business One", "erp", "basic",
       health_path="/b1s/v1/Login", capabilities=["sync_customers", "sync_orders", "sync_inventory"],
       config_fields=["company_db"]),
    _c("odoo", "Odoo", "erp", "api_key",
       health_path="/web/session/get_session_info",
       capabilities=["sync_customers", "sync_orders", "sync_invoices"], config_fields=["database"]),
    _c("microsoft_dynamics", "Microsoft Dynamics 365", "erp", "oauth2",
       base_url="https://graph.microsoft.com/v1.0",
       capabilities=["sync_customers", "sync_orders"], config_fields=["tenant_id", "environment_url"]),
    _c("netsuite", "Oracle NetSuite", "erp", "oauth2",
       capabilities=["sync_customers", "sync_orders", "sync_invoices"], config_fields=["account_id"]),
    _c("tally", "Tally ERP", "erp", "none",
       capabilities=["sync_invoices", "sync_ledgers"], config_fields=["server_url", "company_name"]),

    # ---------------- Accounting ----------------
    _c("quickbooks", "QuickBooks Online", "accounting", "oauth2",
       base_url="https://quickbooks.api.intuit.com/v3", capabilities=["sync_invoices", "sync_payments", "sync_customers"],
       config_fields=["realm_id"]),
    _c("xero", "Xero", "accounting", "oauth2",
       base_url="https://api.xero.com/api.xro/2.0", health_path="/Organisation",
       capabilities=["sync_invoices", "sync_payments"], config_fields=["tenant_id"]),
    _c("zoho_books", "Zoho Books", "accounting", "oauth2",
       base_url="https://www.zohoapis.com/books/v3", health_path="/organizations",
       capabilities=["sync_invoices", "sync_payments"], config_fields=["organization_id"]),
    _c("freshbooks", "FreshBooks", "accounting", "oauth2",
       base_url="https://api.freshbooks.com", capabilities=["sync_invoices"], config_fields=["account_id"]),

    # ---------------- HRMS ----------------
    _c("bamboohr", "BambooHR", "hrms", "api_key",
       health_path="/v1/employees/directory", capabilities=["sync_employees", "sync_leave"],
       config_fields=["subdomain"]),
    _c("workday", "Workday", "hrms", "basic",
       capabilities=["sync_employees", "sync_org_chart"], config_fields=["tenant"]),
    _c("keka", "Keka", "hrms", "bearer",
       capabilities=["sync_employees", "sync_attendance", "sync_leave"], config_fields=["subdomain"]),
    _c("darwinbox", "Darwinbox", "hrms", "api_key",
       capabilities=["sync_employees", "sync_attendance"], config_fields=["subdomain"]),
    _c("zoho_people", "Zoho People", "hrms", "oauth2",
       base_url="https://people.zoho.com/people/api", capabilities=["sync_employees", "sync_leave"]),

    # ---------------- E-commerce ----------------
    _c("shopify", "Shopify", "ecommerce", "api_key",
       health_path="/admin/api/2024-01/shop.json", capabilities=["sync_orders", "sync_customers", "sync_products"],
       config_fields=["shop_domain"]),
    _c("woocommerce", "WooCommerce", "ecommerce", "basic",
       health_path="/wp-json/wc/v3/system_status", capabilities=["sync_orders", "sync_customers", "sync_products"],
       config_fields=["store_url"]),
    _c("magento", "Magento", "ecommerce", "bearer",
       health_path="/rest/V1/store/storeConfigs", capabilities=["sync_orders", "sync_products"],
       config_fields=["store_url"]),
    _c("amazon_seller", "Amazon Seller Central", "ecommerce", "oauth2",
       capabilities=["sync_orders"], config_fields=["marketplace_id", "seller_id"]),

    # ---------------- Marketing ----------------
    _c("mailchimp", "Mailchimp", "marketing", "api_key",
       health_path="/3.0/ping", capabilities=["sync_contacts", "campaigns", "lists"],
       config_fields=["server_prefix", "list_id"]),
    _c("hubspot_marketing", "HubSpot Marketing", "marketing", "bearer",
       base_url="https://api.hubapi.com", health_path="/crm/v3/objects/contacts?limit=1",
       capabilities=["sync_contacts", "campaigns", "forms"]),
    _c("google_ads", "Google Ads", "marketing", "oauth2",
       base_url="https://googleads.googleapis.com", capabilities=["lead_forms", "campaign_stats"],
       config_fields=["customer_id"]),
    _c("meta_ads", "Meta Ads", "marketing", "bearer",
       base_url="https://graph.facebook.com/v19.0", capabilities=["lead_forms", "campaign_stats"],
       config_fields=["ad_account_id"]),
    _c("sendgrid_marketing", "SendGrid Marketing", "marketing", "bearer",
       base_url="https://api.sendgrid.com/v3", health_path="/user/account",
       capabilities=["campaigns", "sync_contacts"]),

    # ---------------- Social media ----------------
    _c("linkedin", "LinkedIn", "social", "oauth2",
       base_url="https://api.linkedin.com/v2", health_path="/me",
       capabilities=["lead_gen_forms", "post", "profile_enrich"]),
    _c("facebook_pages", "Facebook Pages", "social", "bearer",
       base_url="https://graph.facebook.com/v19.0", capabilities=["lead_ads", "post", "messages"],
       config_fields=["page_id"]),
    _c("instagram", "Instagram", "social", "bearer",
       base_url="https://graph.facebook.com/v19.0", capabilities=["post", "messages"],
       config_fields=["ig_user_id"]),
    _c("x_twitter", "X (Twitter)", "social", "oauth2",
       base_url="https://api.twitter.com/2", health_path="/users/me", capabilities=["post", "mentions"]),
    _c("youtube", "YouTube", "social", "oauth2",
       base_url="https://www.googleapis.com/youtube/v3", capabilities=["post", "stats"],
       config_fields=["channel_id"]),

    # ---------------- CRM connectors ----------------
    _c("salesforce", "Salesforce", "crm", "oauth2",
       health_path="/services/data/v59.0/sobjects", capabilities=["import_leads", "export_leads", "two_way_sync"],
       config_fields=["instance_url"]),
    _c("hubspot_crm", "HubSpot CRM", "crm", "bearer",
       base_url="https://api.hubapi.com", health_path="/crm/v3/objects/contacts?limit=1",
       capabilities=["import_leads", "export_leads", "two_way_sync"]),
    _c("zoho_crm", "Zoho CRM", "crm", "oauth2",
       base_url="https://www.zohoapis.com/crm/v5", health_path="/settings/modules",
       capabilities=["import_leads", "export_leads"]),
    _c("pipedrive", "Pipedrive", "crm", "api_key",
       base_url="https://api.pipedrive.com/v1", health_path="/users/me",
       capabilities=["import_leads", "export_leads"]),
    _c("freshsales", "Freshsales", "crm", "bearer",
       health_path="/api/settings/modules", capabilities=["import_leads", "export_leads"],
       config_fields=["subdomain"]),

    # ---------------- Identity / SSO / LDAP ----------------
    _c("okta", "Okta", "identity", "api_key",
       health_path="/api/v1/users?limit=1", capabilities=["sso_oidc", "user_provisioning"],
       config_fields=["org_url", "client_id"]),
    _c("azure_ad", "Microsoft Entra ID (Azure AD)", "identity", "oauth2",
       base_url="https://graph.microsoft.com/v1.0", health_path="/organization",
       capabilities=["sso_oidc", "sso_saml", "user_provisioning"], config_fields=["tenant_id"]),
    _c("google_workspace", "Google Workspace", "identity", "oauth2",
       base_url="https://admin.googleapis.com/admin/directory/v1",
       capabilities=["sso_oidc", "user_provisioning"], config_fields=["domain"]),
    _c("auth0", "Auth0", "identity", "oauth2",
       capabilities=["sso_oidc", "user_provisioning"], config_fields=["domain"]),
    _c("onelogin", "OneLogin", "identity", "oauth2",
       capabilities=["sso_saml", "sso_oidc"], config_fields=["subdomain"]),
    _c("saml_generic", "Generic SAML 2.0", "identity", "saml",
       capabilities=["sso_saml"], config_fields=["entity_id", "sso_url", "attribute_map"]),
    _c("ldap", "LDAP", "identity", "ldap",
       capabilities=["directory_sync", "authentication"],
       config_fields=["host", "port", "base_dn", "user_filter", "use_ssl", "attribute_map"]),
    _c("active_directory", "Active Directory", "identity", "ldap",
       capabilities=["directory_sync", "authentication"],
       config_fields=["host", "port", "base_dn", "user_filter", "use_ssl", "attribute_map"]),

    # ---------------- Webhook + API connectors ----------------
    _c("inbound_webhook", "Inbound Webhook", "webhook", "none",
       capabilities=["receive", "signature_verify", "forward_to_event_bus"],
       config_fields=["event_type", "forward_to_event_bus"]),
    _c("outbound_webhook", "Outbound Webhook", "webhook", "none",
       capabilities=["send", "retry", "fallback"], config_fields=["url", "method", "headers"]),
    _c("rest_api", "Generic REST API", "api", "api_key",
       capabilities=["call", "retry", "fallback"],
       config_fields=["base_url", "default_headers", "auth_header"]),
    _c("graphql_api", "Generic GraphQL API", "api", "bearer",
       capabilities=["call", "retry"], config_fields=["base_url"]),
]

# `custom` in every category — anything not listed is still a first-class citizen.
for _cat in CATEGORIES:
    CONNECTORS.append(_c(f"custom_{_cat}", "Custom / Other", _cat, "api_key",
                         capabilities=["call", "retry", "fallback"],
                         config_fields=["base_url", "health_path", "default_headers"]))

BY_KEY: dict[str, dict] = {c["key"]: c for c in CONNECTORS}


def connector(key: str) -> dict | None:
    return BY_KEY.get(key)


def by_category(category: str) -> list[dict]:
    return [c for c in CONNECTORS if c["category"] == category]


def catalog() -> dict:
    return {
        "categories": [
            {"key": k, "label": v["label"], "managed_by": v["managed_by"],
             "connectors": [
                 {ck: cv for ck, cv in c.items() if ck != "category"} for c in by_category(k)
             ]}
            for k, v in CATEGORIES.items()
        ],
        "auth_types": list(AUTH_TYPES),
        "auth_fields": AUTH_FIELDS,
        "total_connectors": len(CONNECTORS),
    }
