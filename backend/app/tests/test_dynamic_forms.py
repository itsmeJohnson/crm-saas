"""Phase 7 — Dynamic Forms (Work Package) tests.

Covers form CRUD, schema validation (known/unknown/duplicate/foreign field keys),
entity allowlist, default-uniqueness, tenant/org isolation, authorization,
sections/ordering/overrides persistence, and that the form layer never lets a
record bypass MetadataValidationEngine.
"""
import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException

from app.core.security import create_access_token, get_password_hash
from app.repositories.organization import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.services.form_service import FormService
from app.services.custom_field_service import CustomFieldService
from app.services.custom_object_service import CustomObjectService


async def make_org(db: AsyncSession, slug: str, role: str = "OrgAdmin"):
    org = await OrganizationRepository(db).create({
        "name": slug, "slug": slug, "industry": "generic", "business_template": "generic",
    })
    await db.commit()
    admin = await UserRepository(db).create_user(org.id, {
        "email": f"a@{slug}.com", "hashed_password": get_password_hash("password123"),
        "first_name": "A", "last_name": "B", "role": role, "is_active": True,
    })
    await db.commit()
    return org, admin


async def add_field(db, actor, entity, **kw):
    d = await CustomFieldService(db).create_definition(actor, kw, entity_type=entity)
    await db.commit()
    return d


def form_payload(key="lead_form", name="Lead Form", fields=None, is_default=False):
    return {
        "key": key, "name": name, "is_default": is_default,
        "schema": {"sections": [{"title": "Main", "columns": 2,
                                 "fields": fields or [{"key": "budget", "required": True}]}]},
    }


# ── CRUD ────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_form_crud(db: AsyncSession):
    _, admin = await make_org(db, "form-crud")
    await add_field(db, admin, "lead", key="budget", label="Budget", field_type="currency")
    svc = FormService(db)

    form = await svc.create_form(admin, "lead", form_payload())
    await db.commit()
    assert form.key == "lead_form"
    assert form.schema["sections"][0]["fields"][0]["key"] == "budget"

    forms = await svc.list_forms(admin, "lead")
    assert any(f.key == "lead_form" for f in forms)

    upd = await svc.update_form(admin, form.id, {"name": "Renamed"})
    await db.commit()
    assert upd.name == "Renamed"

    await svc.delete_form(admin, form.id)
    await db.commit()
    assert await svc.list_forms(admin, "lead") == []


@pytest.mark.asyncio
async def test_sections_ordering_and_overrides_persist(db: AsyncSession):
    _, admin = await make_org(db, "form-schema")
    for k in ("budget", "location", "remarks"):
        await add_field(db, admin, "lead", key=k, label=k, field_type="text")
    svc = FormService(db)
    schema_fields = [
        {"key": "remarks", "hidden": True},
        {"key": "budget", "required": True, "read_only": False},
        {"key": "location", "read_only": True},
    ]
    form = await svc.create_form(admin, "lead", form_payload(fields=schema_fields))
    await db.commit()
    stored = form.schema["sections"][0]["fields"]
    assert [f["key"] for f in stored] == ["remarks", "budget", "location"]  # order preserved
    assert stored[0]["hidden"] is True
    assert stored[1]["required"] is True
    assert stored[2]["read_only"] is True


# ── Schema validation ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_unknown_field_key_rejected(db: AsyncSession):
    _, admin = await make_org(db, "form-unknown")
    await add_field(db, admin, "lead", key="budget", label="Budget", field_type="text")
    with pytest.raises(HTTPException) as e:
        await FormService(db).create_form(admin, "lead", form_payload(fields=[{"key": "ghost"}]))
    assert e.value.status_code == 400 and "Unknown or inactive field" in e.value.detail


@pytest.mark.asyncio
async def test_duplicate_field_in_form_rejected(db: AsyncSession):
    _, admin = await make_org(db, "form-dup")
    await add_field(db, admin, "lead", key="budget", label="Budget", field_type="text")
    with pytest.raises(HTTPException) as e:
        await FormService(db).create_form(admin, "lead", form_payload(
            fields=[{"key": "budget"}, {"key": "budget"}]))
    assert e.value.status_code == 400 and "more than once" in e.value.detail


@pytest.mark.asyncio
async def test_field_from_other_entity_rejected(db: AsyncSession):
    _, admin = await make_org(db, "form-crossentity")
    await add_field(db, admin, "lead", key="budget", label="Budget", field_type="text")
    await add_field(db, admin, "contact", key="loyalty", label="Loyalty", field_type="text")
    # lead form referencing a CONTACT field must fail
    with pytest.raises(HTTPException) as e:
        await FormService(db).create_form(admin, "lead", form_payload(fields=[{"key": "loyalty"}]))
    assert e.value.status_code == 400


@pytest.mark.parametrize("entity", ["patient", "ghost_object"])
@pytest.mark.asyncio
async def test_unsupported_entity_rejected(db: AsyncSession, entity):
    _, admin = await make_org(db, f"form-ent-{entity}")
    with pytest.raises(HTTPException) as e:
        await FormService(db).create_form(admin, entity, form_payload(fields=[]))
    assert e.value.status_code == 400


@pytest.mark.asyncio
async def test_form_on_custom_object(db: AsyncSession):
    _, admin = await make_org(db, "form-object")
    await CustomObjectService(db).create_object(admin, {"key": "property", "label": "Property"})
    await db.commit()
    await add_field(db, admin, "property", key="ptype", label="Type", field_type="text")
    form = await FormService(db).create_form(admin, "property", form_payload(
        key="prop_form", name="Property Form", fields=[{"key": "ptype", "required": True}]))
    await db.commit()
    assert form.entity_type == "property"


@pytest.mark.asyncio
async def test_duplicate_form_key_rejected(db: AsyncSession):
    _, admin = await make_org(db, "form-dupkey")
    await add_field(db, admin, "lead", key="budget", label="Budget", field_type="text")
    svc = FormService(db)
    await svc.create_form(admin, "lead", form_payload())
    await db.commit()
    with pytest.raises(HTTPException) as e:
        await svc.create_form(admin, "lead", form_payload())
    assert e.value.status_code == 400


# ── Default uniqueness ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_single_default_per_entity(db: AsyncSession):
    _, admin = await make_org(db, "form-default")
    await add_field(db, admin, "lead", key="budget", label="Budget", field_type="text")
    svc = FormService(db)
    f1 = await svc.create_form(admin, "lead", form_payload(key="f1", is_default=True))
    await db.commit()
    f2 = await svc.create_form(admin, "lead", form_payload(key="f2", is_default=True))
    await db.commit()
    forms = {f.key: f.is_default for f in await svc.list_forms(admin, "lead")}
    assert forms["f2"] is True and forms["f1"] is False  # newest default wins


# ── Authorization + tenant isolation ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_non_admin_cannot_manage_forms(db: AsyncSession):
    _, emp = await make_org(db, "form-perm", role="Employee")
    with pytest.raises(HTTPException) as e:
        await FormService(db).create_form(emp, "lead", form_payload(fields=[]))
    assert e.value.status_code == 403


@pytest.mark.asyncio
async def test_tenant_isolation(db: AsyncSession):
    _, admin_a = await make_org(db, "form-iso-a")
    _, admin_b = await make_org(db, "form-iso-b")
    await add_field(db, admin_a, "lead", key="budget", label="Budget", field_type="text")
    svc = FormService(db)
    fa = await svc.create_form(admin_a, "lead", form_payload())
    await db.commit()

    assert await svc.list_forms(admin_b, "lead") == []          # B sees none of A's forms
    with pytest.raises(HTTPException) as e1:
        await svc.get_form(admin_b, fa.id)
    assert e1.value.status_code == 404
    with pytest.raises(HTTPException) as e2:
        await svc.update_form(admin_b, fa.id, {"name": "hax"})
    assert e2.value.status_code == 404
    with pytest.raises(HTTPException) as e3:
        await svc.delete_form(admin_b, fa.id)
    assert e3.value.status_code == 404


# ── The form layer never bypasses MetadataValidationEngine ──────────────────────

@pytest.mark.asyncio
async def test_form_does_not_bypass_record_validation(db: AsyncSession, client: AsyncClient):
    org, admin = await make_org(db, "form-noby")
    headers = {"Authorization": f"Bearer {create_access_token(admin.id)}"}
    # numeric field with a max bound (non-reserved key)
    await add_field(db, admin, "lead", key="credit_score", label="Credit Score", field_type="number",
                    validation_rules={"max_value": 100})
    # a form that (incorrectly) marks the field hidden
    r = await client.post("/api/v1/forms?entity_type=lead",
                          json={"key": "lf", "name": "LF",
                                "schema": {"sections": [{"fields": [{"key": "credit_score", "hidden": True}]}]}},
                          headers=headers)
    assert r.status_code == 201
    # Submitting an out-of-range value through the normal lead API is STILL rejected
    # by MetadataValidationEngine — the form cannot loosen record validation.
    bad = await client.post("/api/v1/leads/",
                            json={"first_name": "X", "last_name": "Y", "title": "T",
                                  "custom_fields": {"credit_score": 999}},
                            headers=headers)
    assert bad.status_code == 400


# ── HTTP surface (routing, serialization, bootstrap-independent list) ───────────

@pytest.mark.asyncio
async def test_api_flow_and_serialization(db: AsyncSession, client: AsyncClient):
    org, admin = await make_org(db, "form-api")
    headers = {"Authorization": f"Bearer {create_access_token(admin.id)}"}
    await client.post("/api/v1/metadata/custom-fields?entity_type=lead",
                      json={"key": "budget", "label": "Budget", "field_type": "currency"}, headers=headers)
    r = await client.post("/api/v1/forms?entity_type=lead",
                          json={"key": "lf", "name": "Lead Form",
                                "schema": {"sections": [{"title": "Main", "fields": [{"key": "budget", "required": True}]}]}},
                          headers=headers)
    assert r.status_code == 201
    body = r.json()
    assert body["schema"]["sections"][0]["fields"][0]["key"] == "budget"   # JSON key is "schema"
    lst = await client.get("/api/v1/forms?entity_type=lead", headers=headers)
    assert lst.status_code == 200 and any(f["key"] == "lf" for f in lst.json())


@pytest.mark.asyncio
async def test_api_non_admin_cannot_create(db: AsyncSession, client: AsyncClient):
    _, emp = await make_org(db, "form-api-perm", role="Employee")
    headers = {"Authorization": f"Bearer {create_access_token(emp.id)}"}
    r = await client.post("/api/v1/forms?entity_type=lead",
                          json={"key": "lf", "name": "LF", "schema": {"sections": []}}, headers=headers)
    assert r.status_code == 403
