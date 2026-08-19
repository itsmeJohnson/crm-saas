"""Phase 4.2 — Custom Objects tests.

Covers object CRUD, tenant isolation, permissions, field defs on objects, record
CRUD, all field types, entity_reference (single + multi), the 10 query operators,
typed filtering, sort, pagination, invalid filters, cross-tenant references,
deletion protection, and Lead/Contact backward compatibility.
"""
import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException

from app.core.security import create_access_token, get_password_hash
from app.repositories.organization import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.services.custom_object_service import CustomObjectService
from app.services.custom_object_record_service import CustomObjectRecordService
from app.services.custom_field_service import CustomFieldService


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


async def make_object(db, actor, key="property", label="Property"):
    obj = await CustomObjectService(db).create_object(actor, {"key": key, "label": label})
    await db.commit()
    return obj


async def add_field(db, actor, entity, **kw):
    d = await CustomFieldService(db).create_definition(actor, kw, entity_type=entity)
    await db.commit()
    return d


async def add_record(db, actor, key, data):
    r = await CustomObjectRecordService(db).create_record(actor, key, {"data": data})
    await db.commit()
    return r


# ── Object definition CRUD + guards ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_object_crud(db: AsyncSession):
    _, admin = await make_org(db, "obj-crud")
    svc = CustomObjectService(db)
    obj = await make_object(db, admin, "property", "Property")
    assert obj.key == "property"
    got = await svc.get_by_key(admin, "property")
    assert got.id == obj.id
    upd = await svc.update_object(admin, obj.id, {"label": "Real Estate Property"})
    await db.commit()
    assert upd.label == "Real Estate Property"
    await svc.delete_object(admin, obj.id)
    await db.commit()
    assert await svc.list_objects(admin) == []


@pytest.mark.asyncio
async def test_reserved_and_duplicate_object_keys(db: AsyncSession):
    _, admin = await make_org(db, "obj-res")
    svc = CustomObjectService(db)
    for bad in ("lead", "contact", "object", "id"):
        with pytest.raises(HTTPException) as e:
            await svc.create_object(admin, {"key": bad, "label": "X"})
        assert e.value.status_code == 400
    await make_object(db, admin, "property")
    with pytest.raises(HTTPException) as e:
        await svc.create_object(admin, {"key": "property", "label": "Dup"})
    assert e.value.status_code == 400


@pytest.mark.asyncio
async def test_non_admin_cannot_manage_objects(db: AsyncSession):
    _, emp = await make_org(db, "obj-perm", role="Employee")
    with pytest.raises(HTTPException) as e:
        await CustomObjectService(db).create_object(emp, {"key": "property", "label": "P"})
    assert e.value.status_code == 403


@pytest.mark.asyncio
async def test_delete_object_blocked_when_records_exist(db: AsyncSession):
    _, admin = await make_org(db, "obj-del")
    obj = await make_object(db, admin, "property")
    await add_field(db, admin, "property", key="name", label="Name", field_type="text")
    await add_record(db, admin, "property", {"name": "Villa 1"})
    with pytest.raises(HTTPException) as e:
        await CustomObjectService(db).delete_object(admin, obj.id)
    assert e.value.status_code == 409


# ── Fields attach to objects via the existing CustomFieldDefinition ─────────────

@pytest.mark.asyncio
async def test_fields_attach_to_object_via_entity_type(db: AsyncSession):
    _, admin = await make_org(db, "obj-fields")
    await make_object(db, admin, "property")
    d = await add_field(db, admin, "property", key="budget", label="Budget", field_type="currency")
    assert d.entity_type == "property"
    defs = await CustomFieldService(db).list_definitions(admin, "property")
    assert any(x.key == "budget" for x in defs)


@pytest.mark.asyncio
async def test_field_on_unknown_object_rejected(db: AsyncSession):
    _, admin = await make_org(db, "obj-nofield")
    with pytest.raises(HTTPException) as e:
        await add_field(db, admin, "ghost_object", key="x", label="X", field_type="text")
    assert e.value.status_code == 400


# ── Record CRUD + all field types ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_record_crud_and_all_field_types(db: AsyncSession):
    _, admin = await make_org(db, "obj-rec")
    await make_object(db, admin, "property")
    specs = [
        ("f_text", "text", None), ("f_number", "number", None), ("f_currency", "currency", None),
        ("f_percentage", "percentage", None), ("f_date", "date", None), ("f_datetime", "datetime", None),
        ("f_boolean", "boolean", None), ("f_email", "email", None), ("f_phone", "phone", None),
        ("f_url", "url", None), ("f_select", "select", ["a", "b"]), ("f_multiselect", "multiselect", ["x", "y", "z"]),
    ]
    for key, ftype, options in specs:
        await add_field(db, admin, "property", key=key, label=key, field_type=ftype, options=options)

    svc = CustomObjectRecordService(db)
    rec = await svc.create_record(admin, "property", {"data": {
        "f_text": "hi", "f_number": 5, "f_currency": 100.5, "f_percentage": 40,
        "f_date": "2026-08-19", "f_datetime": "2026-08-19T10:00:00", "f_boolean": True,
        "f_email": "X@Y.com", "f_phone": "+91 99999 88888", "f_url": "https://x.com",
        "f_select": "a", "f_multiselect": ["x", "z"],
    }})
    await db.commit()
    assert rec.data["f_email"] == "x@y.com"
    assert rec.data["f_multiselect"] == ["x", "z"]

    upd = await svc.update_record(admin, "property", rec.id, {"data": {"f_number": 9}})
    await db.commit()
    assert upd.data["f_number"] == 9 and upd.data["f_text"] == "hi"  # merge preserves

    await svc.delete_record(admin, "property", rec.id)
    await db.commit()
    with pytest.raises(HTTPException) as e:
        await svc.get_record(admin, "property", rec.id)
    assert e.value.status_code == 404


@pytest.mark.asyncio
async def test_record_validation_rejects_bad_value(db: AsyncSession):
    _, admin = await make_org(db, "obj-val")
    await make_object(db, admin, "property")
    await add_field(db, admin, "property", key="pct", label="Pct", field_type="percentage")
    with pytest.raises(HTTPException) as e:
        await CustomObjectRecordService(db).create_record(admin, "property", {"data": {"pct": 500}})
    assert e.value.status_code == 400


# ── entity_reference (single + multi), incl. cross-tenant ───────────────────────

@pytest.mark.asyncio
async def test_entity_reference_single_and_multi(db: AsyncSession):
    _, admin = await make_org(db, "obj-ref")
    await make_object(db, admin, "customer", "Customer")
    await make_object(db, admin, "loan", "Loan")
    await add_field(db, admin, "customer", key="name", label="Name", field_type="text")
    await add_field(db, admin, "loan", key="borrower", label="Borrower", field_type="entity_reference",
                    validation_rules={"reference_object": "customer"})
    await add_field(db, admin, "loan", key="guarantors", label="Guarantors", field_type="entity_reference",
                    validation_rules={"reference_object": "customer", "multiple": True})

    c1 = await add_record(db, admin, "customer", {"name": "Acme"})
    c2 = await add_record(db, admin, "customer", {"name": "Beta"})

    rec = await CustomObjectRecordService(db).create_record(admin, "loan", {"data": {
        "borrower": str(c1.id), "guarantors": [str(c1.id), str(c2.id)],
    }})
    await db.commit()
    assert rec.data["borrower"] == str(c1.id)

    # Dangling reference rejected.
    with pytest.raises(HTTPException) as e:
        await CustomObjectRecordService(db).create_record(admin, "loan", {"data": {"borrower": str(uuid.uuid4())}})
    assert e.value.status_code == 400


@pytest.mark.asyncio
async def test_cross_tenant_reference_rejected(db: AsyncSession):
    _, admin_a = await make_org(db, "ref-a")
    _, admin_b = await make_org(db, "ref-b")
    await make_object(db, admin_a, "customer", "Customer")
    await add_field(db, admin_a, "customer", key="name", label="Name", field_type="text")
    a_cust = await add_record(db, admin_a, "customer", {"name": "A-owned"})

    await make_object(db, admin_b, "customer", "Customer")
    await add_field(db, admin_b, "customer", key="name", label="Name", field_type="text")
    await make_object(db, admin_b, "loan", "Loan")
    await add_field(db, admin_b, "loan", key="borrower", label="Borrower", field_type="entity_reference",
                    validation_rules={"reference_object": "customer"})

    # B tries to reference A's customer record → rejected.
    with pytest.raises(HTTPException) as e:
        await CustomObjectRecordService(db).create_record(admin_b, "loan", {"data": {"borrower": str(a_cust.id)}})
    assert e.value.status_code == 400


# ── Tenant isolation of objects + records ───────────────────────────────────────

@pytest.mark.asyncio
async def test_tenant_isolation_objects_and_records(db: AsyncSession):
    _, admin_a = await make_org(db, "iso-a")
    _, admin_b = await make_org(db, "iso-b")
    a_obj = await make_object(db, admin_a, "property")
    await add_field(db, admin_a, "property", key="name", label="Name", field_type="text")
    a_rec = await add_record(db, admin_a, "property", {"name": "A villa"})

    # B sees no objects, cannot read A's object or records.
    assert await CustomObjectService(db).list_objects(admin_b) == []
    with pytest.raises(HTTPException) as e1:
        await CustomObjectService(db).get_by_key(admin_b, "property")
    assert e1.value.status_code == 404
    with pytest.raises(HTTPException) as e2:
        await CustomObjectService(db).update_object(admin_b, a_obj.id, {"label": "hax"})
    assert e2.value.status_code == 404
    # B cannot query A's records (B has no such object).
    with pytest.raises(HTTPException) as e3:
        await CustomObjectRecordService(db).list_records(admin_b, "property")
    assert e3.value.status_code == 404
    # Even sharing the object key, B cannot fetch A's record id.
    await make_object(db, admin_b, "property")
    await add_field(db, admin_b, "property", key="name", label="Name", field_type="text")
    with pytest.raises(HTTPException) as e4:
        await CustomObjectRecordService(db).get_record(admin_b, "property", a_rec.id)
    assert e4.value.status_code == 404


# ── Query engine: 10 operators, typed filtering, sort, pagination, invalids ─────

async def _seed_property_records(db, admin):
    await make_object(db, admin, "property")
    await add_field(db, admin, "property", key="ptype", label="Type", field_type="select",
                    options=["Commercial", "Residential"])
    await add_field(db, admin, "property", key="value", label="Value", field_type="currency")
    await add_field(db, admin, "property", key="city", label="City", field_type="text")
    await add_field(db, admin, "property", key="active", label="Active", field_type="boolean")
    data = [
        {"ptype": "Commercial", "value": 20000000, "city": "Bangalore", "active": True},
        {"ptype": "Residential", "value": 5000000, "city": "Bangalore", "active": False},
        {"ptype": "Commercial", "value": 8000000, "city": "Mumbai", "active": True},
    ]
    for d in data:
        await add_record(db, admin, "property", d)


@pytest.mark.asyncio
async def test_query_operators_and_typed_filtering(db: AsyncSession):
    _, admin = await make_org(db, "q-ops")
    await _seed_property_records(db, admin)
    svc = CustomObjectRecordService(db)

    async def q(filters=None, sort=None, page=1, page_size=50):
        return await svc.list_records(admin, "property", filters=filters, sort=sort, page=page, page_size=page_size)

    # eq
    assert (await q([{"field": "ptype", "op": "eq", "value": "Commercial"}]))["total"] == 2
    # gte (numeric, typed)
    assert (await q([{"field": "value", "op": "gte", "value": 8000000}]))["total"] == 2
    # gt + lt
    assert (await q([{"field": "value", "op": "gt", "value": 5000000}]))["total"] == 2
    assert (await q([{"field": "value", "op": "lt", "value": 8000000}]))["total"] == 1
    # combined AND
    res = await q([
        {"field": "ptype", "op": "eq", "value": "Commercial"},
        {"field": "value", "op": "gte", "value": 10000000},
    ])
    assert res["total"] == 1
    # contains (text), ne, in, startswith, boolean eq, is_empty
    assert (await q([{"field": "city", "op": "contains", "value": "bang"}]))["total"] == 2
    assert (await q([{"field": "ptype", "op": "ne", "value": "Commercial"}]))["total"] == 1
    assert (await q([{"field": "ptype", "op": "in", "value": ["Commercial", "Residential"]}]))["total"] == 3
    assert (await q([{"field": "city", "op": "startswith", "value": "Mum"}]))["total"] == 1
    assert (await q([{"field": "active", "op": "eq", "value": True}]))["total"] == 2
    assert (await q([{"field": "city", "op": "is_empty", "value": True}]))["total"] == 0

    # sort desc by numeric
    res = await q(sort="value:desc")
    vals = [r.data["value"] for r in res["items"]]
    assert vals == sorted(vals, reverse=True)

    # pagination
    p1 = await q(page=1, page_size=2)
    assert len(p1["items"]) == 2 and p1["total"] == 3


@pytest.mark.asyncio
async def test_invalid_filters_rejected(db: AsyncSession):
    _, admin = await make_org(db, "q-bad")
    await _seed_property_records(db, admin)
    svc = CustomObjectRecordService(db)

    # unknown field
    with pytest.raises(HTTPException) as e1:
        await svc.list_records(admin, "property", filters=[{"field": "ghost", "op": "eq", "value": 1}])
    assert e1.value.status_code == 400
    # bad operator for type (gt on a select field)
    with pytest.raises(HTTPException) as e2:
        await svc.list_records(admin, "property", filters=[{"field": "ptype", "op": "gt", "value": "x"}])
    assert e2.value.status_code == 400
    # unknown operator
    with pytest.raises(HTTPException) as e3:
        await svc.list_records(admin, "property", filters=[{"field": "value", "op": "between", "value": 1}])
    assert e3.value.status_code == 400
    # non-numeric value for numeric op
    with pytest.raises(HTTPException) as e4:
        await svc.list_records(admin, "property", filters=[{"field": "value", "op": "gte", "value": "abc"}])
    assert e4.value.status_code == 400


# ── HTTP API end-to-end (router, filters param, serialization, bootstrap) ───────

@pytest.mark.asyncio
async def test_api_object_record_flow(db: AsyncSession, client: AsyncClient):
    _, admin = await make_org(db, "api-flow")
    headers = {"Authorization": f"Bearer {create_access_token(admin.id)}"}

    r = await client.post("/api/v1/objects", json={"key": "property", "label": "Property"}, headers=headers)
    assert r.status_code == 201

    f = await client.post("/api/v1/metadata/custom-fields?entity_type=property",
                          json={"key": "value", "label": "Value", "field_type": "currency"}, headers=headers)
    assert f.status_code == 201

    rec = await client.post("/api/v1/objects/property/records",
                            json={"data": {"value": 15000000}}, headers=headers)
    assert rec.status_code == 201

    import json as _json
    flt = _json.dumps([{"field": "value", "op": "gte", "value": 10000000}])
    lst = await client.get(f"/api/v1/objects/property/records?filters={flt}", headers=headers)
    assert lst.status_code == 200
    assert lst.json()["total"] == 1

    # bootstrap exposes the object definition eagerly
    boot = await client.get("/api/v1/metadata/bootstrap", headers=headers)
    assert any(o["key"] == "property" for o in boot.json()["custom_objects"])


@pytest.mark.asyncio
async def test_api_non_admin_cannot_create_object(db: AsyncSession, client: AsyncClient):
    _, emp = await make_org(db, "api-perm", role="Employee")
    headers = {"Authorization": f"Bearer {create_access_token(emp.id)}"}
    r = await client.post("/api/v1/objects", json={"key": "property", "label": "P"}, headers=headers)
    assert r.status_code == 403


# ── Backward compatibility: Lead/Contact custom fields still work ───────────────

@pytest.mark.asyncio
async def test_lead_contact_custom_fields_unaffected(db: AsyncSession):
    _, admin = await make_org(db, "compat")
    dl = await add_field(db, admin, "lead", key="budget", label="Budget", field_type="number")
    dc = await add_field(db, admin, "contact", key="loyalty", label="Loyalty", field_type="select", options=["gold"])
    assert dl.entity_type == "lead" and dc.entity_type == "contact"
    # reserved key still blocked on lead
    with pytest.raises(HTTPException) as e:
        await add_field(db, admin, "lead", key="email", label="Email", field_type="text")
    assert e.value.status_code == 400
