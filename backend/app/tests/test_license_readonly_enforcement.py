"""Behavioural test for the license read-only enforcer (single-tenant instances).

Proves the actual runtime contract the LoanNest/retainer model relies on:
  • when the license is inactive (read_only), writes are blocked with 423,
  • BUT the client can still log in (auth), hit health/license, and EXPORT data,
  • reads (GET) are always allowed,
  • when the license is active again, writes flow normally.

Tests the ReadOnlyEnforcerMiddleware directly on a tiny app, so it needs no DB,
no Redis, and no env flags.
"""
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.services.license_check import ReadOnlyEnforcerMiddleware, STATE


def _build_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(ReadOnlyEnforcerMiddleware)

    @app.get("/api/v1/contacts")
    async def list_contacts():
        return {"ok": True}

    @app.post("/api/v1/contacts")
    async def create_contact():
        return {"ok": True}

    @app.post("/api/v1/auth/login")
    async def login():
        return {"ok": True}

    @app.get("/api/v1/leads/export")
    async def export_get():
        return {"ok": True}

    @app.post("/api/v1/leads/export")
    async def export_post():
        return {"ok": True}

    @app.get("/api/v1/license/status")
    async def license_status():
        return {"ok": True}

    return app


@pytest.fixture
def app_client():
    app = _build_app()
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.fixture(autouse=True)
def _reset_state():
    prev = STATE.read_only
    yield
    STATE.read_only = prev  # never leak read-only into other tests


async def test_writes_blocked_when_read_only(app_client):
    STATE.read_only = True
    async with app_client as c:
        resp = await c.post("/api/v1/contacts")
    assert resp.status_code == 423
    assert resp.json()["error"] == "read_only"


async def test_reads_allowed_when_read_only(app_client):
    STATE.read_only = True
    async with app_client as c:
        resp = await c.get("/api/v1/contacts")
    assert resp.status_code == 200


async def test_login_allowed_when_read_only(app_client):
    """Client must still be able to sign in to SEE the read-only notice."""
    STATE.read_only = True
    async with app_client as c:
        resp = await c.post("/api/v1/auth/login")
    assert resp.status_code == 200


async def test_export_allowed_when_read_only(app_client):
    """Data must stay exportable even in read-only mode (data-portability promise)."""
    STATE.read_only = True
    async with app_client as c:
        get_resp = await c.get("/api/v1/leads/export")
        post_resp = await c.post("/api/v1/leads/export")
    assert get_resp.status_code == 200
    assert post_resp.status_code == 200  # export via POST is allowlisted too


async def test_writes_flow_when_active(app_client):
    STATE.read_only = False
    async with app_client as c:
        resp = await c.post("/api/v1/contacts")
    assert resp.status_code == 200
