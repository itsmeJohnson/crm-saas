import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { branchApi, BranchDashboard } from '../../services/branchApi';
import { Building, MapPin, MapPinOff, Loader2 } from 'lucide-react';

export const BranchesWidget: React.FC = () => {
  const [data, setData] = useState<BranchDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => { branchApi.dashboard().then(setData).catch(() => {}).finally(() => setLoading(false)); }, []);

  return (
    <div className="glass-panel border border-slate-800/85 rounded-2xl p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2"><Building className="w-4 h-4 text-brand-400" /> Branches</h3>
        <button onClick={() => navigate('/branches')} className="text-xs text-brand-400 hover:text-brand-300 cursor-pointer">Open</button>
      </div>
      {loading ? (
        <div className="py-6 text-center text-slate-400"><Loader2 className="w-5 h-5 animate-spin inline" /></div>
      ) : !data || data.total_branches === 0 ? (
        <p className="text-xs text-slate-500">No branches yet.</p>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-2">
            <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
              <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1"><Building className="w-3 h-3 text-brand-400" /> Active</p>
              <p className="text-lg font-bold text-slate-100 mt-0.5">{data.active_branches}<span className="text-[11px] text-slate-500">/{data.total_branches}</span></p>
            </div>
            <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
              <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1"><MapPin className="w-3 h-3 text-emerald-400" /> Mapped PINs</p>
              <p className="text-lg font-bold text-slate-100 mt-0.5">{data.mapped_pincodes}</p>
            </div>
          </div>
          {data.unmapped_leads > 0 && (
            <p className="text-[11px] text-amber-400/80 mt-3 flex items-center gap-1.5"><MapPinOff className="w-3.5 h-3.5" /> {data.unmapped_leads} lead(s) without a branch</p>
          )}
          {data.top_branches.length > 0 && (
            <ul className="mt-3 space-y-1">
              {data.top_branches.slice(0, 3).map((b) => (
                <li key={b.id} className="flex items-center justify-between text-xs">
                  <span className="text-slate-300 truncate">{b.name}</span>
                  <span className="text-slate-500 shrink-0">{b.lead_count}</span>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </div>
  );
};
