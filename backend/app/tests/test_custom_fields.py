"""Phase 4.1 — Custom Fields Engine tests.

Covers the extended engine: all 13 field types, reserved keys, entity-type
allowlist, options normalisation (incl. legacy string compat), tenant isolation,
Lead + Contact validation parity, and permission enforcement.
"""
import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException

from app.core.security import create_access_token, get_password_hash
from app.repositories.organization import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.services.custom_field_service import CustomFieldService
from app.services.metadata_validation_engine import (
    MetadataValidationEngine,
    MetadataValidationError,
)
from app.models.lead import Lead
from app.models.contact import Contact


async def make_org(db: AsyncSession, slug: str, admin_role: str = "OrgAdmin"):
    org = await OrganizationRepository(db).create({
        "name": slug, "slug": slug, "industry": "generic", "business_template": "generic",
    })
    await db.commit()
    admin = await UserRepository(db).create_user(org.id, {
        "email": f"admin@{slug}.com", "hashed_password": get_password_hash("password123"),
        "first_name": "Ada", "last_name": "Admin", "role": admin_role, "is_active": True,
    })
    await db.commit()
    return org, admin


async def define(db, actor, entity, **kw):
    svc = CustomFieldService(db)
    d = await svc.create_definition(actor, kw, entity_type=entity)
    await db.commit()
    return d


# ── CRUD + isolation ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_list_update_deactivate(db: AsyncSession):
    _, admin = await make_org(db, "cf-crud")
    svc = CustomFieldService(db)
    d = await define(db, admin, "lead", key="budget", label="Budget", field_type="currency")
    defs = await svc.list_definitions(admin, "lead")
    assert any(x.key == "budget" for x in defs)

    upd = await svc.update_definition(admin, d.id, {"label": "Deal Budget"})
    await db.commit()
    assert upd.label == "Deal Budget"

    await svc.delete_definition(admin, d.id)
    await db.commit()
    remaining = await svc.list_definitions(admin, "lead")
    assert all(x.key != "budget" for x in remaining)  # soft-deleted, filtered out


@pytest.mark.asyncio
async def test_tenant_isolation(db: AsyncSession):
    _, admin_a = await make_org(db, "cf-iso-a")
    _, admin_b = await make_org(db, "cf-iso-b")
    svc = CustomFieldService(db)

    da = await define(db, admin_a, "lead", key="budget", label="Budget", field_type="number")
    await define(db, admin_b, "lead", key="policy_type", label="Policy", field_type="text")

    a_defs = {d.key for d in await svc.list_definitions(admin_a, "lead")}
    b_defs = {d.key for d in await svc.list_definitions(admin_b, "lead")}
    assert "budget" in a_defs and "policy_type" not in a_defs
    assert "policy_type" in b_defs and "budget" not in b_defs

    # B cannot read/update/delete A's definition → 404
    with pytest.raises(HTTPException) as e1:
        await svc.update_definition(admin_b, da.id, {"label": "hax"})
    assert e1.value.status_code == 404
    with pytest.raises(HTTPException) as e2:
        await svc.delete_definition(admin_b, da.id)
    assert e2.value.status_code == 404


@pytest.mark.asyncio
async def test_duplicate_key_rejected(db: AsyncSession):
    _, admin = await make_org(db, "cf-dup")
    await define(db, admin, "lead", key="budget", label="Budget", field_type="number")
    with pytest.raises(HTTPException) as e:
        await define(db, admin, "lead", key="budget", label="Budget 2", field_type="number")
    assert e.value.status_code == 400


# ── Reserved keys (G3) + entity allowlist (G4) ──────────────────────────────────

@pytest.mark.parametrize("bad_key", ["email", "phone", "id", "score", "first_name", "organization_id"])
@pytest.mark.asyncio
async def test_reserved_keys_rejected(db: AsyncSession, bad_key):
    _, admin = await make_org(db, f"cf-res-{bad_key}")
    with pytest.raises(HTTPException) as e:
        await define(db, admin, "lead", key=bad_key, label="X", field_type="text")
    assert e.value.status_code == 400
    assert "reserved" in e.value.detail.lower()


@pytest.mark.parametrize("entity", ["patient", "appointment", "customer", "task", "opportunity"])
@pytest.mark.asyncio
async def test_unsupported_entity_rejected(db: AsyncSession, entity):
    _, admin = await make_org(db, f"cf-ent-{entity}")
    with pytest.raises(HTTPException) as e:
        await define(db, admin, entity, key="foo", label="Foo", field_type="text")
    assert e.value.status_code == 400


@pytest.mark.parametrize("entity", ["lead", "contact"])
@pytest.mark.asyncio
async def test_supported_entities_accepted(db: AsyncSession, entity):
    _, admin = await make_org(db, f"cf-ok-{entity}")
    d = await define(db, admin, entity, key="foo", label="Foo", field_type="text")
    assert d.entity_type == entity


@pytest.mark.asyncio
async def test_invalid_field_type_rejected(db: AsyncSession):
    _, admin = await make_org(db, "cf-badtype")
    with pytest.raises(HTTPException) as e:
        await define(db, admin, "lead", key="foo", label="Foo", field_type="rocket")
    assert e.value.status_code == 400


# ── Options normalisation (G5) ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_legacy_string_options_coerced(db: AsyncSession):
    _, admin = await make_org(db, "cf-opts")
    d = await define(db, admin, "lead", key="tier", label="Tier", field_type="select",
                     options=["gold", "silver"])
    assert d.options == [{"value": "gold", "label": "gold"}, {"value": "silver", "label": "silver"}]


@pytest.mark.asyncio
async def test_object_options_preserved(db: AsyncSession):
    _, admin = await make_org(db, "cf-opts2")
    d = await define(db, admin, "lead", key="ptype", label="Property Type", field_type="select",
                     options=[{"value": "apartment", "label": "Apartment"}, {"value": "villa", "label": "Villa"}])
    assert {o["value"] for o in d.options} == {"apartment", "villa"}
    assert d.options[0]["label"] == "Apartment"


@pytest.mark.asyncio
async def test_duplicate_option_values_rejected(db: AsyncSession):
    _, admin = await make_org(db, "cf-opts3")
    with pytest.raises(HTTPException) as e:
        await define(db, admin, "lead", key="dup", label="Dup", field_type="select",
                     options=["a", "a"])
    assert e.value.status_code == 400


# ── Validation across every field type ──────────────────────────────────────────

async def _defs_for_all_types(db, admin):
    specs = [
        ("f_text", "text", None, {}),
        ("f_textarea", "textarea", None, {}),
        ("f_number", "number", None, {"min_value": 0, "max_value": 100}),
        ("f_currency", "currency", None, {"min_value": 0}),
        ("f_percentage", "percentage", None, {}),
        ("f_date", "date", None, {}),
        ("f_datetime", "datetime", None, {}),
        ("f_boolean", "boolean", None, {}),
        ("f_checkbox", "checkbox", None, {}),  # legacy alias
        ("f_email", "email", None, {}),
        ("f_phone", "phone", None, {}),
        ("f_url", "url", None, {}),
        ("f_select", "select", ["a", "b"], {}),
        ("f_multiselect", "multiselect", ["x", "y", "z"], {}),
    ]
    out = []
    for key, ftype, options, rules in specs:
        out.append(await define(db, admin, "lead", key=key, label=key, field_type=ftype,
                                options=options, validation_rules=rules))
    return out


@pytest.mark.asyncio
async def test_all_field_types_valid_values(db: AsyncSession):
    org, admin = await make_org(db, "cf-types-ok")
    defs = await _defs_for_all_types(db, admin)
    payload = {
        "f_text": "hello", "f_textarea": "long text", "f_number": 42, "f_currency": 1999.50,
        "f_percentage": 75, "f_date": "2026-08-19", "f_datetime": "2026-08-19T10:30:00",
        "f_boolean": True, "f_checkbox": "yes", "f_email": "USER@Example.com",
        "f_phone": "+91 98765 43210", "f_url": "https://example.com",
        "f_select": "a", "f_multiselect": ["x", "z"],
    }
    out = await MetadataValidationEngine.validate_and_sanitize(db, Lead, org.id, defs, payload)
    assert out["f_number"] == 42
    assert out["f_boolean"] is True and out["f_checkbox"] is True
    assert out["f_email"] == "user@example.com"          # normalised lower
    assert out["f_phone"] == "+919876543210"             # digits + plus only
    assert out["f_multiselect"] == ["x", "z"]


@pytest.mark.parametrize("key,bad", [
    ("f_number", 500),            # > max
    ("f_percentage", 150),        # > 100 default
    ("f_date", "19-08-2026"),     # wrong format
    ("f_datetime", "not-a-time"),
    ("f_email", "nope"),
    ("f_url", "ftp://x"),
    ("f_phone", "abc"),
    ("f_select", "zzz"),          # not an option
])
@pytest.mark.asyncio
async def test_type_validation_failures(db: AsyncSession, key, bad):
    org, admin = await make_org(db, f"cf-bad-{key}-{str(bad)[:4]}")
    defs = await _defs_for_all_types(db, admin)
    with pytest.raises(MetadataValidationError):
        await MetadataValidationEngine.validate_and_sanitize(db, Lead, org.id, defs, {key: bad})


@pytest.mark.asyncio
async def test_multiselect_invalid_member_rejected(db: AsyncSession):
    org, admin = await make_org(db, "cf-multi-bad")
    defs = await _defs_for_all_types(db, admin)
    with pytest.raises(MetadataValidationError):
        await MetadataValidationEngine.validate_and_sanitize(db, Lead, org.id, defs, {"f_multiselect": ["x", "nope"]})


@pytest.mark.asyncio
async def test_required_field_enforced(db: AsyncSession):
    org, admin = await make_org(db, "cf-req")
    d = await define(db, admin, "lead", key="need", label="Need", field_type="text",
                     validation_rules={"required": True})
    with pytest.raises(MetadataValidationError) as e:
        await MetadataValidationEngine.validate_and_sanitize(db, Lead, org.id, [d], {})
    assert e.value.code == "required"


@pytest.mark.asyncio
async def test_unknown_key_rejected(db: AsyncSession):
    org, admin = await make_org(db, "cf-unknown")
    d = await define(db, admin, "lead", key="known", label="Known", field_type="text")
    with pytest.raises(MetadataValidationError) as e:
        await MetadataValidationEngine.validate_and_sanitize(db, Lead, org.id, [d], {"ghost": "x"})
    assert e.value.code == "unknown_field"


# ── Lead + Contact parity through the HTTP API ──────────────────────────────────

@pytest.mark.asyncio
async def test_contact_uses_full_validation_like_lead(db: AsyncSession, client: AsyncClient):
    org, admin = await make_org(db, "cf-contact-parity")
    headers = {"Authorization": f"Bearer {create_access_token(admin.id)}"}

    # Define a numeric contact field with bounds.
    r = await client.post("/api/v1/contacts/custom-fields",
                          json={"key": "coverage", "label": "Coverage", "field_type": "number",
                                "validation_rules": {"min_value": 0, "max_value": 1000000}},
                          headers=headers)
    assert r.status_code == 201

    # Out-of-range value must now be rejected for CONTACTS (was previously unchecked).
    bad = await client.post("/api/v1/contacts/",
                            json={"first_name": "A", "last_name": "B", "custom_fields": {"coverage": 9999999}},
                            headers=headers)
    assert bad.status_code == 400

    # Valid value accepted and stored.
    ok = await client.post("/api/v1/contacts/",
                           json={"first_name": "A", "last_name": "B", "custom_fields": {"coverage": 50000}},
                           headers=headers)
    assert ok.status_code == 201
    assert ok.json()["custom_fields"]["coverage"] == 50000


@pytest.mark.asyncio
async def test_non_admin_cannot_manage_definitions(db: AsyncSession):
    _, employee = await make_org(db, "cf-perm", admin_role="Employee")
    with pytest.raises(HTTPException) as e:
        await define(db, employee, "lead", key="foo", label="Foo", field_type="text")
    assert e.value.status_code == 403


@pytest.mark.asyncio
async def test_bootstrap_exposes_per_entity_map(db: AsyncSession, client: AsyncClient):
    org, admin = await make_org(db, "cf-bootstrap")
    headers = {"Authorization": f"Bearer {create_access_token(admin.id)}"}
    await define(db, admin, "lead", key="budget", label="Budget", field_type="number")
    await define(db, admin, "contact", key="loyalty", label="Loyalty", field_type="text")

    boot = await client.get("/api/v1/metadata/bootstrap", headers=headers)
    assert boot.status_code == 200
    body = boot.json()
    assert "custom_fields_by_entity" in body
    keys_lead = {f["key"] for f in body["custom_fields_by_entity"]["lead"]}
    keys_contact = {f["key"] for f in body["custom_fields_by_entity"]["contact"]}
    assert "budget" in keys_lead
    assert "loyalty" in keys_contact
    # Backward-compatible flat list still present (lead).
    assert "budget" in {f["key"] for f in body["custom_fields"]}
