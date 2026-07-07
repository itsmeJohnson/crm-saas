import React from 'react';
import { useNavigate } from 'react-router-dom';
import { EmployeeSummary } from '../../services/dashboardApi';
import { FolderKanban, Loader2 } from 'lucide-react';

export const MyLeadsWidget: React.FC<{ data: EmployeeSummary | null; loading?: boolean }> = ({ data, loading }) => {
  const navigate = useNavigate();
  return (
    <div className="glass-panel border border-slate-800/85 rounded-2xl p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2"><FolderKanban className="w-4 h-4 text-brand-400" /> My Leads</h3>
        <button onClick={() => navigate('/leads')} className="text-xs text-brand-400 hover:text-brand-300 cursor-pointer">Open</button>
      </div>
      {loading ? (
        <div className="py-6 text-center text-slate-400"><Loader2 className="w-5 h-5 animate-spin inline" /></div>
      ) : !data || data.my_leads_total === 0 ? (
        <p className="text-xs text-slate-500">No leads assigned to you.</p>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-2">
            <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
              <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">Assigned</p>
              <p className="text-lg font-bold text-slate-100 mt-0.5">{data.my_leads_total}</p>
            </div>
            <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
              <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">Converted</p>
              <p className="text-lg font-bold text-emerald-400 mt-0.5">{data.my_leads_converted}</p>
            </div>
          </div>
          {data.my_leads_by_status.length > 0 && (
            <ul className="mt-3 space-y-1">
              {data.my_leads_by_status.slice(0, 4).map((s) => (
                <li key={s.status} className="flex items-center justify-between text-xs">
                  <span className="text-slate-300 truncate">{s.status}</span>
                  <span className="text-slate-500 shrink-0">{s.count}</span>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </div>
  );
};
