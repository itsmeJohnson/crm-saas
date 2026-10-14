import React, { useEffect, useMemo, useState } from 'react';
import { useParams } from 'react-router-dom';
import {
  publicRestaurantApi, ScanContext, OptInResult,
} from '../services/restaurantApi';

/**
 * Public, unauthenticated guest opt-in page at /r/:venueSlug/t/:tableToken.
 * This is what a diner's phone loads after scanning the table QR. It captures
 * the lead (name + WhatsApp + optional DOB) with explicit consent and shows the
 * issued voucher. Tenant identity is resolved server-side from the URL tokens.
 */
export const RestaurantOptInView: React.FC = () => {
  const { venueSlug = '', tableToken = '' } = useParams();
  const [ctx, setCtx] = useState<ScanContext | null>(null);
  const [loadErr, setLoadErr] = useState<string | null>(null);
  const [form, setForm] = useState({ name: '', phone: '', dob: '', email: '', consent: false });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<OptInResult | null>(null);

  useEffect(() => {
    publicRestaurantApi.scan(venueSlug, tableToken)
      .then(setCtx)
      .catch((e) => setLoadErr(e?.message || 'This QR code is not active.'));
  }, [venueSlug, tableToken]);

  const accent = ctx?.venue.brand_color || '#D97706';
  const S = useMemo(() => makeStyles(accent), [accent]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.name.trim()) { setError('Please enter your name.'); return; }
    if (form.phone.replace(/\D/g, '').length < 8) { setError('Please enter a valid WhatsApp number.'); return; }
    if (!form.consent) { setError('Please tick the box to receive your voucher on WhatsApp.'); return; }
    setSubmitting(true); setError(null);
    try {
      const res = await publicRestaurantApi.optIn(venueSlug, tableToken, {
        name: form.name.trim(),
        phone: form.phone.trim(),
        email: form.email.trim() || null,
        dob: form.dob || null,
        marketing_consent: form.consent,
      });
      setResult(res);
    } catch (err: any) {
      setError(err?.message || 'Something went wrong. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  // ---------------- loading / error ----------------
  if (loadErr) {
    return (
      <div style={S.shell}>
        <div style={{ ...S.card, textAlign: 'center' }}>
          <div style={{ fontSize: 44, marginBottom: 12 }}>🔒</div>
          <h1 style={S.h1}>QR not available</h1>
          <p style={S.muted}>{loadErr}</p>
        </div>
        <Footer S={S} />
      </div>
    );
  }
  if (!ctx) {
    return (
      <div style={S.shell}>
        <div style={{ ...S.card, textAlign: 'center' }}>
          <p style={S.muted}>Loading…</p>
        </div>
      </div>
    );
  }

  const { venue, table, offer } = ctx;

  // ---------------- success ----------------
  if (result) {
    const firstName = result.guest.name.split(' ')[0];
    const delivered = result.voucher.delivery_status;
    const deliveryNote =
      delivered === 'sent' ? '📲 Sent to your WhatsApp — check your chats.'
        : delivered === 'simulated' ? '📲 Voucher ready. (WhatsApp delivery is in demo mode.)'
          : delivered === 'failed' ? '⚠️ We couldn’t reach WhatsApp — show this screen to our team.'
            : 'Your voucher is ready.';
    return (
      <div style={S.shell}>
        <div style={S.card}>
          <VenueHeader venue={venue} tableLabel={table.label} S={S} />
          <div style={{ textAlign: 'center', marginTop: 8 }}>
            <div style={S.tick}>✓</div>
            <h1 style={{ ...S.h1, marginTop: 14 }}>
              {result.is_new_guest ? `Welcome, ${firstName}!` : `Welcome back, ${firstName}!`}
            </h1>
            <p style={S.muted}>
              {result.already_had_voucher
                ? 'Here is your active voucher.'
                : 'Your complimentary treat is unlocked.'}
              {!result.is_new_guest && ` · Visit #${result.guest.visit_count}`}
            </p>
          </div>

          <div style={S.voucherBox}>
            <p style={S.voucherLabel}>{result.voucher.offer_title}</p>
            <div style={S.code}>{result.voucher.code}</div>
            <p style={S.voucherHint}>Show this code to our team to redeem</p>
          </div>

          <p style={{ ...S.muted, textAlign: 'center', marginTop: 16 }}>{deliveryNote}</p>
          {result.voucher.expires_at && (
            <p style={{ ...S.fine, textAlign: 'center' }}>
              Valid until {new Date(result.voucher.expires_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}
            </p>
          )}
        </div>
        <Footer S={S} />
      </div>
    );
  }

  // ---------------- opt-in form ----------------
  return (
    <div style={S.shell}>
      <div style={S.card}>
        <VenueHeader venue={venue} tableLabel={table.label} S={S} />

        <div style={S.offer}>
          {offer.image_url && (
            <img src={offer.image_url} alt="" style={S.offerImg} />
          )}
          <div style={{ flex: 1 }}>
            <p style={S.offerKicker}>🍽 Complimentary welcome treat</p>
            <p style={S.offerTitle}>{offer.title}</p>
            {offer.description && <p style={S.offerDesc}>{offer.description}</p>}
            {offer.terms && <p style={S.fine}>{offer.terms}</p>}
          </div>
        </div>

        <form onSubmit={submit} style={{ marginTop: 20 }}>
          <Field label="Your name" required S={S}>
            <input
              style={S.input} value={form.name} autoComplete="name"
              placeholder="e.g. Priya Sharma"
              onChange={(e) => setForm({ ...form, name: e.target.value })}
            />
          </Field>

          <Field label="WhatsApp number" required S={S} hint="Your voucher is sent instantly to this number.">
            <input
              style={S.input} value={form.phone} inputMode="tel" autoComplete="tel"
              placeholder="10-digit mobile number"
              onChange={(e) => setForm({ ...form, phone: e.target.value })}
            />
          </Field>

          <div style={{ display: 'flex', gap: 12 }}>
            <div style={{ flex: 1 }}>
              <Field label="Birthday" S={S} hint="Optional">
                <input
                  style={S.input} type="date" value={form.dob}
                  onChange={(e) => setForm({ ...form, dob: e.target.value })}
                />
              </Field>
            </div>
            <div style={{ flex: 1 }}>
              <Field label="Email" S={S} hint="Optional">
                <input
                  style={S.input} type="email" value={form.email} autoComplete="email"
                  placeholder="you@email.com"
                  onChange={(e) => setForm({ ...form, email: e.target.value })}
                />
              </Field>
            </div>
          </div>

          <label style={S.consent}>
            <input
              type="checkbox" checked={form.consent} style={{ marginTop: 3, width: 18, height: 18, accentColor: accent }}
              onChange={(e) => setForm({ ...form, consent: e.target.checked })}
            />
            <span style={S.consentText}>{venue.consent_text}</span>
          </label>

          {error && <div style={S.error}>{error}</div>}

          <button type="submit" disabled={submitting} style={{ ...S.submit, opacity: submitting ? 0.7 : 1 }}>
            {submitting ? 'Unlocking…' : 'Unlock my voucher'}
          </button>
          <p style={S.fine}>🔒 DPDP-compliant · No spam · Reply STOP anytime to opt out.</p>
        </form>
      </div>
      <Footer S={S} />
    </div>
  );
};

// ---------------- small components ----------------

const VenueHeader: React.FC<{ venue: ScanContext['venue']; tableLabel: string; S: Styles }> = ({ venue, tableLabel, S }) => (
  <div style={S.venueHead}>
    {venue.logo_url
      ? <img src={venue.logo_url} alt={venue.name} style={S.logo} />
      : <div style={S.logoFallback}>{venue.name.slice(0, 1)}</div>}
    <div style={{ flex: 1 }}>
      <p style={S.brandKicker}>Table Dine-in Rewards</p>
      <h2 style={S.venueName}>{venue.name}</h2>
    </div>
    <span style={S.tableChip}>{tableLabel}</span>
  </div>
);

const Field: React.FC<{ label: string; required?: boolean; hint?: string; S: Styles; children: React.ReactNode }> = ({ label, required, hint, S, children }) => (
  <div style={{ marginBottom: 14 }}>
    <label style={S.fieldLabel}>{label}{required && <span style={{ color: '#f87171' }}> *</span>}</label>
    {children}
    {hint && <p style={S.fine}>{hint}</p>}
  </div>
);

const Footer: React.FC<{ S: Styles }> = ({ S }) => (
  <p style={S.footer}>Powered by <b style={{ color: '#cbd5e1' }}>Johnson Softwares</b></p>
);

// ---------------- styles ----------------

type Styles = ReturnType<typeof makeStyles>;
function makeStyles(accent: string) {
  return {
    shell: {
      minHeight: '100vh', background: 'radial-gradient(120% 80% at 50% 0%, #101828 0%, #080b14 60%)',
      color: '#e5e7eb', fontFamily: 'system-ui, -apple-system, sans-serif',
      display: 'flex', flexDirection: 'column', alignItems: 'center',
      padding: '24px 16px', boxSizing: 'border-box',
    } as React.CSSProperties,
    card: {
      width: '100%', maxWidth: 460, background: 'rgba(17,24,39,.7)',
      border: '1px solid #1f2937', borderRadius: 22, padding: 24,
      boxShadow: '0 20px 60px rgba(0,0,0,.45)', boxSizing: 'border-box',
    } as React.CSSProperties,
    venueHead: { display: 'flex', alignItems: 'center', gap: 12, marginBottom: 18 } as React.CSSProperties,
    logo: { width: 48, height: 48, borderRadius: 12, objectFit: 'cover' } as React.CSSProperties,
    logoFallback: {
      width: 48, height: 48, borderRadius: 12, background: accent, color: '#0a0c14',
      display: 'grid', placeItems: 'center', fontWeight: 800, fontSize: 22,
    } as React.CSSProperties,
    brandKicker: { color: accent, fontSize: 11, fontWeight: 700, letterSpacing: '.08em', textTransform: 'uppercase', margin: 0 } as React.CSSProperties,
    venueName: { fontSize: 20, fontWeight: 800, margin: '2px 0 0' } as React.CSSProperties,
    tableChip: { background: `${accent}22`, color: accent, border: `1px solid ${accent}55`, borderRadius: 20, padding: '5px 12px', fontSize: 13, fontWeight: 700 } as React.CSSProperties,
    offer: {
      display: 'flex', gap: 12, alignItems: 'center', background: `${accent}12`,
      border: `1px solid ${accent}44`, borderRadius: 16, padding: 14,
    } as React.CSSProperties,
    offerImg: { width: 64, height: 64, borderRadius: 12, objectFit: 'cover' } as React.CSSProperties,
    offerKicker: { color: accent, fontSize: 11, fontWeight: 700, letterSpacing: '.05em', textTransform: 'uppercase', margin: 0 } as React.CSSProperties,
    offerTitle: { fontSize: 17, fontWeight: 700, color: '#f8fafc', margin: '4px 0 0' } as React.CSSProperties,
    offerDesc: { fontSize: 13, color: '#9ca3af', margin: '4px 0 0', lineHeight: 1.4 } as React.CSSProperties,
    fieldLabel: { display: 'block', fontSize: 12, fontWeight: 600, color: '#cbd5e1', textTransform: 'uppercase', letterSpacing: '.04em', marginBottom: 6 } as React.CSSProperties,
    input: {
      width: '100%', boxSizing: 'border-box', padding: '12px 14px', borderRadius: 12,
      background: '#0b1220', border: '1px solid #293244', color: '#e5e7eb', fontSize: 16, outline: 'none',
    } as React.CSSProperties,
    consent: { display: 'flex', gap: 10, alignItems: 'flex-start', margin: '6px 0 4px', cursor: 'pointer' } as React.CSSProperties,
    consentText: { fontSize: 12.5, color: '#94a3b8', lineHeight: 1.45 } as React.CSSProperties,
    submit: {
      width: '100%', marginTop: 16, padding: '15px 16px', borderRadius: 14, border: 'none',
      background: accent, color: '#0a0c14', fontWeight: 800, fontSize: 16, cursor: 'pointer',
    } as React.CSSProperties,
    error: { background: '#7f1d1d33', border: '1px solid #b91c1c', color: '#fca5a5', borderRadius: 10, padding: '10px 12px', fontSize: 13, marginTop: 12 } as React.CSSProperties,
    tick: { width: 60, height: 60, borderRadius: '50%', background: '#10b98122', color: '#34d399', display: 'grid', placeItems: 'center', margin: '4px auto 0', fontSize: 30, border: '2px solid #10b98155' } as React.CSSProperties,
    voucherBox: { marginTop: 20, background: '#0b1220', border: `2px dashed ${accent}`, borderRadius: 16, padding: 20, textAlign: 'center' } as React.CSSProperties,
    voucherLabel: { fontSize: 14, color: '#cbd5e1', margin: 0, fontWeight: 600 } as React.CSSProperties,
    code: { fontFamily: 'ui-monospace, Menlo, monospace', fontSize: 30, fontWeight: 800, letterSpacing: '.06em', color: accent, margin: '10px 0' } as React.CSSProperties,
    voucherHint: { fontSize: 12, color: '#64748b', margin: 0 } as React.CSSProperties,
    h1: { fontSize: 22, fontWeight: 800, margin: 0 } as React.CSSProperties,
    muted: { color: '#94a3b8', fontSize: 14, margin: '6px 0 0', lineHeight: 1.5 } as React.CSSProperties,
    fine: { color: '#64748b', fontSize: 11.5, margin: '6px 0 0', textAlign: 'center' as const, lineHeight: 1.4 } as React.CSSProperties,
    footer: { color: '#475569', fontSize: 12, marginTop: 18 } as React.CSSProperties,
  };
}
