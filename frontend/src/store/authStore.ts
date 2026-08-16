import { create } from 'zustand';

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
    return JSON.parse(val) as T;
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
    localStorage.setItem('access_token', accessToken);
    localStorage.setItem('refresh_token', refreshToken);
    localStorage.setItem('user', JSON.stringify(user));
    localStorage.setItem('organization', JSON.stringify(organization));
    localStorage.setItem('features', JSON.stringify(features));
    set({ user, organization, features, accessToken, refreshToken });
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
  },
}));
