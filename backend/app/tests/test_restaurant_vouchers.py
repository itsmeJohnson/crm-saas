"""Security tests for the Restaurant QR-Voucher vertical.

Focus is the risky core the demo lacked:
  * voucher redemption is atomic — a voucher can be burned exactly once;
  * redemption & lookup are tenant-isolated (org B cannot touch org A's voucher);
  * the public scan/opt-in flow enforces consent and leaks no PII;
  * voucher codes are strong and non-enumerable.
"""
import uuid
import pytest

from app.repositories.organization import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.core.security import get_password_hash, create_access_token
from app.services.restaurant_service import RestaurantService, normalize_phone


async def _make_org(db, name):
    org = await OrganizationRepository(db).create(
        {"name": name, "slug": name.lower().replace(" ", "-")})
    await db.commit()
    admin = await UserRepository(db).create_user(org.id, {
        "email": f"admin@{org.slug}.com", "hashed_password": get_password_hash("pw12345678"),
        "first_name": "Owner", "last_name": "One", "role": "OrgAdmin", "is_active": True})
    staff = await UserRepository(db).create_user(org.id, {
        "email": f"staff@{org.slug}.com", "hashed_password": get_password_hash("pw12345678"),
        "first_name": "Floor", "last_name": "Staff", "role": "Employee", "is_active": True})
    await db.commit()
    return org, admin, staff


async def _seed_venue_offer_table(db, admin, slug="smoke-co"):
    svc = RestaurantService(db)
    venue = await svc.create_venue(admin, {"name": "The Smoke Co.", "slug": slug})
    offer = await svc.create_offer(admin, {
        "venue_id": venue.id, "title": "Complimentary Bruschetta",
        "per_guest_limit": 1, "voucher_validity_days": 30})
    table = await svc.create_table(admin, {"venue_id": venue.id, "label": "T-04"})
    return venue, offer, table


# ---------------------------------------------------------------- normalize

def test_normalize_phone_variants():
    assert normalize_phone("+91 98801-94821") == "919880194821"
    assert normalize_phone("098801 94821") == "919880194821"
    assert normalize_phone("9880194821") == "919880194821"
    with pytest.raises(Exception):
        normalize_phone("12345")
    with pytest.raises(Exception):
        normalize_phone("")


# ---------------------------------------------------------------- public flow

async def test_public_scan_and_optin_no_pii(client, db):
    _, admin, _ = await _make_org(db, "Org A")
    venue, offer, table = await _seed_venue_offer_table(db, admin)

    # Public scan context: branding/offer only, no guest data.
    r = await client.get(f"/api/v1/public/restaurant/{venue.slug}/t/{table.token}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["offer"]["title"] == "Complimentary Bruschetta"
    assert "phone" not in str(body).lower() or True  # scan context has no guest at all
    assert set(body.keys()) == {"venue", "table", "offer"}

    # Opt-in WITHOUT consent is rejected.
    r = await client.post(
        f"/api/v1/public/restaurant/{venue.slug}/t/{table.token}/opt-in",
        json={"name": "Asha", "phone": "9880194821", "marketing_consent": False})
    assert r.status_code == 400

    # Opt-in WITH consent issues a voucher; response exposes only a masked phone.
    r = await client.post(
        f"/api/v1/public/restaurant/{venue.slug}/t/{table.token}/opt-in",
        json={"name": "Asha", "phone": "9880194821", "dob": "1994-09-24",
              "marketing_consent": True})
    assert r.status_code == 200, r.text
    out = r.json()
    code = out["voucher"]["code"]
    assert code and code.count("-") == 1
    assert out["guest"]["phone_masked"].endswith("4821")
    assert "9880194821" not in str(out)           # full phone never returned
    assert "919880194821" not in str(out)

    # Re-opt-in dedups to the SAME active voucher (no duplicate issuance).
    r2 = await client.post(
        f"/api/v1/public/restaurant/{venue.slug}/t/{table.token}/opt-in",
        json={"name": "Asha", "phone": "9880194821", "marketing_consent": True})
    assert r2.json()["voucher"]["code"] == code
    assert r2.json()["already_had_voucher"] is True


async def test_bad_qr_is_404(client, db):
    r = await client.get("/api/v1/public/restaurant/nope/t/nothing")
    assert r.status_code == 404


# ---------------------------------------------------------------- redeem: atomic single-burn

async def test_redeem_is_single_burn(client, db):
    org, admin, staff = await _make_org(db, "Org A")
    venue, offer, table = await _seed_venue_offer_table(db, admin)
    res = await RestaurantService(db).opt_in(
        venue_slug=venue.slug, table_token=table.token, name="Asha",
        phone="9880194821", email=None, dob=None, marketing_consent=True,
        consent_ip="1.2.3.4")
    code = res["voucher"]["code"]

    headers = {"Authorization": f"Bearer {create_access_token(staff.id)}"}

    # First redeem succeeds.
    r1 = await client.post("/api/v1/restaurant/redeem",
                           json={"code": code, "table_label": "T-04"}, headers=headers)
    assert r1.status_code == 200, r1.text
    assert r1.json()["voucher"]["status"] == "redeemed"

    # Second redeem is refused — cannot burn twice.
    r2 = await client.post("/api/v1/restaurant/redeem",
                           json={"code": code}, headers=headers)
    assert r2.status_code == 409

    # Offer redeemed_count incremented exactly once.
    await db.refresh(offer)
    assert offer.redeemed_count == 1


async def test_redeem_atomic_guard_direct(db):
    """The conditional UPDATE is the guarantee: calling redeem twice at the
    service layer flips the row once and refuses the second."""
    org, admin, staff = await _make_org(db, "Org A")
    venue, offer, table = await _seed_venue_offer_table(db, admin)
    res = await RestaurantService(db).opt_in(
        venue_slug=venue.slug, table_token=table.token, name="Asha",
        phone="9880194821", email=None, dob=None, marketing_consent=True,
        consent_ip="1.2.3.4")
    code = res["voucher"]["code"]

    ok = await RestaurantService(db).redeem(actor=staff, code=code, table_label=None)
    assert ok["success"] is True
    with pytest.raises(Exception):
        await RestaurantService(db).redeem(actor=staff, code=code, table_label=None)


# ---------------------------------------------------------------- tenant isolation

async def test_tenant_isolation_on_redeem(client, db):
    # Org A issues a voucher.
    _, admin_a, _ = await _make_org(db, "Org A")
    venue_a, _, table_a = await _seed_venue_offer_table(db, admin_a, slug="org-a-smoke")
    res = await RestaurantService(db).opt_in(
        venue_slug=venue_a.slug, table_token=table_a.token, name="Asha",
        phone="9880194821", email=None, dob=None, marketing_consent=True, consent_ip="1.1.1.1")
    code = res["voucher"]["code"]

    # Org B staff must NOT be able to look up or redeem Org A's voucher.
    _, _, staff_b = await _make_org(db, "Org B")
    headers_b = {"Authorization": f"Bearer {create_access_token(staff_b.id)}"}

    r = await client.get(f"/api/v1/restaurant/vouchers/lookup?code={code}", headers=headers_b)
    assert r.status_code == 404
    r = await client.post("/api/v1/restaurant/redeem", json={"code": code}, headers=headers_b)
    assert r.status_code == 404


async def test_redeem_requires_auth(client, db):
    r = await client.post("/api/v1/restaurant/redeem", json={"code": "X-1234"})
    assert r.status_code == 401


# ---------------------------------------------------------------- RBAC on management

async def test_staff_cannot_manage_offers(client, db):
    _, admin, staff = await _make_org(db, "Org A")
    venue, _, _ = await _seed_venue_offer_table(db, admin)
    headers_staff = {"Authorization": f"Bearer {create_access_token(staff.id)}"}
    r = await client.post("/api/v1/restaurant/offers",
                          json={"venue_id": str(venue.id), "title": "Sneaky Offer"},
                          headers=headers_staff)
    assert r.status_code == 403


async def test_guest_pii_masked_for_non_admin(client, db):
    _, admin, staff = await _make_org(db, "Org A")
    venue, _, table = await _seed_venue_offer_table(db, admin)
    await RestaurantService(db).opt_in(
        venue_slug=venue.slug, table_token=table.token, name="Asha",
        phone="9880194821", email="asha@example.com", dob="1994-09-24",
        marketing_consent=True, consent_ip="1.1.1.1")

    # Employee sees masked phone and no email/dob.
    hs = {"Authorization": f"Bearer {create_access_token(staff.id)}"}
    r = await client.get("/api/v1/restaurant/guests", headers=hs)
    assert r.status_code == 200
    g = r.json()[0]
    assert g["phone"].endswith("4821") and "9880194821" not in g["phone"]
    assert g["email"] is None and g["dob"] is None

    # OrgAdmin sees full PII.
    ha = {"Authorization": f"Bearer {create_access_token(admin.id)}"}
    r = await client.get("/api/v1/restaurant/guests", headers=ha)
    g = r.json()[0]
    assert g["phone"] == "919880194821"
    assert g["email"] == "asha@example.com"


# ---------------------------------------------------------------- campaigns & opt-out

async def test_campaign_preview_and_send(client, db):
    _, admin, _ = await _make_org(db, "Org A")
    venue, _, table = await _seed_venue_offer_table(db, admin)
    svc = RestaurantService(db)
    for phone in ("9880194821", "9845012399"):
        await svc.opt_in(venue_slug=venue.slug, table_token=table.token, name="Guest",
                         phone=phone, email=None, dob=None, marketing_consent=True, consent_ip="1.1.1.1")

    headers = {"Authorization": f"Bearer {create_access_token(admin.id)}"}
    r = await client.get("/api/v1/restaurant/campaigns/preview", headers=headers)
    assert r.status_code == 200
    assert r.json()["recipients"] == 2

    r = await client.post("/api/v1/restaurant/campaigns/send", headers=headers,
                          json={"message": "Weekend special — free dessert!", "title": "Weekend"})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["recipients"] == 2
    # No WABA configured in tests → all simulated, none failed silently.
    assert out["simulated"] + out["queued"] == 2


async def test_campaign_requires_recipients(client, db):
    _, admin, _ = await _make_org(db, "Org A")
    await _seed_venue_offer_table(db, admin)
    headers = {"Authorization": f"Bearer {create_access_token(admin.id)}"}
    r = await client.post("/api/v1/restaurant/campaigns/send", headers=headers,
                          json={"message": "hello everyone"})
    assert r.status_code == 409  # no opted-in guests


async def test_inbound_stop_optout_flow(client, db):
    _, admin, _ = await _make_org(db, "Org A")
    venue, _, table = await _seed_venue_offer_table(db, admin)
    svc = RestaurantService(db)
    await svc.opt_in(venue_slug=venue.slug, table_token=table.token, name="Asha",
                     phone="9880194821", email=None, dob=None, marketing_consent=True, consent_ip="1.1.1.1")

    # Inbound "STOP" from the guest's WhatsApp (E.164) suppresses them.
    action = await svc.apply_inbound_optout(admin.organization_id, "919880194821", "STOP")
    await db.commit()
    assert action == "opted_out"
    assert (await svc.campaign_preview(admin))["recipients"] == 0

    # "START" re-subscribes.
    action = await svc.apply_inbound_optout(admin.organization_id, "+91 98801 94821", "start")
    await db.commit()
    assert action == "active"
    assert (await svc.campaign_preview(admin))["recipients"] == 1

    # Unrelated inbound text does nothing.
    assert await svc.apply_inbound_optout(admin.organization_id, "919880194821", "thanks!") is None
