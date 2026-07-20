import React, { useCallback, useEffect, useState } from 'react';
import {
  Wand2, Loader2, Download, Lightbulb, AlertOctagon, Sparkles, Activity,
  CheckCircle2, XCircle, Gauge, ShieldCheck, Play, PlusCircle,
} from 'lucide-react';
import {
  workflowAssistantApi as api, WaSuggestion, WaAutomationSuggestion, WaRuleRecommendation,
  WaBottleneck, WaOptimization, WaGenerated, WaInsights, WaValidation,
} from '../services/workflowAssistantApi';
import { extractErrorMessage } from '../utils/errors';

const card = 'glass-panel border border-slate-800/85 rounded-xl p-4';
const F = 'w-full bg-slate-800/70 border border-slate-700/70 text-slate-200 py-1.5 px-2 rounded-lg text-xs';
const BTN = 'px-3 py-1.5 rounded-lg text-xs font-semibold bg-brand-500/20 text-brand-300 hover:bg-brand-500/30 cursor-pointer flex items-center gap-1.5';
const SEV: Record<string, string> = {
  high: 'bg-red-500/15 text-red-300', medium: 'bg-amber-500/15 text-amber-300', low: 'bg-slate-500/15 text-slate-300',
};

const downloadText = (name: string, text: string) => {
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([text], { type: 'text/csv' }));
  a.download = name; a.click(); URL.revokeObjectURL(a.href);
};

export const WorkflowAssistantPage: React.FC = () => {
  const [tab, setTab] = useState<'suggestions' | 'bottlenecks' | 'generate' | 'insights'>('suggestions');
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState('');
  const [ok, setOk] = useState('');

  const [sugg, setSugg] = useState<WaSuggestion[]>([]);
  const [auto, setAuto] = useState<WaAutomationSuggestion[]>([]);
  const [rules, setRules] = useState<WaRuleRecommendation[]>([]);
  const [bott, setBott] = useState<WaBottleneck[]>([]);
  const [opt, setOpt] = useState<WaOptimization[]>([]);
  const [ins, setIns] = useState<WaInsights | null>(null);
  const [validation, setValidation] = useState<WaValidation | null>(null);
  const [simResult, setSimResult] = useState<any | null>(null);

  const [prompt, setPrompt] = useState('');
  const [genName, setGenName] = useState('');
  const [gen, setGen] = useState<WaGenerated | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setLoading(true); setErr('');
    try {
      if (tab === 'suggestions') {
        const [s, a, r] = await Promise.all([api.suggestions(), api.automationSuggestions(), api.ruleRecommendations()]);
        setSugg(s.suggestions); setAuto(a.suggestions); setRules(r.recommendations);
      }
      if (tab === 'bottlenecks') {
        const [b, o] = await Promise.all([api.bottlenecks(), api.optimizations()]);
        setBott(b.bottlenecks); setOpt(o.optimizations);
      }
      if (tab === 'insights') setIns(await api.insights());
    } catch (e) { setErr(extractErrorMessage(e, 'Failed to load workflow assistant.')); } finally { setLoading(false); }
  }, [tab]);
  useEffect(() => { load(); }, [load]);

  const runGenerate = async (create: boolean) => {
    if (!prompt.trim()) return;
    setBusy(true); setErr(''); setOk('');
    try {
      const g = await api.generate(prompt, create, genName || undefined);
      setGen(g);
      if (create && g.created) setOk(`Draft workflow "${g.name}" created (disabled) — open Workflows to review & publish.`);
    } catch (e) { setErr(extractErrorMessage(e, 'Generation failed.')); } finally { setBusy(false); }
  };

  const checkWorkflow = async (id: string) => {
    setErr(''); setSimResult(null);
    try { setValidation(await api.validate(id)); }
    catch (e) { setErr(extractErrorMessage(e, 'Validation failed.')); }
  };

  const simulateWorkflow = async (id: string) => {
    setErr('');
    try { setSimResult(await api.simulate(id)); }
    catch (e) { setErr(extractErrorMessage(e, 'Simulation failed.')); }
  };

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div>
          <h1 className="text-2xl font-extrabold text-slate-100 flex items-center gap-2"><Wand2 className="w-6 h-6 text-brand-400" /> Workflow Assistant</h1>
          <p className="text-sm text-slate-500 mt-1">Data-driven workflow & rule suggestions, bottleneck detection, natural-language workflow generation, validation and execution insights.</p>
        </div>
        <button onClick={async () => { try { downloadText('workflow-assistant-report.csv', await api.exportCsv()); } catch (e) { setErr(extractErrorMessage(e, 'Export failed')); } }} className={BTN}><Download className="w-3.5 h-3.5" /> Export Report</button>
      </div>

      {err && <div className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">{err}</div>}
      {ok && <div className="text-xs text-emerald-300 bg-emerald-500/10 border border-emerald-500/20 rounded-lg px-3 py-2">{ok}</div>}

      <div className="flex items-center gap-1 bg-slate-900/50 border border-slate-800/70 rounded-xl p-1 w-fit">
        {([['suggestions', 'Suggestions', Lightbulb], ['bottlenecks', 'Bottlenecks', AlertOctagon], ['generate', 'Generate', Sparkles], ['insights', 'Insights', Activity]] as [any, string, any][]).map(([k, l, Icon]) => (
          <button key={k} onClick={() => setTab(k)} className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 cursor-pointer ${tab === k ? 'bg-brand-500/20 text-brand-300' : 'text-slate-400 hover:text-slate-200'}`}><Icon className="w-3.5 h-3.5" /> {l}</button>
        ))}
      </div>

      {loading && tab !== 'generate' ? <div className="py-20 text-center text-slate-400"><Loader2 className="w-6 h-6 animate-spin inline" /></div> : (
        <>
          {tab === 'suggestions' && (
            <div className="space-y-4">
              <div className={card}>
                <h3 className="text-xs font-bold text-slate-300 mb-2 flex items-center gap-1.5"><Lightbulb className="w-3.5 h-3.5 text-brand-400" /> Workflow Suggestions</h3>
                {sugg.length === 0 ? <p className="text-xs text-slate-500">No suggestions — your automation coverage looks healthy.</p> :
                  sugg.map(s => (
                    <div key={s.key} className="py-2 border-b border-slate-800/60 last:border-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${SEV[s.impact]}`}>{s.impact}</span>
                        <span className="text-xs text-slate-200 font-semibold">{s.title}</span>
                        <span className="text-[10px] text-slate-500">on {s.trigger_event}</span>
                        {s.already_covered && <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/15 text-emerald-300">trigger already covered</span>}
                      </div>
                      <p className="text-[11px] text-slate-400 mt-1">{s.reason}</p>
                    </div>
                  ))}
              </div>
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <div className={card}>
                  <h3 className="text-xs font-bold text-slate-300 mb-2">Automation Suggestions</h3>
                  {auto.length === 0 ? <p className="text-xs text-slate-500">Queue, campaigns and schedules look fine.</p> :
                    auto.map(s => (
                      <div key={s.key} className="py-2 border-b border-slate-800/60 last:border-0">
                        <div className="flex items-center gap-2"><span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${SEV[s.impact]}`}>{s.impact}</span><span className="text-xs text-slate-200 font-semibold">{s.title}</span><span className="text-[10px] text-slate-500">{s.area}</span></div>
                        <p className="text-[11px] text-slate-400 mt-1">{s.reason}</p>
                      </div>
                    ))}
                </div>
                <div className={card}>
                  <h3 className="text-xs font-bold text-slate-300 mb-2">Rule Recommendations</h3>
                  {rules.length === 0 ? <p className="text-xs text-slate-500">Not enough signal yet for rule recommendations.</p> :
                    rules.map(r => (
                      <div key={r.key} className="py-2 border-b border-slate-800/60 last:border-0">
                        <div className="flex items-center gap-2"><span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${SEV[r.impact]}`}>{r.impact}</span><span className="text-xs text-slate-200 font-semibold">{r.title}</span></div>
                        <p className="text-[11px] text-slate-400 mt-1">{r.reason}</p>
                        <p className="text-[10px] text-brand-300 mt-0.5">→ {r.suggested_action}</p>
                      </div>
                    ))}
                </div>
              </div>
            </div>
          )}

          {tab === 'bottlenecks' && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <div className={card}>
                <h3 className="text-xs font-bold text-slate-300 mb-2 flex items-center gap-1.5"><AlertOctagon className="w-3.5 h-3.5 text-red-400" /> Bottlenecks</h3>
                {bott.length === 0 ? <p className="text-xs text-slate-500">No bottlenecks detected across workflows, queue, approvals, SLA or pipeline.</p> :
                  bott.map((b, i) => (
                    <div key={i} className="py-2 border-b border-slate-800/60 last:border-0">
                      <div className="flex items-center gap-2"><span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${SEV[b.severity]}`}>{b.severity}</span><span className="text-xs text-slate-200 font-semibold">{b.title}</span><span className="text-[10px] text-slate-500">{b.area}</span></div>
                      <p className="text-[11px] text-slate-400 mt-1">{b.evidence}</p>
                      <p className="text-[10px] text-brand-300 mt-0.5">→ {b.recommendation}</p>
                    </div>
                  ))}
              </div>
              <div className={card}>
                <h3 className="text-xs font-bold text-slate-300 mb-2 flex items-center gap-1.5"><Gauge className="w-3.5 h-3.5 text-amber-400" /> Optimization Suggestions</h3>
                {opt.length === 0 ? <p className="text-xs text-slate-500">Workflow hygiene is clean.</p> :
                  opt.map((o, i) => (
                    <div key={i} className="py-2 border-b border-slate-800/60 last:border-0">
                      <p className="text-xs text-slate-200 font-semibold">{o.workflow || 'Org-wide'} <span className="text-[10px] text-slate-500 font-normal">({o.kind.replace(/_/g, ' ')})</span></p>
                      <p className="text-[11px] text-slate-400 mt-0.5">{o.advice}</p>
                      {o.workflow_id && (
                        <div className="flex gap-2 mt-1">
                          <button onClick={() => checkWorkflow(o.workflow_id!)} className="text-[10px] text-brand-300 cursor-pointer flex items-center gap-1"><ShieldCheck className="w-3 h-3" /> Validate</button>
                          <button onClick={() => simulateWorkflow(o.workflow_id!)} className="text-[10px] text-sky-300 cursor-pointer flex items-center gap-1"><Play className="w-3 h-3" /> Simulate</button>
                        </div>
                      )}
                    </div>
                  ))}
              </div>
              {validation && (
                <div className={`${card} lg:col-span-2`}>
                  <h3 className="text-xs font-bold text-slate-300 mb-2 flex items-center gap-1.5">
                    {validation.valid ? <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" /> : <XCircle className="w-3.5 h-3.5 text-red-400" />}
                    Validation — {validation.name} · Health {validation.health_score}/100 · {validation.runs_30d} runs (30d)
                  </h3>
                  {validation.errors.map((e, i) => <p key={i} className="text-[11px] text-red-300">✗ {e}</p>)}
                  {validation.warnings.map((w, i) => <p key={i} className="text-[11px] text-amber-300">⚠ {w}</p>)}
                  {validation.valid && validation.warnings.length === 0 && <p className="text-[11px] text-emerald-300">Structurally valid with no warnings.</p>}
                </div>
              )}
              {simResult && (
                <div className={`${card} lg:col-span-2`}>
                  <h3 className="text-xs font-bold text-slate-300 mb-2 flex items-center gap-1.5"><Play className="w-3.5 h-3.5 text-sky-400" /> Simulation (test mode — nothing was mutated)</h3>
                  <p className="text-[11px] text-slate-400">Status: {simResult.status} · steps run: {simResult.steps_run}</p>
                  {(simResult.steps || simResult.logs || []).slice(0, 12).map((s: any, i: number) => (
                    <p key={i} className="text-[11px] text-slate-400">• [{s.status}] {s.node_type}{s.action_type ? `/${s.action_type}` : ''} — {s.detail}</p>
                  ))}
                </div>
              )}
            </div>
          )}

          {tab === 'generate' && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <div className={card}>
                <h3 className="text-xs font-bold text-slate-300 mb-2 flex items-center gap-1.5"><Sparkles className="w-3.5 h-3.5 text-brand-400" /> Describe the workflow in plain English</h3>
                <textarea value={prompt} onChange={e => setPrompt(e.target.value)} rows={4} className={F}
                  placeholder={'e.g. "When a new lead comes in with value over 50000, send an email saying \'Thanks, we\'ll call you shortly\' and create a task to call them"'} />
                <input value={genName} onChange={e => setGenName(e.target.value)} placeholder="Workflow name (optional)" className={`${F} mt-2`} />
                <div className="flex gap-2 mt-2">
                  <button disabled={busy} onClick={() => runGenerate(false)} className={BTN}>{busy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Wand2 className="w-3.5 h-3.5" />} Preview</button>
                  <button disabled={busy} onClick={() => runGenerate(true)} className={BTN}><PlusCircle className="w-3.5 h-3.5" /> Create Draft</button>
                </div>
                <p className="text-[10px] text-slate-500 mt-2">Drafts are created disabled — review, assign users where needed and publish from the Workflows page.</p>
              </div>
              <div className={card}>
                <h3 className="text-xs font-bold text-slate-300 mb-2">Generated Workflow</h3>
                {!gen ? <p className="text-xs text-slate-500 py-8 text-center">The parsed trigger, conditions and actions will appear here.</p> : (
                  <div className="space-y-1.5">
                    <p className="text-xs text-slate-200 font-semibold">{gen.name} <span className="text-[10px] text-slate-500 font-normal">({gen.status})</span></p>
                    {gen.explanation.map((l, i) => <p key={i} className="text-[11px] text-slate-400">• {l}</p>)}
                    <p className="text-[10px] text-slate-500 mt-1">{gen.graph.nodes.length} nodes · {gen.graph.edges.length} edges · trigger {gen.trigger_event} on {gen.entity_type}</p>
                  </div>
                )}
              </div>
            </div>
          )}

          {tab === 'insights' && ins && (
            <div className="space-y-4">
              <div className="grid grid-cols-3 gap-3">
                <div className={card}><p className="text-[10px] font-semibold text-slate-500 uppercase">Runs (30d)</p><p className="text-xl font-bold text-slate-100 mt-1">{ins.totals.runs}</p></div>
                <div className={card}><p className="text-[10px] font-semibold text-slate-500 uppercase">Failed</p><p className="text-xl font-bold text-red-400 mt-1">{ins.totals.failed}</p></div>
                <div className={card}><p className="text-[10px] font-semibold text-slate-500 uppercase">Success Rate</p><p className="text-xl font-bold text-emerald-400 mt-1">{ins.totals.success_rate}%</p></div>
              </div>
              <div className={card}>
                <h3 className="text-xs font-bold text-slate-300 mb-2">Per-Workflow Execution Insights</h3>
                {ins.workflows.length === 0 ? <p className="text-xs text-slate-500">No live executions in the last 30 days.</p> : (
                  <table className="w-full text-xs">
                    <thead><tr className="text-left text-[10px] uppercase text-slate-500 border-b border-slate-800/70">
                      <th className="py-2 pr-2">Workflow</th><th className="pr-2">Runs</th><th className="pr-2">Failed</th><th className="pr-2">Success</th><th className="pr-2">Avg Duration</th><th className="pr-2">Actions</th>
                    </tr></thead>
                    <tbody>
                      {ins.workflows.map(w => (
                        <tr key={w.workflow_id} className="border-b border-slate-800/50 last:border-0">
                          <td className="py-2 pr-2 text-slate-200 font-medium">{w.workflow}</td>
                          <td className="pr-2 text-slate-400">{w.runs_30d}</td>
                          <td className="pr-2 text-red-400">{w.failed}</td>
                          <td className="pr-2 text-emerald-400">{w.success_rate}%</td>
                          <td className="pr-2 text-slate-400">{w.avg_duration_s != null ? `${w.avg_duration_s}s` : '—'}</td>
                          <td className="pr-2">
                            <span className="flex gap-2">
                              <button onClick={() => checkWorkflow(w.workflow_id)} className="text-[10px] text-brand-300 cursor-pointer">Validate</button>
                              <button onClick={() => simulateWorkflow(w.workflow_id)} className="text-[10px] text-sky-300 cursor-pointer">Simulate</button>
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
              {validation && (
                <div className={card}>
                  <h3 className="text-xs font-bold text-slate-300 mb-2">Validation — {validation.name} · Health {validation.health_score}/100</h3>
                  {validation.errors.map((e, i) => <p key={i} className="text-[11px] text-red-300">✗ {e}</p>)}
                  {validation.warnings.map((w, i) => <p key={i} className="text-[11px] text-amber-300">⚠ {w}</p>)}
                  {validation.valid && validation.warnings.length === 0 && <p className="text-[11px] text-emerald-300">Structurally valid with no warnings.</p>}
                </div>
              )}
              {simResult && (
                <div className={card}>
                  <h3 className="text-xs font-bold text-slate-300 mb-2">Simulation Result</h3>
                  <p className="text-[11px] text-slate-400">Status: {simResult.status} · steps run: {simResult.steps_run}</p>
                  {(simResult.steps || simResult.logs || []).slice(0, 12).map((s: any, i: number) => (
                    <p key={i} className="text-[11px] text-slate-400">• [{s.status}] {s.node_type}{s.action_type ? `/${s.action_type}` : ''} — {s.detail}</p>
                  ))}
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
};
