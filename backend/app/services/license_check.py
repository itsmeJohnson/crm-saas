"""
License heartbeat service (OPTIONAL, single-tenant deployments only).

⚠ ZERO-REGRESSION CONTRACT
   This module is completely inert unless ENABLE_LICENSE_HEARTBEAT=true. When the
   flag is unset/false, main.py never imports, starts, or mounts anything here, so
   the base CRM behaves exactly as before. Nothing in this file runs at import time.

When enabled (single-tenant client instances like LoanNest), every
LICENSE_INTERVAL_HOURS the instance calls the Johnson Softwares license endpoint.
If the license is reported inactive (e.g. retainer unpaid) the CRM enters
READ-ONLY mode: reads + CSV export keep working; write methods return 423 LOCKED
with a friendly support notice.

DESIGN NOTES:
  • Fail OPEN. A network error / 5xx / unreachable license server NEVER takes a
    paying client offline — we only degrade on an EXPLICIT "inactive" answer, or
    after GRACE_DAYS of being unable to confirm.
  • Read-only, never destructive. Data is retained and stays CSV-exportable.
  • DISCLOSURE: this remote-restrict behaviour must be a clause in the signed
    retainer/SLA the client agrees to.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger("license")


def _enabled() -> bool:
    return os.getenv("ENABLE_LICENSE_HEARTBEAT", "false").strip().lower() == "true"


VERIFY_URL = os.getenv("LICENSE_VERIFY_URL", "https://johnsonsoftwares.com/api/crm/license/verify")
CLIENT_ID = os.getenv("CLIENT_ID", "")
LICENSE_KEY = os.getenv("CLIENT_LICENSE_KEY", "")
INTERVAL_HOURS = float(os.getenv("LICENSE_INTERVAL_HOURS", "24"))
GRACE_DAYS = float(os.getenv("LICENSE_GRACE_DAYS", "7"))
HTTP_TIMEOUT = float(os.getenv("LICENSE_HTTP_TIMEOUT", "10"))

# Write methods that read-only mode blocks.
_WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

# Path prefixes that stay allowed even in read-only mode (login so the client can
# reach the notice; CSV export so data stays retrievable; health/license/openapi).
_ALLOW_PREFIXES = (
    "/api/v1/auth",
    "/api/v1/license",
    "/api/v1/health",
    "/health",
    "/api/v1/openapi.json",
)
# Substrings that mark an export/download endpoint (kept writable-safe: they're GET
# anyway, but this belt-and-suspenders allowlist covers POST-based exports too).
_ALLOW_SUBSTRINGS = ("/export", "/csv", "/download")


@dataclass
class LicenseState:
    active: bool = True
    read_only: bool = False
    message: str = ""
    last_ok_ts: float = field(default_factory=time.time)
    last_checked_ts: float = 0.0

    def as_public_dict(self) -> dict:
        return {
            "active": self.active,
            "readOnly": self.read_only,
            "message": self.message,
            "lastChecked": (
                datetime.fromtimestamp(self.last_checked_ts, tz=timezone.utc).isoformat()
                if self.last_checked_ts else None
            ),
        }


STATE = LicenseState()

READ_ONLY_NOTICE = (
    "Your CRM is temporarily in read-only mode while we sort out the account with "
    "Johnson Softwares support. Your data is safe and still fully exportable. "
    "Please contact support to restore full access."
)


def is_read_only() -> bool:
    return STATE.read_only


def _verify_once() -> dict:
    body = json.dumps({"clientId": CLIENT_ID, "licenseKey": LICENSE_KEY}).encode("utf-8")
    req = urllib.request.Request(
        VERIFY_URL,
        data=body,
        headers={"Content-Type": "application/json", "User-Agent": f"crm-{CLIENT_ID or 'unknown'}/license"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


async def _check() -> None:
    STATE.last_checked_ts = time.time()
    try:
        result = await asyncio.to_thread(_verify_once)
    except Exception as exc:  # FAIL OPEN
        stale_days = (time.time() - STATE.last_ok_ts) / 86400.0
        if stale_days > GRACE_DAYS:
            STATE.read_only = True
            STATE.message = READ_ONLY_NOTICE
            logger.warning("License unconfirmed for %.1f days (>%s grace) -> read-only", stale_days, GRACE_DAYS)
        else:
            logger.info("License check failed (%s); within grace, staying active", exc)
        return

    active = bool(result.get("active", True))
    STATE.active = active
    if active:
        STATE.read_only = False
        STATE.message = ""
        STATE.last_ok_ts = time.time()
        logger.info("License active for client=%s", CLIENT_ID)
    else:
        STATE.read_only = True
        STATE.message = result.get("message") or READ_ONLY_NOTICE
        logger.warning("License reported INACTIVE for client=%s -> read-only", CLIENT_ID)


async def run_loop() -> None:
    """Background heartbeat. Created as a task from main.py lifespan when enabled.
    Cancellable like the other cron loops (honours asyncio.CancelledError)."""
    if not LICENSE_KEY:
        logger.warning("ENABLE_LICENSE_HEARTBEAT set but CLIENT_LICENSE_KEY missing — heartbeat idle.")
        return
    try:
        await asyncio.sleep(5)
        while True:
            await _check()
            await asyncio.sleep(INTERVAL_HOURS * 3600)
    except asyncio.CancelledError:
        raise


class ReadOnlyEnforcerMiddleware(BaseHTTPMiddleware):
    """Blocks write methods with 423 when the license is in read-only mode.
    Only mounted by main.py when ENABLE_LICENSE_HEARTBEAT=true, so it is never in
    the middleware stack for the base/default CRM."""

    async def dispatch(self, request: Request, call_next):
        if STATE.read_only and request.method in _WRITE_METHODS:
            path = request.url.path
            allowed = path.startswith(_ALLOW_PREFIXES) or any(s in path for s in _ALLOW_SUBSTRINGS)
            if not allowed:
                return JSONResponse(
                    status_code=423,
                    content={"success": False, "error": "read_only",
                             "message": STATE.message or READ_ONLY_NOTICE},
                )
        return await call_next(request)
