import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { reportBuilderApi } from '../../services/reportBuilderApi';
import { Table2, Pin, Loader2 } from 'lucide-react';

export const ReportBuilderWidget: React.FC = () => {
  const [reports, setReports] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    reportBuilderApi.dashboard().then((d) => setReports(d.reports || [])).catch(() => {}).finally(() => setLoading(false));
  }, []);

  return (
    <div className="glass-panel border border-slate-800/85 rounded-2xl p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2"><Table2 className="w-4 h-4 text-brand-400" /> Pinned Reports</h3>
        <button onClick={() => navigate('/report-builder')} className="text-xs text-brand-400 hover:text-brand-300 cursor-pointer">Open</button>
      </div>
      {loading ? (
        <div className="py-6 text-center text-slate-400"><Loader2 className="w-5 h-5 animate-spin inline" /></div>
      ) : reports.length === 0 ? (
        <p className="text-xs text-slate-500">Pin a report to see it here.</p>
      ) : (
        <ul className="space-y-2">
          {reports.slice(0, 4).map((r) => (
            <li key={r.id} className="flex items-center justify-between p-2 bg-slate-950/40 border border-slate-800/60 rounded-lg cursor-pointer hover:border-slate-700/70" onClick={() => navigate('/report-builder')}>
              <span className="text-xs text-slate-300 truncate flex items-center gap-1.5"><Pin className="w-3 h-3 text-brand-400" /> {r.name}</span>
              <span className="text-xs font-bold text-slate-100 shrink-0">{r.total}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};
