import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { approvalApi, ApprovalDashboard } from '../../services/approvalApi';
import { CheckCircle2, Inbox, Clock, Loader2 } from 'lucide-react';

export const ApprovalsWidget: React.FC = () => {
  const [data, setData] = useState<ApprovalDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => { approvalApi.dashboard().then(setData).catch(() => {}).finally(() => setLoading(false)); }, []);

  return (
    <div className="glass-panel border border-slate-800/85 rounded-2xl p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2"><CheckCircle2 className="w-4 h-4 text-brand-400" /> Approvals</h3>
        <button onClick={() => navigate('/approvals')} className="text-xs text-brand-400 hover:text-brand-300 cursor-pointer">Open</button>
      </div>
      {loading ? (
        <div className="py-6 text-center text-slate-400"><Loader2 className="w-5 h-5 animate-spin inline" /></div>
      ) : !data ? (
        <p className="text-xs text-slate-500">No approval data.</p>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-2">
            <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
              <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1"><Inbox className="w-3 h-3 text-amber-400" /> To action</p>
              <p className="text-lg font-bold text-slate-100 mt-0.5">{data.awaiting_my_action}</p>
            </div>
            <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
              <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1"><Clock className="w-3 h-3 text-brand-400" /> My pending</p>
              <p className="text-lg font-bold text-slate-100 mt-0.5">{data.my_pending}</p>
            </div>
          </div>
          <p className="text-[11px] text-slate-500 mt-3">{data.approved} approved · {data.rejected} rejected · {data.pending} pending</p>
        </>
      )}
    </div>
  );
};
