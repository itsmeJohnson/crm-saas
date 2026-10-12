import React from 'react';
import { Search, RotateCcw, X, SlidersHorizontal } from 'lucide-react';

export interface FilterChip {
  id: string;
  label: string;
  value: string;
  onRemove: () => void;
}

interface FiltersProps {
  search: string;
  onSearchChange: (val: string) => void;
  placeholder?: string;
  onReset: () => void;
  children?: React.ReactNode;
  activeChips?: FilterChip[];
  extraFilters?: React.ReactNode;
  hasActiveFilters?: boolean;
}

export const Filters: React.FC<FiltersProps> = ({
  search,
  onSearchChange,
  placeholder = 'Search leads by name, company, email, phone, or title...',
  onReset,
  children,
  activeChips = [],
  extraFilters,
}) => {
  const [showAdvanced, setShowAdvanced] = React.useState(false);

  return (
    <div className="space-y-2 mb-3">
      {/* Main Filter Bar */}
      <div className="bg-slate-900/70 border border-slate-800/90 shadow-2xs p-2.5 sm:p-3 rounded-xl flex flex-wrap items-center gap-2">
        {/* Search */}
        <div className="relative flex-1 min-w-[220px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-400" />
          <input
            type="text"
            placeholder={placeholder}
            value={search}
            onChange={(e) => onSearchChange(e.target.value)}
            className="w-full pl-9 pr-8 py-1.5 bg-slate-950 border border-slate-700/80 rounded-lg text-xs text-slate-100 placeholder-slate-400 focus:outline-none focus:bg-slate-900 focus:border-brand-500 focus:ring-1 focus:ring-brand-500/20 shadow-2xs transition-all"
          />
          {search && (
            <button
              onClick={() => onSearchChange('')}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-200 p-0.5"
              title="Clear search"
            >
              <X className="w-3 h-3" />
            </button>
          )}
        </div>

        {/* Quick Select Filters (Status, Owner, Priority) */}
        {children}

        {/* Toggle Advanced Filters Button */}
        {extraFilters && (
          <button
            type="button"
            onClick={() => setShowAdvanced(!showAdvanced)}
            className={`flex items-center gap-1.5 px-2.5 py-1.5 border rounded-lg text-xs font-semibold transition-all cursor-pointer shadow-2xs ${
              showAdvanced
                ? 'bg-brand-500/15 border-brand-500/40 text-brand-400'
                : 'bg-slate-950 border-slate-700/80 text-slate-300 hover:border-slate-600'
            }`}
            title="Toggle advanced filters"
          >
            <SlidersHorizontal className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Advanced</span>
          </button>
        )}

        {/* Reset Button */}
        <button
          onClick={onReset}
          className="flex items-center justify-center gap-1.5 px-2.5 py-1.5 bg-slate-800/80 border border-slate-700/80 hover:border-slate-600 hover:bg-slate-700/80 active:scale-[0.98] rounded-lg text-xs font-semibold text-slate-200 transition-all cursor-pointer shrink-0 shadow-2xs hover:shadow-xs"
          title="Reset all filters"
        >
          <RotateCcw className="w-3 h-3 text-slate-400" />
          <span>Reset</span>
        </button>
      </div>

      {/* Advanced Filters Drawer/Panel */}
      {showAdvanced && extraFilters && (
        <div className="p-3 bg-slate-900/50 border border-slate-800/80 rounded-xl flex flex-wrap items-center gap-2.5 animate-in fade-in duration-150">
          {extraFilters}
        </div>
      )}

      {/* Active Filter Chips */}
      {activeChips.length > 0 && (
        <div className="flex items-center gap-2 flex-wrap pt-0.5 px-0.5">
          <span className="text-[11px] font-semibold text-slate-400">
            Active filters ({activeChips.length}):
          </span>
          {activeChips.map((chip) => (
            <span
              key={chip.id}
              className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md bg-slate-800/80 border border-slate-700/80 text-[11px] text-slate-200 shadow-2xs"
            >
              <span className="text-slate-400">{chip.label}:</span>
              <span className="font-semibold text-brand-300">{chip.value}</span>
              <button
                type="button"
                onClick={chip.onRemove}
                className="text-slate-400 hover:text-rose-400 transition-colors cursor-pointer ml-0.5"
                title={`Remove ${chip.label} filter`}
              >
                <X className="w-3 h-3" />
              </button>
            </span>
          ))}
          <button
            type="button"
            onClick={onReset}
            className="text-[11px] text-brand-400 hover:text-brand-300 hover:underline font-medium cursor-pointer ml-1"
          >
            Clear all
          </button>
        </div>
      )}
    </div>
  );
};
