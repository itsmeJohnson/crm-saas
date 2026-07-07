import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { automationAnalyticsApi, AutomationAnalyticsDashboard } from '../../services/automationAnalyticsApi';
import { Activity, GitBranch, ShieldCheck, AlertTriangle, Loader2 } from 'lucide-react';

export const AutomationAnalyticsWidget: React.FC = () => {
  const [data, setData] = useState<AutomationAnalyticsDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => { automationAnalyticsApi.dashboard().then(setData).catch(() => {}).finally(() => setLoading(false)); }, []);

  return (
    <div className="glass-panel border border-slate-800/85 rounded-2xl p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2"><Activity className="w-4 h-4 text-brand-400" /> Automation Analytics</h3>
        <button onClick={() => navigate('/automation-analytics')} className="text-xs text-brand-400 hover:text-brand-300 cursor-pointer">Open</button>
      </div>
      {loading ? (
        <div className="py-6 text-center text-slate-400"><Loader2 className="w-5 h-5 animate-spin inline" /></div>
      ) : !data ? (
        <p className="text-xs text-slate-500">No analytics yet.</p>
      ) : (
        <>
          <div className="grid grid-cols-3 gap-2">
            <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
              <p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><GitBranch className="w-3 h-3 text-brand-400" /> WF success</p>
              <p className="text-base font-bold text-slate-100 mt-0.5">{data.workflow_success_rate}%</p>
            </div>
            <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
              <p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><ShieldCheck className="w-3 h-3 text-emerald-400" /> SLA</p>
              <p className="text-base font-bold text-slate-100 mt-0.5">{data.sla_compliance_rate}%</p>
            </div>
            <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
              <p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><AlertTriangle className="w-3 h-3 text-amber-400" /> WF fails</p>
              <p className="text-base font-bold text-slate-100 mt-0.5">{data.workflow_failed}</p>
            </div>
          </div>
          <div className="mt-3 flex items-center justify-between text-xs text-slate-400">
            <span>Queue failed <span className="text-slate-200">{data.queue_failed}</span></span>
            <span>Escalations <span className="text-slate-200">{data.escalations}</span></span>
            <span>Pending <span className="text-slate-200">{data.approvals_pending}</span></span>
          </div>
        </>
      )}
    </div>
  );
};
