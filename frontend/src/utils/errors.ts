/**
 * FastAPI's `detail` field on error responses isn't always a plain string -
 * validation errors (422) return an array of {loc, msg, type} objects, and
 * some handlers may return an object. Rendering that directly as a React
 * child throws ("Objects are not valid as a React child"), which surfaces as
 * a full-page crash instead of an inline error message. Always pass error
 * responses through this before calling setError().
 */
export function extractErrorMessage(err: any, fallback: string): string {
  const detail = err?.response?.data?.detail;
  if (!detail) return fallback;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((item) => (typeof item === 'string' ? item : item?.msg || JSON.stringify(item)))
      .join('; ') || fallback;
  }
  if (typeof detail === 'object') {
    return (detail as any).msg || JSON.stringify(detail);
  }
  return fallback;
}
