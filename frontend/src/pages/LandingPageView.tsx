import React, { useEffect, useMemo, useState } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';
import { publicLandingApi, LandingConfig, LandingFormField } from '../services/landingApi';

const DEFAULT_FIELDS: LandingFormField[] = [
  { key: 'name', label: 'Full Name', type: 'text', required: true },
  { key: 'email', label: 'Email', type: 'email' },
  { key: 'phone', label: 'Phone', type: 'tel', required: true },
  { key: 'message', label: 'Message', type: 'textarea' },
];

/** Public, unauthenticated landing page rendered at /lp/:slug. */
export const LandingPageView: React.FC = () => {
  const { slug = '' } = useParams();
  const [params] = useSearchParams();
  const [config, setConfig] = useState<LandingConfig | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [values, setValues] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    publicLandingApi.get(slug).then((r) => setConfig(r.config || {})).catch(() => setNotFound(true));
  }, [slug]);

  const utm = useMemo(() => {
    const keys = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content'];
    const out: Record<string, string> = {};
    keys.forEach((k) => { const v = params.get(k); if (v) out[k] = v; });
    return out;
  }, [params]);

  const fields = config?.form_fields?.length ? config.form_fields : DEFAULT_FIELDS;
  const accent = config?.theme || '#6366f1';

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    for (const f of fields) {
      if (f.required && !values[f.key]?.trim()) { setError(`${f.label} is required`); return; }
    }
    setSubmitting(true); setError(null);
    try {
      await publicLandingApi.submit(slug, values, utm);
      setDone(true);
    } catch {
      setError('Something went wrong. Please try again.');
    } finally { setSubmitting(false); }
  };

  if (notFound) {
    return <div style={{ minHeight: '100vh', display: 'grid', placeItems: 'center', background: '#0f172a', color: '#94a3b8', fontFamily: 'system-ui' }}>Page not found.</div>;
  }
  if (!config) {
    return <div style={{ minHeight: '100vh', display: 'grid', placeItems: 'center', background: '#0f172a', color: '#94a3b8', fontFamily: 'system-ui' }}>Loading…</div>;
  }

  return (
    <div style={{ minHeight: '100vh', background: '#0b1220', color: '#e2e8f0', fontFamily: 'system-ui, sans-serif' }}>
      <div style={{ maxWidth: 1040, margin: '0 auto', padding: '64px 24px', display: 'grid', gap: 40, gridTemplateColumns: 'minmax(0,1fr)' }}>
        <div style={{ display: 'grid', gap: 40, gridTemplateColumns: '1.1fr 0.9fr', alignItems: 'start' }} className="lp-grid">
          {/* Hero */}
          <div>
            <h1 style={{ fontSize: 40, fontWeight: 800, lineHeight: 1.15, margin: 0 }}>
              {config.headline || 'Grow your business with us'}
            </h1>
            {config.subheadline && (
              <p style={{ fontSize: 18, color: '#94a3b8', marginTop: 16 }}>{config.subheadline}</p>
            )}
            {config.body && (
              <p style={{ fontSize: 15, color: '#cbd5e1', marginTop: 20, whiteSpace: 'pre-wrap' }}>{config.body}</p>
            )}
          </div>

          {/* Form card */}
          <div style={{ background: '#111a2e', border: '1px solid #1e293b', borderRadius: 16, padding: 28 }}>
            {done ? (
              <div style={{ textAlign: 'center', padding: '24px 8px' }}>
                <div style={{ width: 56, height: 56, borderRadius: '50%', background: `${accent}22`, border: `1px solid ${accent}55`, display: 'grid', placeItems: 'center', margin: '0 auto 16px', color: accent, fontSize: 26 }}>✓</div>
                <h3 style={{ margin: 0, fontSize: 20 }}>Thank you!</h3>
                <p style={{ color: '#94a3b8', marginTop: 8, fontSize: 14 }}>We've received your details and will be in touch shortly.</p>
              </div>
            ) : (
              <form onSubmit={submit} style={{ display: 'grid', gap: 14 }}>
                <h3 style={{ margin: 0, fontSize: 18 }}>{config.cta_text || 'Request a callback'}</h3>
                {error && <div style={{ background: '#7f1d1d33', border: '1px solid #7f1d1d', color: '#fca5a5', padding: 10, borderRadius: 8, fontSize: 13 }}>{error}</div>}
                {fields.map((f) => (
                  <label key={f.key} style={{ display: 'grid', gap: 6 }}>
                    <span style={{ fontSize: 12, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: 0.5 }}>
                      {f.label}{f.required ? ' *' : ''}
                    </span>
                    {f.type === 'textarea' ? (
                      <textarea rows={3} value={values[f.key] || ''} onChange={(e) => setValues({ ...values, [f.key]: e.target.value })}
                        style={{ background: '#0b1220', border: '1px solid #1e293b', borderRadius: 8, color: '#e2e8f0', padding: '10px 12px', fontSize: 14 }} />
                    ) : (
                      <input type={f.type} value={values[f.key] || ''} onChange={(e) => setValues({ ...values, [f.key]: e.target.value })}
                        style={{ background: '#0b1220', border: '1px solid #1e293b', borderRadius: 8, color: '#e2e8f0', padding: '10px 12px', fontSize: 14 }} />
                    )}
                  </label>
                ))}
                <button type="submit" disabled={submitting}
                  style={{ background: accent, color: '#fff', border: 'none', borderRadius: 10, padding: '12px 16px', fontWeight: 700, fontSize: 15, cursor: 'pointer', opacity: submitting ? 0.6 : 1 }}>
                  {submitting ? 'Submitting…' : (config.cta_text || 'Submit')}
                </button>
              </form>
            )}
          </div>
        </div>
      </div>
      <style>{`@media (max-width: 780px){ .lp-grid{ grid-template-columns: minmax(0,1fr) !important; } }`}</style>
    </div>
  );
};
