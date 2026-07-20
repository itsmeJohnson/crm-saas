import React, { useCallback, useEffect, useState } from 'react';
import {
  Layers, Loader2, X, Plus, Ban, RotateCcw, Clock, AlertOctagon, Cpu, BarChart3,
  ListChecks, Trash2, ChevronRight,
} from 'lucide-react';
import {
  queueApi, QueueJob, QueueWorker, QueueCatalog, QueueReport,
} from '../services/queueApi';
import { extractErrorMessage } from '../utils/errors';

const F = 'w-full bg-slate-800/70 border border-slate-700/70 text-slate-200 py-2 px-3 rounded-lg text-sm';

const StatusChip: React.FC<{ s: string }> = ({ s }) => {
  const tone = s === 'succeeded' ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
    : s === 'running' ? 'bg-brand-500/10 text-brand-300 border-brand-500/20'
      : s === 'failed' ? 'bg-amber-500/10 text-amber-400 border-amber-500/20'
        : s === 'dead_letter' ? 'bg-red-500/10 text-red-400 border-red-500/20'
          : s === 'cancelled' ? 'bg-slate-700/40 text-slate-500 border-slate-600/40'
            : 'bg-slate-700/40 text-slate-300 border-slate-600/40';
  return <span className={`px-1.5 py-0.5 text-[10px] font-semibold rounded-md border ${tone}`}>{s}</span>;
};

type Tab = 'jobs' | 'scheduled' | 'dlq' | 'workers' | 'monitoring';

export const QueuePage: React.FC = () => {
  const [tab, setTab] = useState<Tab>('jobs');
  const [catalog, setCatalog] = useState<QueueCatalog | null>(null);
  const [jobs, setJobs] = useState<QueueJob[]>([]);
  const [workers, setWorkers] = useState<QueueWorker[]>([]);
  const [report, setReport] = useState<QueueReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState('');
  const [msg, setMsg] = useState('');
  const [queueFilter, setQueueFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [expanded, setExpanded] = useState<string | null>(null);
  const [enq, setEnq] = useState<any>(null);

  const flash = (m: string) => { setMsg(m); setTimeout(() => setMsg(''), 2500); };
  const fail = (e: any) => setErr(extractErrorMessage(e, 'Something went wrong.'));

  const loadTab = useCallback(async (t: Tab, qf = queueFilter, sf = statusFilter) => {
    try {
      if (t === 'jobs') setJobs(await queueApi.jobs({ queue: qf || undefined, status: sf || undefined, limit: 100 }));
      if (t === 'scheduled') setJobs(await queueApi.scheduled({ limit: 100 }));
      if (t === 'dlq') setJobs(await queueApi.deadLetter({ limit: 100 }));
      if (t === 'workers') setWorkers(await queueApi.workers());
      if (t === 'monitoring') setReport(await queueApi.report());
    } catch (e) { fail(e); }
  }, [queueFilter, statusFilter]);

  useEffect(() => {
    (async () => {
      setLoading(true);
      try { setCatalog(await queueApi.catalog()); await loadTab('jobs'); } catch (e) { fail(e); } finally { setLoading(false); }
    })();
  }, []);
  useEffect(() => { loadTab(tab); }, [tab]);

  const act = async (fn: () => Promise<any>, ok: string) => { try { await fn(); flash(ok); await loadTab(tab); } catch (e) { fail(e); } };

  const submitEnqueue = async () => {
    if (!enq?.job_type) { setErr('Job type is required.'); return; }
    try {
      let payload = undefined;
      if (enq.payload?.trim()) payload = JSON.parse(enq.payload);
      const body: any = { job_type: enq.job_type, priority: enq.priority, max_attempts: enq.max_attempts, payload };
      if (enq.queue) body.queue = enq.queue;
      if (enq.run_at) body.run_at = new Date(enq.run_at).toISOString();
      await queueApi.enqueue(body);
      setEnq(null); flash('Job enqueued.'); await loadTab(tab);
    } catch (e) { fail(e); }
  };

  const Tabs = (
    <div className="flex items-center gap-1 bg-slate-900/50 border border-slate-800/70 rounded-xl p-1 w-fit flex-wrap">
      {([['jobs', 'Jobs', ListChecks], ['scheduled', 'Scheduled', Clock], ['dlq', 'Dead Letter', AlertOctagon],
         ['workers', 'Workers', Cpu], ['monitoring', 'Monitoring', BarChart3]] as [Tab, string, any][])
        .map(([k, label, Icon]) => (
          <button key={k} onClick={() => setTab(k)}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 cursor-pointer ${tab === k ? 'bg-brand-500/20 text-brand-300' : 'text-slate-400 hover:text-slate-200'}`}>
            <Icon className="w-3.5 h-3.5" /> {label}
          </button>
        ))}
    </div>
  );

  const JobRow: React.FC<{ j: QueueJob }> = ({ j }) => (
    <div className="glass-panel border border-slate-800/85 rounded-xl overflow-hidden">
      <div className="flex items-center gap-3 p-3">
        <button onClick={() => setExpanded(expanded === j.id ? null : j.id)} className="text-slate-500 hover:text-slate-300 cursor-pointer"><ChevronRight className={`w-4 h-4 transition-transform ${expanded === j.id ? 'rotate-90' : ''}`} /></button>
        <span className="font-mono text-xs text-brand-300">{j.job_type}</span>
        <span className="px-1.5 py-0.5 text-[10px] rounded-md bg-slate-700/40 text-slate-400 border border-slate-600/40">{j.queue}</span>
        <span className="text-[10px] text-slate-500">P{j.priority}</span>
        <StatusChip s={j.status} />
        <span className="text-[11px] text-slate-500 ml-auto">
          {j.attempts}/{j.max_attempts} attempts{j.duration_ms != null ? ` · ${j.duration_ms}ms` : ''}
          {j.status === 'queued' && j.run_at ? ` · runs ${new Date(j.run_at).toLocaleTimeString()}` : ''}
        </span>
        <div className="flex items-center gap-1.5">
          {j.status === 'queued' && <button title="Cancel" onClick={() => act(() => queueApi.cancel(j.id), 'Cancelled.')} className="p-1.5 rounded-md hover:bg-slate-800 text-slate-400 hover:text-red-400 cursor-pointer"><Ban className="w-4 h-4" /></button>}
          {['failed', 'dead_letter', 'cancelled'].includes(j.status) && <button title="Retry" onClick={() => act(() => queueApi.retry(j.id), 'Requeued.')} className="p-1.5 rounded-md hover:bg-slate-800 text-slate-400 hover:text-brand-300 cursor-pointer"><RotateCcw className="w-4 h-4" /></button>}
        </div>
      </div>
      {expanded === j.id && (
        <div className="px-4 pb-3 border-t border-slate-800/60 space-y-2 pt-2">
          {j.error && <p className="text-[11px] text-red-400">Error: {j.error}</p>}
          {j.payload && <div><p className="text-[10px] uppercase font-semibold text-slate-500">Payload</p><pre className="text-[10px] text-slate-400 overflow-x-auto">{JSON.stringify(j.payload, null, 2)}</pre></div>}
          {j.result && <div><p className="text-[10px] uppercase font-semibold text-slate-500">Result</p><pre className="text-[10px] text-slate-400 overflow-x-auto">{JSON.stringify(j.result, null, 2)}</pre></div>}
        </div>
      )}
    </div>
  );

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-extrabold text-slate-100 flex items-center gap-2"><Layers className="w-6 h-6 text-brand-400" /> Background Queue</h1>
          <p className="text-sm text-slate-500 mt-1">Durable jobs with priority, retry, dead-letter, scheduling and workers.</p>
        </div>
        <button onClick={() => setEnq({ job_type: catalog?.job_types[0] || 'ai_task', queue: '', priority: 5, max_attempts: 3, payload: '', run_at: '' })}
          className="px-3 py-2 rounded-lg text-xs font-semibold bg-brand-500/20 text-brand-300 hover:bg-brand-500/30 cursor-pointer flex items-center gap-1.5"><Plus className="w-3.5 h-3.5" /> Enqueue job</button>
      </div>

      {Tabs}
      {msg && <div className="text-xs text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 rounded-lg px-3 py-2">{msg}</div>}
      {err && <div className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2 flex items-center justify-between"><span>{err}</span><button onClick={() => setErr('')}><X className="w-3.5 h-3.5" /></button></div>}

      {loading ? (
        <div className="py-16 text-center text-slate-400"><Loader2 className="w-6 h-6 animate-spin inline" /></div>
      ) : tab === 'jobs' ? (
        <div className="space-y-2">
          {catalog && (
            <div className="flex items-center gap-2 flex-wrap">
              <select value={queueFilter} onChange={(e) => { setQueueFilter(e.target.value); loadTab('jobs', e.target.value, statusFilter); }} className={`${F} !w-auto`}>
                <option value="">All queues</option>
                {catalog.queues.map((q) => <option key={q} value={q}>{q}</option>)}
              </select>
              <select value={statusFilter} onChange={(e) => { setStatusFilter(e.target.value); loadTab('jobs', queueFilter, e.target.value); }} className={`${F} !w-auto`}>
                <option value="">All statuses</option>
                {catalog.statuses.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
          )}
          {jobs.length === 0 && <p className="text-sm text-slate-500">No jobs.</p>}
          {jobs.map((j) => <JobRow key={j.id} j={j} />)}
        </div>
      ) : tab === 'scheduled' ? (
        <div className="space-y-2">
          {jobs.length === 0 && <p className="text-sm text-slate-500">No scheduled jobs.</p>}
          {jobs.map((j) => <JobRow key={j.id} j={j} />)}
        </div>
      ) : tab === 'dlq' ? (
        <div className="space-y-2">
          {jobs.length === 0 ? <p className="text-sm text-slate-500">Dead-letter queue is empty. 🎉</p> : (
            <>
              <div className="flex justify-end"><button onClick={() => window.confirm('Purge all dead-letter jobs?') && act(() => queueApi.purge('dead_letter'), 'Purged.')} className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-800/70 hover:bg-slate-700/70 text-slate-300 cursor-pointer flex items-center gap-1.5"><Trash2 className="w-3.5 h-3.5" /> Purge DLQ</button></div>
              {jobs.map((j) => <JobRow key={j.id} j={j} />)}
            </>
          )}
        </div>
      ) : tab === 'workers' ? (
        <div className="glass-panel border border-slate-800/85 rounded-xl overflow-hidden">
          <table className="w-full text-xs">
            <thead className="bg-slate-900/60 text-slate-400"><tr>
              <th className="text-left px-4 py-2 font-semibold">Worker</th>
              <th className="text-left px-4 py-2 font-semibold">Status</th>
              <th className="text-left px-4 py-2 font-semibold">Processed</th>
              <th className="text-left px-4 py-2 font-semibold">Last heartbeat</th>
            </tr></thead>
            <tbody>
              {workers.length === 0 && <tr><td colSpan={4} className="px-4 py-6 text-center text-slate-500">No workers registered.</td></tr>}
              {workers.map((w) => (
                <tr key={w.id} className="border-t border-slate-800/60">
                  <td className="px-4 py-2 font-mono text-slate-300">{w.name}</td>
                  <td className="px-4 py-2"><span className={w.status === 'offline' ? 'text-slate-500' : w.status === 'busy' ? 'text-brand-300' : 'text-emerald-400'}>{w.status}</span></td>
                  <td className="px-4 py-2 text-slate-400">{w.jobs_processed}</td>
                  <td className="px-4 py-2 text-slate-500">{w.last_heartbeat ? new Date(w.last_heartbeat).toLocaleString() : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="space-y-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {report && [['Total jobs', report.total], ['Success rate', `${report.success_rate}%`], ['Avg duration', `${report.avg_duration_ms}ms`]].map(([k, v]) => (
              <div key={k as string} className="glass-panel border border-slate-800/85 rounded-xl p-4">
                <p className="text-[10px] font-semibold text-slate-500 uppercase">{k}</p>
                <p className="text-xl font-bold text-slate-100 mt-1">{v}</p>
              </div>
            ))}
          </div>
          {report && (
            <div className="glass-panel border border-slate-800/85 rounded-xl overflow-hidden">
              <table className="w-full text-xs">
                <thead className="bg-slate-900/60 text-slate-400"><tr>
                  <th className="text-left px-4 py-2 font-semibold">Queue</th>
                  <th className="px-3 py-2 font-semibold">Queued</th>
                  <th className="px-3 py-2 font-semibold">Running</th>
                  <th className="px-3 py-2 font-semibold">Succeeded</th>
                  <th className="px-3 py-2 font-semibold">Failed</th>
                  <th className="px-3 py-2 font-semibold">DLQ</th>
                </tr></thead>
                <tbody>
                  {Object.keys(report.by_queue).length === 0 && <tr><td colSpan={6} className="px-4 py-6 text-center text-slate-500">No jobs yet.</td></tr>}
                  {Object.entries(report.by_queue).map(([q, c]) => (
                    <tr key={q} className="border-t border-slate-800/60">
                      <td className="px-4 py-2 text-slate-300 font-semibold">{q}</td>
                      <td className="px-3 py-2 text-center text-slate-400">{c.queued || 0}</td>
                      <td className="px-3 py-2 text-center text-brand-300">{c.running || 0}</td>
                      <td className="px-3 py-2 text-center text-emerald-400">{c.succeeded || 0}</td>
                      <td className="px-3 py-2 text-center text-amber-400">{c.failed || 0}</td>
                      <td className="px-3 py-2 text-center text-red-400">{c.dead_letter || 0}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Enqueue modal */}
      {enq && catalog && (
        <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4" onClick={() => setEnq(null)}>
          <div className="glass-panel border border-slate-800 rounded-2xl w-full max-w-lg p-5" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-bold text-slate-100">Enqueue job</h3>
              <button onClick={() => setEnq(null)} className="text-slate-500 hover:text-slate-300 cursor-pointer"><X className="w-5 h-5" /></button>
            </div>
            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <select value={enq.job_type} onChange={(e) => setEnq({ ...enq, job_type: e.target.value })} className={F}>
                  {catalog.job_types.map((t) => <option key={t} value={t}>{t}</option>)}
                </select>
                <select value={enq.queue} onChange={(e) => setEnq({ ...enq, queue: e.target.value })} className={F}>
                  <option value="">default for type ({catalog.queue_for_type[enq.job_type]})</option>
                  {catalog.queues.map((q) => <option key={q} value={q}>{q}</option>)}
                </select>
                <div>
                  <label className="text-[11px] text-slate-500">Priority (higher = sooner)</label>
                  <input type="number" value={enq.priority} onChange={(e) => setEnq({ ...enq, priority: parseInt(e.target.value) || 0 })} className={F} />
                </div>
                <div>
                  <label className="text-[11px] text-slate-500">Max attempts</label>
                  <input type="number" value={enq.max_attempts} onChange={(e) => setEnq({ ...enq, max_attempts: parseInt(e.target.value) || 1 })} className={F} />
                </div>
              </div>
              <div>
                <label className="text-[11px] text-slate-500">Schedule (optional — leave blank to run now)</label>
                <input type="datetime-local" value={enq.run_at} onChange={(e) => setEnq({ ...enq, run_at: e.target.value })} className={F} />
              </div>
              <div>
                <label className="text-[11px] text-slate-500">Payload (JSON, optional)</label>
                <textarea value={enq.payload} onChange={(e) => setEnq({ ...enq, payload: e.target.value })} rows={4} placeholder='{"prompt": "hello"}' className={`${F} font-mono`} />
              </div>
            </div>
            <div className="flex items-center justify-end gap-2 mt-5">
              <button onClick={() => setEnq(null)} className="px-3 py-2 rounded-lg text-xs font-semibold text-slate-400 hover:text-slate-200 cursor-pointer">Cancel</button>
              <button onClick={submitEnqueue} className="px-4 py-2 rounded-lg text-xs font-semibold bg-brand-500/20 text-brand-300 hover:bg-brand-500/30 cursor-pointer flex items-center gap-1.5"><Plus className="w-3.5 h-3.5" /> Enqueue</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
