import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { employeeAnalyticsApi, EmployeeDashboard } from '../../services/employeeAnalyticsApi';
import { Users, Gauge, CalendarCheck, GraduationCap, Loader2 } from 'lucide-react';

export const EmployeeAnalyticsWidget: React.FC = () => {
  const [data, setData] = useState<EmployeeDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    employeeAnalyticsApi.dashboard().then(setData).catch(() => {}).finally(() => setLoading(false));
  }, []);

  return (
    <div className="glass-panel border border-slate-800/85 rounded-2xl p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2"><Users className="w-4 h-4 text-brand-400" /> Employee Analytics</h3>
        <button onClick={() => navigate('/employee-analytics')} className="text-xs text-brand-400 hover:text-brand-300 cursor-pointer">Open</button>
      </div>
      {loading ? (
        <div className="py-6 text-center text-slate-400"><Loader2 className="w-5 h-5 animate-spin inline" /></div>
      ) : !data ? (
        <p className="text-xs text-slate-500">No workforce data.</p>
      ) : (
        <>
          <div className="grid grid-cols-3 gap-2">
            <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
              <p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><Gauge className="w-3 h-3 text-brand-400" /> Productivity</p>
              <p className="text-base font-bold text-slate-100 mt-0.5">{data.avg_productivity}</p>
            </div>
            <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
              <p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><CalendarCheck className="w-3 h-3 text-emerald-400" /> Attendance</p>
              <p className="text-base font-bold text-slate-100 mt-0.5">{data.avg_attendance}%</p>
            </div>
            <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
              <p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><GraduationCap className="w-3 h-3 text-amber-400" /> Training</p>
              <p className="text-base font-bold text-slate-100 mt-0.5">{data.avg_training_score}</p>
            </div>
          </div>
          {data.top_performer && (
            <p className="mt-3 text-[11px] text-slate-400">Top performer: <span className="text-slate-200">{data.top_performer.name}</span> ({data.top_performer.productivity_score})</p>
          )}
        </>
      )}
    </div>
  );
};
