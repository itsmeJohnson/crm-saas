import { api } from './api';

export interface LandingFormField {
  key: string;
  label: string;
  type: string;
  required?: boolean;
}

export interface LandingConfig {
  headline?: string;
  subheadline?: string;
  body?: string;
  cta_text?: string;
  theme?: string; // accent color hex
  form_fields?: LandingFormField[];
}

export interface LandingPage {
  id: string;
  name: string;
  slug: string;
  is_published: boolean;
  views: number;
  submissions: number;
  created_at: string;
  owner_user_id: string | null;
  config?: LandingConfig;
}

export interface LandingList {
  items: LandingPage[];
  count: number;
  website_limit: number;
}

export const landingApi = {
  list: async () => (await api.get<LandingList>('/landing-pages')).data,
  create: async (payload: Partial<LandingPage> & { config?: LandingConfig }) =>
    (await api.post<LandingPage>('/landing-pages', payload)).data,
  get: async (id: string) => (await api.get<LandingPage>(`/landing-pages/${id}`)).data,
  update: async (id: string, payload: Partial<LandingPage> & { config?: LandingConfig }) =>
    (await api.put<LandingPage>(`/landing-pages/${id}`, payload)).data,
  remove: async (id: string) => { await api.delete(`/landing-pages/${id}`); },
};

// ── Public (anonymous visitor) — plain fetch, no auth interceptors ──
const apiBase = () => `${window.location.origin.replace(/:\d+$/, (m) => m)}/api/v1`;

export const publicLandingApi = {
  get: async (slug: string): Promise<{ name: string; slug: string; config: LandingConfig }> => {
    const res = await fetch(`${apiBase()}/public/landing/${encodeURIComponent(slug)}`);
    if (!res.ok) throw new Error('not found');
    return res.json();
  },
  submit: async (slug: string, form: Record<string, any>, utm: Record<string, any>) => {
    const res = await fetch(`${apiBase()}/public/landing/${encodeURIComponent(slug)}/submit`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ form, utm }),
    });
    if (!res.ok) throw new Error('submit failed');
    return res.json();
  },
};
