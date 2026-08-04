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
    <div className="glass-panel p-4 sm:p-5 rounded-2xl border border-slate-800/80 mb-6 flex flex-wrap items-center gap-3">
      {/* Search — grows to fill the first row, then filters wrap below */}
      <div className="relative flex-1 min-w-[200px]">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
        <input
          type="text"
          placeholder={placeholder}
          value={search}
          onChange={(e) => onSearchChange(e.target.value)}
          className="w-full pl-10 pr-4 py-2.5 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-brand-500/50 focus:ring-2 focus:ring-brand-500/10 transition-all"
        />
      </div>

      {/* Custom selectors (dropdowns etc.) — wrap onto new rows as needed */}
      {children}

      {/* Reset Button — pushed to the end of the last row */}
      <button
        onClick={onReset}
        className="flex items-center justify-center gap-2 px-4 py-2.5 bg-slate-900 border border-slate-800 hover:border-slate-700 hover:bg-slate-900/80 active:bg-slate-900/50 rounded-xl text-sm font-medium text-slate-300 transition-all cursor-pointer shrink-0 ml-auto"
      >
        <RotateCcw className="w-4 h-4 text-slate-400" />
        Reset Filters
      </button>
    </div>
  );
};
