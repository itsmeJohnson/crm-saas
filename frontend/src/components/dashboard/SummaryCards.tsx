import React from 'react';
import { FolderKanban, CalendarRange, UserCheck } from 'lucide-react';
import { DashboardSummaryResponse } from '../../services/dashboardApi';

interface SummaryCardsProps {
  summary: DashboardSummaryResponse | null;
  isLoading: boolean;
}

export const SummaryCards: React.FC<SummaryCardsProps> = ({ summary, isLoading }) => {
  const cards = [
    {
      title: 'Total Leads',
      value: summary?.total_leads ?? 0,
      icon: FolderKanban,
      gradient: 'from-brand-500/10 to-brand-500/5 border-brand-500/20 text-brand-400',
      description: 'Active opportunities'
    },
    {
      title: 'Activities',
      value: summary?.activities_count ?? 0,
      icon: CalendarRange,
      gradient: 'from-emerald-500/10 to-emerald-500/5 border-emerald-500/20 text-emerald-400',
      description: 'Logged interactions'
    },
    {
      title: 'Active Team',
      value: summary?.user_count ?? 0,
      icon: UserCheck,
      gradient: 'from-sky-500/10 to-sky-500/5 border-sky-500/20 text-sky-400',
      description: 'Active organization users'
    }
  ];

  if (isLoading) {
    return (
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="glass-panel p-5 rounded-2xl border border-slate-800/80 animate-pulse h-28 flex flex-col justify-between bg-slate-950/20">
            <div className="h-4 bg-slate-800 rounded w-2/3"></div>
            <div className="h-8 bg-slate-800 rounded w-1/3 mt-2"></div>
            <div className="h-3 bg-slate-800 rounded w-1/2 mt-1"></div>
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
      {cards.map((card) => {
        const Icon = card.icon;
        return (
          <div
            key={card.title}
            className={`glass-panel bg-gradient-to-b ${card.gradient} border p-5 rounded-2xl transition-all hover:scale-[1.02] duration-300 flex flex-col justify-between`}
          >
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                {card.title}
              </span>
              <Icon className="w-5 h-5 opacity-80" />
            </div>
            <div className="mt-3">
              <p className="text-3xl font-bold text-slate-100 tracking-tight animate-fade-in">
                {card.value}
              </p>
              <p className="text-[10px] text-slate-400 mt-1 font-medium">
                {card.description}
              </p>
            </div>
          </div>
        );
      })}
    </div>
  );
};
