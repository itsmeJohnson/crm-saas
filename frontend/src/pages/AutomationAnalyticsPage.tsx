import React, { useCallback, useEffect, useState } from 'react';
import {
  Activity, Loader2, Download, GitBranch, ListChecks, Boxes, ShieldCheck, TrendingUp, CheckSquare,
  Layers, Zap, AlertTriangle, BarChart3,
} from 'lucide-react';
import {
  automationAnalyticsApi as api, AutomationOverview, WorkflowsAnalytics, QueueAnalytics, RuleUsage,
  SLACompliance, EscalationAnalytics, ApprovalAnalytics, AutomationTrend, TopAutomations,
} from '../services/automationAnalyticsApi';
import { extractErrorMessage } from '../utils/errors';

const F = 'bg-slate-800/70 border border-slate-700/70 text-slate-200 py-1.5 px-2 rounded-lg text-xs';
const card = 'glass-panel border border-slate-800/85 rounded-xl p-4';

const Stat: React.FC<{ label: string; value: React.ReactNode; tone?: string }> = ({ label, value, tone }) => (
  <div className={card}>
    <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">{label}</p>
    <p className={`text-xl font-bold mt-1 ${tone || 'text-slate-100'}`}>{value}</p>
  </div>
);

type Tab = 'overview' | 'workflows' | 'queue' | 'rules' | 'sla' | 'escalation' | 'approval' | 'trends' | 'top';

export const AutomationAnalyticsPage: React.FC = () => {
  const [tab, setTab] = useState<Tab>('overview');
  const [from, setFrom] = useState('');
  const [to, setTo] = useState('');
  const [granularity, setGranularity] = useState('daily');
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState('');

  const [ov, setOv] = useState<AutomationOverview | null>(null);
  const [wf, setWf] = useState<WorkflowsAnalytics | null>(null);
  const [q, setQ] = useState<QueueAnalytics | null>(null);
  const [ru, setRu] = useState<RuleUsage | null>(null);
  const [sla, setSla] = useState<SLACompliance | null>(null);
  const [esc, setEsc] = useState<EscalationAnalytics | null>(null);
  const [appr, setAppr] = useState<ApprovalAnalytics | null>(null);
  const [tr, setTr] = useState<AutomationTrend | null>(null);
  const [top, setTop] = useState<TopAutomations | null>(null);

  const range = () => ({ date_from: from || undefined, date_to: to || undefined });

  const load = useCallback(async () => {
    setLoading(true); setErr('');
    const r = { date_from: from || undefined, date_to: to || undefined };
    try {
      if (tab === 'overview') setOv(await api.overview(r));
      else if (tab === 'workflows') setWf(await api.workflows(r));
      else if (tab === 'queue') setQ(await api.queue(r));
      else if (tab === 'rules') setRu(await api.rules(r));
      else if (tab === 'sla') setSla(await api.sla(r));
      else if (tab === 'escalation') setEsc(await api.escalation(r));
      else if (tab === 'approval') setAppr(await api.approval(r));
      else if (tab === 'trends') setTr(await api.trend({ ...r, granularity }));
      else if (tab === 'top') setTop(await api.top(r));
    } catch (e) { setErr(extractErrorMessage(e, 'Failed to load analytics.')); } finally { setLoading(false); }
  }, [tab, from, to, granularity]);
  useEffect(() => { load(); }, [load]);

  const exportCsv = async () => {
    try {
      const blob = await api.exportCsv(range());
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a'); a.href = url; a.download = 'automation-analytics.csv'; a.click();
      URL.revokeObjectURL(url);
    } catch (e) { setErr(extractErrorMessage(e, 'Export failed.')); }
  };

  const TABS: [Tab, string, any][] = [
    ['overview', 'Overview', Layers], ['workflows', 'Workflows', GitBranch], ['queue', 'Queue', Boxes],
    ['rules', 'Rules', ListChecks], ['sla', 'SLA', ShieldCheck], ['escalation', 'Escalation', AlertTriangle],
    ['approval', 'Approval', CheckSquare], ['trends', 'Trends', TrendingUp], ['top', 'Top', Zap],
  ];

  const Bars: React.FC<{ data: Record<string, number>; empty?: string }> = ({ data, empty }) => {
    const entries = Object.entries(data || {});
    const max = Math.max(1, ...entries.map(([, v]) => v));
    if (!entries.length) return <p className="text-xs text-slate-500">{empty || 'No data.'}</p>;
    return (
      <div className="space-y-1.5">
        {entries.map(([k, v]) => (
          <div key={k} className="flex items-center gap-2">
            <span className="text-[11px] text-slate-400 w-32 truncate">{k}</span>
            <div className="flex-1 h-2.5 bg-slate-800/60 rounded"><div className="h-2.5 rounded bg-brand-500/70" style={{ width: `${(v / max) * 100}%` }} /></div>
            <span className="text-[11px] text-slate-300 w-8 text-right">{v}</span>
          </div>
        ))}
      </div>
    );
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-extrabold text-slate-100 flex items-center gap-2"><Activity className="w-6 h-6 text-brand-400" /> Automation Analytics</h1>
          <p className="text-sm text-slate-500 mt-1">Cross-cutting metrics over workflows, queue, rules, SLA, escalation and approvals.</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <input type="date" value={from} onChange={(e) => setFrom(e.target.value)} className={F} />
          <span className="text-slate-600 text-xs">→</span>
          <input type="date" value={to} onChange={(e) => setTo(e.target.value)} className={F} />
          <button onClick={exportCsv} className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-800/70 hover:bg-slate-700/70 text-slate-200 cursor-pointer flex items-center gap-1.5"><Download className="w-3.5 h-3.5" /> Export</button>
        </div>
      </div>

      <div className="flex items-center gap-1 bg-slate-900/50 border border-slate-800/70 rounded-xl p-1 w-fit flex-wrap">
        {TABS.map(([k, label, Icon]) => (
          <button key={k} onClick={() => setTab(k)}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 cursor-pointer ${tab === k ? 'bg-brand-500/20 text-brand-300' : 'text-slate-400 hover:text-slate-200'}`}>
            <Icon className="w-3.5 h-3.5" /> {label}
          </button>
        ))}
      </div>

      {err && <div className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">{err}</div>}

      {loading ? (
        <div className="py-16 text-center text-slate-400"><Loader2 className="w-6 h-6 animate-spin inline" /></div>
      ) : tab === 'overview' && ov ? (
        <div className="space-y-4">
          <div>
            <p className="text-xs font-semibold text-slate-400 mb-2 flex items-center gap-1.5"><GitBranch className="w-3.5 h-3.5" /> Workflows</p>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <Stat label="Runs" value={ov.workflow.total_runs} />
              <Stat label="Success rate" value={`${ov.workflow.success_rate}%`} tone="text-emerald-400" />
              <Stat label="Failures" value={ov.workflow.failed} tone={ov.workflow.failed ? 'text-red-400' : undefined} />
              <Stat label="Avg exec" value={`${Math.round(ov.workflow.avg_execution_ms)}ms`} />
            </div>
          </div>
          <div className="grid md:grid-cols-2 gap-4">
            <div>
              <p className="text-xs font-semibold text-slate-400 mb-2 flex items-center gap-1.5"><Boxes className="w-3.5 h-3.5" /> Queue</p>
              <div className="grid grid-cols-2 gap-3">
                <Stat label="Jobs" value={ov.queue.total} />
                <Stat label="Success rate" value={`${ov.queue.success_rate}%`} tone="text-emerald-400" />
                <Stat label="Failed" value={ov.queue.failed} tone={ov.queue.failed ? 'text-red-400' : undefined} />
                <Stat label="Dead letter" value={ov.queue.dead_letter} />
              </div>
            </div>
            <div>
              <p className="text-xs font-semibold text-slate-400 mb-2 flex items-center gap-1.5"><Layers className="w-3.5 h-3.5" /> Automation jobs</p>
              <div className="grid grid-cols-2 gap-3">
                <Stat label="Runs" value={ov.automation_jobs.runs} />
                <Stat label="Success rate" value={`${ov.automation_jobs.success_rate}%`} tone="text-emerald-400" />
                <Stat label="Items" value={ov.automation_jobs.items_processed} />
                <Stat label="Enabled" value={ov.automation_jobs.enabled_jobs} />
              </div>
            </div>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <Stat label="Rule match rate" value={`${ov.rules.match_rate}%`} />
            <Stat label="SLA compliance" value={`${ov.sla.compliance_rate}%`} tone="text-emerald-400" />
            <Stat label="Open breaches" value={ov.sla.open_breaches} tone={ov.sla.open_breaches ? 'text-red-400' : undefined} />
            <Stat label="Escalations" value={ov.escalation.total} />
            <Stat label="Approvals total" value={ov.approval.total} />
            <Stat label="Approval rate" value={`${ov.approval.approval_rate}%`} />
            <Stat label="Approvals pending" value={ov.approval.pending} />
            <Stat label="Avg decision" value={`${ov.approval.avg_decision_hours}h`} />
          </div>
        </div>
      ) : tab === 'workflows' && wf ? (
        <div className="space-y-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <Stat label="Runs" value={wf.total_runs} />
            <Stat label="Success rate" value={`${wf.success_rate}%`} tone="text-emerald-400" />
            <Stat label="Failures" value={wf.failed} tone={wf.failed ? 'text-red-400' : undefined} />
            <Stat label="Avg / max exec" value={`${Math.round(wf.avg_execution_ms)} / ${Math.round(wf.max_execution_ms)}ms`} />
          </div>
          <div className={card}>
            <p className="text-xs font-semibold text-slate-400 mb-2">Top workflows</p>
            {wf.top_workflows.length === 0 ? <p className="text-xs text-slate-500">No runs in range.</p> : (
              <table className="w-full text-xs">
                <thead className="text-slate-500"><tr><th className="text-left py-1">Workflow</th><th className="text-right">Runs</th><th className="text-right">Failed</th></tr></thead>
                <tbody>{wf.top_workflows.map((t) => (
                  <tr key={t.workflow_id} className="border-t border-slate-800/60 text-slate-300"><td className="py-1">{t.name}</td><td className="text-right">{t.runs}</td><td className="text-right text-red-400">{t.failed}</td></tr>
                ))}</tbody>
              </table>
            )}
          </div>
          <div className={card}>
            <p className="text-xs font-semibold text-slate-400 mb-2">Recent failures</p>
            {wf.failures.length === 0 ? <p className="text-xs text-slate-500">No failures — nice.</p> : (
              <ul className="space-y-1.5">{wf.failures.map((f) => (
                <li key={f.id} className="text-[11px] text-slate-400"><span className="text-slate-200">{f.name}</span> · {f.trigger_event} · <span className="text-red-400">{f.error || 'error'}</span></li>
              ))}</ul>
            )}
          </div>
        </div>
      ) : tab === 'queue' && q ? (
        <div className="space-y-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <Stat label="Jobs" value={q.total} />
            <Stat label="Success rate" value={`${q.success_rate}%`} tone="text-emerald-400" />
            <Stat label="Failed / dead" value={`${q.failed} / ${q.dead_letter}`} tone={q.failed + q.dead_letter ? 'text-red-400' : undefined} />
            <Stat label="Avg duration" value={`${Math.round(q.avg_duration_ms)}ms`} />
          </div>
          <div className="grid md:grid-cols-2 gap-4">
            <div className={card}><p className="text-xs font-semibold text-slate-400 mb-2">By queue</p><Bars data={Object.fromEntries(q.by_queue.map((r) => [r.queue, r.count]))} /></div>
            <div className={card}><p className="text-xs font-semibold text-slate-400 mb-2">By job type</p><Bars data={Object.fromEntries(q.by_type.map((r) => [r.job_type, r.count]))} /></div>
          </div>
        </div>
      ) : tab === 'rules' && ru ? (
        <div className="space-y-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <Stat label="Rules" value={ru.total} />
            <Stat label="Active" value={ru.active} />
            <Stat label="Evaluations" value={ru.evaluations} />
            <Stat label="Match rate" value={`${ru.match_rate}%`} />
          </div>
          <div className={card}>
            <p className="text-xs font-semibold text-slate-400 mb-2">Most-used rules</p>
            {ru.top_rules.length === 0 ? <p className="text-xs text-slate-500">No rule activity.</p> : (
              <table className="w-full text-xs">
                <thead className="text-slate-500"><tr><th className="text-left py-1">Rule</th><th className="text-right">Evals</th><th className="text-right">Matches</th><th className="text-right">Rate</th></tr></thead>
                <tbody>{ru.top_rules.map((r) => (
                  <tr key={r.id} className="border-t border-slate-800/60 text-slate-300"><td className="py-1">{r.name} <span className="text-slate-600">{r.entity_type}</span></td><td className="text-right">{r.evaluations}</td><td className="text-right">{r.matches}</td><td className="text-right">{r.match_rate}%</td></tr>
                ))}</tbody>
              </table>
            )}
          </div>
        </div>
      ) : tab === 'sla' && sla ? (
        <div className="space-y-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <Stat label="Tracked" value={sla.tracked} />
            <Stat label="Compliance" value={`${sla.compliance_rate}%`} tone="text-emerald-400" />
            <Stat label="Breached" value={sla.breached} tone={sla.breached ? 'text-red-400' : undefined} />
            <Stat label="Open breaches" value={sla.open_breaches} tone={sla.open_breaches ? 'text-red-400' : undefined} />
          </div>
          <div className="grid md:grid-cols-2 gap-4">
            <div className={card}><p className="text-xs font-semibold text-slate-400 mb-2">Breaches by metric</p><Bars data={sla.breaches_by_metric} empty="No breaches." /></div>
            <div className={card}><p className="text-xs font-semibold text-slate-400 mb-2">Breaches by entity</p><Bars data={sla.breaches_by_entity} empty="No breaches." /></div>
          </div>
        </div>
      ) : tab === 'escalation' && esc ? (
        <div className="space-y-4">
          <Stat label="Escalation events" value={esc.total} />
          <div className="grid md:grid-cols-3 gap-4">
            <div className={card}><p className="text-xs font-semibold text-slate-400 mb-2">By level</p><Bars data={esc.by_level} /></div>
            <div className={card}><p className="text-xs font-semibold text-slate-400 mb-2">By entity</p><Bars data={esc.by_entity} /></div>
            <div className={card}><p className="text-xs font-semibold text-slate-400 mb-2">By target</p><Bars data={esc.by_target} /></div>
          </div>
        </div>
      ) : tab === 'approval' && appr ? (
        <div className="space-y-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <Stat label="Total" value={appr.total} />
            <Stat label="Approval rate" value={`${appr.approval_rate}%`} tone="text-emerald-400" />
            <Stat label="Pending" value={appr.pending} />
            <Stat label="Avg decision" value={`${appr.avg_decision_hours}h`} />
          </div>
          <div className={card}><p className="text-xs font-semibold text-slate-400 mb-2">By request type</p><Bars data={appr.by_type} /></div>
        </div>
      ) : tab === 'trends' && tr ? (
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-400">Granularity</span>
            <select value={granularity} onChange={(e) => setGranularity(e.target.value)} className={F}>
              {['daily', 'weekly', 'monthly'].map((g) => <option key={g} value={g}>{g}</option>)}
            </select>
          </div>
          <div className={`${card} overflow-x-auto`}>
            <table className="w-full text-xs">
              <thead className="text-slate-500"><tr>
                <th className="text-left py-1">Bucket</th><th className="text-right">WF runs</th><th className="text-right">WF fails</th>
                <th className="text-right">Queue</th><th className="text-right">Jobs</th><th className="text-right">Escal.</th><th className="text-right">Approvals</th>
              </tr></thead>
              <tbody>
                {tr.series.length === 0 && <tr><td colSpan={7} className="py-6 text-center text-slate-500">No activity in range.</td></tr>}
                {tr.series.map((b: any) => (
                  <tr key={b.bucket} className="border-t border-slate-800/60 text-slate-300">
                    <td className="py-1">{b.bucket}</td><td className="text-right">{b.workflow_runs}</td>
                    <td className="text-right text-red-400">{b.workflow_failures}</td><td className="text-right">{b.queue_jobs}</td>
                    <td className="text-right">{b.automation_runs}</td><td className="text-right">{b.escalations}</td><td className="text-right">{b.approvals}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : tab === 'top' && top ? (
        <div className={card}>
          <p className="text-xs font-semibold text-slate-400 mb-2 flex items-center gap-1.5"><BarChart3 className="w-3.5 h-3.5" /> Busiest automations</p>
          {top.items.length === 0 ? <p className="text-xs text-slate-500">No automation activity in range.</p> : (
            <table className="w-full text-xs">
              <thead className="text-slate-500"><tr><th className="text-left py-1">Automation</th><th className="text-left">Kind</th><th className="text-right">Runs</th></tr></thead>
              <tbody>{top.items.map((i, idx) => (
                <tr key={idx} className="border-t border-slate-800/60 text-slate-300"><td className="py-1">{i.name}</td><td className="text-slate-500">{i.kind}</td><td className="text-right">{i.runs}</td></tr>
              ))}</tbody>
            </table>
          )}
        </div>
      ) : null}
    </div>
  );
};
