import { useAuthStore } from '../store/authStore';

/** Symbols for currencies we surface in the tenant settings. */
const SYMBOLS: Record<string, string> = {
  INR: '₹', USD: '$', EUR: '€', GBP: '£', AED: 'د.إ',
  AUD: 'A$', CAD: 'C$', SGD: 'S$', JPY: '¥',
};

/** Preferred locale per currency so grouping/format reads naturally (e.g. Indian lakhs). */
const LOCALES: Record<string, string> = {
  INR: 'en-IN', USD: 'en-US', EUR: 'en-IE', GBP: 'en-GB',
  AED: 'en-AE', AUD: 'en-AU', CAD: 'en-CA', SGD: 'en-SG', JPY: 'ja-JP',
};

/** The current tenant's currency code, read live from the auth store. Defaults to INR. */
export const getOrgCurrency = (): string =>
  (useAuthStore.getState().organization?.currency || 'INR').toUpperCase();

export const currencySymbol = (code?: string): string => {
  const c = (code || getOrgCurrency()).toUpperCase();
  return SYMBOLS[c] || c + ' ';
};

/**
 * Format a number as money in the tenant's currency (or an explicit code).
 * Falls back to a symbol + grouped number if Intl rejects the code.
 */
export const formatMoney = (
  n: number | null | undefined,
  opts?: { code?: string; maximumFractionDigits?: number },
): string => {
  const amount = n || 0;
  const code = (opts?.code || getOrgCurrency()).toUpperCase();
  const locale = LOCALES[code] || 'en-US';
  try {
    return new Intl.NumberFormat(locale, {
      style: 'currency',
      currency: code,
      maximumFractionDigits: opts?.maximumFractionDigits ?? 0,
    }).format(amount);
  } catch {
    return `${currencySymbol(code)}${amount.toLocaleString()}`;
  }
};
