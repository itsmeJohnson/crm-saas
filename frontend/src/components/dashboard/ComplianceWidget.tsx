import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { complianceApi, ComplianceDashboard } from '../../services/complianceApi';
import { ShieldCheck, Activity, AlertTriangle, Users, Loader2 } from 'lucide-react';

export const ComplianceWidget: React.FC = () => {
  const [data, setData] = useState<ComplianceDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    complianceApi.dashboard().then(setData).catch(() => {}).finally(() => setLoading(false));
  }, []);

  return (
    <div className="glass-panel border border-slate-800/85 rounded-2xl p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2"><ShieldCheck className="w-4 h-4 text-brand-400" /> Audit & Compliance</h3>
        <button onClick={() => navigate('/compliance')} className="text-xs text-brand-400 hover:text-brand-300 cursor-pointer">Open</button>
      </div>
      {loading ? (
        <div className="py-6 text-center text-slate-400"><Loader2 className="w-5 h-5 animate-spin inline" /></div>
      ) : !data ? (
        <p className="text-xs text-slate-500">No audit data.</p>
      ) : (
        <div className="grid grid-cols-3 gap-2">
          <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
            <p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><Activity className="w-3 h-3 text-brand-400" /> Events 7d</p>
            <p className="text-base font-bold text-slate-100 mt-0.5">{data.counts.last_7d}</p>
          </div>
          <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
            <p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><AlertTriangle className="w-3 h-3 text-red-400" /> Failed logins</p>
            <p className="text-base font-bold text-slate-100 mt-0.5">{data.failed_logins_30d}</p>
          </div>
          <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
            <p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><Users className="w-3 h-3 text-emerald-400" /> Actors</p>
            <p className="text-base font-bold text-slate-100 mt-0.5">{data.top_actors.length}</p>
          </div>
        </div>
      )}
    </div>
  );
};
