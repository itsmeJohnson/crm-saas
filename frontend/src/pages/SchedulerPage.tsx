import React, { useCallback, useEffect, useState } from 'react';
import {
  CalendarClock, Loader2, X, Check, Trash2, Plus, Play, Power, Pencil, History as HistoryIcon,
  BarChart3, ListChecks, Building2, PartyPopper, Eye,
} from 'lucide-react';
import {
  schedulerApi, Schedule, ScheduleRun, SchedulerCatalog, SchedulerReport,
} from '../services/schedulerApi';
import { extractErrorMessage } from '../utils/errors';

const F = 'w-full bg-slate-800/70 border border-slate-700/70 text-slate-200 py-2 px-3 rounded-lg text-sm';
const WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

const StatusChip: React.FC<{ s: string | null }> = ({ s }) => {
  const tone = s === 'success' ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
    : s === 'failed' ? 'bg-red-500/10 text-red-400 border-red-500/20'
      : s === 'skipped' ? 'bg-amber-500/10 text-amber-400 border-amber-500/20'
        : 'bg-slate-700/40 text-slate-400 border-slate-600/40';
  return <span className={`px-1.5 py-0.5 text-[10px] font-semibold rounded-md border ${tone}`}>{s || 'never'}</span>;
};

const describe = (s: Schedule): string => {
  if (s.schedule_kind === 'cron') return `cron: ${s.cron_expr}`;
  if (s.schedule_kind === 'interval') return `every ${s.interval_minutes}m`;
  if (s.schedule_kind === 'hourly') return `hourly at :${(s.time_of_day || '00:00').slice(3)}`;
  if (s.schedule_kind === 'daily') return `daily at ${s.time_of_day || '00:00'}`;
  if (s.schedule_kind === 'weekly') return `${WEEKDAYS[s.day_of_week ?? 0]} at ${s.time_of_day || '00:00'}`;
  if (s.schedule_kind === 'monthly') return `day ${s.day_of_month ?? 1} at ${s.time_of_day || '00:00'}`;
  return s.schedule_kind;
};

type Tab = 'schedules' | 'history' | 'dashboard';

export const SchedulerPage: React.FC = () => {
  const [tab, setTab] = useState<Tab>('schedules');
  const [catalog, setCatalog] = useState<SchedulerCatalog | null>(null);
  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [runs, setRuns] = useState<ScheduleRun[]>([]);
  const [report, setReport] = useState<SchedulerReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState('');
  const [msg, setMsg] = useState('');
  const [draft, setDraft] = useState<any>(null);
  const [preview, setPreview] = useState<string[] | null>(null);

  const flash = (m: string) => { setMsg(m); setTimeout(() => setMsg(''), 2500); };
  const fail = (e: any) => setErr(extractErrorMessage(e, 'Something went wrong.'));

  const load = useCallback(async () => {
    setLoading(true);
    try { const [cat, list] = await Promise.all([schedulerApi.catalog(), schedulerApi.list()]); setCatalog(cat); setSchedules(list); }
    catch (e) { fail(e); } finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    if (tab === 'history') schedulerApi.runs({ limit: 50 }).then(setRuns).catch(() => {});
    if (tab === 'dashboard') schedulerApi.report().then(setReport).catch(() => {});
  }, [tab]);

  const act = async (fn: () => Promise<any>, ok: string) => { try { await fn(); flash(ok); await load(); } catch (e) { fail(e); } };

  const newSchedule = () => setDraft({
    name: '', task_type: catalog?.task_types[0] || 'noop', task_config: '', schedule_kind: 'daily',
    cron_expr: '0 9 * * *', time_of_day: '09:00', day_of_week: 0, day_of_month: 1, interval_minutes: 60,
    timezone: 'UTC', business_hours_only: false, skip_holidays: false, is_active: true, max_retries: 1,
  });
  const editSchedule = (s: Schedule) => setDraft({ ...s, task_config: s.task_config ? JSON.stringify(s.task_config, null, 2) : '' });

  const save = async () => {
    if (!draft?.name?.trim()) { setErr('Name is required.'); return; }
    try {
      const payload: any = { ...draft };
      payload.task_config = draft.task_config?.trim() ? JSON.parse(draft.task_config) : null;
      if (draft.id) await schedulerApi.update(draft.id, payload);
      else await schedulerApi.create(payload);
      setDraft(null); flash('Schedule saved.'); await load();
    } catch (e) { fail(e); }
  };
  const showPreview = async (s: Schedule) => {
    try { setPreview((await schedulerApi.nextRuns(s.id, 6)).next_runs); } catch (e) { fail(e); }
  };

  const Tabs = (
    <div className="flex items-center gap-1 bg-slate-900/50 border border-slate-800/70 rounded-xl p-1 w-fit">
      {([['schedules', 'Schedules', ListChecks], ['history', 'Execution History', HistoryIcon], ['dashboard', 'Dashboard', BarChart3]] as [Tab, string, any][])
        .map(([k, label, Icon]) => (
          <button key={k} onClick={() => setTab(k)}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 cursor-pointer ${tab === k ? 'bg-brand-500/20 text-brand-300' : 'text-slate-400 hover:text-slate-200'}`}>
            <Icon className="w-3.5 h-3.5" /> {label}
          </button>
        ))}
    </div>
  );

  const K = (kind: string, extra?: React.ReactNode) => draft.schedule_kind === kind && extra;

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-extrabold text-slate-100 flex items-center gap-2"><CalendarClock className="w-6 h-6 text-brand-400" /> Scheduler</h1>
          <p className="text-sm text-slate-500 mt-1">Cron & recurring jobs — timezone-aware, business-hours and holiday-aware, with retry and history.</p>
        </div>
        <button onClick={newSchedule} className="px-3 py-2 rounded-lg text-xs font-semibold bg-brand-500/20 text-brand-300 hover:bg-brand-500/30 cursor-pointer flex items-center gap-1.5"><Plus className="w-3.5 h-3.5" /> New schedule</button>
      </div>

      {Tabs}
      {msg && <div className="text-xs text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 rounded-lg px-3 py-2">{msg}</div>}
      {err && <div className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2 flex items-center justify-between"><span>{err}</span><button onClick={() => setErr('')}><X className="w-3.5 h-3.5" /></button></div>}

      {loading ? (
        <div className="py-16 text-center text-slate-400"><Loader2 className="w-6 h-6 animate-spin inline" /></div>
      ) : tab === 'schedules' ? (
        <div className="space-y-2">
          {schedules.length === 0 && <p className="text-sm text-slate-500">No schedules yet.</p>}
          {schedules.map((s) => (
            <div key={s.id} className="glass-panel border border-slate-800/85 rounded-xl p-4 flex items-center gap-4">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-sm font-semibold text-slate-100 truncate">{s.name}</span>
                  <span className="px-1.5 py-0.5 text-[10px] rounded-md bg-slate-700/40 text-slate-400 border border-slate-600/40">{s.task_type.replace(/_/g, ' ')}</span>
                  <span className="font-mono text-[10px] px-1.5 py-0.5 rounded-md bg-brand-500/10 text-brand-300 border border-brand-500/20">{describe(s)}</span>
                  {s.business_hours_only && <span title="Business hours only" className="text-[10px] text-slate-500 flex items-center gap-0.5"><Building2 className="w-3 h-3" /></span>}
                  {s.skip_holidays && <span title="Skips holidays" className="text-[10px] text-slate-500 flex items-center gap-0.5"><PartyPopper className="w-3 h-3" /></span>}
                  {!s.is_active && <span className="px-1.5 py-0.5 text-[10px] rounded-md bg-slate-700/40 text-slate-500">paused</span>}
                  <StatusChip s={s.last_status} />
                </div>
                <p className="text-[11px] text-slate-500 mt-0.5">
                  {s.timezone} · runs {s.run_count} · fails {s.fail_count} · skips {s.skip_count}
                  {s.next_run_at ? ` · next ${new Date(s.next_run_at).toLocaleString()}` : ''}
                </p>
              </div>
              <div className="flex items-center gap-1.5 shrink-0">
                <button title="Preview next runs" onClick={() => showPreview(s)} className="p-1.5 rounded-md hover:bg-slate-800 text-slate-400 hover:text-brand-300 cursor-pointer"><Eye className="w-4 h-4" /></button>
                <button title="Run now" onClick={() => act(() => schedulerApi.runNow(s.id), 'Ran.')} className="p-1.5 rounded-md hover:bg-slate-800 text-slate-400 hover:text-brand-300 cursor-pointer"><Play className="w-4 h-4" /></button>
                <button title={s.is_active ? 'Pause' : 'Resume'} onClick={() => act(() => schedulerApi.enable(s.id, !s.is_active), 'Updated.')} className={`p-1.5 rounded-md hover:bg-slate-800 cursor-pointer ${s.is_active ? 'text-emerald-400' : 'text-slate-500'}`}><Power className="w-4 h-4" /></button>
                <button title="Edit" onClick={() => editSchedule(s)} className="p-1.5 rounded-md hover:bg-slate-800 text-slate-400 hover:text-brand-300 cursor-pointer"><Pencil className="w-4 h-4" /></button>
                <button title="Delete" onClick={() => window.confirm(`Delete "${s.name}"?`) && act(() => schedulerApi.remove(s.id), 'Deleted.')} className="p-1.5 rounded-md hover:bg-slate-800 text-slate-400 hover:text-red-400 cursor-pointer"><Trash2 className="w-4 h-4" /></button>
              </div>
            </div>
          ))}
        </div>
      ) : tab === 'history' ? (
        <div className="glass-panel border border-slate-800/85 rounded-xl overflow-hidden">
          <table className="w-full text-xs">
            <thead className="bg-slate-900/60 text-slate-400"><tr>
              <th className="text-left px-4 py-2 font-semibold">Status</th>
              <th className="text-left px-4 py-2 font-semibold">Trigger</th>
              <th className="text-left px-4 py-2 font-semibold">Reason / error</th>
              <th className="text-left px-4 py-2 font-semibold">Duration</th>
              <th className="text-left px-4 py-2 font-semibold">When</th>
            </tr></thead>
            <tbody>
              {runs.length === 0 && <tr><td colSpan={5} className="px-4 py-6 text-center text-slate-500">No runs recorded yet.</td></tr>}
              {runs.map((r) => (
                <tr key={r.id} className="border-t border-slate-800/60">
                  <td className="px-4 py-2"><StatusChip s={r.status} /></td>
                  <td className="px-4 py-2 text-slate-500">{r.triggered_by}{r.attempts > 1 ? ` (×${r.attempts})` : ''}</td>
                  <td className="px-4 py-2 text-slate-400 truncate max-w-[18rem]">{r.reason || r.error || '—'}</td>
                  <td className="px-4 py-2 text-slate-500">{r.duration_ms != null ? `${r.duration_ms}ms` : '—'}</td>
                  <td className="px-4 py-2 text-slate-500">{r.started_at ? new Date(r.started_at).toLocaleString() : ''}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {report && [['Total', report.total], ['Active', report.active], ['Runs', report.runs],
            ['Success rate', `${report.success_rate}%`], ['Failed', report.failed], ['Skipped', report.skipped]].map(([k, v]) => (
            <div key={k as string} className="glass-panel border border-slate-800/85 rounded-xl p-4">
              <p className="text-[10px] font-semibold text-slate-500 uppercase">{k}</p>
              <p className="text-xl font-bold text-slate-100 mt-1">{v}</p>
            </div>
          ))}
        </div>
      )}

      {/* Editor modal */}
      {draft && catalog && (
        <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4" onClick={() => setDraft(null)}>
          <div className="glass-panel border border-slate-800 rounded-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto p-5" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-bold text-slate-100">{draft.id ? 'Edit schedule' : 'New schedule'}</h3>
              <button onClick={() => setDraft(null)} className="text-slate-500 hover:text-slate-300 cursor-pointer"><X className="w-5 h-5" /></button>
            </div>
            <div className="space-y-3">
              <input value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} placeholder="Schedule name" className={F} />
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-[11px] text-slate-500">Task type</label>
                  <select value={draft.task_type} onChange={(e) => setDraft({ ...draft, task_type: e.target.value })} className={F}>
                    {catalog.task_types.map((t) => <option key={t} value={t}>{t.replace(/_/g, ' ')}</option>)}
                  </select>
                </div>
                <div>
                  <label className="text-[11px] text-slate-500">Recurrence</label>
                  <select value={draft.schedule_kind} onChange={(e) => setDraft({ ...draft, schedule_kind: e.target.value })} className={F}>
                    {catalog.schedule_kinds.map((k) => <option key={k} value={k}>{k}</option>)}
                  </select>
                </div>
              </div>
              {K('cron', <div><label className="text-[11px] text-slate-500">Cron expression (min hour dom mon dow)</label><input value={draft.cron_expr} onChange={(e) => setDraft({ ...draft, cron_expr: e.target.value })} placeholder="0 9 * * 1-5" className={`${F} font-mono`} /></div>)}
              {K('interval', <div><label className="text-[11px] text-slate-500">Every N minutes</label><input type="number" value={draft.interval_minutes} onChange={(e) => setDraft({ ...draft, interval_minutes: parseInt(e.target.value) || 1 })} className={F} /></div>)}
              {['hourly', 'daily', 'weekly', 'monthly'].includes(draft.schedule_kind) && (
                <div className="grid grid-cols-2 gap-3">
                  <div><label className="text-[11px] text-slate-500">Time of day</label><input type="time" value={draft.time_of_day} onChange={(e) => setDraft({ ...draft, time_of_day: e.target.value })} className={F} /></div>
                  {draft.schedule_kind === 'weekly' && <div><label className="text-[11px] text-slate-500">Day of week</label><select value={draft.day_of_week} onChange={(e) => setDraft({ ...draft, day_of_week: parseInt(e.target.value) })} className={F}>{WEEKDAYS.map((d, i) => <option key={d} value={i}>{d}</option>)}</select></div>}
                  {draft.schedule_kind === 'monthly' && <div><label className="text-[11px] text-slate-500">Day of month</label><input type="number" min={1} max={31} value={draft.day_of_month} onChange={(e) => setDraft({ ...draft, day_of_month: parseInt(e.target.value) || 1 })} className={F} /></div>}
                </div>
              )}
              <div className="grid grid-cols-2 gap-3">
                <div><label className="text-[11px] text-slate-500">Timezone</label><input value={draft.timezone} onChange={(e) => setDraft({ ...draft, timezone: e.target.value })} placeholder="UTC" className={F} /></div>
                <div><label className="text-[11px] text-slate-500">Max retries</label><input type="number" value={draft.max_retries} onChange={(e) => setDraft({ ...draft, max_retries: parseInt(e.target.value) || 1 })} className={F} /></div>
              </div>
              <div className="flex items-center gap-4">
                <label className="flex items-center gap-2 text-xs text-slate-300"><input type="checkbox" checked={draft.business_hours_only} onChange={(e) => setDraft({ ...draft, business_hours_only: e.target.checked })} /> Business hours only</label>
                <label className="flex items-center gap-2 text-xs text-slate-300"><input type="checkbox" checked={draft.skip_holidays} onChange={(e) => setDraft({ ...draft, skip_holidays: e.target.checked })} /> Skip holidays</label>
                <label className="flex items-center gap-2 text-xs text-slate-300"><input type="checkbox" checked={draft.is_active} onChange={(e) => setDraft({ ...draft, is_active: e.target.checked })} /> Active</label>
              </div>
              <div>
                <label className="text-[11px] text-slate-500">Task config (JSON — e.g. {'{"job_key":"sla_scan"}'} or {'{"job_type":"ai_task","payload":{}}'})</label>
                <textarea value={draft.task_config} onChange={(e) => setDraft({ ...draft, task_config: e.target.value })} rows={3} className={`${F} font-mono`} />
              </div>
            </div>
            <div className="flex items-center justify-end gap-2 mt-5">
              <button onClick={() => setDraft(null)} className="px-3 py-2 rounded-lg text-xs font-semibold text-slate-400 hover:text-slate-200 cursor-pointer">Cancel</button>
              <button onClick={save} className="px-4 py-2 rounded-lg text-xs font-semibold bg-brand-500/20 text-brand-300 hover:bg-brand-500/30 cursor-pointer flex items-center gap-1.5"><Check className="w-3.5 h-3.5" /> Save</button>
            </div>
          </div>
        </div>
      )}

      {/* Next-runs preview */}
      {preview && (
        <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4" onClick={() => setPreview(null)}>
          <div className="glass-panel border border-slate-800 rounded-2xl w-full max-w-sm p-5" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-bold text-slate-100 flex items-center gap-2"><Eye className="w-4 h-4 text-brand-400" /> Next runs</h3>
              <button onClick={() => setPreview(null)} className="text-slate-500 hover:text-slate-300 cursor-pointer"><X className="w-4 h-4" /></button>
            </div>
            {preview.length === 0 ? <p className="text-xs text-slate-500">No upcoming runs.</p> : (
              <ul className="space-y-1.5">
                {preview.map((t, i) => <li key={i} className="text-xs text-slate-300 font-mono">{new Date(t).toLocaleString()}</li>)}
              </ul>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
