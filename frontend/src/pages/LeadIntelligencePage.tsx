import React, { useCallback, useEffect, useState } from 'react';
import {
  Brain, Loader2, Download, LayoutDashboard, ListChecks, X, Flame, Snowflake, Thermometer,
  AlertTriangle, Sparkles, Copy, Wand2, TrendingUp, Target,
} from 'lucide-react';
import {
  leadIntelligenceApi as api, LeadIntelDashboard, LeadIntelligence,
} from '../services/leadIntelligenceApi';
import { extractErrorMessage } from '../utils/errors';

const card = 'glass-panel border border-slate-800/85 rounded-xl p-4';
const F = 'bg-slate-800/70 border border-slate-700/70 text-slate-200 py-1.5 px-2 rounded-lg text-xs';
const TEMP_TONE: Record<string, string> = { hot: 'text-red-400', warm: 'text-amber-400', cold: 'text-sky-400' };
const TEMP_ICON: Record<string, any> = { hot: Flame, warm: Thermometer, cold: Snowflake };
const GRADE_TONE: Record<string, string> = { A: 'bg-emerald-500/15 text-emerald-300', B: 'bg-sky-500/15 text-sky-300', C: 'bg-amber-500/15 text-amber-300', D: 'bg-red-500/15 text-red-300' };
const PRIORITY_TONE: Record<string, string> = { high: 'text-red-300', medium: 'text-amber-300', low: 'text-slate-400' };

const downloadText = (name: string, text: string) => {
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([text], { type: 'text/csv' }));
  a.download = name;
  a.click();
  URL.revokeObjectURL(a.href);
};

export const LeadIntelligencePage: React.FC = () => {
  const [tab, setTab] = useState<'dashboard' | 'leads'>('dashboard');
  const [dash, setDash] = useState<LeadIntelDashboard | null>(null);
  const [rows, setRows] = useState<LeadIntelligence[]>([]);
  const [temperature, setTemperature] = useState('');
  const [sort, setSort] = useState('opportunity');
  const [detail, setDetail] = useState<LeadIntelligence | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState('');

  const load = useCallback(async () => {
    setLoading(true); setErr('');
    try {
      if (tab === 'dashboard') setDash(await api.dashboard());
      else setRows((await api.list({ temperature: temperature || undefined, sort })).rows);
    } catch (e) { setErr(extractErrorMessage(e, 'Failed to load lead intelligence.')); } finally { setLoading(false); }
  }, [tab, temperature, sort]);
  useEffect(() => { load(); }, [load]);

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div>
          <h1 className="text-2xl font-extrabold text-slate-100 flex items-center gap-2"><Brain className="w-6 h-6 text-brand-400" /> Lead Intelligence</h1>
          <p className="text-sm text-slate-500 mt-1">Scoring, temperature, quality, conversion prediction, risk & next best action for every lead.</p>
        </div>
        <button onClick={async () => { try { downloadText('lead-intelligence.csv', await api.exportCsv()); } catch (e) { setErr(extractErrorMessage(e, 'Export failed')); } }} className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-brand-500/20 text-brand-300 hover:bg-brand-500/30 cursor-pointer flex items-center gap-1.5"><Download className="w-3.5 h-3.5" /> Export CSV</button>
      </div>

      {err && <div className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">{err}</div>}

      <div className="flex items-center gap-1 bg-slate-900/50 border border-slate-800/70 rounded-xl p-1 w-fit">
        {([['dashboard', 'Dashboard', LayoutDashboard], ['leads', 'Ranked Leads', ListChecks]] as [any, string, any][]).map(([k, l, Icon]) => (
          <button key={k} onClick={() => setTab(k)} className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 cursor-pointer ${tab === k ? 'bg-brand-500/20 text-brand-300' : 'text-slate-400 hover:text-slate-200'}`}><Icon className="w-3.5 h-3.5" /> {l}</button>
        ))}
      </div>

      {loading ? (
        <div className="py-20 text-center text-slate-400"><Loader2 className="w-6 h-6 animate-spin inline" /></div>
      ) : tab === 'dashboard' && dash ? (
        <div className="space-y-4">
          <div className="grid grid-cols-2 md:grid-cols-6 gap-3">
            <div className={card}><p className="text-[10px] font-semibold text-slate-500 uppercase">Leads</p><p className="text-xl font-bold text-slate-100 mt-1">{dash.total}</p></div>
            <div className={card}><p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><Flame className="w-3 h-3 text-red-400" /> Hot</p><p className="text-xl font-bold text-red-400 mt-1">{dash.by_temperature.hot || 0}</p></div>
            <div className={card}><p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><Snowflake className="w-3 h-3 text-sky-400" /> Cold</p><p className="text-xl font-bold text-sky-400 mt-1">{dash.by_temperature.cold || 0}</p></div>
            <div className={card}><p className="text-[10px] font-semibold text-slate-500 uppercase">Avg score</p><p className="text-xl font-bold text-slate-100 mt-1">{dash.avg_score}</p></div>
            <div className={card}><p className="text-[10px] font-semibold text-slate-500 uppercase">Avg complete</p><p className="text-xl font-bold text-slate-100 mt-1">{dash.avg_completeness}%</p></div>
            <div className={card}><p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><TrendingUp className="w-3 h-3 text-emerald-400" /> Avg conv.</p><p className="text-xl font-bold text-emerald-400 mt-1">{dash.avg_conversion_probability}%</p></div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <IntelList title="Hottest leads" icon={Flame} rows={dash.hot_leads} onOpen={setDetail} metric="opportunity_score" suffix="" />
            <IntelList title="At risk" icon={AlertTriangle} rows={dash.at_risk_leads} onOpen={setDetail} metric="risk_score" suffix="" />
            <IntelList title="Needs enrichment" icon={Wand2} rows={dash.needs_enrichment} onOpen={setDetail} metric="completeness_pct" suffix="%" />
          </div>
        </div>
      ) : tab === 'leads' ? (
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <select value={temperature} onChange={(e) => setTemperature(e.target.value)} className={F}>
              <option value="">All temperatures</option>
              <option value="hot">Hot</option><option value="warm">Warm</option><option value="cold">Cold</option>
            </select>
            <select value={sort} onChange={(e) => setSort(e.target.value)} className={F}>
              <option value="opportunity">Sort: opportunity</option>
              <option value="score">Sort: score</option>
              <option value="probability">Sort: conversion</option>
              <option value="risk">Sort: risk</option>
            </select>
          </div>
          {rows.length === 0 && <p className="text-sm text-slate-500">No leads match.</p>}
          {rows.map((r) => <LeadRow key={r.lead_id} r={r} onOpen={() => setDetail(r)} />)}
        </div>
      ) : null}

      {detail && <DetailModal lead={detail} onClose={() => setDetail(null)} setErr={setErr} />}
    </div>
  );
};

const IntelList: React.FC<{ title: string; icon: any; rows: LeadIntelligence[]; onOpen: (r: LeadIntelligence) => void; metric: string; suffix: string }> =
  ({ title, icon: Icon, rows, onOpen, metric }) => (
    <div className={card}>
      <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2 flex items-center gap-1.5"><Icon className="w-3.5 h-3.5 text-brand-400" /> {title}</p>
      {rows.length === 0 ? <p className="text-xs text-slate-500">Nothing here.</p> :
        rows.map((r) => (
          <button key={r.lead_id} onClick={() => onOpen(r)} className="w-full text-left py-1.5 border-b border-slate-800/50 last:border-0 cursor-pointer">
            <p className="text-sm text-slate-200 truncate">{r.name}</p>
            <p className="text-[10px] text-slate-500">{metric === 'completeness_pct' ? `${r.completeness.pct}% complete` : metric === 'risk_score' ? `risk ${r.risk_score}` : `opp ${r.opportunity_score} · ${r.conversion_probability}%`}</p>
          </button>
        ))}
    </div>
  );

const LeadRow: React.FC<{ r: LeadIntelligence; onOpen: () => void }> = ({ r, onOpen }) => {
  const TIcon = TEMP_ICON[r.temperature] || Thermometer;
  return (
    <button onClick={onOpen} className="w-full glass-panel border border-slate-800/85 rounded-xl p-3 flex items-center gap-3 text-left cursor-pointer hover:border-brand-500/30">
      <div className="flex flex-col items-center w-14 shrink-0">
        <span className="text-lg font-extrabold text-slate-100">{r.opportunity_score}</span>
        <span className="text-[9px] text-slate-500 uppercase">opp</span>
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-sm font-semibold text-slate-100 truncate">{r.name}</span>
          <span className={`text-[11px] font-semibold flex items-center gap-1 ${TEMP_TONE[r.temperature]}`}><TIcon className="w-3 h-3" /> {r.temperature}</span>
          <span className={`px-1.5 py-0.5 text-[10px] rounded ${GRADE_TONE[r.quality_grade]}`}>Q{r.quality_grade}</span>
          <span className="text-[10px] text-slate-500">{r.status} · ₹{Math.round(r.value).toLocaleString()}</span>
        </div>
        <p className="text-[11px] text-slate-500 mt-0.5 truncate">score {r.score} · {r.conversion_probability}% conv · risk {r.risk_score} · {r.completeness.pct}% complete · {r.next_best_action.action}</p>
      </div>
    </button>
  );
};

const DetailModal: React.FC<{ lead: LeadIntelligence; onClose: () => void; setErr: (s: string) => void }> = ({ lead, onClose, setErr }) => {
  const [full, setFull] = useState<LeadIntelligence>(lead);
  const [summary, setSummary] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => { api.lead(lead.lead_id).then(setFull).catch(() => {}); }, [lead.lead_id]);
  const genSummary = async () => {
    setBusy(true);
    try { setSummary((await api.summary(lead.lead_id)).text); }
    catch (e) { setErr(extractErrorMessage(e, 'Summary failed')); } finally { setBusy(false); }
  };
  const TIcon = TEMP_ICON[full.temperature] || Thermometer;
  return (
    <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4" onClick={onClose}>
      <div className="glass-panel border border-slate-800 rounded-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto p-5 bg-slate-900" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-bold text-slate-100 flex items-center gap-2"><Brain className="w-4 h-4 text-brand-400" /> {full.name}
            <span className={`text-[11px] font-semibold flex items-center gap-1 ${TEMP_TONE[full.temperature]}`}><TIcon className="w-3 h-3" /> {full.temperature}</span>
            <span className={`px-1.5 py-0.5 text-[10px] rounded ${GRADE_TONE[full.quality_grade]}`}>Quality {full.quality_grade}</span>
          </h3>
          <button onClick={onClose} className="text-slate-500 hover:text-slate-300 cursor-pointer"><X className="w-4 h-4" /></button>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-3">
          {[['Score', `${full.score} (${full.score_grade})`], ['Conversion', `${full.conversion_probability}%`], ['Opportunity', full.opportunity_score], ['Risk', full.risk_score]].map(([l, v]) => (
            <div key={l as string} className="bg-slate-950/40 border border-slate-800/60 rounded-lg p-2.5"><p className="text-[10px] text-slate-500 uppercase font-semibold">{l}</p><p className="text-lg font-bold text-slate-100">{v}</p></div>
          ))}
        </div>

        <div className={`${card} mb-3`}>
          <p className="text-xs font-semibold text-slate-400 uppercase mb-1.5 flex items-center gap-1.5"><Target className="w-3.5 h-3.5 text-brand-400" /> Next best action</p>
          <p className="text-sm text-slate-200">{full.next_best_action.action} <span className={`text-[10px] ${PRIORITY_TONE[full.next_best_action.priority]}`}>({full.next_best_action.priority})</span></p>
          <p className="text-[11px] text-slate-500">{full.next_best_action.reason}</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-3">
          <div className={card}>
            <p className="text-xs font-semibold text-slate-400 uppercase mb-1.5">Conversion factors</p>
            {full.conversion_factors.map((f, i) => (
              <div key={i} className="flex items-center justify-between text-[11px] py-0.5">
                <span className="text-slate-400">{f.factor}</span>
                <span className={f.points >= 0 ? 'text-emerald-400' : 'text-red-400'}>{f.points > 0 ? '+' : ''}{f.points}</span>
              </div>
            ))}
          </div>
          <div className={card}>
            <p className="text-xs font-semibold text-slate-400 uppercase mb-1.5">Insights</p>
            {full.insights.map((s, i) => <p key={i} className="text-[11px] text-slate-300 py-0.5">{s}</p>)}
            {full.risk_reasons.length > 0 && <p className="text-[11px] text-red-300 mt-1">Risk: {full.risk_reasons.join('; ')}</p>}
          </div>
        </div>

        {full.completeness.missing.length > 0 && (
          <div className={`${card} mb-3`}>
            <p className="text-xs font-semibold text-slate-400 uppercase mb-1.5 flex items-center gap-1.5"><Wand2 className="w-3.5 h-3.5 text-amber-400" /> Enrichment ({full.completeness.pct}% complete)</p>
            {full.enrichment_suggestions.map((e) => (
              <p key={e.field} className="text-[11px] text-slate-400 py-0.5"><span className="text-amber-300">{e.field}</span> — {e.suggestion}</p>
            ))}
          </div>
        )}

        {full.duplicate_suggestions && full.duplicate_suggestions.length > 0 && (
          <div className={`${card} mb-3`}>
            <p className="text-xs font-semibold text-slate-400 uppercase mb-1.5 flex items-center gap-1.5"><Copy className="w-3.5 h-3.5 text-red-400" /> Possible duplicates</p>
            {full.duplicate_suggestions.map((d) => (
              <div key={d.lead_id} className="flex items-center justify-between text-[11px] py-0.5">
                <span className="text-slate-300">{d.name}</span>
                <span className="text-slate-500">{d.match_on.join(', ')} · <span className={d.confidence === 'high' ? 'text-red-400' : 'text-amber-400'}>{d.confidence}</span></span>
              </div>
            ))}
          </div>
        )}

        <div className={card}>
          <div className="flex items-center justify-between mb-1.5">
            <p className="text-xs font-semibold text-slate-400 uppercase flex items-center gap-1.5"><Sparkles className="w-3.5 h-3.5 text-brand-400" /> AI summary</p>
            {!summary && <button onClick={genSummary} disabled={busy} className="text-xs text-brand-400 hover:text-brand-300 cursor-pointer flex items-center gap-1">{busy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5" />} Generate</button>}
          </div>
          {summary ? <p className="text-sm text-slate-200 whitespace-pre-wrap">{summary}</p> : <p className="text-[11px] text-slate-500">Generate an AI summary of this lead via the AI Platform.</p>}
        </div>
      </div>
    </div>
  );
};
