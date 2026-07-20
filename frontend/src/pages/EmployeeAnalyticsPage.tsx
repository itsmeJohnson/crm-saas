import React, { useCallback, useEffect, useState } from 'react';
import {
  Users, Loader2, Download, Trophy, Grid3x3, GitCompareArrows, Table2, GraduationCap,
  X, Plus, Trash2, CalendarClock,
} from 'lucide-react';
import {
  employeeAnalyticsApi as api, Roster, EmployeeRow, EmployeeDetail, ManagerComparison,
  Heatmap, AttendanceTrend, Training, EMP_METRICS,
} from '../services/employeeAnalyticsApi';
import { extractErrorMessage } from '../utils/errors';

const F = 'bg-slate-800/70 border border-slate-700/70 text-slate-200 py-1.5 px-2 rounded-lg text-xs';
const card = 'glass-panel border border-slate-800/85 rounded-xl p-4';
const cur = (n: any) => (typeof n === 'number' ? `₹${Math.round(n).toLocaleString()}` : '—');
const scoreTone = (n: number) => (n >= 70 ? 'text-emerald-400' : n >= 40 ? 'text-amber-400' : 'text-red-400');

type Tab = 'roster' | 'comparison' | 'leaderboard' | 'heatmap' | 'attendance';

export const EmployeeAnalyticsPage: React.FC = () => {
  const [tab, setTab] = useState<Tab>('roster');
  const [from, setFrom] = useState('');
  const [to, setTo] = useState('');
  const [metric, setMetric] = useState('leads_converted');
  const [dim, setDim] = useState<'department' | 'branch'>('department');
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState('');

  const [roster, setRoster] = useState<Roster | null>(null);
  const [mgrCmp, setMgrCmp] = useState<ManagerComparison | null>(null);
  const [structCmp, setStructCmp] = useState<{ rows: any[] } | null>(null);
  const [lb, setLb] = useState<any[]>([]);
  const [hm, setHm] = useState<Heatmap | null>(null);
  const [att, setAtt] = useState<AttendanceTrend | null>(null);
  const [detail, setDetail] = useState<EmployeeDetail | null>(null);

  const range = () => ({ date_from: from || undefined, date_to: to || undefined });

  const load = useCallback(async () => {
    setLoading(true); setErr('');
    const p = { date_from: from || undefined, date_to: to || undefined };
    try {
      if (tab === 'roster') setRoster(await api.roster(p));
      else if (tab === 'comparison') { setMgrCmp(await api.managerComparison(p)); setStructCmp(await api.comparison(dim, p)); }
      else if (tab === 'leaderboard') setLb(await api.leaderboard({ ...p, metric }));
      else if (tab === 'heatmap') setHm(await api.heatmap(p));
      else if (tab === 'attendance') setAtt(await api.attendanceTrend(p));
    } catch (e) { setErr(extractErrorMessage(e, 'Failed to load employee analytics.')); } finally { setLoading(false); }
  }, [tab, from, to, metric, dim]);
  useEffect(() => { load(); }, [load]);

  const exportCsv = async () => {
    try {
      const blob = await api.exportCsv(range());
      const url = URL.createObjectURL(blob); const a = document.createElement('a');
      a.href = url; a.download = 'employee-analytics.csv'; a.click(); URL.revokeObjectURL(url);
    } catch (e) { setErr(extractErrorMessage(e, 'Export failed.')); }
  };
  const openDetail = async (row: EmployeeRow) => {
    try { setDetail(await api.employee(row.user_id, range())); } catch (e) { setErr(extractErrorMessage(e, 'Failed.')); }
  };

  const TABS: [Tab, string, any][] = [
    ['roster', 'Roster', Table2], ['comparison', 'Comparisons', GitCompareArrows],
    ['leaderboard', 'Leaderboards', Trophy], ['heatmap', 'Heat Map', Grid3x3], ['attendance', 'Attendance', CalendarClock],
  ];
  const heatColor = (v: number, max: number) => (!v ? 'rgba(148,163,184,0.06)' : `rgba(99,102,241,${0.15 + Math.min(1, v / max) * 0.65})`);

  return (
    <div className="space-y-5">
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-extrabold text-slate-100 flex items-center gap-2"><Users className="w-6 h-6 text-brand-400" /> Employee Analytics</h1>
          <p className="text-sm text-slate-500 mt-1">Workforce productivity, attendance, task/call/lead output, training and comparisons.</p>
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
          <button key={k} onClick={() => setTab(k)} className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 cursor-pointer ${tab === k ? 'bg-brand-500/20 text-brand-300' : 'text-slate-400 hover:text-slate-200'}`}><Icon className="w-3.5 h-3.5" /> {label}</button>
        ))}
      </div>

      {err && <div className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">{err}</div>}

      {loading ? (
        <div className="py-20 text-center text-slate-400"><Loader2 className="w-6 h-6 animate-spin inline" /></div>
      ) : tab === 'roster' && roster ? (
        <div className={`${card} overflow-x-auto`}>
          <p className="text-xs text-slate-500 mb-2">{roster.headcount} employees · {roster.from} → {roster.to} · click a row for detail</p>
          <table className="w-full text-xs">
            <thead className="text-slate-500"><tr>
              <th className="text-left py-1">Employee</th><th className="text-right px-2">Productivity</th><th className="text-right px-2">Leads won</th>
              <th className="text-right px-2">Calls</th><th className="text-right px-2">Task %</th><th className="text-right px-2">Attend %</th>
              <th className="text-right px-2">Leave</th><th className="text-right px-2">Training</th>
            </tr></thead>
            <tbody>
              {roster.employees.map((e) => (
                <tr key={e.user_id} onClick={() => openDetail(e)} className="border-t border-slate-800/60 text-slate-300 hover:bg-slate-800/30 cursor-pointer">
                  <td className="py-1.5">{e.name} <span className="text-slate-600">{e.role}</span></td>
                  <td className={`text-right px-2 font-bold ${scoreTone(e.productivity_score)}`}>{e.productivity_score}</td>
                  <td className="text-right px-2">{e.leads_converted}</td><td className="text-right px-2">{e.calls}</td>
                  <td className="text-right px-2">{e.task_completion_rate}%</td><td className="text-right px-2">{e.attendance_rate}%</td>
                  <td className="text-right px-2">{e.leave_days}</td><td className="text-right px-2">{e.training_score || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : tab === 'comparison' ? (
        <div className="space-y-4">
          <div className={`${card} overflow-x-auto`}>
            <p className="text-xs font-semibold text-slate-400 mb-2">Manager comparison</p>
            <table className="w-full text-xs">
              <thead className="text-slate-500"><tr><th className="text-left py-1">Manager</th><th className="text-right px-2">Team</th><th className="text-right px-2">Leads won</th><th className="text-right px-2">Calls</th><th className="text-right px-2">Revenue</th><th className="text-right px-2">Avg task %</th><th className="text-right px-2">Avg attend %</th></tr></thead>
              <tbody>
                {(mgrCmp?.managers || []).length === 0 && <tr><td colSpan={7} className="py-4 text-center text-slate-500">No managers with teams.</td></tr>}
                {(mgrCmp?.managers || []).map((m) => (
                  <tr key={m.manager_id} className="border-t border-slate-800/60 text-slate-300"><td className="py-1.5">{m.manager_name}</td><td className="text-right px-2">{m.team_size}</td><td className="text-right px-2">{m.leads_converted}</td><td className="text-right px-2">{m.calls}</td><td className="text-right px-2 text-emerald-400">{cur(m.revenue)}</td><td className="text-right px-2">{m.avg_task_completion}%</td><td className="text-right px-2">{m.avg_attendance}%</td></tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className={card}>
            <div className="flex items-center justify-between mb-2">
              <p className="text-xs font-semibold text-slate-400">Structure comparison</p>
              <select value={dim} onChange={(e) => setDim(e.target.value as any)} className={F}><option value="department">Department</option><option value="branch">Branch</option></select>
            </div>
            {(structCmp?.rows || []).length === 0 ? <p className="text-xs text-slate-500">No {dim} data.</p> : (
              <div className="space-y-1.5">
                {structCmp!.rows.map((r: any, i: number) => (
                  <div key={i} className="flex items-center justify-between text-xs border-b border-slate-800/40 pb-1">
                    <span className="text-slate-300">{r.name || r.label || r.department || `#${i + 1}`}</span>
                    <span className="text-slate-500">{[r.headcount != null ? `${r.headcount} ppl` : null, r.leads != null ? `${r.leads} leads` : null, r.revenue != null ? cur(r.revenue) : null].filter(Boolean).join(' · ') || '—'}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      ) : tab === 'leaderboard' ? (
        <div className={card}>
          <div className="flex items-center justify-between mb-3">
            <p className="text-xs font-semibold text-slate-400 flex items-center gap-1.5"><Trophy className="w-3.5 h-3.5 text-amber-400" /> Leaderboard</p>
            <select value={metric} onChange={(e) => setMetric(e.target.value)} className={F}>{EMP_METRICS.map((m) => <option key={m} value={m}>{m.replace(/_/g, ' ')}</option>)}</select>
          </div>
          {lb.length === 0 ? <p className="text-xs text-slate-500">No data.</p> : (
            <ul className="space-y-1.5">
              {lb.map((r: any, i: number) => (
                <li key={r.user_id || i} className="flex items-center gap-3 p-2 bg-slate-950/40 border border-slate-800/60 rounded-lg">
                  <span className="text-xs font-bold text-slate-500 w-6">#{r.rank ?? i + 1}</span>
                  <span className="text-sm text-slate-200 flex-1 truncate">{r.name}</span>
                  <span className="text-sm font-bold text-brand-300">{typeof r.value === 'number' ? r.value.toLocaleString() : r.value}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      ) : tab === 'heatmap' && hm ? (
        <div className={`${card} overflow-x-auto`}>
          <p className="text-xs font-semibold text-slate-400 mb-3">Activity heat map · weekday × hour {hm.peak.count > 0 && <span className="text-slate-500">· peak {hm.peak.weekday_label} {hm.peak.hour}:00 ({hm.peak.count})</span>}</p>
          {(() => { const max = Math.max(1, ...hm.grid.flat()); return (
            <table className="text-[9px] border-separate" style={{ borderSpacing: 2 }}>
              <thead><tr><th></th>{Array.from({ length: 24 }).map((_, h) => <th key={h} className="text-slate-600 font-normal">{h % 3 === 0 ? h : ''}</th>)}</tr></thead>
              <tbody>
                {hm.grid.map((row, wd) => (
                  <tr key={wd}><td className="text-slate-500 pr-1 text-right">{hm.weekdays[wd]}</td>
                    {row.map((v, h) => <td key={h} title={`${hm.weekdays[wd]} ${h}:00 — ${v}`} style={{ background: heatColor(v, max), width: 14, height: 14 }} className="rounded-sm"></td>)}
                  </tr>
                ))}
              </tbody>
            </table>
          ); })()}
        </div>
      ) : tab === 'attendance' && att ? (
        <div className={`${card} overflow-x-auto`}>
          <p className="text-xs font-semibold text-slate-400 mb-3">Attendance trend</p>
          <table className="w-full text-xs">
            <thead className="text-slate-500"><tr><th className="text-left py-1">Date</th><th className="text-right px-2">Present</th><th className="text-right px-2">Late</th><th className="text-right px-2">Half day</th><th className="text-right px-2">Absent</th><th className="text-right px-2">On leave</th></tr></thead>
            <tbody>
              {att.series.length === 0 && <tr><td colSpan={6} className="py-6 text-center text-slate-500">No attendance in range.</td></tr>}
              {att.series.map((b) => (
                <tr key={b.date} className="border-t border-slate-800/60 text-slate-300"><td className="py-1">{b.date}</td><td className="text-right px-2 text-emerald-400">{b.present}</td><td className="text-right px-2 text-amber-400">{b.late}</td><td className="text-right px-2">{b.half_day}</td><td className="text-right px-2 text-red-400">{b.absent}</td><td className="text-right px-2">{b.on_leave}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      {detail && <DetailModal detail={detail} onClose={() => setDetail(null)} onChanged={async () => setDetail(await api.employee(detail.user_id, range()))} />}
    </div>
  );
};

/* employee deep-dive + training management */
const DetailModal: React.FC<{ detail: EmployeeDetail; onClose: () => void; onChanged: () => void }> = ({ detail, onClose, onChanged }) => {
  const [name, setName] = useState('');
  const [score, setScore] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const d = detail;
  const addTraining = async () => {
    if (!name.trim()) { setErr('Training name required'); return; }
    setBusy(true); setErr('');
    try {
      await api.createTraining({ user_id: d.user_id, name, status: 'completed', score: score ? Number(score) : undefined });
      setName(''); setScore(''); await onChanged();
    } catch (e) { setErr(extractErrorMessage(e, 'Failed to add')); } finally { setBusy(false); }
  };
  const Tile: React.FC<{ label: string; value: React.ReactNode; tone?: string }> = ({ label, value, tone }) => (
    <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg"><p className="text-[10px] font-semibold text-slate-500 uppercase">{label}</p><p className={`text-base font-bold mt-0.5 ${tone || 'text-slate-100'}`}>{value}</p></div>
  );
  return (
    <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4" onClick={onClose}>
      <div className="glass-panel border border-slate-800 rounded-2xl w-full max-w-2xl max-h-[88vh] overflow-y-auto p-5 bg-slate-900" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-bold text-slate-100 flex items-center gap-2"><Users className="w-4 h-4 text-brand-400" /> {d.name} <span className="text-slate-500 font-normal">{d.role}</span></h3>
          <div className="flex items-center gap-3">
            <span className={`text-lg font-bold ${scoreTone(d.productivity_score)}`}>{d.productivity_score}</span>
            <button onClick={onClose} className="text-slate-500 hover:text-slate-300 cursor-pointer"><X className="w-4 h-4" /></button>
          </div>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mb-4">
          <Tile label="Leads won" value={d.lead_productivity.leads_converted} />
          <Tile label="Conversion" value={`${d.lead_productivity.conversion_rate}%`} />
          <Tile label="Revenue" value={cur(d.lead_productivity.revenue)} tone="text-emerald-400" />
          <Tile label="Calls" value={d.call_productivity.calls} />
          <Tile label="Activities" value={d.call_productivity.activities} />
          <Tile label="Task completion" value={`${d.task_completion.completion_rate}% (${d.task_completion.done}/${d.task_completion.total})`} />
          <Tile label="Attendance" value={`${d.attendance.attendance_rate}%`} />
          <Tile label="Leave days" value={d.leave_analysis.approved_days} />
        </div>
        <div className="flex items-center justify-between mb-2">
          <p className="text-xs font-semibold text-slate-300 flex items-center gap-1.5"><GraduationCap className="w-3.5 h-3.5 text-brand-400" /> Training <span className="text-slate-500">· avg {d.training.avg_score}</span></p>
        </div>
        <div className="space-y-1 mb-3">
          {d.training.records.length === 0 && <p className="text-[11px] text-slate-600">No training records.</p>}
          {d.training.records.map((t: Training) => (
            <div key={t.id} className="flex items-center justify-between text-xs px-2 py-1.5 rounded bg-slate-950/40 border border-slate-800/60">
              <span className="text-slate-300">{t.name} <span className="text-slate-600">· {t.status}{t.score != null ? ` · ${t.score}` : ''}</span></span>
              <button onClick={async () => { await api.deleteTraining(t.id); onChanged(); }} className="text-slate-500 hover:text-red-400 cursor-pointer"><Trash2 className="w-3.5 h-3.5" /></button>
            </div>
          ))}
        </div>
        {err && <div className="text-xs text-red-400 mb-2">{err}</div>}
        <div className="flex items-center gap-2">
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Add training / certification" className={`${F} flex-1`} />
          <input value={score} onChange={(e) => setScore(e.target.value)} type="number" placeholder="score" className={`${F} w-20`} />
          <button onClick={addTraining} disabled={busy} className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-brand-500/20 text-brand-300 hover:bg-brand-500/30 cursor-pointer flex items-center gap-1.5">{busy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Plus className="w-3.5 h-3.5" />} Add</button>
        </div>
      </div>
    </div>
  );
};
