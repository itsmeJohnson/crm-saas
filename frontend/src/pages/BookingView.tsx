import React, { useEffect, useMemo, useState } from 'react';
import { useParams } from 'react-router-dom';
import { publicBookingApi, PublicBookingPage, Availability } from '../services/bookingApi';

const shell: React.CSSProperties = {
  minHeight: '100vh', background: '#0b1220', color: '#e2e8f0',
  fontFamily: 'system-ui, sans-serif', display: 'grid', placeItems: 'start center',
};
const ACCENT = '#4F46E5';

function fmtDay(iso: string): string {
  const d = new Date(iso + 'T00:00:00');
  return d.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' });
}
function fmtTime(iso: string): string {
  return new Date(iso).toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' });
}

/** Public, unauthenticated self-service booking page at /book/:slug. */
export const BookingView: React.FC = () => {
  const { slug = '' } = useParams();
  const [page, setPage] = useState<PublicBookingPage | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [avail, setAvail] = useState<Availability | null>(null);
  const [chosen, setChosen] = useState<string | null>(null);
  const [form, setForm] = useState({ name: '', email: '', phone: '', notes: '' });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirmed, setConfirmed] = useState<{ start: string; host_name: string } | null>(null);

  useEffect(() => {
    publicBookingApi.get(slug).then(setPage).catch(() => setNotFound(true));
  }, [slug]);

  useEffect(() => {
    if (!page) return;
    const today = new Date();
    const from = today.toISOString().slice(0, 10);
    const to = new Date(today.getTime() + (page.advance_days) * 86400000).toISOString().slice(0, 10);
    publicBookingApi.availability(slug, from, to).then(setAvail).catch(() => setAvail(null));
  }, [page, slug]);

  const daysWithSlots = useMemo(
    () => (avail?.days || []).filter((d) => d.slots.length > 0),
    [avail],
  );

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!chosen) { setError('Pick a time first.'); return; }
    if (!form.name.trim()) { setError('Your name is required.'); return; }
    if (!form.email.trim() && !form.phone.trim()) { setError('An email or phone is required.'); return; }
    setSubmitting(true); setError(null);
    try {
      const res = await publicBookingApi.book(slug, { slot_start: chosen, ...form });
      setConfirmed({ start: res.start, host_name: res.host_name });
    } catch (err: any) {
      setError(err?.message || 'Could not book that slot. Please pick another.');
      // Refresh availability so a just-taken slot disappears.
      if (page) {
        const today = new Date();
        publicBookingApi.availability(slug, today.toISOString().slice(0, 10),
          new Date(today.getTime() + page.advance_days * 86400000).toISOString().slice(0, 10))
          .then(setAvail).catch(() => {});
      }
      setChosen(null);
    } finally { setSubmitting(false); }
  };

  if (notFound) return <div style={{ ...shell, alignContent: 'center' }}><p style={{ color: '#94a3b8' }}>This booking page isn’t available.</p></div>;
  if (!page) return <div style={{ ...shell, alignContent: 'center' }}><p style={{ color: '#94a3b8' }}>Loading…</p></div>;

  if (confirmed) {
    return (
      <div style={{ ...shell, alignContent: 'center' }}>
        <div style={{ maxWidth: 460, padding: 32, textAlign: 'center' }}>
          <div style={{ width: 56, height: 56, borderRadius: '50%', background: '#10b98122', color: '#34d399', display: 'grid', placeItems: 'center', margin: '0 auto 16px', fontSize: 28 }}>✓</div>
          <h1 style={{ fontSize: 22, margin: '0 0 8px' }}>You’re booked!</h1>
          <p style={{ color: '#94a3b8', margin: 0 }}>
            {new Date(confirmed.start).toLocaleString(undefined, { weekday: 'long', month: 'long', day: 'numeric', hour: 'numeric', minute: '2-digit' })}
            {' '}with {confirmed.host_name}.
          </p>
          <p style={{ color: '#64748b', fontSize: 13, marginTop: 16 }}>A reminder will be sent before your appointment.</p>
        </div>
      </div>
    );
  }

  return (
    <div style={shell}>
      <div style={{ width: '100%', maxWidth: 720, padding: '48px 20px' }}>
        <div style={{ borderLeft: `3px solid ${ACCENT}`, paddingLeft: 16, marginBottom: 28 }}>
          <p style={{ color: ACCENT, fontSize: 12, fontWeight: 700, letterSpacing: '.08em', textTransform: 'uppercase', margin: '0 0 6px' }}>Book with {page.host_name}</p>
          <h1 style={{ fontSize: 28, margin: '0 0 6px', lineHeight: 1.1 }}>{page.title}</h1>
          {page.description && <p style={{ color: '#94a3b8', margin: 0 }}>{page.description}</p>}
          <p style={{ color: '#64748b', fontSize: 13, marginTop: 8 }}>
            {page.slot_minutes} min{page.location ? ` · ${page.location}` : ''}
          </p>
        </div>

        {!avail && <p style={{ color: '#94a3b8' }}>Loading times…</p>}
        {avail && daysWithSlots.length === 0 && (
          <p style={{ color: '#94a3b8' }}>No open times in the next {page.advance_days} days. Please check back later.</p>
        )}

        <div style={{ display: 'grid', gap: 20 }}>
          {daysWithSlots.map((day) => (
            <div key={day.date}>
              <p style={{ fontSize: 13, fontWeight: 600, color: '#cbd5e1', margin: '0 0 10px' }}>{fmtDay(day.date)}</p>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                {day.slots.map((s) => {
                  const active = chosen === s;
                  return (
                    <button
                      key={s}
                      type="button"
                      onClick={() => { setChosen(s); setError(null); }}
                      style={{
                        padding: '8px 14px', borderRadius: 10, cursor: 'pointer', fontSize: 14,
                        border: `1px solid ${active ? ACCENT : '#293244'}`,
                        background: active ? ACCENT : '#111a2e',
                        color: active ? '#fff' : '#cbd5e1', fontWeight: active ? 600 : 400,
                      }}
                    >
                      {fmtTime(s)}
                    </button>
                  );
                })}
              </div>
            </div>
          ))}
        </div>

        {chosen && (
          <form onSubmit={submit} style={{ marginTop: 28, background: '#0f1830', border: '1px solid #1e2740', borderRadius: 14, padding: 20, display: 'grid', gap: 12 }}>
            <p style={{ margin: 0, fontSize: 14, color: '#cbd5e1' }}>
              Booking <strong style={{ color: '#fff' }}>{new Date(chosen).toLocaleString(undefined, { weekday: 'short', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })}</strong>
            </p>
            <input placeholder="Your name *" value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })} style={inputStyle} />
            <input placeholder="Email" type="email" value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })} style={inputStyle} />
            <input placeholder="Phone" value={form.phone}
              onChange={(e) => setForm({ ...form, phone: e.target.value })} style={inputStyle} />
            <textarea placeholder="Anything we should know? (optional)" value={form.notes} rows={3}
              onChange={(e) => setForm({ ...form, notes: e.target.value })} style={{ ...inputStyle, resize: 'vertical' }} />
            {error && <p style={{ color: '#f87171', fontSize: 13, margin: 0 }}>{error}</p>}
            <button type="submit" disabled={submitting}
              style={{ padding: '12px', borderRadius: 10, border: 'none', background: ACCENT, color: '#fff', fontWeight: 600, cursor: submitting ? 'default' : 'pointer', opacity: submitting ? 0.7 : 1 }}>
              {submitting ? 'Booking…' : 'Confirm booking'}
            </button>
          </form>
        )}
      </div>
    </div>
  );
};

const inputStyle: React.CSSProperties = {
  width: '100%', padding: '10px 12px', borderRadius: 10, border: '1px solid #293244',
  background: '#0b1220', color: '#e2e8f0', fontSize: 14, boxSizing: 'border-box',
};

export default BookingView;
