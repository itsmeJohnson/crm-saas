import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { teamApi, TeamDashboard } from '../../services/teamApi';
import { UsersRound, Gauge, Loader2 } from 'lucide-react';

export const TeamsWidget: React.FC = () => {
  const [data, setData] = useState<TeamDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => { teamApi.dashboard().then(setData).catch(() => {}).finally(() => setLoading(false)); }, []);

  return (
    <div className="glass-panel border border-slate-800/85 rounded-2xl p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2"><UsersRound className="w-4 h-4 text-brand-400" /> Teams</h3>
        <button onClick={() => navigate('/teams')} className="text-xs text-brand-400 hover:text-brand-300 cursor-pointer">Open</button>
      </div>
      {loading ? (
        <div className="py-6 text-center text-slate-400"><Loader2 className="w-5 h-5 animate-spin inline" /></div>
      ) : !data || data.total === 0 ? (
        <p className="text-xs text-slate-500">No teams yet.</p>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-2">
            <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
              <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1"><UsersRound className="w-3 h-3 text-brand-400" /> Active</p>
              <p className="text-lg font-bold text-slate-100 mt-0.5">{data.active}<span className="text-[11px] text-slate-500">/{data.total}</span></p>
            </div>
            <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
              <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1"><Gauge className="w-3 h-3 text-emerald-400" /> Capacity</p>
              <p className="text-lg font-bold text-slate-100 mt-0.5">{data.capacity_utilization != null ? `${data.capacity_utilization}%` : '—'}</p>
            </div>
          </div>
          <p className="text-[11px] text-slate-500 mt-3">{data.total_members} member(s) across teams</p>
          {data.largest.length > 0 && (
            <ul className="mt-2 space-y-1">
              {data.largest.slice(0, 3).map((t) => (
                <li key={t.id} className="flex items-center justify-between text-xs">
                  <span className="text-slate-300 truncate">{t.name}</span>
                  <span className="text-slate-500 shrink-0">{t.member_count}{t.capacity ? `/${t.capacity}` : ''}</span>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </div>
  );
};
