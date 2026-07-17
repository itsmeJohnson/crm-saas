import React, { useCallback, useEffect, useState } from 'react';
import {
  CalendarClock, Loader2, Plus, X, Check, Pencil, Trash2, Play, RotateCcw,
  LayoutDashboard, ListChecks, History as HistoryIcon, Mail, MessageCircle, Bell, CheckCircle2, AlertTriangle,
} from 'lucide-react';
import { scheduledReportsApi as api, SchedMeta, ReportSchedule, DeliveryLog, SchedDashboard } from '../services/scheduledReportsApi';
import { reportBuilderApi } from '../services/reportBuilderApi';
import { userApi } from '../services/userApi';
import { extractErrorMessage } from '../utils/errors';

const F = 'w-full bg-slate-800/70 border border-slate-700/70 text-slate-200 py-1.5 px-2 rounded-lg text-xs';
const card = 'glass-panel border border-slate-800/85 rounded-xl p-4';
const CHANNEL_ICON: Record<string, any> = { email: Mail, whatsapp: MessageCircle, notification: Bell };
const STATUS_TONE: Record<string, string> = { success: 'text-emerald-400', partial: 'text-amber-400', failed: 'text-red-400', pending: 'text-slate-400' };

export const ScheduledReportsPage: React.FC = () => {
  const [tab, setTab] = useState<'dashboard' | 'schedules' | 'history'>('dashboard');
  const [meta, setMeta] = useState<SchedMeta | null>(null);
  const [dash, setDash] = useState<SchedDashboard | null>(null);
  const [rows, setRows] = useState<ReportSchedule[]>([]);
  const [logs, setLogs] = useState<DeliveryLog[]>([]);
  const [reports, setReports] = useState<any[]>([]);
  const [users, setUsers] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState('');
  const [msg, setMsg] = useState('');
  const [edit, setEdit] = useState<any | null>(null);
  const flash = (m: string) => { setMsg(m); setTimeout(() => setMsg(''), 2500); };

  useEffect(() => {
    reportBuilderApi.list({}).then(setReports).catch(() => {});
    userApi.getUsers({ is_active: true, limit: 200 }).then(setUsers).catch(() => {});
  }, []);

  const load = useCallback(async () => {
    setLoading(true); setErr('');
    try {
      if (!meta) setMeta(await api.meta());
      if (tab === 'dashboard') setDash(await api.dashboard());
      else if (tab === 'schedules') setRows(await api.list());
      else setLogs(await api.history({ limit: 100 }));
    } catch (e) { setErr(extractErrorMessage(e, 'Failed to load scheduled reports.')); } finally { setLoading(false); }
  }, [tab, meta]);
  useEffect(() => { load(); }, [load]);

  const act = async (fn: () => Promise<any>, ok: string) => { try { await fn(); flash(ok); await load(); } catch (e) { setErr(extractErrorMessage(e, 'Failed')); } };

  return (
    <div className="space-y-5">
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-extrabold text-slate-100 flex items-center gap-2"><CalendarClock className="w-6 h-6 text-brand-400" /> Scheduled Reports</h1>
          <p className="text-sm text-slate-500 mt-1">Deliver your report-builder reports on a schedule — CSV, Excel or PDF over email, WhatsApp and in-app notifications.</p>
        </div>
        <button onClick={() => setEdit({ frequency: 'weekly', formats: ['csv'], channels: ['notification'], recipients: [], max_retries: 2 })} className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-brand-500/20 text-brand-300 hover:bg-brand-500/30 cursor-pointer flex items-center gap-1.5 w-fit"><Plus className="w-3.5 h-3.5" /> New schedule</button>
      </div>

      {msg && <div className="text-xs text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 rounded-lg px-3 py-2">{msg}</div>}
      {err && <div className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">{err}</div>}

      <div className="flex items-center gap-1 bg-slate-900/50 border border-slate-800/70 rounded-xl p-1 w-fit">
        {([['dashboard', 'Dashboard', LayoutDashboard], ['schedules', 'Schedules', ListChecks], ['history', 'History', HistoryIcon]] as [any, string, any][]).map(([k, l, Icon]) => (
          <button key={k} onClick={() => setTab(k)} className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 cursor-pointer ${tab === k ? 'bg-brand-500/20 text-brand-300' : 'text-slate-400 hover:text-slate-200'}`}><Icon className="w-3.5 h-3.5" /> {l}</button>
        ))}
      </div>

      {loading ? (
        <div className="py-20 text-center text-slate-400"><Loader2 className="w-6 h-6 animate-spin inline" /></div>
      ) : tab === 'dashboard' && dash ? (
        <div className="space-y-4">
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            <div className={card}><p className="text-[10px] font-semibold text-slate-500 uppercase">Schedules</p><p className="text-xl font-bold text-slate-100 mt-1">{dash.schedules}</p></div>
            <div className={card}><p className="text-[10px] font-semibold text-slate-500 uppercase">Active</p><p className="text-xl font-bold text-slate-100 mt-1">{dash.active}</p></div>
            <div className={card}><p className="text-[10px] font-semibold text-slate-500 uppercase">Deliveries</p><p className="text-xl font-bold text-slate-100 mt-1">{dash.deliveries}</p></div>
            <div className={card}><p className="text-[10px] font-semibold text-slate-500 uppercase">Success rate</p><p className="text-xl font-bold text-emerald-400 mt-1">{dash.success_rate}%</p></div>
            <div className={card}><p className="text-[10px] font-semibold text-slate-500 uppercase">Failed</p><p className="text-xl font-bold text-red-400 mt-1">{dash.by_status.failed}</p></div>
          </div>
          <div className={card}>
            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Upcoming deliveries</p>
            {dash.upcoming.length === 0 ? <p className="text-xs text-slate-500">No active schedules.</p> :
              dash.upcoming.map((s) => (
                <div key={s.id} className="flex items-center justify-between py-1.5 border-b border-slate-800/50 last:border-0 text-sm">
                  <div className="min-w-0"><span className="text-slate-200">{s.name}</span> <span className="text-[10px] text-slate-500">({s.report_name} · {s.frequency})</span></div>
                  <span className="text-[11px] text-slate-400 shrink-0">{s.next_run_at ? new Date(s.next_run_at).toLocaleString() : '—'}</span>
                </div>
              ))}
          </div>
        </div>
      ) : tab === 'schedules' ? (
        <div className="space-y-2">
          {rows.length === 0 && <p className="text-sm text-slate-500">No schedules — create one to start delivering reports.</p>}
          {rows.map((s) => (
            <div key={s.id} className="glass-panel border border-slate-800/85 rounded-xl p-4 flex items-center gap-3">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-sm font-semibold text-slate-100 truncate">{s.name}</span>
                  <span className="px-1.5 py-0.5 text-[10px] rounded bg-slate-700/40 text-slate-400 border border-slate-600/40">{s.report_name}</span>
                  <span className="px-1.5 py-0.5 text-[10px] rounded bg-brand-500/10 text-brand-300 capitalize">{s.frequency}</span>
                  {s.formats.map((fm) => <span key={fm} className="text-[10px] text-slate-400 uppercase">{fm}</span>)}
                  {s.channels.map((ch) => { const I = CHANNEL_ICON[ch] || Bell; return <I key={ch} className="w-3 h-3 text-slate-500" />; })}
                  {!s.is_active && <span className="text-[10px] text-slate-500">paused</span>}
                  {s.last_status && <span className={`text-[10px] font-semibold ${STATUS_TONE[s.last_status] || ''}`}>{s.last_status}</span>}
                </div>
                <p className="text-[11px] text-slate-500 mt-0.5">next {s.next_run_at ? new Date(s.next_run_at).toLocaleString() : '—'} · sent {s.run_count}× · {s.recipients.length + s.extra_emails.length || 1} recipient(s)</p>
              </div>
              <div className="flex items-center gap-1.5 shrink-0">
                <button title="Run now" onClick={() => act(() => api.runNow(s.id), 'Delivered.')} className="p-1.5 rounded hover:bg-slate-800 text-slate-400 hover:text-emerald-400 cursor-pointer"><Play className="w-4 h-4" /></button>
                <button title="Edit" onClick={() => setEdit({ ...s })} className="p-1.5 rounded hover:bg-slate-800 text-slate-400 hover:text-brand-300 cursor-pointer"><Pencil className="w-4 h-4" /></button>
                <button title={s.is_active ? 'Pause' : 'Resume'} onClick={() => act(() => api.update(s.id, { is_active: !s.is_active }), s.is_active ? 'Paused.' : 'Resumed.')} className="p-1.5 rounded hover:bg-slate-800 text-slate-400 hover:text-amber-300 cursor-pointer">{s.is_active ? <X className="w-4 h-4" /> : <Check className="w-4 h-4" />}</button>
                <button title="Delete" onClick={() => window.confirm(`Delete "${s.name}"?`) && act(() => api.remove(s.id), 'Deleted.')} className="p-1.5 rounded hover:bg-slate-800 text-slate-400 hover:text-red-400 cursor-pointer"><Trash2 className="w-4 h-4" /></button>
              </div>
            </div>
          ))}
        </div>
      ) : tab === 'history' ? (
        <div className="space-y-2">
          {logs.length === 0 && <p className="text-sm text-slate-500">No deliveries yet.</p>}
          {logs.map((l) => (
            <div key={l.id} className={`glass-panel border ${l.status === 'failed' ? 'border-red-500/30' : l.status === 'partial' ? 'border-amber-500/30' : 'border-slate-800/85'} rounded-xl p-3 flex items-center gap-3`}>
              {l.status === 'success' ? <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" /> : <AlertTriangle className={`w-4 h-4 ${l.status === 'failed' ? 'text-red-400' : 'text-amber-400'} shrink-0`} />}
              <div className="flex-1 min-w-0">
                <p className="text-sm text-slate-200 truncate">{l.schedule_name || '—'} <span className={`text-[10px] font-semibold ${STATUS_TONE[l.status]}`}>{l.status}</span>
                  <span className="text-[10px] text-slate-500"> · attempt {l.attempt} · {l.triggered_by} · {l.rows_count} rows · {l.recipient_count} recipient(s)</span></p>
                <p className="text-[11px] text-slate-500 truncate">{l.error || (l.detail?.artifacts || []).map((a: any) => a.filename).join(', ') || '—'}{l.finished_at ? ` · ${new Date(l.finished_at).toLocaleString()}` : ''}</p>
              </div>
              {l.status !== 'success' && (
                <button onClick={() => act(() => api.retryDelivery(l.id), 'Retried.')} className="text-xs text-brand-400 hover:text-brand-300 cursor-pointer flex items-center gap-1 shrink-0"><RotateCcw className="w-3.5 h-3.5" /> Retry</button>
              )}
            </div>
          ))}
        </div>
      ) : null}

      {edit && meta && (
        <ScheduleModal draft={edit} meta={meta} reports={reports} users={users}
                       onClose={() => setEdit(null)}
                       onSaved={async () => { setEdit(null); flash('Saved.'); await load(); }} setErr={setErr} />
      )}
    </div>
  );
};

const ScheduleModal: React.FC<{ draft: any; meta: SchedMeta; reports: any[]; users: any[]; onClose: () => void; onSaved: () => void; setErr: (s: string) => void }> =
  ({ draft, meta, reports, users, onClose, onSaved, setErr }) => {
    const [f, setF] = useState<any>(draft);
    const [busy, setBusy] = useState(false);
    const set = (patch: any) => setF({ ...f, ...patch });
    const toggle = (key: 'formats' | 'channels', v: string) => {
      const cur: string[] = f[key] || [];
      set({ [key]: cur.includes(v) ? cur.filter((x) => x !== v) : [...cur, v] });
    };
    const save = async () => {
      if (!f.name?.trim()) { setErr('Name is required'); return; }
      if (!f.id && !f.report_id) { setErr('Pick a report'); return; }
      if (!(f.formats || []).length) { setErr('Pick at least one format'); return; }
      if (!(f.channels || []).length) { setErr('Pick at least one channel'); return; }
      setBusy(true); setErr('');
      const payload: any = {
        name: f.name, frequency: f.frequency, formats: f.formats, channels: f.channels,
        recipients: f.recipients || [], max_retries: Number(f.max_retries) ?? 2,
        extra_emails: (typeof f.extra_emails === 'string'
          ? f.extra_emails.split(',').map((s: string) => s.trim()).filter(Boolean)
          : f.extra_emails) || [],
        is_active: f.is_active !== false,
      };
      try {
        if (f.id) await api.update(f.id, payload);
        else await api.create({ ...payload, report_id: f.report_id });
        onSaved();
      } catch (e) { setErr(extractErrorMessage(e, 'Save failed')); } finally { setBusy(false); }
    };
    return (
      <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4" onClick={onClose}>
        <div className="glass-panel border border-slate-800 rounded-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto p-5 bg-slate-900" onClick={(e) => e.stopPropagation()}>
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-bold text-slate-100 flex items-center gap-2"><CalendarClock className="w-4 h-4 text-brand-400" /> {f.id ? 'Edit' : 'New'} schedule</h3>
            <button onClick={onClose} className="text-slate-500 hover:text-slate-300 cursor-pointer"><X className="w-4 h-4" /></button>
          </div>
          <div className="space-y-2">
            <input value={f.name || ''} onChange={(e) => set({ name: e.target.value })} placeholder="Schedule name" className={F} />
            {!f.id && (
              <label className="text-[11px] text-slate-400 block">Report
                <select value={f.report_id || ''} onChange={(e) => set({ report_id: e.target.value })} className={F}>
                  <option value="">Select a report…</option>
                  {reports.map((r) => <option key={r.id} value={r.id}>{r.name} ({r.dataset})</option>)}
                </select>
              </label>
            )}
            <label className="text-[11px] text-slate-400 block">Frequency
              <select value={f.frequency} onChange={(e) => set({ frequency: e.target.value })} className={F}>
                {meta.frequencies.map((fr) => <option key={fr} value={fr}>{fr}</option>)}
              </select>
            </label>
            <div>
              <p className="text-[11px] text-slate-400 mb-1">Formats</p>
              <div className="flex items-center gap-3">
                {meta.formats.map((fm) => (
                  <label key={fm} className="flex items-center gap-1.5 text-xs text-slate-300 uppercase">
                    <input type="checkbox" checked={(f.formats || []).includes(fm)} onChange={() => toggle('formats', fm)} /> {fm}
                  </label>
                ))}
              </div>
            </div>
            <div>
              <p className="text-[11px] text-slate-400 mb-1">Channels</p>
              <div className="flex items-center gap-3">
                {meta.channels.map((ch) => {
                  const I = CHANNEL_ICON[ch] || Bell;
                  return (
                    <label key={ch} className="flex items-center gap-1.5 text-xs text-slate-300 capitalize">
                      <input type="checkbox" checked={(f.channels || []).includes(ch)} onChange={() => toggle('channels', ch)} /> <I className="w-3 h-3" /> {ch}
                    </label>
                  );
                })}
              </div>
            </div>
            <label className="text-[11px] text-slate-400 block">Recipients (defaults to you)
              <select multiple value={f.recipients || []} onChange={(e) => set({ recipients: Array.from(e.target.selectedOptions).map((o) => o.value) })} className={`${F} h-24`}>
                {users.map((u) => <option key={u.id} value={u.id}>{u.first_name} {u.last_name} ({u.role})</option>)}
              </select>
            </label>
            <label className="text-[11px] text-slate-400 block">Extra emails (comma-separated)
              <input value={Array.isArray(f.extra_emails) ? f.extra_emails.join(', ') : f.extra_emails || ''} onChange={(e) => set({ extra_emails: e.target.value })} placeholder="boss@example.com" className={F} />
            </label>
            <label className="text-[11px] text-slate-400 block w-32">Max retries
              <input type="number" min={0} max={5} value={f.max_retries ?? 2} onChange={(e) => set({ max_retries: e.target.value })} className={F} />
            </label>
            <button onClick={save} disabled={busy} className="w-full inline-flex items-center justify-center gap-2 bg-brand-500/20 text-brand-300 hover:bg-brand-500/30 font-medium py-2 rounded-lg text-sm cursor-pointer mt-2">{busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />} Save</button>
          </div>
        </div>
      </div>
    );
  };
