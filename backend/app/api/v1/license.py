"""
License status endpoint (OPTIONAL — mounted by main.py only when
ENABLE_LICENSE_HEARTBEAT=true). Read-only, unauthenticated status so the SPA can
render a friendly banner. No secrets are exposed (the license key is never returned).
"""

from fastapi import APIRouter

from app.services.license_check import STATE

router = APIRouter()


@router.get("/status")
async def license_status() -> dict:
    return STATE.as_public_dict()
