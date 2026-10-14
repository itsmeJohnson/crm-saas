import React, { useEffect } from 'react';
import { AlertTriangle } from 'lucide-react';
import { api } from '../../services/api';
import { useLicenseStore } from '../../store/licenseStore';

/**
 * Sticky notice shown when the single-tenant license is in read-only mode.
 * Renders nothing on the base CRM (readOnly stays false). Proactively checks
 * /license/status once on mount; that endpoint only exists when the license
 * heartbeat is enabled, so a 404 is ignored and the banner stays hidden.
 */
export const ReadOnlyBanner: React.FC = () => {
  const { readOnly, message, setReadOnly } = useLicenseStore();

  useEffect(() => {
    let cancelled = false;
    api
      .get('/license/status')
      .then((res) => {
        if (!cancelled && res.data?.readOnly) {
          setReadOnly(true, res.data?.message);
        }
      })
      .catch(() => {
        /* endpoint absent (base CRM) or transient error — stay hidden */
      });
    return () => {
      cancelled = true;
    };
  }, [setReadOnly]);

  if (!readOnly) return null;

  return (
    <div
      role="alert"
      className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-amber-900 bg-amber-100 border-b border-amber-300"
    >
      <AlertTriangle className="w-4 h-4 shrink-0" />
      <span>{message}</span>
    </div>
  );
};
