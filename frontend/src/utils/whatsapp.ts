// Click-to-chat helper (Feature 5). Builds a wa.me deep link from a phone number.
// Returns null when the number is missing or masked (e.g. "+91******21"), since
// those can't be dialled — callers hide the action in that case.

export function isDialableNumber(phone?: string | null): boolean {
  if (!phone) return false;
  if (phone.includes('*')) return false;
  return phone.replace(/[^0-9]/g, '').length >= 8;
}

/**
 * @param phone  raw phone string (any format)
 * @param message optional pre-filled message
 * @returns a https://wa.me/... URL, or null if the number isn't dialable
 */
export function whatsappHref(phone?: string | null, message?: string): string | null {
  if (!isDialableNumber(phone)) return null;
  const digits = (phone as string).replace(/[^0-9]/g, '');
  const base = `https://wa.me/${digits}`;
  return message ? `${base}?text=${encodeURIComponent(message)}` : base;
}
