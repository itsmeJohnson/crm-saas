"""Zero-regression guard for the optional license heartbeat (single-tenant).

The license status route and the read-only enforcer middleware must exist ONLY
when ENABLE_LICENSE_HEARTBEAT=true. For the base/default CRM (flag unset/false)
neither may be present — no route, no middleware, no behavioural change.

The gated wiring in main.py runs at IMPORT time, so we drive both states by
reloading `main` under a controlled env value, and always restore the default
(flag-off) app for the rest of the suite.
"""
import importlib
import os

import pytest

import main

LICENSE_STATUS_PATH = "/api/v1/license/status"
ENFORCER_NAME = "ReadOnlyEnforcerMiddleware"


def _reload_main_with_flag(value: str | None):
    """Reload main.py with ENABLE_LICENSE_HEARTBEAT set to `value` (None = unset)."""
    if value is None:
        os.environ.pop("ENABLE_LICENSE_HEARTBEAT", None)
    else:
        os.environ["ENABLE_LICENSE_HEARTBEAT"] = value
    return importlib.reload(main)


def _has_license_route(app) -> bool:
    return any(getattr(r, "path", None) == LICENSE_STATUS_PATH for r in app.routes)


def _has_enforcer_middleware(app) -> bool:
    return any(m.cls.__name__ == ENFORCER_NAME for m in app.user_middleware)


@pytest.fixture(autouse=True)
def _restore_default_app():
    """Guarantee the shared `main.app` is back to flag-off after each test here."""
    prev = os.environ.get("ENABLE_LICENSE_HEARTBEAT")
    yield
    if prev is None:
        os.environ.pop("ENABLE_LICENSE_HEARTBEAT", None)
    else:
        os.environ["ENABLE_LICENSE_HEARTBEAT"] = prev
    _reload_main_with_flag(None)


def test_base_crm_has_no_license_route_or_middleware():
    reloaded = _reload_main_with_flag(None)   # flag unset → default CRM
    assert not _has_license_route(reloaded.app), \
        "base CRM must NOT expose the license status route"
    assert not _has_enforcer_middleware(reloaded.app), \
        "base CRM must NOT mount the read-only enforcer middleware"


def test_flag_false_is_also_inert():
    reloaded = _reload_main_with_flag("false")
    assert not _has_license_route(reloaded.app)
    assert not _has_enforcer_middleware(reloaded.app)


def test_flag_true_mounts_route_and_middleware():
    reloaded = _reload_main_with_flag("true")   # single-tenant client instance
    assert _has_license_route(reloaded.app), \
        "with the flag on, /api/v1/license/status must be registered"
    assert _has_enforcer_middleware(reloaded.app), \
        "with the flag on, the read-only enforcer middleware must be mounted"
