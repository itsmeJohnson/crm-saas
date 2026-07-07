import React from 'react';
import { useNavigate } from 'react-router-dom';
import { BarChart3, FolderKanban, Trophy, Clock, CalendarDays, ChevronRight } from 'lucide-react';

const REPORTS = [
  { label: 'Lead Reports', path: '/leads/reports', icon: FolderKanban },
  { label: 'My Performance', path: '/performance', icon: Trophy },
  { label: 'My Attendance', path: '/attendance', icon: Clock },
  { label: 'My Leave', path: '/leaves', icon: CalendarDays },
];

export const MyReportsWidget: React.FC = () => {
  const navigate = useNavigate();
  return (
    <div className="glass-panel border border-slate-800/85 rounded-2xl p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2"><BarChart3 className="w-4 h-4 text-brand-400" /> My Reports</h3>
      </div>
      <ul className="space-y-1.5">
        {REPORTS.map((r) => (
          <li key={r.path}>
            <button onClick={() => navigate(r.path)} className="w-full flex items-center justify-between p-2 bg-slate-950/40 border border-slate-800/60 rounded-lg text-xs text-slate-300 hover:border-slate-700 hover:text-slate-100 cursor-pointer">
              <span className="flex items-center gap-2"><r.icon className="w-3.5 h-3.5 text-brand-400" /> {r.label}</span>
              <ChevronRight className="w-3.5 h-3.5 text-slate-600" />
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
};
