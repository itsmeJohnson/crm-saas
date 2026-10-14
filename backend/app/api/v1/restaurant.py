"""Restaurant QR-Voucher vertical — HTTP API.

Two routers:
  * ``public_router`` — no auth. The scan flow (guest opt-in). Tenant identity is
    resolved from the URL's venue slug + table token, never from the body.
  * ``router`` — authenticated staff/admin. Redemption, and owner management of
    venues, offers, tables, guests, vouchers.

PII exposure is role-gated: only SuperAdmin/OrgAdmin/Manager see full guest
phone/email/dob; everyone else gets masked values.
"""
import io
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.middleware.permissions import require_active_user
from app.dependencies.auth import RoleChecker
from app.models.user import User
from app.models.restaurant import RestaurantGuest
from app.services.restaurant_service import (
    RestaurantService, mask_phone, PRIVILEGED_ROLES, STAFF_ROLES,
)
from app.schemas.restaurant import (
    PublicOptInRequest, PublicScanContext,
    VenueCreate, VenueUpdate, VenueResponse,
    OfferCreate, OfferUpdate, OfferResponse,
    TableCreate, TableBulkCreate, TableUpdate, TableResponse,
    GuestResponse, VoucherResponse, RedeemRequest, StatsResponse,
    CampaignPreview, CampaignSendRequest, CampaignResult,
)

router = APIRouter()
public_router = APIRouter()

# Role gates. Redemption is allowed for any staff member; management is not.
require_staff = RoleChecker(list(STAFF_ROLES))
require_manager = RoleChecker(list(PRIVILEGED_ROLES))


def _client_ip(req: Request) -> str:
    fwd = req.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return req.client.host if req.client else "0.0.0.0"


def _guest_out(g: RestaurantGuest, privileged: bool) -> GuestResponse:
    return GuestResponse(
        id=g.id, name=g.name,
        phone=g.phone if privileged else mask_phone(g.phone),
        email=(g.email if privileged else None),
        dob=(g.dob if privileged else None),
        status=g.status, marketing_consent=g.marketing_consent,
        visit_count=g.visit_count, last_visit_at=g.last_visit_at,
        last_table_label=g.last_table_label, rating=g.rating,
        created_at=g.created_at,
    )


# ============================= PUBLIC (unauthenticated) =============================

@public_router.get("/{venue_slug}/t/{table_token}", response_model=PublicScanContext)
async def public_scan(venue_slug: str, table_token: str,
                      db: Annotated[AsyncSession, Depends(get_db)]):
    """What a guest's phone loads after scanning the table QR."""
    return await RestaurantService(db).get_scan_context(venue_slug, table_token)


@public_router.post("/{venue_slug}/t/{table_token}/opt-in")
async def public_opt_in(venue_slug: str, table_token: str, body: PublicOptInRequest,
                        request: Request, db: Annotated[AsyncSession, Depends(get_db)]):
    """Capture the lead + issue and deliver the voucher. Rate-limited globally by
    the middleware and per-phone inside the service."""
    return await RestaurantService(db).opt_in(
        venue_slug=venue_slug, table_token=table_token,
        name=body.name, phone=body.phone, email=body.email, dob=body.dob,
        marketing_consent=body.marketing_consent, consent_ip=_client_ip(request))


# ============================= STAFF: redemption =============================

@router.post("/redeem")
async def redeem_voucher(body: RedeemRequest,
                         actor: Annotated[User, Depends(require_staff)],
                         db: Annotated[AsyncSession, Depends(get_db)]):
    return await RestaurantService(db).redeem(
        actor=actor, code=body.code, table_label=body.table_label)


@router.get("/vouchers/lookup")
async def lookup_voucher(code: Annotated[str, Query(min_length=3, max_length=40)],
                         actor: Annotated[User, Depends(require_staff)],
                         db: Annotated[AsyncSession, Depends(get_db)]):
    """Staff scanner preview before burning (valid / used / expired)."""
    return await RestaurantService(db).lookup_for_staff(actor=actor, code=code)


# ============================= ADMIN: venues =============================

@router.get("/venues", response_model=list[VenueResponse])
async def list_venues(actor: Annotated[User, Depends(require_manager)],
                      db: Annotated[AsyncSession, Depends(get_db)]):
    return await RestaurantService(db).list_venues(actor)


@router.post("/venues", response_model=VenueResponse, status_code=status.HTTP_201_CREATED)
async def create_venue(body: VenueCreate,
                       actor: Annotated[User, Depends(require_manager)],
                       db: Annotated[AsyncSession, Depends(get_db)]):
    return await RestaurantService(db).create_venue(actor, body.model_dump(exclude_unset=True))


@router.patch("/venues/{venue_id}", response_model=VenueResponse)
async def update_venue(venue_id: uuid.UUID, body: VenueUpdate,
                       actor: Annotated[User, Depends(require_manager)],
                       db: Annotated[AsyncSession, Depends(get_db)]):
    return await RestaurantService(db).update_venue(actor, venue_id, body.model_dump(exclude_unset=True))


# ============================= ADMIN: offers =============================

@router.get("/offers", response_model=list[OfferResponse])
async def list_offers(actor: Annotated[User, Depends(require_manager)],
                      db: Annotated[AsyncSession, Depends(get_db)],
                      venue_id: uuid.UUID | None = None):
    return await RestaurantService(db).list_offers(actor, venue_id)


@router.post("/offers", response_model=OfferResponse, status_code=status.HTTP_201_CREATED)
async def create_offer(body: OfferCreate,
                       actor: Annotated[User, Depends(require_manager)],
                       db: Annotated[AsyncSession, Depends(get_db)]):
    return await RestaurantService(db).create_offer(actor, body.model_dump(exclude_unset=True))


@router.patch("/offers/{offer_id}", response_model=OfferResponse)
async def update_offer(offer_id: uuid.UUID, body: OfferUpdate,
                       actor: Annotated[User, Depends(require_manager)],
                       db: Annotated[AsyncSession, Depends(get_db)]):
    return await RestaurantService(db).update_offer(actor, offer_id, body.model_dump(exclude_unset=True))


# ============================= ADMIN: tables + QR =============================

async def _table_out(svc: RestaurantService, t) -> TableResponse:
    resp = TableResponse.model_validate(t)
    resp.scan_url = await svc.scan_url_for(t)
    return resp


@router.get("/tables", response_model=list[TableResponse])
async def list_tables(actor: Annotated[User, Depends(require_manager)],
                      db: Annotated[AsyncSession, Depends(get_db)],
                      venue_id: uuid.UUID | None = None):
    svc = RestaurantService(db)
    return [await _table_out(svc, t) for t in await svc.list_tables(actor, venue_id)]


@router.post("/tables", response_model=TableResponse, status_code=status.HTTP_201_CREATED)
async def create_table(body: TableCreate,
                       actor: Annotated[User, Depends(require_manager)],
                       db: Annotated[AsyncSession, Depends(get_db)]):
    svc = RestaurantService(db)
    t = await svc.create_table(actor, body.model_dump(exclude_unset=True))
    return await _table_out(svc, t)


@router.post("/tables/bulk", response_model=list[TableResponse], status_code=status.HTTP_201_CREATED)
async def bulk_create_tables(body: TableBulkCreate,
                             actor: Annotated[User, Depends(require_manager)],
                             db: Annotated[AsyncSession, Depends(get_db)]):
    svc = RestaurantService(db)
    tables = await svc.bulk_create_tables(actor, body.model_dump(exclude_unset=True))
    return [await _table_out(svc, t) for t in tables]


@router.patch("/tables/{table_id}", response_model=TableResponse)
async def update_table(table_id: uuid.UUID, body: TableUpdate,
                       actor: Annotated[User, Depends(require_manager)],
                       db: Annotated[AsyncSession, Depends(get_db)]):
    svc = RestaurantService(db)
    t = await svc.update_table(actor, table_id, body.model_dump(exclude_unset=True))
    return await _table_out(svc, t)


@router.get("/tables/{table_id}/qr.png")
async def table_qr_png(table_id: uuid.UUID,
                       actor: Annotated[User, Depends(require_manager)],
                       db: Annotated[AsyncSession, Depends(get_db)]):
    """PNG QR of the table's scan URL, for printing acrylic stands."""
    import qrcode
    from qrcode.constants import ERROR_CORRECT_H

    svc = RestaurantService(db)
    tables = await svc.list_tables(actor)
    table = next((t for t in tables if t.id == table_id), None)
    if not table:
        return Response(status_code=404, content="Table not found.")
    url = await svc.scan_url_for(table)
    qr = qrcode.QRCode(error_correction=ERROR_CORRECT_H, box_size=10, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#0F172A", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return Response(content=buf.getvalue(), media_type="image/png",
                    headers={"Content-Disposition": f'inline; filename="qr-{table.label}.png"'})


# ============================= ADMIN: guests / vouchers / stats =============================

@router.get("/guests", response_model=list[GuestResponse])
async def list_guests(actor: Annotated[User, Depends(require_staff)],
                      db: Annotated[AsyncSession, Depends(get_db)],
                      venue_id: uuid.UUID | None = None,
                      search: str | None = None,
                      limit: int = Query(100, ge=1, le=500),
                      offset: int = Query(0, ge=0)):
    privileged = actor.role in PRIVILEGED_ROLES
    guests = await RestaurantService(db).list_guests(
        actor, venue_id=venue_id, search=search, limit=limit, offset=offset)
    return [_guest_out(g, privileged) for g in guests]


@router.get("/vouchers", response_model=list[VoucherResponse])
async def list_vouchers(actor: Annotated[User, Depends(require_staff)],
                        db: Annotated[AsyncSession, Depends(get_db)],
                        status_filter: str | None = Query(None, alias="status"),
                        limit: int = Query(100, ge=1, le=500),
                        offset: int = Query(0, ge=0)):
    return await RestaurantService(db).list_vouchers(
        actor, status_filter=status_filter, limit=limit, offset=offset)


@router.get("/stats", response_model=StatsResponse)
async def stats(actor: Annotated[User, Depends(require_manager)],
                db: Annotated[AsyncSession, Depends(get_db)]):
    return await RestaurantService(db).stats(actor)


# ============================= ADMIN: campaigns =============================

@router.get("/campaigns/preview", response_model=CampaignPreview)
async def campaign_preview(actor: Annotated[User, Depends(require_manager)],
                           db: Annotated[AsyncSession, Depends(get_db)],
                           venue_id: uuid.UUID | None = None):
    return await RestaurantService(db).campaign_preview(actor, venue_id)


@router.post("/campaigns/send", response_model=CampaignResult)
async def campaign_send(body: CampaignSendRequest,
                        actor: Annotated[User, Depends(require_manager)],
                        db: Annotated[AsyncSession, Depends(get_db)]):
    return await RestaurantService(db).send_campaign(
        actor, message=body.message, title=body.title, venue_id=body.venue_id)
