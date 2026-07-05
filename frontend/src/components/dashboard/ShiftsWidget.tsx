import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { shiftApi, ShiftDashboard } from '../../services/shiftApi';
import { Clock, RefreshCw, Moon, Loader2 } from 'lucide-react';

export const ShiftsWidget: React.FC = () => {
  const [data, setData] = useState<ShiftDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => { shiftApi.dashboard().then(setData).catch(() => {}).finally(() => setLoading(false)); }, []);

  return (
    <div className="glass-panel border border-slate-800/85 rounded-2xl p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2"><Clock className="w-4 h-4 text-brand-400" /> Shifts</h3>
        <button onClick={() => navigate('/shifts')} className="text-xs text-brand-400 hover:text-brand-300 cursor-pointer">Open</button>
      </div>
      {loading ? (
        <div className="py-6 text-center text-slate-400"><Loader2 className="w-5 h-5 animate-spin inline" /></div>
      ) : !data ? (
        <p className="text-xs text-slate-500">No shift data.</p>
      ) : (
        <>
          <div className="mb-3">
            <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">My shift today</p>
            <p className="text-lg font-bold text-slate-100 mt-0.5">
              {data.my_shift_today ? `${data.my_shift_today.name} · ${data.my_shift_today.start_time}–${data.my_shift_today.end_time}` : 'No shift'}
            </p>
          </div>
          <div className="grid grid-cols-3 gap-2">
            <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
              <p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><Clock className="w-3 h-3 text-brand-400" /> Shifts</p>
              <p className="text-base font-bold text-slate-100 mt-0.5">{data.total_shifts}</p>
            </div>
            <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
              <p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><Moon className="w-3 h-3 text-indigo-300" /> Night</p>
              <p className="text-base font-bold text-slate-100 mt-0.5">{data.night_shifts}</p>
            </div>
            <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
              <p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><RefreshCw className="w-3 h-3 text-emerald-400" /> Rotations</p>
              <p className="text-base font-bold text-slate-100 mt-0.5">{data.active_rotations}</p>
            </div>
          </div>
        </>
      )}
    </div>
  );
};
