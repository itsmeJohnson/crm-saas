import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { leaveApi, LeaveDashboard } from '../../services/leaveApi';
import { CalendarDays, Wallet, ClipboardCheck, Plane, Loader2 } from 'lucide-react';
import { useAuthStore } from '../../store/authStore';

export const LeaveWidget: React.FC = () => {
  const { user } = useAuthStore();
  const isManager = user?.role === 'OrgAdmin' || user?.role === 'Manager';
  const [data, setData] = useState<LeaveDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => { leaveApi.dashboard().then(setData).catch(() => {}).finally(() => setLoading(false)); }, []);

  return (
    <div className="glass-panel border border-slate-800/85 rounded-2xl p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2"><CalendarDays className="w-4 h-4 text-brand-400" /> Leave</h3>
        <button onClick={() => navigate('/leaves')} className="text-xs text-brand-400 hover:text-brand-300 cursor-pointer">Open</button>
      </div>
      {loading ? (
        <div className="py-6 text-center text-slate-400"><Loader2 className="w-5 h-5 animate-spin inline" /></div>
      ) : !data ? (
        <p className="text-xs text-slate-500">No leave data.</p>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-2">
            <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
              <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1"><Wallet className="w-3 h-3 text-emerald-400" /> Available</p>
              <p className="text-lg font-bold text-slate-100 mt-0.5">{data.my_available_days}<span className="text-[11px] text-slate-500"> days</span></p>
            </div>
            <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
              <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1">{isManager ? <ClipboardCheck className="w-3 h-3 text-brand-400" /> : <CalendarDays className="w-3 h-3 text-brand-400" />} {isManager ? 'To approve' : 'My pending'}</p>
              <p className="text-lg font-bold text-slate-100 mt-0.5">{isManager ? data.pending_approvals : data.my_pending}</p>
            </div>
          </div>
          {data.on_leave_today.length > 0 && (
            <div className="mt-3">
              <p className="text-[11px] text-slate-500 flex items-center gap-1.5"><Plane className="w-3.5 h-3.5" /> On leave today</p>
              <ul className="mt-1 space-y-0.5">
                {data.on_leave_today.slice(0, 3).map((u) => (
                  <li key={u.user_id} className="text-xs text-slate-300 truncate">{u.name}</li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}
    </div>
  );
};
