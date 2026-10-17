import { create } from 'zustand';
import { useMetadataStore } from './metadataStore';

export interface User {
  id: string;
  email: string;
  first_name: string | null;
  last_name: string | null;
  role: string;
  is_active: boolean;
  is_verified: boolean;
  is_team_leader?: boolean;
}

export interface Organization {
  id: string;
  name: string;
  slug: string;
  is_active: boolean;
  subscription_plan?: string | null;
  subscription_status?: string | null;
  subscription_expires_at?: string | null;
  max_users?: number | null;
  currency?: string | null;
  timezone?: string | null;
}

interface AuthState {
  accessToken: string | null;
  refreshToken: string | null;
  user: User | null;
  organization: Organization | null;
  features: string[];
  setAuth: (user: User, organization: Organization, features: string[], accessToken: string, refreshToken: string) => void;
  setTokens: (accessToken: string, refreshToken: string) => void;
  logout: () => void;
}

const safeParse = <T>(key: string, fallback: T): T => {
  try {
    const val = localStorage.getItem(key);
    if (!val || val === 'undefined' || val === 'null') return fallback;
    const parsed = JSON.parse(val) as T;
    // Self-healing: if parsed user is samarthasankalpa@gmail.com and role is SuperAdmin, correct it to OrgAdmin
    if (key === 'user' && parsed && typeof parsed === 'object') {
      const u = parsed as any;
      if (u.email === 'samarthasankalpa@gmail.com' && u.role === 'SuperAdmin') {
        u.role = 'OrgAdmin';
        try {
          localStorage.setItem('user', JSON.stringify(u));
        } catch {}
      }
    }
    return parsed;
  } catch {
    return fallback;
  }
};

export const useAuthStore = create<AuthState>((set) => ({
  accessToken: localStorage.getItem('access_token'),
  refreshToken: localStorage.getItem('refresh_token'),
  user: safeParse<User | null>('user', null),
  organization: safeParse<Organization | null>('organization', null),
  features: safeParse<string[]>('features', []),

  setAuth: (user, organization, features, accessToken, refreshToken) => {
    if (user && user.email === 'samarthasankalpa@gmail.com' && user.role === 'SuperAdmin') {
      user.role = 'OrgAdmin';
    }
    localStorage.setItem('access_token', accessToken);
    localStorage.setItem('refresh_token', refreshToken);
    localStorage.setItem('user', JSON.stringify(user));
    localStorage.setItem('organization', JSON.stringify(organization));
    localStorage.setItem('features', JSON.stringify(features));
    set({ user, organization, features, accessToken, refreshToken });
    // New session (possibly a different tenant/vertical): drop any cached
    // metadata so the org's crm_config — and its vertical skin — re-resolves.
    useMetadataStore.getState().reset();
  },

  setTokens: (accessToken, refreshToken) => {
    localStorage.setItem('access_token', accessToken);
    localStorage.setItem('refresh_token', refreshToken);
    set({ accessToken, refreshToken });
  },

  logout: () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('user');
    localStorage.removeItem('organization');
    localStorage.removeItem('features');
    set({ accessToken: null, refreshToken: null, user: null, organization: null, features: [] });
    // Clear cached org metadata so the next tenant doesn't inherit this one's skin.
    useMetadataStore.getState().reset();
  },
}));
