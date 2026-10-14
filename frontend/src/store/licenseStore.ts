import { create } from 'zustand';

/**
 * License state for single-tenant instances. On the base CRM (no license
 * heartbeat) this simply stays { readOnly: false } forever — the backend never
 * returns a 423 read_only and /license/status 404s, so the banner never shows.
 */
interface LicenseState {
  readOnly: boolean;
  message: string;
  setReadOnly: (readOnly: boolean, message?: string) => void;
}

const DEFAULT_MESSAGE =
  'Your CRM is temporarily in read-only mode. Your data is safe and still fully ' +
  'exportable. Please contact support to restore full access.';

export const useLicenseStore = create<LicenseState>((set) => ({
  readOnly: false,
  message: '',
  setReadOnly: (readOnly, message) =>
    set({ readOnly, message: readOnly ? message || DEFAULT_MESSAGE : '' }),
}));
