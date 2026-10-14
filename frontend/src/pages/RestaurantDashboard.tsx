import React, { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  restaurantApi, Venue, Offer, Table, Guest, Stats, Voucher,
  CampaignPreview, CampaignResult,
} from '../services/restaurantApi';

/**
 * Owner console for the Restaurant QR-Voucher vertical at /restaurant/manage
 * (authenticated, manager+). Responsive tabbed dashboard: overview stats,
 * guests (opted-in leads), offers, tables with printable QR stands, and vouchers.
 */

const ACCENT = '#D97706';
const GREEN = '#10b981';
type Tab = 'overview' | 'guests' | 'offers' | 'tables' | 'campaigns' | 'vouchers';

export const RestaurantDashboard: React.FC = () => {
  const [venues, setVenues] = useState<Venue[] | null>(null);
  const [venueId, setVenueId] = useState<string>('');
  const [tab, setTab] = useState<Tab>('overview');
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    restaurantApi.listVenues()
      .then((v) => { setVenues(v); if (v.length) setVenueId(v[0].id); })
      .catch((e) => setErr(e?.response?.data?.detail || 'Failed to load. Are you signed in as a manager?'));
  }, []);

  const venue = venues?.find((v) => v.id === venueId) || null;

  if (err) return <Shell><div style={S.card}><p style={S.warn}>{err}</p></div></Shell>;
  if (!venues) return <Shell><p style={S.muted}>Loading…</p></Shell>;
  if (venues.length === 0) return <Shell><CreateVenue onCreated={(v) => { setVenues([v]); setVenueId(v.id); }} /></Shell>;

  return (
    <Shell>
      <div style={S.topbar}>
        <div>
          <p style={S.kicker}>Restaurant Console</p>
          <h1 style={S.h1}>{venue?.name}</h1>
        </div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {venues.length > 1 && (
            <select value={venueId} onChange={(e) => setVenueId(e.target.value)} style={S.select}>
              {venues.map((v) => <option key={v.id} value={v.id}>{v.name}</option>)}
            </select>
          )}
          <Link to="/staff/redeem" style={S.linkBtn}>🔥 Scanner</Link>
        </div>
      </div>

      <div style={S.tabs}>
        {(['overview', 'guests', 'offers', 'tables', 'campaigns', 'vouchers'] as Tab[]).map((t) => (
          <button key={t} onClick={() => setTab(t)}
            style={{ ...S.tab, ...(tab === t ? S.tabActive : {}) }}>{t}</button>
        ))}
      </div>

      {tab === 'overview' && <Overview />}
      {tab === 'guests' && <Guests />}
      {tab === 'offers' && venue && <Offers venueId={venueId} />}
      {tab === 'tables' && venue && <Tables venueId={venueId} />}
      {tab === 'campaigns' && venue && <Campaigns venueId={venueId} />}
      {tab === 'vouchers' && <Vouchers />}
    </Shell>
  );
};

// ============================= tabs =============================

const Overview: React.FC = () => {
  const [s, setS] = useState<Stats | null>(null);
  const [e, setE] = useState<string | null>(null);
  useEffect(() => { restaurantApi.stats().then(setS).catch(() => setE('Failed to load stats.')); }, []);
  if (e) return <p style={S.warn}>{e}</p>;
  if (!s) return <p style={S.muted}>Loading…</p>;
  const cards: [string, string | number, string, string][] = [
    ['Opted-in guests', s.active_opted_in, `${s.total_guests} total captured`, ACCENT],
    ['Redemption rate', `${s.redemption_rate_pct}%`, `${s.redeemed_vouchers} of ${s.total_vouchers} vouchers`, GREEN],
    ['Active vouchers', s.active_vouchers, 'awaiting redemption', '#60a5fa'],
    ['Birthdays this month', s.birthdays_this_month, 'auto-treat opportunities', '#c084fc'],
    ['Total visits', s.total_visits, 'across all guests', '#f472b6'],
    ['Opted out', s.opted_out, 'suppressed from campaigns', '#94a3b8'],
  ];
  return (
    <div style={S.grid}>
      {cards.map(([label, val, sub, col]) => (
        <div key={label} style={S.stat}>
          <p style={S.statLabel}>{label}</p>
          <p style={{ ...S.statVal, color: col }}>{val}</p>
          <p style={S.statSub}>{sub}</p>
        </div>
      ))}
    </div>
  );
};

const Guests: React.FC = () => {
  const [rows, setRows] = useState<Guest[] | null>(null);
  const [q, setQ] = useState('');
  const load = useCallback(() => {
    restaurantApi.listGuests(q ? { search: q } : undefined).then(setRows).catch(() => setRows([]));
  }, [q]);
  useEffect(() => { const t = setTimeout(load, 250); return () => clearTimeout(t); }, [load]);
  return (
    <div>
      <input style={S.input} placeholder="Search name or phone…" value={q} onChange={(e) => setQ(e.target.value)} />
      {!rows ? <p style={S.muted}>Loading…</p> : rows.length === 0 ? <Empty text="No guests yet. Share a table QR to start capturing." /> : (
        <div style={S.tableWrap}>
          <table style={S.table}>
            <thead><tr>{['Guest', 'WhatsApp', 'Visits', 'Birthday', 'Consent', 'Status', 'Last visit'].map((h) => <th key={h} style={S.th}>{h}</th>)}</tr></thead>
            <tbody>
              {rows.map((g) => (
                <tr key={g.id}>
                  <td style={S.td}><b>{g.name}</b>{g.email && <div style={S.sub}>{g.email}</div>}</td>
                  <td style={S.td}>{g.phone}</td>
                  <td style={S.td}>{g.visit_count}</td>
                  <td style={S.td}>{g.dob ? new Date(g.dob).toLocaleDateString(undefined, { day: 'numeric', month: 'short' }) : '—'}</td>
                  <td style={S.td}>{g.marketing_consent ? <Pill c={GREEN}>Consented</Pill> : <Pill c="#94a3b8">No</Pill>}</td>
                  <td style={S.td}>{g.status === 'active' ? <Pill c={GREEN}>Active</Pill> : <Pill c="#f87171">{g.status === 'opted_out' ? 'Opted out' : g.status}</Pill>}</td>
                  <td style={S.td}>{g.last_visit_at ? new Date(g.last_visit_at).toLocaleDateString() : '—'}{g.last_table_label ? ` · ${g.last_table_label}` : ''}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

const Offers: React.FC<{ venueId: string }> = ({ venueId }) => {
  const [rows, setRows] = useState<Offer[] | null>(null);
  const [form, setForm] = useState({ title: '', description: '', terms: '', voucher_validity_days: 30, per_guest_limit: 1 });
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const load = useCallback(() => { restaurantApi.listOffers(venueId).then(setRows).catch(() => setRows([])); }, [venueId]);
  useEffect(() => { load(); }, [load]);
  const create = async (e: React.FormEvent) => {
    e.preventDefault(); if (!form.title.trim()) return;
    setBusy(true); setMsg(null);
    try {
      await restaurantApi.createOffer({ venue_id: venueId, ...form });
      setForm({ title: '', description: '', terms: '', voucher_validity_days: 30, per_guest_limit: 1 });
      setMsg('Offer created.'); load();
    } catch (err: any) { setMsg(err?.response?.data?.detail || 'Failed to create offer.'); }
    finally { setBusy(false); }
  };
  return (
    <div style={S.split}>
      <div style={{ flex: 2, minWidth: 260 }}>
        {!rows ? <p style={S.muted}>Loading…</p> : rows.length === 0 ? <Empty text="No offers yet — create one on the right." /> :
          rows.map((o) => (
            <div key={o.id} style={S.rowCard}>
              <div style={{ flex: 1 }}>
                <b>{o.title}</b> {o.is_active ? <Pill c={GREEN}>Active</Pill> : <Pill c="#94a3b8">Off</Pill>}
                {o.description && <div style={S.sub}>{o.description}</div>}
                {o.terms && <div style={S.fine}>{o.terms}</div>}
              </div>
              <div style={{ textAlign: 'right' }}>
                <div style={S.sub}>Issued <b>{o.issued_count}</b></div>
                <div style={S.sub}>Redeemed <b style={{ color: GREEN }}>{o.redeemed_count}</b></div>
              </div>
            </div>
          ))}
      </div>
      <form onSubmit={create} style={{ flex: 1, minWidth: 240 }}>
        <div style={S.card}>
          <p style={S.formTitle}>New offer</p>
          <input style={S.input} placeholder="Title *" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
          <input style={S.input} placeholder="Description" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
          <input style={S.input} placeholder="Terms (e.g. Min order ₹800)" value={form.terms} onChange={(e) => setForm({ ...form, terms: e.target.value })} />
          <div style={{ display: 'flex', gap: 8 }}>
            <input style={S.input} type="number" min={1} placeholder="Valid days" value={form.voucher_validity_days} onChange={(e) => setForm({ ...form, voucher_validity_days: +e.target.value })} />
            <input style={S.input} type="number" min={1} placeholder="Per guest" value={form.per_guest_limit} onChange={(e) => setForm({ ...form, per_guest_limit: +e.target.value })} />
          </div>
          <button style={S.primary} disabled={busy}>{busy ? 'Creating…' : 'Create offer'}</button>
          {msg && <p style={S.fine}>{msg}</p>}
        </div>
      </form>
    </div>
  );
};

const Tables: React.FC<{ venueId: string }> = ({ venueId }) => {
  const [rows, setRows] = useState<Table[] | null>(null);
  const [label, setLabel] = useState('');
  const [bulk, setBulk] = useState({ prefix: 'T-', start: 1, count: 10 });
  const [qr, setQr] = useState<{ url: string; label: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const load = useCallback(() => { restaurantApi.listTables(venueId).then(setRows).catch(() => setRows([])); }, [venueId]);
  useEffect(() => { load(); }, [load]);

  const addOne = async () => { if (!label.trim()) return; setBusy(true); try { await restaurantApi.createTable({ venue_id: venueId, label: label.trim() }); setLabel(''); load(); } finally { setBusy(false); } };
  const addBulk = async () => { setBusy(true); try { await restaurantApi.bulkCreateTables({ venue_id: venueId, ...bulk }); load(); } finally { setBusy(false); } };
  const showQr = async (t: Table) => { const url = await restaurantApi.qrBlobUrl(t.id); setQr({ url, label: t.label }); };
  const printAll = async () => {
    if (!rows || !rows.length) return;
    const w = window.open('', '_blank'); if (!w) return;
    w.document.write('<title>Table QR Stands</title><style>body{font-family:sans-serif;margin:0}.g{display:flex;flex-wrap:wrap;gap:16px;padding:16px}.c{width:260px;text-align:center;border:1px solid #ddd;border-radius:12px;padding:16px;page-break-inside:avoid}.c img{width:220px}.c h3{margin:8px 0 0}</style><div class="g" id="g"></div>');
    for (const t of rows) {
      const url = await restaurantApi.qrBlobUrl(t.id);
      const el = w.document.createElement('div'); el.className = 'c';
      el.innerHTML = `<img src="${url}"/><h3>${t.label}</h3><p>Scan for your complimentary treat</p>`;
      w.document.getElementById('g')?.appendChild(el);
    }
    setTimeout(() => w.print(), 600);
  };

  return (
    <div>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 14 }}>
        <input style={{ ...S.input, maxWidth: 160, margin: 0 }} placeholder="Label e.g. T-05" value={label} onChange={(e) => setLabel(e.target.value)} />
        <button style={S.secondary} onClick={addOne} disabled={busy}>Add table</button>
        <span style={{ flex: 1 }} />
        <button style={S.secondary} onClick={printAll} disabled={!rows?.length}>🖨 Print all QR</button>
      </div>
      <div style={{ ...S.card, marginBottom: 14, display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
        <span style={S.fine}>Bulk add:</span>
        <input style={{ ...S.input, maxWidth: 90, margin: 0 }} value={bulk.prefix} onChange={(e) => setBulk({ ...bulk, prefix: e.target.value })} />
        <input style={{ ...S.input, maxWidth: 80, margin: 0 }} type="number" value={bulk.start} onChange={(e) => setBulk({ ...bulk, start: +e.target.value })} />
        <span style={S.fine}>×</span>
        <input style={{ ...S.input, maxWidth: 80, margin: 0 }} type="number" value={bulk.count} onChange={(e) => setBulk({ ...bulk, count: +e.target.value })} />
        <button style={S.secondary} onClick={addBulk} disabled={busy}>Generate</button>
      </div>

      {!rows ? <p style={S.muted}>Loading…</p> : rows.length === 0 ? <Empty text="No tables yet. Add one or bulk-generate above." /> : (
        <div style={S.grid}>
          {rows.map((t) => (
            <div key={t.id} style={S.stat}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <b style={{ fontSize: 18 }}>{t.label}</b>
                <Pill c={t.is_active ? GREEN : '#94a3b8'}>{t.is_active ? 'Active' : 'Off'}</Pill>
              </div>
              <p style={S.fine}>{t.scan_count} scans</p>
              <button style={{ ...S.secondary, marginTop: 8 }} onClick={() => showQr(t)}>View QR</button>
            </div>
          ))}
        </div>
      )}

      {qr && (
        <div style={S.modalBg} onClick={() => setQr(null)}>
          <div style={S.modal} onClick={(e) => e.stopPropagation()}>
            <p style={S.formTitle}>Table {qr.label}</p>
            <img src={qr.url} alt="QR" style={{ width: 260, borderRadius: 12, background: '#fff', padding: 8 }} />
            <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
              <a href={qr.url} download={`qr-${qr.label}.png`} style={{ ...S.primary, textAlign: 'center', textDecoration: 'none' }}>Download</a>
              <button style={S.secondary} onClick={() => setQr(null)}>Close</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

const Vouchers: React.FC = () => {
  const [rows, setRows] = useState<Voucher[] | null>(null);
  const [status, setStatus] = useState('');
  useEffect(() => { restaurantApi.listVouchers(status ? { status } : undefined).then(setRows).catch(() => setRows([])); }, [status]);
  return (
    <div>
      <select style={S.select} value={status} onChange={(e) => setStatus(e.target.value)}>
        <option value="">All statuses</option><option value="active">Active</option>
        <option value="redeemed">Redeemed</option><option value="expired">Expired</option>
      </select>
      {!rows ? <p style={S.muted}>Loading…</p> : rows.length === 0 ? <Empty text="No vouchers yet." /> : (
        <div style={S.tableWrap}>
          <table style={S.table}>
            <thead><tr>{['Code', 'Offer', 'Status', 'Table', 'Delivery', 'Issued'].map((h) => <th key={h} style={S.th}>{h}</th>)}</tr></thead>
            <tbody>
              {rows.map((v) => (
                <tr key={v.id}>
                  <td style={{ ...S.td, fontFamily: 'ui-monospace, monospace', color: ACCENT }}>{v.code}</td>
                  <td style={S.td}>{v.offer_title}</td>
                  <td style={S.td}>{v.status === 'redeemed' ? <Pill c="#94a3b8">Redeemed</Pill> : v.status === 'active' ? <Pill c={GREEN}>Active</Pill> : <Pill c="#fbbf24">{v.status}</Pill>}</td>
                  <td style={S.td}>{v.redeemed_table_label || v.issued_table_label || '—'}</td>
                  <td style={S.td}>{v.delivery_status}</td>
                  <td style={S.td}>{new Date(v.created_at).toLocaleDateString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

const Campaigns: React.FC<{ venueId: string }> = ({ venueId }) => {
  const [preview, setPreview] = useState<CampaignPreview | null>(null);
  const [title, setTitle] = useState('Weekend Special');
  const [message, setMessage] = useState("Hi {name}! This weekend, enjoy a complimentary dessert on us. Book your table today — see you soon!");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<CampaignResult | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const loadPreview = useCallback(() => {
    restaurantApi.campaignPreview(venueId).then(setPreview).catch(() => setPreview(null));
  }, [venueId]);
  useEffect(() => { loadPreview(); }, [loadPreview]);

  const send = async () => {
    if (message.trim().length < 3) { setErr('Write a message first.'); return; }
    setBusy(true); setErr(null); setResult(null);
    try {
      const res = await restaurantApi.sendCampaign({ message: message.trim(), title: title.trim() || undefined, venue_id: venueId });
      setResult(res); loadPreview();
    } catch (e: any) { setErr(e?.response?.data?.detail || 'Failed to send campaign.'); }
    finally { setBusy(false); }
  };

  return (
    <div style={S.split}>
      <div style={{ flex: 2, minWidth: 280 }}>
        <div style={S.card}>
          <p style={S.formTitle}>Compose WhatsApp campaign</p>
          <input style={S.input} placeholder="Campaign title (internal)" value={title} onChange={(e) => setTitle(e.target.value)} />
          <textarea style={{ ...S.input, minHeight: 140, resize: 'vertical', fontFamily: 'inherit' }}
            value={message} onChange={(e) => setMessage(e.target.value)} />
          <p style={S.fine}>Tip: use <b>{'{name}'}</b> to personalize with each guest's first name. A "Reply STOP to opt out" line is added automatically.</p>
          {err && <p style={S.warn}>{err}</p>}
          <button style={{ ...S.primary, marginTop: 10 }} onClick={send} disabled={busy || !preview?.recipients}>
            {busy ? 'Sending…' : preview ? `Send to ${preview.recipients} opted-in guest${preview.recipients === 1 ? '' : 's'}` : 'Send campaign'}
          </button>
        </div>

        {result && (
          <div style={{ ...S.card, marginTop: 12, borderColor: `${GREEN}55` }}>
            <p style={{ ...S.formTitle, color: GREEN, margin: '0 0 8px' }}>✓ Campaign sent</p>
            <p style={S.sub}>Reached <b>{result.recipients}</b> guests · {result.queued} queued
              {result.simulated > 0 && ` · ${result.simulated} simulated`} · channel: {result.channel}</p>
            <p style={S.fine}>Estimated Meta fee: ₹{result.est_cost.toFixed(2)}</p>
          </div>
        )}
      </div>

      <div style={{ flex: 1, minWidth: 220 }}>
        <div style={S.card}>
          <p style={S.formTitle}>Audience</p>
          {!preview ? <p style={S.muted}>Loading…</p> : (
            <>
              <p style={{ ...S.statVal, color: ACCENT, fontSize: 34, margin: '4px 0' }}>{preview.recipients}</p>
              <p style={S.sub}>opted-in guests will receive this</p>
              <div style={{ borderTop: '1px solid #1f2937', margin: '12px 0', paddingTop: 12 }}>
                <p style={S.sub}>Est. Meta fee: <b>₹{preview.est_cost.toFixed(2)}</b></p>
                <p style={S.fine}>@ ₹{preview.cost_per_msg.toFixed(2)}/message</p>
                <p style={S.fine}>{preview.suppressed_opted_out} opted-out guests are auto-suppressed.</p>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
};

// ============================= bits =============================

const CreateVenue: React.FC<{ onCreated: (v: Venue) => void }> = ({ onCreated }) => {
  const [name, setName] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const create = async () => {
    if (!name.trim()) return; setBusy(true); setErr(null);
    try { onCreated(await restaurantApi.createVenue({ name: name.trim() })); }
    catch (e: any) { setErr(e?.response?.data?.detail || 'Failed to create venue.'); setBusy(false); }
  };
  return (
    <div style={S.card}>
      <p style={S.formTitle}>Create your first venue</p>
      <input style={S.input} placeholder="Restaurant / branch name" value={name} onChange={(e) => setName(e.target.value)} />
      <button style={S.primary} onClick={create} disabled={busy}>{busy ? 'Creating…' : 'Create venue'}</button>
      {err && <p style={S.warn}>{err}</p>}
    </div>
  );
};

const Shell: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <div style={S.page}><div style={S.container}>{children}</div></div>
);
const Pill: React.FC<{ c: string; children: React.ReactNode }> = ({ c, children }) => (
  <span style={{ background: `${c}22`, color: c, border: `1px solid ${c}55`, borderRadius: 16, padding: '2px 10px', fontSize: 12, fontWeight: 700 }}>{children}</span>
);
const Empty: React.FC<{ text: string }> = ({ text }) => <div style={{ ...S.card, textAlign: 'center' }}><p style={S.muted}>{text}</p></div>;

const S: Record<string, React.CSSProperties> = {
  page: { minHeight: '100vh', background: 'radial-gradient(120% 60% at 50% 0%, #101828 0%, #080b14 55%)', color: '#e5e7eb', fontFamily: 'system-ui, -apple-system, sans-serif', padding: '20px 16px 40px' },
  container: { maxWidth: 980, margin: '0 auto' },
  topbar: { display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12, flexWrap: 'wrap', marginBottom: 16 },
  kicker: { color: ACCENT, fontSize: 11, fontWeight: 700, letterSpacing: '.08em', textTransform: 'uppercase', margin: 0 },
  h1: { fontSize: 26, fontWeight: 800, margin: '2px 0 0' },
  linkBtn: { background: '#111827', border: '1px solid #293244', color: '#e5e7eb', borderRadius: 10, padding: '9px 14px', fontWeight: 700, textDecoration: 'none', fontSize: 14 },
  select: { background: '#0b1220', border: '1px solid #293244', color: '#e5e7eb', borderRadius: 10, padding: '9px 12px', fontSize: 14 },
  tabs: { display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 18, borderBottom: '1px solid #1f2937', paddingBottom: 10 },
  tab: { textTransform: 'capitalize', background: 'transparent', border: '1px solid #293244', color: '#94a3b8', borderRadius: 20, padding: '8px 16px', fontWeight: 700, fontSize: 14, cursor: 'pointer' },
  tabActive: { background: ACCENT, color: '#0a0c14', border: `1px solid ${ACCENT}` },
  grid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(150px, 1fr))', gap: 12 },
  stat: { background: 'rgba(17,24,39,.7)', border: '1px solid #1f2937', borderRadius: 16, padding: 16 },
  statLabel: { color: '#94a3b8', fontSize: 12, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '.04em', margin: 0 },
  statVal: { fontSize: 30, fontWeight: 800, margin: '6px 0 2px' },
  statSub: { color: '#64748b', fontSize: 12, margin: 0 },
  card: { background: 'rgba(17,24,39,.7)', border: '1px solid #1f2937', borderRadius: 16, padding: 18 },
  rowCard: { display: 'flex', gap: 12, background: 'rgba(17,24,39,.7)', border: '1px solid #1f2937', borderRadius: 14, padding: 14, marginBottom: 10 },
  split: { display: 'flex', gap: 16, flexWrap: 'wrap', alignItems: 'flex-start' },
  input: { width: '100%', boxSizing: 'border-box', padding: '11px 13px', borderRadius: 10, background: '#0b1220', border: '1px solid #293244', color: '#e5e7eb', fontSize: 15, outline: 'none', marginBottom: 10 },
  primary: { width: '100%', padding: '12px', borderRadius: 10, border: 'none', background: ACCENT, color: '#0a0c14', fontWeight: 800, fontSize: 15, cursor: 'pointer' },
  secondary: { padding: '10px 14px', borderRadius: 10, border: '1px solid #334155', background: '#111827', color: '#e5e7eb', fontWeight: 700, fontSize: 14, cursor: 'pointer' },
  formTitle: { fontSize: 15, fontWeight: 800, margin: '0 0 12px' },
  tableWrap: { overflowX: 'auto', border: '1px solid #1f2937', borderRadius: 14, marginTop: 12 },
  table: { width: '100%', borderCollapse: 'collapse', fontSize: 14, minWidth: 640 },
  th: { textAlign: 'left', padding: '12px 14px', color: '#94a3b8', fontSize: 11, textTransform: 'uppercase', letterSpacing: '.05em', borderBottom: '1px solid #1f2937', whiteSpace: 'nowrap' },
  td: { padding: '12px 14px', borderBottom: '1px solid #131b2b', verticalAlign: 'top' },
  sub: { color: '#94a3b8', fontSize: 12 },
  fine: { color: '#64748b', fontSize: 12 },
  muted: { color: '#94a3b8', fontSize: 14 },
  warn: { color: '#fca5a5', fontSize: 14 },
  modalBg: { position: 'fixed', inset: 0, background: 'rgba(0,0,0,.7)', display: 'grid', placeItems: 'center', padding: 20, zIndex: 50 },
  modal: { background: '#0b1220', border: '1px solid #293244', borderRadius: 18, padding: 22, textAlign: 'center', maxWidth: 340 },
};
