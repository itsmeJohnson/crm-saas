import React, { useCallback, useEffect, useState } from 'react';
import {
  ShieldCheck, Loader2, Download, LayoutDashboard, ScrollText, KeyRound, FileCheck2,
  AlertTriangle, CheckCircle2, XCircle,
} from 'lucide-react';
import {
  complianceApi as api, ComplianceCategory, ComplianceDashboard, ComplianceReport, AuditRow, LoginRow,
} from '../services/complianceApi';
import { extractErrorMessage } from '../utils/errors';

const F = 'w-full bg-slate-800/70 border border-slate-700/70 text-slate-200 py-1.5 px-2 rounded-lg text-xs';
const card = 'glass-panel border border-slate-800/85 rounded-xl p-4';

const CAT_TONE: Record<string, string> = {
  login: 'bg-sky-500/10 text-sky-300', permission: 'bg-red-500/10 text-red-300',
  workflow: 'bg-purple-500/10 text-purple-300', configuration: 'bg-amber-500/10 text-amber-300',
  financial: 'bg-emerald-500/10 text-emerald-300', communication: 'bg-cyan-500/10 text-cyan-300',
  export: 'bg-orange-500/10 text-orange-300', approval: 'bg-lime-500/10 text-lime-300',
  activity: 'bg-slate-700/40 text-slate-400',
};

const downloadText = (name: string, text: string) => {
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([text], { type: 'text/csv' }));
  a.download = name;
  a.click();
  URL.revokeObjectURL(a.href);
};

export const CompliancePage: React.FC = () => {
  const [tab, setTab] = useState<'dashboard' | 'trail' | 'logins' | 'report'>('dashboard');
  const [cats, setCats] = useState<ComplianceCategory[]>([]);
  const [dash, setDash] = useState<ComplianceDashboard | null>(null);
  const [rows, setRows] = useState<AuditRow[]>([]);
  const [total, setTotal] = useState(0);
  const [logins, setLogins] = useState<LoginRow[]>([]);
  const [report, setReport] = useState<ComplianceReport | null>(null);
  const [category, setCategory] = useState('');
  const [q, setQ] = useState('');
  const [days, setDays] = useState(30);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState('');

  const load = useCallback(async () => {
    setLoading(true); setErr('');
    try {
      if (cats.length === 0) setCats((await api.meta()).categories);
      if (tab === 'dashboard') setDash(await api.dashboard());
      else if (tab === 'trail') {
        const res = await api.logs({ category: category || undefined, q: q || undefined, days, limit: 100 });
        setRows(res.rows); setTotal(res.total);
      } else if (tab === 'logins') setLogins(await api.loginHistory({ days }));
      else setReport(await api.report(days));
    } catch (e) { setErr(extractErrorMessage(e, 'Failed to load audit data.')); } finally { setLoading(false); }
  }, [tab, cats.length, category, q, days]);
  useEffect(() => { load(); }, [load]);

  return (
    <div className="space-y-5">
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-extrabold text-slate-100 flex items-center gap-2"><ShieldCheck className="w-6 h-6 text-brand-400" /> Audit & Compliance</h1>
          <p className="text-sm text-slate-500 mt-1">The org-wide audit trail — logins, permission & configuration changes, workflows, financials, communications, exports and approvals.</p>
        </div>
        <div className="flex items-center gap-2">
          <select value={days} onChange={(e) => setDays(Number(e.target.value))} className={`${F} !w-32`}>
            {[7, 30, 90, 180, 365].map((d) => <option key={d} value={d}>{d} days</option>)}
          </select>
          <button onClick={async () => { try { downloadText('audit-trail.csv', await api.exportCsv({ category: category || undefined, days })); } catch (e) { setErr(extractErrorMessage(e, 'Export failed')); } }} className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-brand-500/20 text-brand-300 hover:bg-brand-500/30 cursor-pointer flex items-center gap-1.5"><Download className="w-3.5 h-3.5" /> Export CSV</button>
        </div>
      </div>

      {err && <div className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">{err}</div>}

      <div className="flex items-center gap-1 bg-slate-900/50 border border-slate-800/70 rounded-xl p-1 w-fit flex-wrap">
        {([['dashboard', 'Dashboard', LayoutDashboard], ['trail', 'Audit Trail', ScrollText], ['logins', 'Login History', KeyRound], ['report', 'Compliance Report', FileCheck2]] as [any, string, any][]).map(([k, l, Icon]) => (
          <button key={k} onClick={() => setTab(k)} className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 cursor-pointer ${tab === k ? 'bg-brand-500/20 text-brand-300' : 'text-slate-400 hover:text-slate-200'}`}><Icon className="w-3.5 h-3.5" /> {l}</button>
        ))}
      </div>

      {loading ? (
        <div className="py-20 text-center text-slate-400"><Loader2 className="w-6 h-6 animate-spin inline" /></div>
      ) : tab === 'dashboard' && dash ? (
        <div className="space-y-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className={card}><p className="text-[10px] font-semibold text-slate-500 uppercase">Events (24h)</p><p className="text-xl font-bold text-slate-100 mt-1">{dash.counts.last_24h}</p></div>
            <div className={card}><p className="text-[10px] font-semibold text-slate-500 uppercase">Events (7d)</p><p className="text-xl font-bold text-slate-100 mt-1">{dash.counts.last_7d}</p></div>
            <div className={card}><p className="text-[10px] font-semibold text-slate-500 uppercase">Events (30d)</p><p className="text-xl font-bold text-slate-100 mt-1">{dash.counts.last_30d}</p></div>
            <div className={card}><p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><AlertTriangle className="w-3 h-3 text-red-400" /> Failed logins (30d)</p><p className="text-xl font-bold text-red-400 mt-1">{dash.failed_logins_30d}</p></div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div className={card}>
              <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">By category (30d)</p>
              {dash.by_category.filter((c) => c.count > 0).map((c) => (
                <div key={c.key} className="flex items-center justify-between py-1 text-sm">
                  <span className={`px-1.5 py-0.5 text-[10px] rounded ${CAT_TONE[c.key]}`}>{c.label}</span>
                  <span className="text-slate-100 font-semibold">{c.count}</span>
                </div>
              ))}
            </div>
            <div className={card}>
              <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Most active users (30d)</p>
              {dash.top_actors.map((a) => (
                <div key={a.user_id} className="flex items-center justify-between py-1 text-sm">
                  <span className="text-slate-300 truncate">{a.name}</span>
                  <span className="text-slate-100 font-semibold">{a.events}</span>
                </div>
              ))}
              {dash.top_actors.length === 0 && <p className="text-xs text-slate-500">No activity yet.</p>}
            </div>
            <div className={card}>
              <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Recent sensitive events</p>
              {dash.recent_sensitive.map((r) => (
                <div key={r.id} className="py-1 border-b border-slate-800/50 last:border-0">
                  <p className="text-[11px] text-slate-200 truncate">{r.action} <span className={`px-1 py-0.5 text-[9px] rounded ${CAT_TONE[r.category]}`}>{r.category}</span></p>
                  <p className="text-[10px] text-slate-500">{r.actor_name}{r.created_at ? ` · ${new Date(r.created_at).toLocaleString()}` : ''}</p>
                </div>
              ))}
              {dash.recent_sensitive.length === 0 && <p className="text-xs text-slate-500">Nothing sensitive lately.</p>}
            </div>
          </div>
        </div>
      ) : tab === 'trail' ? (
        <div className="space-y-3">
          <div className="flex items-center gap-2 flex-wrap">
            <select value={category} onChange={(e) => setCategory(e.target.value)} className={`${F} !w-56`}>
              <option value="">All categories</option>
              {cats.map((c) => <option key={c.key} value={c.key}>{c.label}</option>)}
            </select>
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search action / resource / details…" className={`${F} !w-72`} />
            <span className="text-[11px] text-slate-500">{total} event(s)</span>
          </div>
          <div className={card}>
            <div className="overflow-x-auto">
              <table className="w-full text-[11px]">
                <thead><tr className="text-slate-400 border-b border-slate-800"><th className="text-left py-1.5 px-2">When</th><th className="text-left py-1.5 px-2">Category</th><th className="text-left py-1.5 px-2">Action</th><th className="text-left py-1.5 px-2">Actor</th><th className="text-left py-1.5 px-2">Resource</th><th className="text-left py-1.5 px-2">Details</th></tr></thead>
                <tbody>
                  {rows.map((r) => (
                    <tr key={r.id} className="border-b border-slate-800/50">
                      <td className="py-1 px-2 text-slate-400 whitespace-nowrap">{r.created_at ? new Date(r.created_at).toLocaleString() : '—'}</td>
                      <td className="py-1 px-2"><span className={`px-1.5 py-0.5 text-[10px] rounded ${CAT_TONE[r.category]}`}>{r.category}</span></td>
                      <td className="py-1 px-2 text-slate-200 whitespace-nowrap">{r.action}</td>
                      <td className="py-1 px-2 text-slate-300 whitespace-nowrap">{r.actor_name}</td>
                      <td className="py-1 px-2 text-slate-400">{r.resource_type}</td>
                      <td className="py-1 px-2 text-slate-500 max-w-[280px] truncate">{r.metadata ? JSON.stringify(r.metadata) : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {rows.length === 0 && <p className="text-sm text-slate-500 py-8 text-center">No audit events match.</p>}
            </div>
          </div>
        </div>
      ) : tab === 'logins' ? (
        <div className={card}>
          <div className="overflow-x-auto">
            <table className="w-full text-[11px]">
              <thead><tr className="text-slate-400 border-b border-slate-800"><th className="text-left py-1.5 px-2">When</th><th className="text-left py-1.5 px-2">Event</th><th className="text-left py-1.5 px-2">User</th><th className="text-left py-1.5 px-2">IP</th><th className="text-left py-1.5 px-2">Browser / details</th></tr></thead>
              <tbody>
                {logins.map((l) => (
                  <tr key={l.id} className="border-b border-slate-800/50">
                    <td className="py-1 px-2 text-slate-400 whitespace-nowrap">{l.created_at ? new Date(l.created_at).toLocaleString() : '—'}</td>
                    <td className="py-1 px-2 whitespace-nowrap">
                      {l.success ? <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 inline mr-1" /> : <XCircle className="w-3.5 h-3.5 text-red-400 inline mr-1" />}
                      <span className={l.success ? 'text-slate-200' : 'text-red-300'}>{l.event.replace('AUTH_', '')}</span>
                    </td>
                    <td className="py-1 px-2 text-slate-300">{l.user_name}</td>
                    <td className="py-1 px-2 text-slate-400">{l.ip_address || '—'}</td>
                    <td className="py-1 px-2 text-slate-500 max-w-[320px] truncate">{l.browser || l.description || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {logins.length === 0 && <p className="text-sm text-slate-500 py-8 text-center">No login events in this window.</p>}
          </div>
        </div>
      ) : tab === 'report' && report ? (
        <div className="space-y-4">
          <div className={card}>
            <p className="text-sm font-semibold text-slate-100">Compliance report — last {report.days} days</p>
            <p className="text-[11px] text-slate-500">Generated {new Date(report.generated_at).toLocaleString()} · window from {new Date(report.window_start).toLocaleDateString()}</p>
            <div className="grid grid-cols-3 gap-3 mt-3">
              <div><p className="text-[10px] font-semibold text-slate-500 uppercase">Total events</p><p className="text-xl font-bold text-slate-100">{report.total_events}</p></div>
              <div><p className="text-[10px] font-semibold text-slate-500 uppercase">Unique actors</p><p className="text-xl font-bold text-slate-100">{report.unique_actors}</p></div>
              <div><p className="text-[10px] font-semibold text-slate-500 uppercase">Failed logins</p><p className={`text-xl font-bold ${report.failed_logins ? 'text-red-400' : 'text-emerald-400'}`}>{report.failed_logins}</p></div>
            </div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {report.categories.filter((c) => c.count > 0).map((c) => (
              <div key={c.key} className={card}>
                <div className="flex items-center justify-between mb-1">
                  <span className={`px-1.5 py-0.5 text-[10px] rounded ${CAT_TONE[c.key]}`}>{c.label}</span>
                  <span className="text-sm font-bold text-slate-100">{c.count}</span>
                </div>
                {c.top_actions.map((a) => (
                  <div key={a.action} className="flex items-center justify-between text-[11px] py-0.5">
                    <span className="text-slate-400 truncate">{a.action}</span><span className="text-slate-300">{a.count}</span>
                  </div>
                ))}
              </div>
            ))}
          </div>
          {[['Permission changes', report.permission_changes], ['Configuration changes', report.configuration_changes], ['Data exports', report.data_exports]].map(([title, list]: any) => (
            <div key={title} className={card}>
              <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">{title} ({list.length})</p>
              {list.length === 0 ? <p className="text-xs text-slate-500">None in this window.</p> :
                list.map((r: AuditRow) => (
                  <div key={r.id} className="flex items-center gap-2 py-1 border-b border-slate-800/50 last:border-0 text-[11px]">
                    <span className="text-slate-400 w-36 shrink-0">{r.created_at ? new Date(r.created_at).toLocaleString() : '—'}</span>
                    <span className="text-slate-200">{r.action}</span>
                    <span className="text-slate-500">by {r.actor_name}</span>
                  </div>
                ))}
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
};
