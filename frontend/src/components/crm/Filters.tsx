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
    <div className="bg-slate-900/60 border border-slate-800/80 shadow-2xs p-2.5 sm:p-3 rounded-xl mb-4 flex flex-wrap items-center gap-2.5">
      {/* Search — grows to fill the first row, then filters wrap below */}
      <div className="relative flex-1 min-w-[200px]">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-400" />
        <input
          type="text"
          placeholder={placeholder}
          value={search}
          onChange={(e) => onSearchChange(e.target.value)}
          className="w-full pl-9 pr-3 py-1.5 bg-slate-950 border border-slate-700/80 rounded-lg text-xs text-slate-100 placeholder-slate-400 focus:outline-none focus:bg-slate-900 focus:border-brand-500 focus:ring-1 focus:ring-brand-500/20 shadow-2xs transition-all"
        />
      </div>

      {/* Custom selectors (dropdowns etc.) — wrap onto new rows as needed */}
      {children}

      {/* Reset Button — pushed to the end */}
      <button
        onClick={onReset}
        className="flex items-center justify-center gap-1.5 px-3 py-1.5 bg-slate-800/80 border border-slate-700/80 hover:border-slate-600 hover:bg-slate-700/80 active:scale-[0.98] rounded-lg text-xs font-semibold text-slate-200 transition-all cursor-pointer shrink-0 ml-auto shadow-2xs hover:shadow-xs"
        title="Reset all filters"
      >
        <RotateCcw className="w-3 h-3 text-slate-400" />
        Reset
      </button>
    </div>
  );
};
