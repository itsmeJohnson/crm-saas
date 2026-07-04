import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { departmentApi, Dashboard } from '../../services/departmentApi';
import { Building2, Wallet, UserX, Loader2 } from 'lucide-react';

export const DepartmentsWidget: React.FC = () => {
  const [data, setData] = useState<Dashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => { departmentApi.dashboard().then(setData).catch(() => {}).finally(() => setLoading(false)); }, []);

  return (
    <div className="glass-panel border border-slate-800/85 rounded-2xl p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2"><Building2 className="w-4 h-4 text-brand-400" /> Departments</h3>
        <button onClick={() => navigate('/departments')} className="text-xs text-brand-400 hover:text-brand-300 cursor-pointer">Open</button>
      </div>
      {loading ? (
        <div className="py-6 text-center text-slate-400"><Loader2 className="w-5 h-5 animate-spin inline" /></div>
      ) : !data || data.total === 0 ? (
        <p className="text-xs text-slate-500">No departments yet.</p>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-2">
            <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
              <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1"><Building2 className="w-3 h-3 text-brand-400" /> Active</p>
              <p className="text-lg font-bold text-slate-100 mt-0.5">{data.active}<span className="text-[11px] text-slate-500">/{data.total}</span></p>
            </div>
            <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
              <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1"><Wallet className="w-3 h-3 text-emerald-400" /> Budget</p>
              <p className="text-lg font-bold text-slate-100 mt-0.5">₹{Math.round(data.total_budget).toLocaleString()}</p>
            </div>
          </div>
          {data.unassigned_members > 0 && (
            <p className="text-[11px] text-amber-400/80 mt-3 flex items-center gap-1.5"><UserX className="w-3.5 h-3.5" /> {data.unassigned_members} unassigned member(s)</p>
          )}
          {data.largest.length > 0 && (
            <ul className="mt-3 space-y-1">
              {data.largest.slice(0, 3).map((d) => (
                <li key={d.id} className="flex items-center justify-between text-xs">
                  <span className="text-slate-300 truncate">{d.name}</span>
                  <span className="text-slate-500 shrink-0">{d.member_count}</span>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </div>
  );
};
