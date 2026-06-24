import React from 'react';
import { Search, RotateCcw } from 'lucide-react';

interface FiltersProps {
  search: string;
  onSearchChange: (val: string) => void;
  placeholder?: string;
  onReset: () => void;
  children?: React.ReactNode;
}

export const Filters: React.FC<FiltersProps> = ({
  search,
  onSearchChange,
  placeholder = 'Search...',
  onReset,
  children
}) => {
  return (
    <div className="glass-panel p-5 rounded-2xl border border-slate-800/80 mb-6 flex flex-col lg:flex-row lg:items-center justify-between gap-4">
      <div className="flex-1 flex flex-col sm:flex-row items-stretch sm:items-center gap-4">
        {/* Search */}
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
          <input
            type="text"
            placeholder={placeholder}
            value={search}
            onChange={(e) => onSearchChange(e.target.value)}
            className="w-full pl-10 pr-4 py-2.5 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-brand-500/50 focus:ring-2 focus:ring-brand-500/10 transition-all"
          />
        </div>

        {/* Custom selectors (dropdowns etc.) */}
        {children}
      </div>

      {/* Reset Button */}
      <button
        onClick={onReset}
        className="flex items-center justify-center gap-2 px-4 py-2.5 bg-slate-900 border border-slate-800 hover:border-slate-700 hover:bg-slate-900/80 active:bg-slate-900/50 rounded-xl text-sm font-medium text-slate-300 transition-all cursor-pointer shrink-0"
      >
        <RotateCcw className="w-4 h-4 text-slate-400" />
        Reset Filters
      </button>
    </div>
  );
};
