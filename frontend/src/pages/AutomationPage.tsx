import React, { useCallback, useEffect, useState } from 'react';
import {
  Cog, Loader2, X, Check, Trash2, Play, RotateCcw, Power, Plus, ShieldAlert,
  FileClock, ListChecks, BarChart3, Activity, AlertTriangle,
} from 'lucide-react';
import {
  automationApi, AutomationJob, AutomationRun, SLAPolicy, SLABreach, ScheduledReport,
  AutomationCatalog, AutomationReport,
} from '../services/automationApi';
import { extractErrorMessage } from '../utils/errors';

const F = 'w-full bg-slate-800/70 border border-slate-700/70 text-slate-200 py-2 px-3 rounded-lg text-sm';

const StatusDot: React.FC<{ s: string | null }> = ({ s }) => {
  const tone = s === 'success' ? 'bg-emerald-400' : s === 'failed' ? 'bg-red-400' : s === 'running' ? 'bg-amber-400' : 'bg-slate-600';
  return <span className={`inline-block w-2 h-2 rounded-full ${tone}`} />;
};

type Tab = 'jobs' | 'sla' | 'reports' | 'runs' | 'dashboard';

export const AutomationPage: React.FC = () => {
  const [tab, setTab] = useState<Tab>('jobs');
  const [catalog, setCatalog] = useState<AutomationCatalog | null>(null);
  const [jobs, setJobs] = useState<AutomationJob[]>([]);
  const [runs, setRuns] = useState<AutomationRun[]>([]);
  const [slas, setSlas] = useState<SLAPolicy[]>([]);
  const [breaches, setBreaches] = useState<SLABreach[]>([]);
  const [reports, setReports] = useState<ScheduledReport[]>([]);
  const [report, setReport] = useState<AutomationReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState('');
  const [msg, setMsg] = useState('');
  const [busy, setBusy] = useState('');

  // SLA editor
  const [slaDraft, setSlaDraft] = useState<any>(null);
  // report editor
  const [repDraft, setRepDraft] = useState<any>(null);

  const flash = (m: string) => { setMsg(m); setTimeout(() => setMsg(''), 2500); };
  const fail = (e: any) => setErr(extractErrorMessage(e, 'Something went wrong.'));

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [cat, js] = await Promise.all([automationApi.catalog(), automationApi.listJobs()]);
      setCatalog(cat); setJobs(js);
    } catch (e) { fail(e); } finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    if (tab === 'runs') automationApi.runs({ limit: 50 }).then(setRuns).catch(() => {});
    if (tab === 'sla') { automationApi.listSla().then(setSlas).catch(() => {}); automationApi.breaches({ limit: 50 }).then(setBreaches).catch(() => {}); }
    if (tab === 'reports') automationApi.listReports().then(setReports).catch(() => {});
    if (tab === 'dashboard') automationApi.report().then(setReport).catch(() => {});
  }, [tab]);

  const act = async (fn: () => Promise<any>, ok: string) => {
    try { await fn(); flash(ok); } catch (e) { fail(e); }
  };
  const toggleJob = (j: AutomationJob) => act(async () => { await automationApi.enableJob(j.job_key, !j.is_enabled); await load(); }, 'Updated.');
  const runJob = async (j: AutomationJob) => {
    setBusy(j.job_key); setErr('');
    try { const r = await automationApi.runJob(j.job_key); flash(`Ran ${j.name}: ${r.status} (${r.items_processed} items)`); await load(); }
    catch (e) { fail(e); } finally { setBusy(''); }
  };

  const saveSla = async () => {
    if (!slaDraft?.name?.trim()) { setErr('Name is required.'); return; }
    try {
      if (slaDraft.id) await automationApi.updateSla(slaDraft.id, slaDraft);
      else await automationApi.createSla(slaDraft);
      setSlaDraft(null); flash('SLA saved.'); automationApi.listSla().then(setSlas);
    } catch (e) { fail(e); }
  };
  const saveReport = async () => {
    if (!repDraft?.name?.trim()) { setErr('Name is required.'); return; }
    try {
      const payload = { ...repDraft, recipients: (repDraft.recipients || '').toString().split(',').map((s: string) => s.trim()).filter(Boolean) };
      if (repDraft.id) await automationApi.updateReport(repDraft.id, payload);
      else await automationApi.createReport(payload);
      setRepDraft(null); flash('Report saved.'); automationApi.listReports().then(setReports);
    } catch (e) { fail(e); }
  };

  const Tabs = (
    <div className="flex items-center gap-1 bg-slate-900/50 border border-slate-800/70 rounded-xl p-1 w-fit flex-wrap">
      {([['jobs', 'Jobs', ListChecks], ['sla', 'SLA Policies', ShieldAlert], ['reports', 'Scheduled Reports', FileClock],
         ['runs', 'Run History', Activity], ['dashboard', 'Dashboard', BarChart3]] as [Tab, string, any][])
        .map(([k, label, Icon]) => (
          <button key={k} onClick={() => setTab(k)}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 cursor-pointer ${tab === k ? 'bg-brand-500/20 text-brand-300' : 'text-slate-400 hover:text-slate-200'}`}>
            <Icon className="w-3.5 h-3.5" /> {label}
          </button>
        ))}
    </div>
  );

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-extrabold text-slate-100 flex items-center gap-2"><Cog className="w-6 h-6 text-brand-400" /> Automation Engine</h1>
        <p className="text-sm text-slate-500 mt-1">Background jobs, SLA policies, scheduled reports and execution history.</p>
      </div>
      {Tabs}
      {msg && <div className="text-xs text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 rounded-lg px-3 py-2">{msg}</div>}
      {err && <div className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2 flex items-center justify-between"><span>{err}</span><button onClick={() => setErr('')}><X className="w-3.5 h-3.5" /></button></div>}

      {loading ? (
        <div className="py-16 text-center text-slate-400"><Loader2 className="w-6 h-6 animate-spin inline" /></div>
      ) : tab === 'jobs' ? (
        <div className="space-y-2">
          {jobs.map((j) => (
            <div key={j.job_key} className="glass-panel border border-slate-800/85 rounded-xl p-4 flex items-center gap-4">
              <StatusDot s={j.last_status} />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-semibold text-slate-100 truncate">{j.name}</span>
                  <span className="px-1.5 py-0.5 text-[10px] rounded-md bg-slate-700/40 text-slate-400 border border-slate-600/40">{j.category}</span>
                  <span className="px-1.5 py-0.5 text-[10px] rounded-md bg-slate-800/60 text-slate-500">{j.schedule}</span>
                  {!j.is_enabled && <span className="px-1.5 py-0.5 text-[10px] rounded-md bg-slate-700/40 text-slate-500">disabled</span>}
                </div>
                <p className="text-[11px] text-slate-500 mt-0.5 truncate">
                  {j.description} · runs {j.run_count} · fails {j.fail_count}
                  {j.last_run_at ? ` · last ${new Date(j.last_run_at).toLocaleString()}` : ' · never run'}
                </p>
              </div>
              <div className="flex items-center gap-1.5 shrink-0">
                <button title="Run now" disabled={busy === j.job_key} onClick={() => runJob(j)} className="p-1.5 rounded-md hover:bg-slate-800 text-slate-400 hover:text-brand-300 cursor-pointer">
                  {busy === j.job_key ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
                </button>
                <button title={j.is_enabled ? 'Disable' : 'Enable'} onClick={() => toggleJob(j)} className={`p-1.5 rounded-md hover:bg-slate-800 cursor-pointer ${j.is_enabled ? 'text-emerald-400' : 'text-slate-500'}`}><Power className="w-4 h-4" /></button>
              </div>
            </div>
          ))}
        </div>
      ) : tab === 'sla' ? (
        <div className="space-y-4">
          <div className="flex justify-end">
            <button onClick={() => setSlaDraft({ name: '', entity_type: 'lead', metric: 'first_response', threshold_hours: 4, on_breach: 'notify_manager', is_active: true })}
              className="px-3 py-2 rounded-lg text-xs font-semibold bg-brand-500/20 text-brand-300 hover:bg-brand-500/30 cursor-pointer flex items-center gap-1.5"><Plus className="w-3.5 h-3.5" /> New SLA policy</button>
          </div>
          {slas.length === 0 && <p className="text-sm text-slate-500">No SLA policies yet.</p>}
          {slas.map((p) => (
            <div key={p.id} className="glass-panel border border-slate-800/85 rounded-xl p-4 flex items-center gap-4">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-semibold text-slate-100">{p.name}</span>
                  <span className="px-1.5 py-0.5 text-[10px] rounded-md bg-brand-500/10 text-brand-300 border border-brand-500/20">{p.metric.replace(/_/g, ' ')}</span>
                  {!p.is_active && <span className="px-1.5 py-0.5 text-[10px] rounded-md bg-slate-700/40 text-slate-500">inactive</span>}
                </div>
                <p className="text-[11px] text-slate-500 mt-0.5">within {p.threshold_hours}h · on breach: {p.on_breach.replace(/_/g, ' ')} · {p.breach_count} breaches</p>
              </div>
              <div className="flex items-center gap-1.5 shrink-0">
                <button onClick={() => setSlaDraft({ ...p })} className="px-2 py-1 text-xs rounded-md bg-slate-800/70 hover:bg-slate-700/70 text-slate-300 cursor-pointer">Edit</button>
                <button onClick={() => window.confirm(`Delete "${p.name}"?`) && act(async () => { await automationApi.removeSla(p.id); automationApi.listSla().then(setSlas); }, 'Deleted.')} className="p-1.5 rounded-md hover:bg-slate-800 text-slate-400 hover:text-red-400 cursor-pointer"><Trash2 className="w-4 h-4" /></button>
              </div>
            </div>
          ))}
          {breaches.length > 0 && (
            <div className="mt-6">
              <h3 className="text-sm font-semibold text-slate-300 mb-2 flex items-center gap-2"><AlertTriangle className="w-4 h-4 text-amber-400" /> Recent breaches</h3>
              <div className="space-y-1.5">
                {breaches.map((b) => (
                  <div key={b.id} className="flex items-center justify-between text-xs glass-panel border border-slate-800/70 rounded-lg px-3 py-2">
                    <span className="text-slate-300">{b.metric.replace(/_/g, ' ')} · {b.hours_elapsed}h · {b.entity_id.slice(0, 8)}</span>
                    {b.resolved ? <span className="text-emerald-400">resolved</span>
                      : <button onClick={() => act(async () => { await automationApi.resolveBreach(b.id); automationApi.breaches({ limit: 50 }).then(setBreaches); }, 'Resolved.')} className="text-brand-400 hover:text-brand-300 cursor-pointer">Resolve</button>}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      ) : tab === 'reports' ? (
        <div className="space-y-4">
          <div className="flex justify-end">
            <button onClick={() => setRepDraft({ name: '', report_type: 'lead_summary', frequency: 'weekly', channel: 'in_app', recipients: '', is_active: true })}
              className="px-3 py-2 rounded-lg text-xs font-semibold bg-brand-500/20 text-brand-300 hover:bg-brand-500/30 cursor-pointer flex items-center gap-1.5"><Plus className="w-3.5 h-3.5" /> New scheduled report</button>
          </div>
          {reports.length === 0 && <p className="text-sm text-slate-500">No scheduled reports yet.</p>}
          {reports.map((r) => (
            <div key={r.id} className="glass-panel border border-slate-800/85 rounded-xl p-4 flex items-center gap-4">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-semibold text-slate-100">{r.name}</span>
                  <span className="px-1.5 py-0.5 text-[10px] rounded-md bg-brand-500/10 text-brand-300 border border-brand-500/20">{r.report_type.replace(/_/g, ' ')}</span>
                  <span className="px-1.5 py-0.5 text-[10px] rounded-md bg-slate-800/60 text-slate-500">{r.frequency}</span>
                </div>
                <p className="text-[11px] text-slate-500 mt-0.5">{r.recipients.length} recipient(s) · sent {r.send_count}×{r.last_sent_at ? ` · last ${new Date(r.last_sent_at).toLocaleDateString()}` : ''}</p>
              </div>
              <div className="flex items-center gap-1.5 shrink-0">
                <button title="Send now" onClick={() => act(async () => { const x = await automationApi.runReport(r.id); flash(`Delivered to ${x.delivered}.`); automationApi.listReports().then(setReports); }, 'Sent.')} className="p-1.5 rounded-md hover:bg-slate-800 text-slate-400 hover:text-brand-300 cursor-pointer"><Play className="w-4 h-4" /></button>
                <button onClick={() => setRepDraft({ ...r, recipients: r.recipients.join(', ') })} className="px-2 py-1 text-xs rounded-md bg-slate-800/70 hover:bg-slate-700/70 text-slate-300 cursor-pointer">Edit</button>
                <button onClick={() => window.confirm(`Delete "${r.name}"?`) && act(async () => { await automationApi.removeReport(r.id); automationApi.listReports().then(setReports); }, 'Deleted.')} className="p-1.5 rounded-md hover:bg-slate-800 text-slate-400 hover:text-red-400 cursor-pointer"><Trash2 className="w-4 h-4" /></button>
              </div>
            </div>
          ))}
        </div>
      ) : tab === 'runs' ? (
        <div className="glass-panel border border-slate-800/85 rounded-xl overflow-hidden">
          <table className="w-full text-xs">
            <thead className="bg-slate-900/60 text-slate-400"><tr>
              <th className="text-left px-4 py-2 font-semibold">Job</th>
              <th className="text-left px-4 py-2 font-semibold">Status</th>
              <th className="text-left px-4 py-2 font-semibold">Trigger</th>
              <th className="text-left px-4 py-2 font-semibold">Items</th>
              <th className="text-left px-4 py-2 font-semibold">Duration</th>
              <th className="text-left px-4 py-2 font-semibold">When</th>
              <th className="px-4 py-2"></th>
            </tr></thead>
            <tbody>
              {runs.length === 0 && <tr><td colSpan={7} className="px-4 py-6 text-center text-slate-500">No runs recorded yet.</td></tr>}
              {runs.map((r) => (
                <tr key={r.id} className="border-t border-slate-800/60">
                  <td className="px-4 py-2 text-slate-300">{r.job_key.replace(/_/g, ' ')}</td>
                  <td className="px-4 py-2"><span className="inline-flex items-center gap-1.5"><StatusDot s={r.status} /><span className={r.status === 'failed' ? 'text-red-400' : 'text-slate-400'}>{r.status}</span></span></td>
                  <td className="px-4 py-2 text-slate-500">{r.triggered_by}{r.retry_count ? ` (×${r.retry_count})` : ''}</td>
                  <td className="px-4 py-2 text-slate-400">{r.items_processed}</td>
                  <td className="px-4 py-2 text-slate-500">{r.duration_ms != null ? `${r.duration_ms}ms` : '—'}</td>
                  <td className="px-4 py-2 text-slate-500">{r.started_at ? new Date(r.started_at).toLocaleString() : ''}</td>
                  <td className="px-4 py-2 text-right">
                    {r.status === 'failed' && <button title="Retry" onClick={() => act(async () => { await automationApi.retryRun(r.id); automationApi.runs({ limit: 50 }).then(setRuns); }, 'Retried.')} className="text-brand-400 hover:text-brand-300 cursor-pointer inline-flex items-center gap-1"><RotateCcw className="w-3.5 h-3.5" /></button>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {report && [['Total runs', report.total_runs], ['Succeeded', report.succeeded], ['Failed', report.failed],
            ['Success rate', `${report.success_rate}%`], ['Open breaches', report.open_breaches], ['Active reports', report.active_reports]].map(([k, v]) => (
            <div key={k as string} className="glass-panel border border-slate-800/85 rounded-xl p-4">
              <p className="text-[10px] font-semibold text-slate-500 uppercase">{k}</p>
              <p className="text-xl font-bold text-slate-100 mt-1">{v}</p>
            </div>
          ))}
        </div>
      )}

      {/* SLA editor modal */}
      {slaDraft && catalog && (
        <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4" onClick={() => setSlaDraft(null)}>
          <div className="glass-panel border border-slate-800 rounded-2xl w-full max-w-lg p-5" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-bold text-slate-100">{slaDraft.id ? 'Edit SLA policy' : 'New SLA policy'}</h3>
              <button onClick={() => setSlaDraft(null)} className="text-slate-500 hover:text-slate-300 cursor-pointer"><X className="w-5 h-5" /></button>
            </div>
            <div className="space-y-3">
              <input value={slaDraft.name} onChange={(e) => setSlaDraft({ ...slaDraft, name: e.target.value })} placeholder="Policy name" className={F} />
              <div className="grid grid-cols-2 gap-3">
                <select value={slaDraft.metric} onChange={(e) => setSlaDraft({ ...slaDraft, metric: e.target.value })} className={F}>
                  {catalog.sla_metrics.map((m) => <option key={m} value={m}>{m.replace(/_/g, ' ')}</option>)}
                </select>
                <input type="number" value={slaDraft.threshold_hours} onChange={(e) => setSlaDraft({ ...slaDraft, threshold_hours: parseFloat(e.target.value) || 0 })} placeholder="Threshold (hours)" className={F} />
                <select value={slaDraft.on_breach} onChange={(e) => setSlaDraft({ ...slaDraft, on_breach: e.target.value })} className={F}>
                  {catalog.sla_breach_actions.map((a) => <option key={a} value={a}>{a.replace(/_/g, ' ')}</option>)}
                </select>
                <label className="flex items-center gap-2 text-xs text-slate-300 px-1"><input type="checkbox" checked={slaDraft.is_active} onChange={(e) => setSlaDraft({ ...slaDraft, is_active: e.target.checked })} /> Active</label>
              </div>
              <textarea value={slaDraft.description || ''} onChange={(e) => setSlaDraft({ ...slaDraft, description: e.target.value })} placeholder="Description (optional)" rows={2} className={F} />
            </div>
            <div className="flex items-center justify-end gap-2 mt-5">
              <button onClick={() => setSlaDraft(null)} className="px-3 py-2 rounded-lg text-xs font-semibold text-slate-400 hover:text-slate-200 cursor-pointer">Cancel</button>
              <button onClick={saveSla} className="px-4 py-2 rounded-lg text-xs font-semibold bg-brand-500/20 text-brand-300 hover:bg-brand-500/30 cursor-pointer flex items-center gap-1.5"><Check className="w-3.5 h-3.5" /> Save</button>
            </div>
          </div>
        </div>
      )}

      {/* Scheduled report editor modal */}
      {repDraft && catalog && (
        <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4" onClick={() => setRepDraft(null)}>
          <div className="glass-panel border border-slate-800 rounded-2xl w-full max-w-lg p-5" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-bold text-slate-100">{repDraft.id ? 'Edit scheduled report' : 'New scheduled report'}</h3>
              <button onClick={() => setRepDraft(null)} className="text-slate-500 hover:text-slate-300 cursor-pointer"><X className="w-5 h-5" /></button>
            </div>
            <div className="space-y-3">
              <input value={repDraft.name} onChange={(e) => setRepDraft({ ...repDraft, name: e.target.value })} placeholder="Report name" className={F} />
              <div className="grid grid-cols-2 gap-3">
                <select value={repDraft.report_type} onChange={(e) => setRepDraft({ ...repDraft, report_type: e.target.value })} className={F}>
                  {catalog.report_types.map((t) => <option key={t} value={t}>{t.replace(/_/g, ' ')}</option>)}
                </select>
                <select value={repDraft.frequency} onChange={(e) => setRepDraft({ ...repDraft, frequency: e.target.value })} className={F}>
                  {catalog.frequencies.map((f) => <option key={f} value={f}>{f}</option>)}
                </select>
              </div>
              <input value={repDraft.recipients} onChange={(e) => setRepDraft({ ...repDraft, recipients: e.target.value })} placeholder="Recipient user IDs (comma-separated; blank = you)" className={F} />
              <label className="flex items-center gap-2 text-xs text-slate-300 px-1"><input type="checkbox" checked={repDraft.is_active} onChange={(e) => setRepDraft({ ...repDraft, is_active: e.target.checked })} /> Active</label>
            </div>
            <div className="flex items-center justify-end gap-2 mt-5">
              <button onClick={() => setRepDraft(null)} className="px-3 py-2 rounded-lg text-xs font-semibold text-slate-400 hover:text-slate-200 cursor-pointer">Cancel</button>
              <button onClick={saveReport} className="px-4 py-2 rounded-lg text-xs font-semibold bg-brand-500/20 text-brand-300 hover:bg-brand-500/30 cursor-pointer flex items-center gap-1.5"><Check className="w-3.5 h-3.5" /> Save</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
