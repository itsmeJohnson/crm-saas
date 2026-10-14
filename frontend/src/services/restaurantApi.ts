import { api } from './api';

// ============================= Public (anonymous guest) types =============================

export interface ScanVenue {
  name: string;
  slug: string;
  logo_url?: string | null;
  brand_color: string;
  consent_text: string;
}
export interface ScanOffer {
  title: string;
  description?: string | null;
  terms?: string | null;
  image_url?: string | null;
}
export interface ScanContext {
  venue: ScanVenue;
  table: { label: string; token: string };
  offer: ScanOffer;
}

export interface OptInPayload {
  name: string;
  phone: string;
  email?: string | null;
  dob?: string | null;
  marketing_consent: boolean;
}
export interface OptInResult {
  is_new_guest: boolean;
  already_had_voucher: boolean;
  guest: { name: string; phone_masked: string; visit_count: number };
  voucher: {
    code: string;
    offer_title: string;
    status: string;
    expires_at?: string | null;
    delivery_status: string;
  };
  message: string;
}

// ── Public (anonymous visitor) — plain fetch, no auth interceptors ──
const apiBase = () => `${window.location.origin}/api/v1`;

async function readError(res: Response, fallback: string): Promise<string> {
  const detail = await res.json().catch(() => ({} as any));
  return (detail && (detail.detail || detail.error)) || fallback;
}

export const publicRestaurantApi = {
  scan: async (venueSlug: string, tableToken: string): Promise<ScanContext> => {
    const res = await fetch(
      `${apiBase()}/public/restaurant/${encodeURIComponent(venueSlug)}/t/${encodeURIComponent(tableToken)}`,
    );
    if (!res.ok) throw new Error(await readError(res, 'This QR code is not active.'));
    return res.json();
  },
  optIn: async (venueSlug: string, tableToken: string, payload: OptInPayload): Promise<OptInResult> => {
    const res = await fetch(
      `${apiBase()}/public/restaurant/${encodeURIComponent(venueSlug)}/t/${encodeURIComponent(tableToken)}/opt-in`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      },
    );
    if (!res.ok) throw new Error(await readError(res, 'Could not issue your voucher. Please try again.'));
    return res.json();
  },
};

// ============================= Authenticated staff/admin surface =============================
// (Used by the staff PWA scanner and owner dashboard — Phases 3 & 4.)

export interface Voucher {
  id: string;
  code: string;
  offer_title: string;
  status: string;
  issued_table_label?: string | null;
  expires_at?: string | null;
  redeemed_at?: string | null;
  redeemed_table_label?: string | null;
  delivery_status: string;
  created_at: string;
}
export interface RedeemResult {
  success: boolean;
  message: string;
  voucher: { code: string; offer_title: string; status: string; redeemed_at?: string | null; redeemed_by?: string | null };
}
export interface VoucherLookup {
  code: string;
  offer_title: string;
  status: string;
  expires_at?: string | null;
  redeemed_at?: string | null;
  guest_name?: string | null;
  guest_phone_masked?: string | null;
  redeemable: boolean;
}

export interface Venue {
  id: string; name: string; slug: string; timezone: string; default_country_code: string;
  logo_url?: string | null; brand_color: string; consent_text: string;
  whatsapp_settings_id?: string | null; default_offer_id?: string | null; is_active: boolean; created_at: string;
}
export interface Offer {
  id: string; venue_id: string; title: string; description?: string | null; terms?: string | null;
  image_url?: string | null; valid_from?: string | null; valid_until?: string | null;
  voucher_validity_days?: number | null; per_guest_limit: number; total_issue_limit?: number | null;
  issued_count: number; redeemed_count: number; is_active: boolean;
}
export interface Table {
  id: string; venue_id: string; label: string; token: string; offer_id?: string | null;
  is_active: boolean; scan_count: number; last_scanned_at?: string | null; scan_url?: string | null;
}
export interface Guest {
  id: string; name: string; phone: string; email?: string | null; dob?: string | null;
  status: string; marketing_consent: boolean; visit_count: number; last_visit_at?: string | null;
  last_table_label?: string | null; rating?: number | null; created_at: string;
}
export interface Stats {
  total_guests: number; active_opted_in: number; opted_out: number; total_visits: number;
  total_vouchers: number; active_vouchers: number; redeemed_vouchers: number;
  redemption_rate_pct: number; birthdays_this_month: number;
}
export interface CampaignPreview {
  recipients: number; suppressed_opted_out: number; est_cost: number; cost_per_msg: number;
}
export interface CampaignResult {
  title: string; recipients: number; queued: number; simulated: number; channel: string; est_cost: number;
}

export const restaurantApi = {
  redeem: async (code: string, table_label?: string) =>
    (await api.post<RedeemResult>('/restaurant/redeem', { code, table_label })).data,
  lookup: async (code: string) =>
    (await api.get<VoucherLookup>(`/restaurant/vouchers/lookup`, { params: { code } })).data,
  stats: async () => (await api.get<Stats>('/restaurant/stats')).data,
  listGuests: async (params?: Record<string, unknown>) =>
    (await api.get<Guest[]>('/restaurant/guests', { params })).data,
  listVouchers: async (params?: Record<string, unknown>) =>
    (await api.get<Voucher[]>('/restaurant/vouchers', { params })).data,

  // Campaigns
  campaignPreview: async (venue_id?: string) =>
    (await api.get<CampaignPreview>('/restaurant/campaigns/preview', { params: venue_id ? { venue_id } : {} })).data,
  sendCampaign: async (payload: { message: string; title?: string; venue_id?: string }) =>
    (await api.post<CampaignResult>('/restaurant/campaigns/send', payload)).data,

  // Venues
  listVenues: async () => (await api.get<Venue[]>('/restaurant/venues')).data,
  createVenue: async (payload: Partial<Venue>) =>
    (await api.post<Venue>('/restaurant/venues', payload)).data,
  updateVenue: async (id: string, payload: Partial<Venue>) =>
    (await api.patch<Venue>(`/restaurant/venues/${id}`, payload)).data,

  // Offers
  listOffers: async (venue_id?: string) =>
    (await api.get<Offer[]>('/restaurant/offers', { params: venue_id ? { venue_id } : {} })).data,
  createOffer: async (payload: Partial<Offer>) =>
    (await api.post<Offer>('/restaurant/offers', payload)).data,
  updateOffer: async (id: string, payload: Partial<Offer>) =>
    (await api.patch<Offer>(`/restaurant/offers/${id}`, payload)).data,

  // Tables
  listTables: async (venue_id?: string) =>
    (await api.get<Table[]>('/restaurant/tables', { params: venue_id ? { venue_id } : {} })).data,
  createTable: async (payload: { venue_id: string; label: string; offer_id?: string }) =>
    (await api.post<Table>('/restaurant/tables', payload)).data,
  bulkCreateTables: async (payload: { venue_id: string; prefix?: string; start?: number; count: number; offer_id?: string }) =>
    (await api.post<Table[]>('/restaurant/tables/bulk', payload)).data,
  updateTable: async (id: string, payload: Partial<Table>) =>
    (await api.patch<Table>(`/restaurant/tables/${id}`, payload)).data,
  // QR PNG for a table (auth-protected → fetch as blob and return an object URL)
  qrBlobUrl: async (tableId: string): Promise<string> => {
    const res = await api.get(`/restaurant/tables/${tableId}/qr.png`, { responseType: 'blob' });
    return URL.createObjectURL(res.data as Blob);
  },
};
