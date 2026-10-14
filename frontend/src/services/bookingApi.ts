import { api } from './api';

export interface BookingLink {
  id: string;
  organization_id: string;
  host_user_id: string;
  slug: string;
  title: string;
  description?: string | null;
  location?: string | null;
  slot_minutes: number;
  buffer_minutes: number;
  advance_days: number;
  is_active: boolean;
  bookings_count: number;
  created_at: string;
}

export interface PublicBookingPage {
  slug: string;
  title: string;
  description?: string | null;
  location?: string | null;
  slot_minutes: number;
  advance_days: number;
  host_name: string;
}

export interface AvailabilityDay {
  date: string;   // YYYY-MM-DD
  slots: string[]; // ISO instants
}

export interface Availability {
  slug: string;
  slot_minutes: number;
  timezone: string;
  days: AvailabilityDay[];
}

// ── Authenticated admin surface ──
export const bookingApi = {
  list: async () => (await api.get<BookingLink[]>('/booking/links')).data,
  create: async (payload: Partial<BookingLink>) =>
    (await api.post<BookingLink>('/booking/links', payload)).data,
  update: async (id: string, payload: Partial<BookingLink>) =>
    (await api.patch<BookingLink>(`/booking/links/${id}`, payload)).data,
  remove: async (id: string) => { await api.delete(`/booking/links/${id}`); },
};

// ── Public (anonymous visitor) — plain fetch, no auth interceptors ──
const apiBase = () => `${window.location.origin}/api/v1`;

export const publicBookingApi = {
  get: async (slug: string): Promise<PublicBookingPage> => {
    const res = await fetch(`${apiBase()}/public/booking/${encodeURIComponent(slug)}`);
    if (!res.ok) throw new Error('not found');
    return res.json();
  },
  availability: async (slug: string, dateFrom: string, dateTo: string): Promise<Availability> => {
    const res = await fetch(
      `${apiBase()}/public/booking/${encodeURIComponent(slug)}/availability?date_from=${dateFrom}&date_to=${dateTo}`
    );
    if (!res.ok) throw new Error('availability failed');
    return res.json();
  },
  book: async (slug: string, payload: { slot_start: string; name: string; email?: string; phone?: string; notes?: string }) => {
    const res = await fetch(`${apiBase()}/public/booking/${encodeURIComponent(slug)}/book`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const detail = await res.json().catch(() => ({}));
      throw new Error(detail.detail || 'Could not book that slot');
    }
    return res.json();
  },
};
